"""Production-conversion tests for withdrawals (§3–§7).

Covers:
- per-network minimum/fee overrides (§4/§8)
- QR image upload round-trip through the multipart API (§7)
- the typed wallet address remains authoritative (§7)
- admin QR endpoint is staff-only (§9)
"""

import shutil
import tempfile
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services import register_user
from apps.wallet.models import Network, WalletTransaction
from apps.wallet.services import admin_adjust

from .models import Withdrawal
from .services import create_withdrawal

PASSWORD = 'S3curePass!x'
TRON_ADDRESS = 'Th82pJGF9p7kpzb6eU326EFZf2cDnimbTF'
TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix='wdr-test-media-')


def _png_bytes() -> bytes:
    import io

    buffer = io.BytesIO()
    Image.new('RGB', (8, 8), (30, 30, 200)).save(buffer, format='PNG')
    return buffer.getvalue()


def _upload(name='qr.png') -> SimpleUploadedFile:
    return SimpleUploadedFile(name, _png_bytes(), content_type='image/png')


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class WithdrawalProductionTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.trx = Network.objects.create(name='Tron (TRC20)', code='TRX')
        cls.bsc = Network.objects.create(
            name='BNB Smart Chain', code='BSC',
            min_withdrawal=Decimal('20.00'),
            withdrawal_fee=Decimal('2.00'),
        )
        cls.user = register_user(
            full_name='PROD WDR', email='prod-wdr@example.com',
            phone='+19988800001', password=PASSWORD, referral_code='',
        ).user
        cls.other = register_user(
            full_name='PROD WDR B', email='prod-wdr-b@example.com',
            phone='+19988800002', password=PASSWORD, referral_code='',
        ).user
        cls.admin = User.objects.create_superuser(
            email='prod-wdr-admin@example.com', password=PASSWORD, phone='+19988800003',
        )
        from apps.wallet.services import ensure_wallet

        for account in (cls.user, cls.other, cls.admin):
            ensure_wallet(account)
            admin_adjust(
                user=account, amount=Decimal('1'),
                balance_type=WalletTransaction.BalanceType.WITHDRAWABLE,
                direction=WalletTransaction.Direction.CREDIT, reason='wallet init',
            )
            # Zero it back out so per-test funding is predictable.
            admin_adjust(
                user=account, amount=Decimal('1'),
                balance_type=WalletTransaction.BalanceType.WITHDRAWABLE,
                direction=WalletTransaction.Direction.DEBIT, reason='wallet reset',
            )

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self) -> None:
        self.client = APIClient()

    def _auth(self, user) -> None:
        from rest_framework_simplejwt.tokens import RefreshToken

        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def _fund(self, amount: str) -> None:
        admin_adjust(
            user=self.user, amount=Decimal(amount),
            balance_type=WalletTransaction.BalanceType.WITHDRAWABLE,
            direction=WalletTransaction.Direction.CREDIT, reason='test funding',
        )

    # ------------------------------------------------------------------ #
    def test_per_network_minimum_enforced(self) -> None:
        self._fund('30')
        # BSC override: minimum 20 → 10 rejected.
        with self.assertRaises(Exception):
            create_withdrawal(
                user=self.user, network_code='BSC',
                destination_address='0x' + 'c' * 40,
                amount=Decimal('10.00'), idempotency_key='wdr-min-1',
            )
        # TRX inherits the global minimum (5) → 10 accepted.
        withdrawal, created = create_withdrawal(
            user=self.user, network_code='TRX',
            destination_address=TRON_ADDRESS,
            amount=Decimal('10.00'), idempotency_key='wdr-min-2',
        )
        self.assertTrue(created)

    def test_per_network_fee_used(self) -> None:
        self._fund('40')
        withdrawal, _ = create_withdrawal(
            user=self.user, network_code='BSC',
            destination_address='0x' + 'c' * 40,
            amount=Decimal('30.00'), idempotency_key='wdr-fee-1',
        )
        self.assertEqual(withdrawal.fee_amount, Decimal('2.00'))
        self.assertEqual(withdrawal.net_amount, Decimal('28.00'))

    def test_quote_uses_network_override(self) -> None:
        self._auth(self.user)
        body = self.client.post(
            '/api/withdrawals/quote/', {'network': 'BSC', 'amount': '30.00'}, format='json',
        ).json()['data']
        self.assertEqual(body['fee'], '2.00')
        self.assertEqual(body['minimum_amount'], '20.00')

    def test_rules_endpoint_network_override(self) -> None:
        self._auth(self.user)
        body = self.client.get('/api/withdrawals/rules/?network=BSC').json()['data']
        self.assertEqual(body['minimum_amount'], '20.00')
        self.assertEqual(body['fee_amount'], '2.00')

    def test_multipart_qr_upload_round_trip(self) -> None:
        self._fund('30')
        self._auth(self.user)
        response = self.client.post(
            '/api/withdrawals/',
            {
                'network': 'TRX',
                'destination_address': TRON_ADDRESS,
                'amount': '10.00',
                'idempotency_key': 'wdr-qr-1',
                'qr_image': _upload(),
            },
            format='multipart',
        )
        self.assertIn(response.status_code, (200, 201), response.content)
        withdrawal = Withdrawal.objects.get(withdrawal_id=response.json()['data']['withdrawal_id'])
        self.assertTrue(withdrawal.qr_image)
        self.assertEqual(withdrawal.wallet_address, TRON_ADDRESS)  # typed address authoritative

    def test_qr_upload_rejects_non_image(self) -> None:
        self._fund('30')
        self._auth(self.user)
        response = self.client.post(
            '/api/withdrawals/',
            {
                'network': 'TRX',
                'destination_address': TRON_ADDRESS,
                'amount': '10.00',
                'idempotency_key': 'wdr-qr-2',
                'qr_image': SimpleUploadedFile('x.txt', b'not an image', content_type='text/plain'),
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)

    def test_admin_qr_endpoint_is_staff_only(self) -> None:
        self._fund('30')
        withdrawal, _ = create_withdrawal(
            user=self.user, network_code='TRX', destination_address=TRON_ADDRESS,
            amount=Decimal('10.00'), idempotency_key='wdr-qr-3', qr_image=_upload(),
        )
        # Regular users (even the owner) cannot fetch it.
        self._auth(self.other)
        self.assertIn(
            self.client.get(f'/api/admin-panel/withdrawals/{withdrawal.withdrawal_id}/qr/').status_code,
            (401, 403),
        )
        # Staff can.
        self._auth(self.admin)
        self.assertEqual(
            self.client.get(f'/api/admin-panel/withdrawals/{withdrawal.withdrawal_id}/qr/').status_code,
            200,
        )

    def test_admin_list_carries_has_qr(self) -> None:
        self._fund('30')
        withdrawal, _ = create_withdrawal(
            user=self.user, network_code='TRX', destination_address=TRON_ADDRESS,
            amount=Decimal('10.00'), idempotency_key='wdr-qr-4', qr_image=_upload(),
        )
        self._auth(self.admin)
        rows = self.client.get('/api/admin-panel/withdrawals/').json()['data']
        row = next(r for r in rows if r['withdrawal_id'] == withdrawal.withdrawal_id)
        self.assertTrue(row['has_qr_image'])

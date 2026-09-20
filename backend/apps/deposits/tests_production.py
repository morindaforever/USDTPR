"""Production-conversion tests for the deposit flow (Section 1/2/8).

Covers the behaviors added in the production conversion:
- per-network minimum deposit override (§1/§8)
- GLOBAL duplicate transaction-hash protection (any user, §2)
- screenshot upload round-trip through the multipart API (§1)
- reviewer stamping (approved/rejected store reviewed_by, §2)
- admin note endpoint never changes status (§2)
- admin screenshot endpoint is staff-only (§9)
- honest verification label (MANUAL_VERIFICATION by default, §2)
- per-network config management via /api/admin-panel/networks/ (§8)
"""

import io
import shutil
import tempfile
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.wallet.models import DepositAddress, Network

from .models import Deposit
from .services import DepositError, approve_deposit, reject_deposit, submit_deposit

PASSWORD = 'S3curePass!x'


def _png_bytes(color=(200, 30, 30)) -> bytes:
    buffer = io.BytesIO()
    Image.new('RGB', (8, 8), color).save(buffer, format='PNG')
    return buffer.getvalue()


def _upload(name='proof.png', content: bytes | None = None) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content or _png_bytes(), content_type='image/png')


def _mk(email: str, i: int, *, staff=False) -> User:
    if staff:
        return User.objects.create_superuser(
            email=email, password=PASSWORD, phone=f'+199777{i:05d}',
        )
    return User.objects.create_user(
        email=email, password=PASSWORD, phone=f'+199777{i:05d}',
    )


TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix='dep-test-media-')


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class DepositProductionTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        # Wallets must exist before approval can credit them.
        from apps.wallet.services import ensure_wallet

        cls.trx = Network.objects.create(
            name='Tron (TRC20)', code='TRX',
            min_deposit=None,  # inherits global minimum
        )
        cls.pol = Network.objects.create(
            name='Polygon', code='POL', min_deposit=Decimal('25.00'),
        )
        for network in (cls.trx, cls.pol):
            DepositAddress.objects.create(
                network=network, asset='USDT',
                address='0x' + 'b' * 40 if network.code == 'POL' else 'T' + 'a' * 33,
                is_active=True,
            )
        cls.user = _mk('prod-dep@example.com', 1)
        cls.other = _mk('prod-dep-b@example.com', 2)
        cls.admin = _mk('prod-dep-admin@example.com', 3, staff=True)
        for account in (cls.user, cls.other, cls.admin):
            ensure_wallet(account)

    def setUp(self) -> None:
        self.client = APIClient()

    def _auth(self, user) -> None:
        from rest_framework_simplejwt.tokens import RefreshToken

        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    # ------------------------------------------------------------------ #
    def test_global_duplicate_tx_hash_rejected_across_users(self) -> None:
        submit_deposit(
            user=self.user, network_code='TRX', amount='10.00',
            tx_hash='0xSHAREDHASH', order_id='',
        )
        with self.assertRaises(DepositError) as ctx:
            submit_deposit(
                user=self.other, network_code='TRX', amount='10.00',
                tx_hash='0xsharedhash', order_id='',  # case-insensitive match
            )
        self.assertIn('tx_hash', ctx.exception.errors)

    def test_same_user_duplicate_still_rejected(self) -> None:
        submit_deposit(
            user=self.user, network_code='TRX', amount='10.00',
            tx_hash='0xDUPSELF', order_id='',
        )
        with self.assertRaises(DepositError):
            submit_deposit(
                user=self.user, network_code='TRX', amount='10.00',
                tx_hash='0xDUPSELF', order_id='',
            )

    def test_duplicate_hash_can_be_resubmitted_after_rejection(self) -> None:
        deposit = submit_deposit(
            user=self.user, network_code='TRX', amount='10.00',
            tx_hash='0xRETRYME', order_id='',
        ).deposit
        reject_deposit(deposit=deposit, admin_user=self.admin, reason='blurry proof')
        second = submit_deposit(
            user=self.user, network_code='TRX', amount='10.00',
            tx_hash='0xRETRYME', order_id='',
        )
        self.assertEqual(second.deposit.status, Deposit.Status.PENDING)

    def test_per_network_minimum_applies(self) -> None:
        # POL has min_deposit 25; a 10 USDT request is rejected.
        with self.assertRaises(DepositError) as ctx:
            submit_deposit(
                user=self.user, network_code='POL', amount='10.00',
                tx_hash='0xPOLMIN', order_id='',
            )
        self.assertIn('25', str(ctx.exception.errors['amount']))

    def test_global_minimum_applies_when_network_unconfigured(self) -> None:
        # TRX inherits the coded default minimum (1 USDT); 0.5 must fail.
        with self.assertRaises(DepositError):
            submit_deposit(
                user=self.user, network_code='TRX', amount='0.50',
                tx_hash='0xTRXMIN', order_id='',
            )

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def test_multipart_submission_with_screenshot(self) -> None:
        self._auth(self.user)
        response = self.client.post(
            '/api/deposits/',
            {
                'network': 'TRX',
                'amount': '15.00',
                'tx_hash': '0xWITHSHOT',
                'order_id': '',
                'screenshot': _upload(),
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()['data']
        self.assertTrue(body['has_screenshot'])
        deposit = Deposit.objects.get(deposit_id=body['deposit_id'])
        self.assertTrue(deposit.screenshot)
        deposit.screenshot.delete(save=False)  # clean the test media dir

    def test_screenshot_rejects_oversize_and_wrong_type(self) -> None:
        from apps.core.uploads import validate_user_image

        with self.assertRaises(Exception):
            validate_user_image(SimpleUploadedFile('x.txt', b'not an image', content_type='text/plain'))

    def test_reviewer_stamped_on_approve_and_reject(self) -> None:
        dep1 = submit_deposit(
            user=self.user, network_code='TRX', amount='10.00', tx_hash='0xREV1', order_id='',
        ).deposit
        dep2 = submit_deposit(
            user=self.user, network_code='TRX', amount='10.00', tx_hash='0xREV2', order_id='',
        ).deposit
        approve_deposit(deposit=dep1, admin_user=self.admin, note='ok')
        reject_deposit(deposit=dep2, admin_user=self.admin, reason='no')
        dep1.refresh_from_db()
        dep2.refresh_from_db()
        self.assertEqual(dep1.reviewed_by, self.admin)
        self.assertEqual(dep1.approved_at is not None, True)
        self.assertEqual(dep2.reviewed_by, self.admin)
        self.assertEqual(dep2.rejected_at is not None, True)

    def test_admin_note_endpoint_updates_without_status_change(self) -> None:
        deposit = submit_deposit(
            user=self.user, network_code='TRX', amount='10.00', tx_hash='0xNOTE1', order_id='',
        ).deposit
        self._auth(self.admin)
        response = self.client.patch(
            f'/api/admin/deposits/{deposit.deposit_id}/note/',
            {'admin_note': 'Waiting on explorer confirmation.'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        deposit.refresh_from_db()
        self.assertEqual(deposit.admin_note, 'Waiting on explorer confirmation.')
        self.assertEqual(deposit.status, Deposit.Status.PENDING)

        # Regular users can never touch it.
        self._auth(self.user)
        response = self.client.patch(
            f'/api/admin/deposits/{deposit.deposit_id}/note/',
            {'admin_note': 'hacked'},
            format='json',
        )
        self.assertIn(response.status_code, (401, 403))

    def test_admin_screenshot_endpoint_is_staff_only(self) -> None:
        self._auth(self.user)
        response = self.client.post(
            '/api/deposits/',
            {
                'network': 'TRX', 'amount': '12.00', 'tx_hash': '0xSHOT2',
                'order_id': '', 'screenshot': _upload(),
            },
            format='multipart',
        )
        deposit_id = response.json()['data']['deposit_id']

        # Owner cannot view; staff can.
        self.assertEqual(
            self.client.get(f'/api/admin/deposits/{deposit_id}/screenshot/').status_code, 403,
        )
        self._auth(self.admin)
        self.assertEqual(
            self.client.get(f'/api/admin/deposits/{deposit_id}/screenshot/').status_code, 200,
        )

    def test_verification_label_defaults_to_manual(self) -> None:
        deposit = submit_deposit(
            user=self.user, network_code='TRX', amount='10.00', tx_hash='0xVERLBL', order_id='',
        ).deposit
        self._auth(self.admin)
        body = self.client.get(f'/api/admin/deposits/{deposit.deposit_id}/').json()['data']
        self.assertEqual(body['verification_status'], 'MANUAL_VERIFICATION')

    def test_admin_deposit_list_carries_new_fields(self) -> None:
        submit_deposit(
            user=self.user, network_code='TRX', amount='10.00', tx_hash='0xLISTFLD', order_id='',
        )
        self._auth(self.admin)
        body = self.client.get('/api/admin/deposits/?status=PENDING').json()
        row = next(r for r in body['data'] if r['tx_hash'] == '0xLISTFLD')
        for field in ('reviewer_email', 'has_screenshot', 'verification_status', 'deposit_address'):
            self.assertIn(field, row)

    def test_user_networks_endpoint_exposes_config(self) -> None:
        self._auth(self.user)
        rows = self.client.get('/api/deposits/networks/').json()['data']
        pol = next(r for r in rows if r['code'] == 'POL')
        self.assertEqual(pol['minimum_amount'], '25.00')
        self.assertTrue(pol['has_address'])
        self.assertIn('contract_address', pol)
        self.assertIn('network_warning', pol)

    def test_admin_network_config_patch(self) -> None:
        self._auth(self.admin)
        response = self.client.patch(
            f'/api/admin/networks/{self.trx.pk}/',
            {
                'min_deposit': '5.00',
                'contract_address': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t',
                'network_warning': 'TRC20 only.',
                'withdrawal_fee_is_percent': 'true',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.trx.refresh_from_db()
        self.assertEqual(self.trx.min_deposit, Decimal('5.00'))
        self.assertEqual(self.trx.contract_address, 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t')
        self.assertEqual(self.trx.network_warning, 'TRC20 only.')
        self.assertIs(self.trx.withdrawal_fee_is_percent, True)

        # Clearing a money field returns to inherit-the-default (None).
        response = self.client.patch(
            f'/api/admin/networks/{self.trx.pk}/', {'min_deposit': ''}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.trx.refresh_from_db()
        self.assertIsNone(self.trx.min_deposit)

        # Regular users are locked out of network administration.
        self._auth(self.user)
        self.assertIn(
            self.client.get('/api/admin/networks/').status_code, (401, 403),
        )

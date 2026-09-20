"""Ensure the platform's USDT networks exist — WITHOUT inventing addresses.

Production conversion (§1/§8): networks are configurable rows. This command
creates any MISSING Network rows with safe, empty configuration and (only in
development/testing, guarded like seed_demo_data) applies the operator's
``--set-address`` values. In production it never fabricates or silently sets
deposit addresses — addresses are supplied by the operator through the admin
deposit-addresses API or the explicit dev-only flag below.

Usage::

    python manage.py bootstrap_deposit_networks                 # create missing rows only
    python manage.py bootstrap_deposit_networks --set-address TRX=THcB... --set-address BSC=0x8b6...   # dev/test only
"""

import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.wallet.models import Network

# code → (display name, default sort order)
DEFAULT_NETWORKS = [
    ('BSC', 'BNB Smart Chain', 1),
    ('TRX', 'Tron (TRC20)', 2),
    ('ETH', 'Ethereum (ERC20)', 3),
    ('POL', 'Polygon', 4),
    ('SOL', 'Solana', 5),
    ('TON', 'TON', 6),
]


class Command(BaseCommand):
    help = (
        'Create missing Network configuration rows (idempotent). Deposit '
        'addresses are NOT invented here: set them via the admin panel '
        '(deposit-addresses API). --set-address works only in DEBUG/testing.'
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--set-address',
            action='append',
            default=[],
            metavar='CODE=ADDRESS',
            help='DEV/TEST ONLY: set the active deposit address for a network.',
        )

    def handle(self, *args, **options) -> None:
        created, updated = [], []
        for code, name, sort_order in DEFAULT_NETWORKS:
            network, was_created = Network.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'asset': 'USDT',
                    'sort_order': sort_order,
                    'is_active': True,
                },
            )
            if was_created:
                created.append(code)
            elif network.name != name and network.name == code:
                network.name = name
                network.save(update_fields=['name', 'updated_at'])
                updated.append(code)

        for entry in options['set_address']:
            if '=' not in entry:
                raise CommandError(f'--set-address expects CODE=ADDRESS, got {entry!r}')
            code, address = entry.split('=', 1)
            code, address = code.strip().upper(), address.strip()
            if not address:
                raise CommandError(f'Empty address for {code!r}.')
            if not settings.DEBUG and not settings.TESTING:
                raise CommandError(
                    'Refusing to set deposit addresses outside development: '
                    'configure production addresses through the admin panel.'
                )
            from apps.deposits.services import get_active_address

            network = Network.objects.filter(code=code).first()
            if network is None:
                raise CommandError(f'Unknown network code {code!r}.')
            from apps.wallet.models import DepositAddress

            DepositAddress.objects.filter(network=network, asset=network.asset, is_active=True).update(is_active=False)
            DepositAddress.objects.create(network=network, asset=network.asset, address=address, is_active=True)
            self.stdout.write(f'  {code}: active address set ({address[:10]}…)')

        for code in created:
            self.stdout.write(self.style.SUCCESS(f'  network {code}: created'))
        for code in updated:
            self.stdout.write(f'  network {code}: name updated')
        if not created and not updated:
            self.stdout.write('All networks already configured; nothing to do.')
        if created:
            self.stdout.write(self.style.WARNING(
                'Reminder: add each network\'s real deposit address and '
                'configuration via /api/admin-panel/deposit-addresses/ and '
                '/api/admin-panel/networks/ before enabling it for users.'
            ))

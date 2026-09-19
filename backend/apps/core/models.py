"""Core models: audit trail, site settings, valuations, ID counters.

Domain-specific business models live in their own apps; this module holds
cross-cutting tables. Nothing here is exposed to normal users.
"""

from django.conf import settings
from django.db import models

from .db import HumanIDCounter, TimeStampedModel, money_field


class AuditLog(models.Model):
    """Append-only trail for sensitive actions (admin and financial events).

    Rows are never exposed to normal users; they exist so that any balance
    change or admin intervention can be reconstructed later.
    """

    class Action(models.TextChoices):
        CREATE = 'CREATE', 'Create'
        UPDATE = 'UPDATE', 'Update'
        DELETE = 'DELETE', 'Delete'
        APPROVE = 'APPROVE', 'Approve'
        REJECT = 'REJECT', 'Reject'
        SUSPEND = 'SUSPEND', 'Suspend'
        ADJUST = 'ADJUST', 'Manual balance adjustment'
        LOGIN = 'LOGIN', 'Login'
        LOGOUT = 'LOGOUT', 'Logout'
        OTHER = 'OTHER', 'Other'

    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    target_type = models.CharField(max_length=64, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['actor_user', '-created_at']),
            models.Index(fields=['target_type', 'target_id']),
        ]

    def __str__(self) -> str:
        actor = self.actor_user or 'system'
        return f'{self.action} by {actor} on {self.target_type or "?"}#{self.target_id or "?"}'


class SiteSetting(TimeStampedModel):
    """Editable key/value platform configuration.

    Never store passwords or secret API keys here — secrets belong in
    environment variables or a secrets manager.
    """

    class ValueType(models.TextChoices):
        STRING = 'string', 'String'
        INTEGER = 'integer', 'Integer'
        DECIMAL = 'decimal', 'Decimal'
        BOOLEAN = 'boolean', 'Boolean'
        JSON = 'json', 'JSON'

    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True)
    value_type = models.CharField(
        max_length=16,
        choices=ValueType.choices,
        default=ValueType.STRING,
    )
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['key']

    def __str__(self) -> str:
        return f'{self.key} = {self.value}'


class CompanyValuation(TimeStampedModel):
    """Daily valuation series shown as a graph.

    Retained only so historical seed rows remain migratable; new rows are
    never created by production code, and the frontend no longer renders
    this series.
    """

    valuation_date = models.DateField(unique=True, db_index=True)
    value = money_field()
    currency = models.CharField(max_length=8, default='USDT')
    is_demo = models.BooleanField(default=True)

    class Meta:
        ordering = ['valuation_date']
        verbose_name_plural = 'Company valuations'

    def __str__(self) -> str:
        return f'{self.valuation_date}: {self.value} {self.currency}'


__all__ = [
    'AuditLog',
    'CompanyValuation',
    'HumanIDCounter',
    'SiteSetting',
]

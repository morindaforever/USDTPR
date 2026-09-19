"""Shared database primitives for all apps.

Financial rules encoded here:
- Every USDT amount uses :func:`money_field` (Decimal, 24 digits / 8 places).
- Never use ``FloatField`` for money anywhere in this project.
- Public business IDs (``TXN202609160001``, ``USR000001``, …) come from
  :class:`HumanIDField`, backed by a serialized counter table so concurrent
  workers cannot mint the same ID.
"""

from django.conf import settings
from django.db import models
from django.db import transaction


def money_field(**kwargs) -> models.DecimalField:
    """Standard USDT money column: Decimal(24, 8), non-null by default.

    USDT has 6 on-chain decimals; 8 places gives headroom for internal
    accounting while avoiding float entirely.
    """
    kwargs.setdefault('max_digits', 24)
    kwargs.setdefault('decimal_places', 8)
    return models.DecimalField(**kwargs)


def optional_money_field(**kwargs) -> models.DecimalField:
    """Money column allowed to be NULL (e.g. snapshots filled on activation)."""
    kwargs.setdefault('max_digits', 24)
    kwargs.setdefault('decimal_places', 8)
    kwargs.setdefault('null', True)
    kwargs.setdefault('blank', True)
    return models.DecimalField(**kwargs)


class HumanIDCounter(models.Model):
    """Serialized counter backing :class:`HumanIDField` (one row per prefix)."""

    prefix = models.CharField(max_length=16, primary_key=True)
    last_value = models.PositiveBigIntegerField(default=0)

    class Meta:
        verbose_name = 'Human ID counter'
        verbose_name_plural = 'Human ID counters'

    def __str__(self) -> str:
        return f'{self.prefix}:{self.last_value}'

    @classmethod
    def next_value(cls, prefix: str) -> int:
        """Atomically increment and return the next integer for ``prefix``.

        Must run inside a transaction. ``select_for_update`` serializes
        concurrent workers/requests so IDs are gap-tolerant but never reused.
        """
        counter, _ = cls.objects.select_for_update().get_or_create(prefix=prefix)
        counter.last_value += 1
        counter.save(update_fields=['last_value'])
        return counter.last_value

    @classmethod
    @transaction.atomic
    def next_value_atomic(cls, prefix: str) -> int:
        """Transaction-wrapped variant safe to call from anywhere."""
        return cls.next_value(prefix)


class HumanIDField(models.CharField):
    """Business-facing unique ID like ``USR000001`` or ``TXN202609160001``.

    Assigned on first save inside the row's insert transaction. The unique
    DB constraint is the final safety net against any race.
    """

    def __init__(self, prefix: str, padding: int = 6, **kwargs) -> None:
        self.prefix = prefix
        self.padding = padding
        kwargs.setdefault('max_length', len(prefix) + padding + 8)
        kwargs.setdefault('unique', True)
        kwargs.setdefault('editable', False)
        kwargs.setdefault('db_index', True)
        super().__init__(**kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs['prefix'] = self.prefix
        kwargs['padding'] = self.padding
        return name, path, args, kwargs

    def pre_save(self, model_instance, add: bool):
        value = getattr(model_instance, self.attname)
        if add and not value:
            # Nested atomic: savepoint when the row insert is already inside
            # a transaction, standalone transaction otherwise. The counter
            # row lock serializes concurrent inserts per prefix.
            number = HumanIDCounter.next_value_atomic(self.prefix)
            value = f'{self.prefix}{number:0{self.padding}d}'
            setattr(model_instance, self.attname, value)
        return value


class TimeStampedModel(models.Model):
    """created_at/updated_at with automatic maintenance."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TimeStampedUserModel(TimeStampedModel):
    """Audit-friendly base carrying an optional actor user reference."""

    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )

    class Meta:
        abstract = True


@transaction.atomic
def allocate_human_id(prefix: str, padding: int = 6) -> str:
    """Public helper: mint the next human ID for ``prefix`` atomically."""
    number = HumanIDCounter.next_value(prefix)
    return f'{prefix}{number:0{padding}d}'

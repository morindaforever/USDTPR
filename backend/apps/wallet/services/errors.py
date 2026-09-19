"""Typed wallet-service errors.

These are INTERNAL service-layer errors. API views catch them and translate
them into the standard ``{success, message, errors}`` envelope with safe
messages; stack traces never reach users.
"""


class WalletError(Exception):
    """Base class for all wallet service errors."""

    default_message = 'Wallet operation failed.'

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.default_message)
        self.message = message or self.default_message


class WalletNotFoundError(WalletError):
    default_message = 'Wallet not found for this account.'


class InvalidAmountError(WalletError):
    default_message = 'Amount must be greater than zero.'


class InvalidBalanceTypeError(WalletError):
    default_message = 'Unknown balance type.'


class InsufficientBalanceError(WalletError):
    default_message = 'Insufficient balance for this operation.'


class DuplicateTransactionError(WalletError):
    default_message = 'A transaction with this idempotency key already exists.'


class InvalidTransactionError(WalletError):
    default_message = 'Transaction cannot be modified in its current state.'

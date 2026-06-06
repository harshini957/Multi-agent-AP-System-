"""
Per-agent credential accessors.
Each function is scoped to exactly one agent identity.
Calling get_payment_headers("accounting_api") raises CredentialDeniedError
because "payment" is not in the accounting_api allow-list.
"""

from auth.credential_broker import CredentialBroker, CredentialDeniedError

_broker = CredentialBroker()


def get_intake_headers(provider: str) -> dict:
    return _broker.get_headers("intake", provider)


def get_matching_headers(provider: str) -> dict:
    return _broker.get_headers("matching", provider)


def get_payment_headers(provider: str) -> dict:
    return _broker.get_headers("payment", provider)
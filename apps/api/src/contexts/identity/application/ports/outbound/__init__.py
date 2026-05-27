"""Outbound ports the identity application layer depends on."""

from __future__ import annotations

from contexts.identity.application.ports.outbound.email_sender import EmailSender
from contexts.identity.application.ports.outbound.identity_provider import (
    Identity,
    IdentityProvider,
)
from contexts.identity.application.ports.outbound.user_repository import UserRepository

__all__ = [
    "EmailSender",
    "Identity",
    "IdentityProvider",
    "UserRepository",
]

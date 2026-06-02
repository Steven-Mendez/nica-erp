"""Domain errors raised by the tenants context."""

from __future__ import annotations


class TenantNotFoundError(Exception):
    """The requested tenant does not exist (or is invisible by RLS)."""


class NotAMemberError(Exception):
    """The actor is not an active member of the requested tenant."""


class OwnerRoleNotAllowedHereError(Exception):
    """Owner role cannot be created via the normal Membership constructor."""


class OwnerAlreadyExistsError(Exception):
    """A second active owner cannot exist for the same tenant."""


class CannotRemoveOwnerError(Exception):
    """The owner cannot be removed without prior ownership transfer."""


class CannotDemoteOwnerError(Exception):
    """The owner cannot be demoted; transfer ownership first (post-MVP)."""


class InvitationExpiredError(Exception):
    """The invitation's ``expires_at`` is in the past."""


class InvitationAlreadyAcceptedError(Exception):
    """The invitation was already accepted."""


class InvitationCancelledError(Exception):
    """The invitation was cancelled before acceptance."""


class InvitationInvalidError(Exception):
    """The invitation token signature is invalid."""


class InvitationNotFoundError(Exception):
    """No invitation found for the provided token hash."""


class InvitationDuplicatePendingError(Exception):
    """A pending invitation already exists for the same tenant + email."""


__all__ = [
    "CannotDemoteOwnerError",
    "CannotRemoveOwnerError",
    "InvitationAlreadyAcceptedError",
    "InvitationCancelledError",
    "InvitationDuplicatePendingError",
    "InvitationExpiredError",
    "InvitationInvalidError",
    "InvitationNotFoundError",
    "NotAMemberError",
    "OwnerAlreadyExistsError",
    "OwnerRoleNotAllowedHereError",
    "TenantNotFoundError",
]

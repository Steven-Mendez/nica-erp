"""Identity bounded context — application layer.

Use cases, outbound port Protocols, and typed errors. Adapter implementations
(local DB IdP, Cognito IdP, SMTP/SES email senders, SQLAlchemy
UserRepository) live in ``contexts.identity.adapters`` and must NOT be
imported here.
"""

from __future__ import annotations

from contexts.identity.application.constants import SYSTEM_GLOBAL_TENANT_ID
from contexts.identity.application.errors import (
    EmailSendError,
    IdentityError,
    InvalidCredentialsError,
    LockoutActiveError,
    SignupEmailNotConfirmedError,
    TokenExpiredError,
    UserNotFoundError,
)
from contexts.identity.application.ports.outbound import (
    EmailSender,
    Identity,
    IdentityProvider,
    UserRepository,
)
from contexts.identity.application.use_cases import (
    Authenticate,
    ChangePassword,
    ConfirmSignup,
    ForgotPassword,
    GetMe,
    Logout,
    RefreshToken,
    RegisterUser,
    ResendCode,
    ResetPassword,
    UpdateProfile,
)

__all__ = [
    "SYSTEM_GLOBAL_TENANT_ID",
    "Authenticate",
    "ChangePassword",
    "ConfirmSignup",
    "EmailSendError",
    "EmailSender",
    "ForgotPassword",
    "GetMe",
    "Identity",
    "IdentityError",
    "IdentityProvider",
    "InvalidCredentialsError",
    "LockoutActiveError",
    "Logout",
    "RefreshToken",
    "RegisterUser",
    "ResendCode",
    "ResetPassword",
    "SignupEmailNotConfirmedError",
    "TokenExpiredError",
    "UpdateProfile",
    "UserNotFoundError",
    "UserRepository",
]

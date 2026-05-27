"""Identity-context use cases.

One class per file. Each is a frozen, keyword-only dataclass that takes its
outbound ports explicitly via the constructor and exposes a single
``async execute(...)`` method.
"""

from __future__ import annotations

from contexts.identity.application.use_cases.authenticate import Authenticate
from contexts.identity.application.use_cases.change_password import ChangePassword
from contexts.identity.application.use_cases.confirm_signup import ConfirmSignup
from contexts.identity.application.use_cases.forgot_password import ForgotPassword
from contexts.identity.application.use_cases.get_me import GetMe
from contexts.identity.application.use_cases.logout import Logout
from contexts.identity.application.use_cases.refresh_token import RefreshToken
from contexts.identity.application.use_cases.register_user import RegisterUser
from contexts.identity.application.use_cases.resend_code import ResendCode
from contexts.identity.application.use_cases.reset_password import ResetPassword
from contexts.identity.application.use_cases.update_profile import UpdateProfile

__all__ = [
    "Authenticate",
    "ChangePassword",
    "ConfirmSignup",
    "ForgotPassword",
    "GetMe",
    "Logout",
    "RefreshToken",
    "RegisterUser",
    "ResendCode",
    "ResetPassword",
    "UpdateProfile",
]

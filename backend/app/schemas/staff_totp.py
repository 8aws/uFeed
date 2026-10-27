from __future__ import annotations

from pydantic import BaseModel, Field


class TotpStatus(BaseModel):
    enabled: bool
    pending: bool  # a secret was issued but no code confirmed it yet
    required: bool  # this instance asks editors/admins for codes
    recovery_left: int


class TotpSetup(BaseModel):
    secret: str  # to type into a password manager
    otpauth_url: str  # the same, as a link/QR (otpauth://totp/...)


class TotpCode(BaseModel):
    code: str = Field(min_length=6, max_length=16)


class StepUp(BaseModel):
    step_up_token: str
    expires_in: int  # seconds


class TotpEnabled(StepUp):
    recovery_codes: list[str]  # shown this once


class RecoveryCodes(BaseModel):
    recovery_codes: list[str]


class TotpDisable(BaseModel):
    code: str = Field(min_length=6, max_length=16)
    password: str

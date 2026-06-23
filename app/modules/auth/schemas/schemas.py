"""app/modules/auth/schemas/schemas.py — Auth and OTP schemas."""

from pydantic import BaseModel, Field


class SendOtpRequest(BaseModel):
    # Enforce basic E.164-like formatting
    phone: str = Field(
        ...,
        pattern=r"^\+[1-9]\d{1,14}$",
        description="Phone number in E.164 format (e.g., +251911234567)",
    )


class VerifyOtpRequest(BaseModel):
    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="The 6-digit OTP code sent via SMS",
    )


class AuthResponse(BaseModel):
    status: str
    message: str

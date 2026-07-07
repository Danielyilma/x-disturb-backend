"""app/modules/auth/services/auth_services.py — OTP business logic."""

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from firebase_admin import auth as firebase_auth

from app.core.sms import AfroMessageClient
from app.modules.auth.exceptions.exceptions import (
    OtpExpiredError,
    OtpInvalidError,
    OtpNotFoundError,
    PhoneAlreadyInUseError,
)
from app.modules.auth.repositories.otp_repository import OtpRepositoryImp
from app.modules.auth.schemas.schemas import AuthResponse

logger = logging.getLogger(__name__)


def _generate_otp(length: int = 6) -> str:
    """Generate a secure numeric OTP."""
    # SystemRandom is cryptographically secure
    rng = secrets.SystemRandom()
    return "".join(str(rng.randint(0, 9)) for _ in range(length))


async def send_otp(
    *,
    phone: str,
    repo: OtpRepositoryImp,
    sms_client: AfroMessageClient,
) -> AuthResponse:
    # 1. Generate code & expiration
    code = _generate_otp()
    expires_at = datetime.now(UTC) + timedelta(minutes=5)

    # 2. Save to Firestore
    await repo.save_otp(phone=phone, code=code, expires_at=expires_at)

    # 3. Dispatch SMS
    message = f"Your x-disturb verification code is: {code}. It expires in 5 minutes."
    try:
        await sms_client.send_sms(to=phone, message=message)
    except Exception as exc:
        logger.error("Failed to send OTP to %s: %s", phone, exc)
        # Even if SMS fails, the code was saved. The client will return 502/503 from sms_client.
        raise

    return AuthResponse(status="success", message="OTP sent successfully.")


async def verify_otp(
    *,
    phone: str,
    code: str,
    repo: OtpRepositoryImp,
) -> AuthResponse:
    # 1. Fetch from Firestore
    otp_data = await repo.get_otp(phone)
    if not otp_data:
        raise OtpNotFoundError()

    # Normalize timestamps if returned as Firestore DatetimeWithNanoseconds
    expires_at = otp_data["expires_at"]
    if hasattr(expires_at, "timestamp"):
        expires_at = datetime.fromtimestamp(expires_at.timestamp(), tz=UTC)

    # 2. Check expiration
    if datetime.now(UTC) > expires_at:
        await repo.delete_otp(phone)  # Cleanup expired code
        raise OtpExpiredError()

    # 3. Validate code
    if otp_data["code"] != code:
        raise OtpInvalidError()

    # 4. Cleanup OTP
    await repo.delete_otp(phone)

    return AuthResponse(status="success", message="Phone number verified successfully.")

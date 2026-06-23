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
    user: dict[str, Any],
    phone: str,
    repo: OtpRepositoryImp,
    sms_client: AfroMessageClient,
) -> AuthResponse:
    uid = user["uid"]

    # 1. Generate code & expiration
    code = _generate_otp()
    expires_at = datetime.now(UTC) + timedelta(minutes=5)

    # 2. Save to Firestore
    await repo.save_otp(uid=uid, code=code, phone=phone, expires_at=expires_at)

    # 3. Dispatch SMS
    message = f"Your x-disturb verification code is: {code}. It expires in 5 minutes."
    try:
        await sms_client.send_sms(to=phone, message=message)
    except Exception as exc:
        logger.error("Failed to send OTP to %s for user %s: %s", phone, uid, exc)
        # Even if SMS fails, the code was saved. The client will return 502/503 from sms_client.
        raise

    return AuthResponse(status="success", message="OTP sent successfully.")


async def verify_otp(
    *,
    user: dict[str, Any],
    code: str,
    repo: OtpRepositoryImp,
) -> AuthResponse:
    uid = user["uid"]

    # 1. Fetch from Firestore
    otp_data = await repo.get_otp(uid)
    if not otp_data:
        raise OtpNotFoundError()

    # Normalize timestamps if returned as Firestore DatetimeWithNanoseconds
    expires_at = otp_data["expires_at"]
    if hasattr(expires_at, "timestamp"):
        expires_at = datetime.fromtimestamp(expires_at.timestamp(), tz=UTC)

    # 2. Check expiration
    if datetime.now(UTC) > expires_at:
        await repo.delete_otp(uid)  # Cleanup expired code
        raise OtpExpiredError()

    # 3. Validate code
    if otp_data["code"] != code:
        raise OtpInvalidError()

    phone = otp_data["phone"]

    # 4. Update Firebase Auth Profile
    try:
        # Note: firebase_admin.auth.update_user is blocking, running it inline for simplicity
        # as it's a relatively fast external API call, but we can wrap it if needed.
        # It's better to wrap it to not block the event loop.
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: firebase_auth.update_user(uid, phone_number=phone)
        )
    except firebase_auth.PhoneNumberAlreadyExistsError as exc:
        raise PhoneAlreadyInUseError() from exc
    except Exception as exc:
        logger.error("Failed to update Firebase user %s with phone %s: %s", uid, phone, exc)
        raise

    # 5. Cleanup OTP
    await repo.delete_otp(uid)

    return AuthResponse(status="success", message="Phone number verified successfully.")

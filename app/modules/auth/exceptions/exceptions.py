"""app/modules/auth/exceptions/exceptions.py — Domain exceptions for OTP auth."""

from app.core.base_exception import BaseExceptionError


class OtpExpiredError(BaseExceptionError):
    def __init__(self) -> None:
        super().__init__(message="OTP code has expired. Please request a new one.", status_code=400)


class OtpInvalidError(BaseExceptionError):
    def __init__(self) -> None:
        super().__init__(message="Invalid OTP code.", status_code=400)


class OtpNotFoundError(BaseExceptionError):
    def __init__(self) -> None:
        super().__init__(message="No active OTP found for this user.", status_code=404)


class PhoneAlreadyInUseError(BaseExceptionError):
    def __init__(self) -> None:
        super().__init__(
            message="This phone number is already linked to another account.",
            status_code=409,
        )

"""app/api/v1/routers/auth_routes.py — Auth routes."""

from fastapi import APIRouter, Depends

from app.core.dependency import CurrentUserDep, OtpRepoDep, SmsClientDep
from app.modules.auth.schemas.schemas import AuthResponse, SendOtpRequest, VerifyOtpRequest
from app.modules.auth.services import auth_services

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/send-otp", response_model=AuthResponse)
async def send_otp_route(
    request: SendOtpRequest,
    user: CurrentUserDep,
    repo: OtpRepoDep,
    sms_client: SmsClientDep,
) -> AuthResponse:
    """Send an OTP code to the provided phone number."""
    return await auth_services.send_otp(
        user=user,
        phone=request.phone,
        repo=repo,
        sms_client=sms_client,
    )


@auth_router.post("/verify-otp", response_model=AuthResponse)
async def verify_otp_route(
    request: VerifyOtpRequest,
    user: CurrentUserDep,
    repo: OtpRepoDep,
) -> AuthResponse:
    """Verify the OTP code and update the user's Firebase phone number."""
    return await auth_services.verify_otp(
        user=user,
        code=request.code,
        repo=repo,
    )

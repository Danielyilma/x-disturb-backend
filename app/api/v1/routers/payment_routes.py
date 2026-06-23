"""app/api/v1/routers/payment_routes.py — Chapa payment endpoints.

Routes:
  POST /api/v1/payments/initiate   — Start a payment; returns Chapa checkout URL.
  GET  /api/v1/payments/callback   — Chapa redirects here after user completes payment.
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.config import MySettings
from app.core.dependency import (
    ChapaClientDep,
    CurrentUserDep,
    PaymentRepoDep,
)
from app.modules.payment.schemas.schemas import InitiatePaymentRequest, InitiatePaymentResponse
from app.modules.payment.services import payment_services

logger = logging.getLogger(__name__)

payment_router = APIRouter(prefix="/payments", tags=["payments"])


@payment_router.post("/initiate", response_model=InitiatePaymentResponse)
async def initiate_payment_route(
    request: Request,
    body: InitiatePaymentRequest,
    user: CurrentUserDep,
    chapa_client: ChapaClientDep,
    payment_repo: PaymentRepoDep,
) -> InitiatePaymentResponse:
    """Initiate a Chapa payment for a subscription plan.

    - Validates the plan exists and is active.
    - Fetches price server-side (client cannot supply an amount).
    - Creates a `pending` transaction in Firestore.
    - Returns a Chapa checkout URL for the client to redirect to.
    """
    # Build the callback URL dynamically from the current request base URL
    base_url = str(request.base_url).rstrip("/")
    callback_url = f"{base_url}/api/v1/payments/callback"

    return await payment_services.initiate_payment(
        user=user,
        plan_id=body.plan_id,
        first_name=body.first_name,
        last_name=body.last_name,
        email=str(body.email),
        chapa_client=chapa_client,
        payment_repo=payment_repo,
        callback_url=callback_url,
        return_url=MySettings.CHAPA_RETURN_URL,
    )


@payment_router.post("/callback")
async def payment_callback_route(
    body: dict,
    chapa_client: ChapaClientDep,
    payment_repo: PaymentRepoDep,
) -> RedirectResponse:
    """Chapa payment callback endpoint.

    Chapa redirects the user's browser here after checkout with:
      ?trx_ref=<tx_ref>&status=<success|failed>

    This endpoint:
      1. Verifies the transaction server-side with Chapa.
      2. Updates the Firestore transaction status.
      3. Redirects the user to the configured CHAPA_RETURN_URL.

    Note: This is a browser redirect (not a webhook POST). No auth required —
    the tx_ref is validated against our own Firestore pending record.
    """
    try:
        trx_ref = body.get("tx_ref")
        if not trx_ref:
            raise HTTPException(status_code=400, detail="Missing tx_ref")
        result = await payment_services.handle_callback(
            trx_ref=trx_ref,
            chapa_client=chapa_client,
            payment_repo=payment_repo,
        )
        redirect_url = f"{MySettings.CHAPA_RETURN_URL}?status={result.status}&tx_ref={result.tx_ref}"
    except Exception as exc:
        logger.error("Payment callback error for trx_ref=%s: %s", trx_ref, exc)
        redirect_url = f"{MySettings.CHAPA_RETURN_URL}?status=failed&tx_ref={trx_ref}"

    return RedirectResponse(url=redirect_url, status_code=302)

"""app/modules/payment/services/payment_services.py — Payment business logic.

Orchestrates:
  1. initiate_payment  — validate plan, call Chapa initialize, persist pending tx
  2. handle_callback   — verify tx with Chapa, update Firestore status
"""

import logging
import uuid
from typing import Any

from app.core.chapa import ChapaAPIError, ChapaClient
from app.modules.payment.exceptions.exceptions import (
    ChapaNotConfiguredError,
    PaymentInitializationError,
    PaymentVerificationError,
    PlanInactiveError,
    PlanNotFoundError,
    TransactionAlreadyProcessedError,
    TransactionNotFoundError,
)
from app.modules.payment.repositories.payment_repository import PaymentRepositoryImp
from app.modules.payment.schemas.schemas import (
    CallbackResponse,
    InitiatePaymentResponse,
)

logger = logging.getLogger(__name__)


def _generate_tx_ref() -> str:
    """Generate a unique, Chapa-safe transaction reference."""
    return f"xdisturb-{uuid.uuid4().hex}"


async def initiate_payment(
    *,
    user: dict[str, Any],
    plan_id: str,
    first_name: str,
    last_name: str,
    email: str,
    chapa_client: ChapaClient,
    payment_repo: PaymentRepositoryImp,
    callback_url: str,
    return_url: str,
) -> InitiatePaymentResponse:
    """Initiate a Chapa payment for a subscription plan.

    Steps:
      1. Fetch the plan from Firestore — raises PlanNotFoundError if missing.
      2. Check `isActive` — raises PlanInactiveError if plan is disabled.
      3. Read the `price` field for the amount (client cannot supply their own).
      4. Generate a unique tx_ref.
      5. Persist a `pending` transaction in Firestore.
      6. Call Chapa /initialize — raises PaymentInitializationError on failure.
      7. Return the Chapa checkout URL.

    Args:
        user          : Decoded Firebase token dict (contains `uid`).
        plan_id       : Firestore document ID in subscription_plans collection.
        first_name    : Payer first name (passed to Chapa).
        last_name     : Payer last name (passed to Chapa).
        email         : Payer email (passed to Chapa).
        chapa_client  : Injected ChapaClient.
        payment_repo  : Injected PaymentRepositoryImp.
        callback_url  : URL Chapa will redirect to after payment (our endpoint).
        return_url    : Frontend URL shown to user after payment completes.

    Returns:
        InitiatePaymentResponse with checkout_url and tx_ref.
    """
    uid = user["uid"]

    # 1 & 2. Validate plan
    plan = await payment_repo.get_plan(plan_id)
    if plan is None:
        raise PlanNotFoundError()
    if not plan.get("isActive", False):
        raise PlanInactiveError()

    # 3. Server-side amount — cannot be overridden by client
    amount: float = float(plan["price"])
    currency: str = plan.get("currency", "ETB")

    # 4. Unique tx_ref
    tx_ref = _generate_tx_ref()

    # 5. Persist pending transaction BEFORE calling Chapa
    #    (so we always have a record even if Chapa call fails)
    await payment_repo.create_transaction(
        tx_ref=tx_ref,
        user_id=uid,
        plan_id=plan_id,
        amount=amount,
        currency=currency,
    )

    # 6. Call Chapa
    payload: dict[str, Any] = {
        "amount": str(amount),
        "currency": currency,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "tx_ref": tx_ref,
        "callback_url": callback_url,
        "return_url": return_url,
    }

    try:
        chapa_resp = await chapa_client.initialize_transaction(payload)
    except ChapaAPIError as exc:
        logger.error(
            "Chapa initialization failed for user=%s tx_ref=%s: %s", uid, tx_ref, exc.message
        )
        # Update tx status to failed so the record is not left orphaned as pending
        await payment_repo.update_transaction_status(tx_ref=tx_ref, status="failed")
        raise PaymentInitializationError(detail=exc.message) from exc

    checkout_url: str = chapa_resp["data"]["checkout_url"]

    return InitiatePaymentResponse(
        checkout_url=checkout_url,
        tx_ref=tx_ref,
    )


async def handle_callback(
    *,
    trx_ref: str,
    chapa_client: ChapaClient,
    payment_repo: PaymentRepositoryImp,
) -> CallbackResponse:
    """Handle Chapa's post-payment callback redirect.

    Steps:
      1. Look up the pending transaction in Firestore.
      2. Guard against double-processing.
      3. Call Chapa /verify to get authoritative payment status.
      4. Update the Firestore transaction with status + raw Chapa response.
      5. Return a CallbackResponse for the route to act on (redirect).

    Args:
        trx_ref        : Transaction reference from Chapa's callback query param.
        chapa_client  : Injected ChapaClient.
        payment_repo  : Injected PaymentRepositoryImp.

    Returns:
        CallbackResponse with `status` = "success" | "failed".
    """
    # 1. Fetch from Firestore
    transaction = await payment_repo.get_transaction(trx_ref)
    if transaction is None:
        raise TransactionNotFoundError()

    # 2. Idempotency guard
    if transaction.get("status") != "pending":
        raise TransactionAlreadyProcessedError()

    # 3. Verify with Chapa
    try:
        verify_resp = await chapa_client.verify_transaction(trx_ref)
    except ChapaAPIError as exc:
        logger.error("Chapa verification failed for tx_ref=%s: %s", trx_ref, exc.message)
        await payment_repo.update_transaction_status(
            tx_ref=trx_ref,
            status="failed",
            chapa_response=exc.raw,
        )
        raise PaymentVerificationError(detail=exc.message) from exc

    # 4. Update Firestore
    chapa_data: dict[str, Any] = verify_resp.get("data", {})
    chapa_status: str = chapa_data.get("status", "failed")
    final_status = "success" if chapa_status == "success" else "failed"

    await payment_repo.update_transaction_status(
        tx_ref=trx_ref,
        status=final_status,
        chapa_response=verify_resp,
    )

    logger.info(
        "Transaction tx_ref=%s finalized with status=%s", trx_ref, final_status
    )

    # 5. Return result
    return CallbackResponse(
        status=final_status,
        tx_ref=trx_ref,
        message="Payment successful." if final_status == "success" else "Payment failed.",
    )

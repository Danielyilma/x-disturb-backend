"""app/modules/payment/schemas/schemas.py — Payment Pydantic schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr


# ── Request schemas ────────────────────────────────────────────────────────────

class InitiatePaymentRequest(BaseModel):
    """Body for POST /payments/initiate."""

    plan_id: str
    first_name: str
    last_name: str
    email: EmailStr


# ── Response schemas ───────────────────────────────────────────────────────────

class InitiatePaymentResponse(BaseModel):
    """Returned after a successful payment initiation."""

    status: str = "success"
    message: str = "Payment initiated successfully."
    checkout_url: str
    tx_ref: str


class TransactionRecord(BaseModel):
    """Represents a transaction document stored in Firestore."""

    tx_ref: str
    user_id: str
    plan_id: str
    amount: float
    currency: str
    status: str          # "pending" | "success" | "failed"
    chapa_response: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CallbackResponse(BaseModel):
    """Internal response used by the callback handler."""

    status: str          # "success" | "failed"
    tx_ref: str
    message: str

"""app/modules/payment/repositories/payment_repository.py — Firestore data-access for payments.

Responsibilities:
  1. Read a subscription plan document to get the price.
  2. Create / update transaction documents in the `transactions` collection.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from google.cloud.firestore_v1.async_client import AsyncClient

logger = logging.getLogger(__name__)

# Firestore collection names
TRANSACTIONS_COLLECTION = "transactions"


class PaymentRepositoryImp:
    """Firestore repository for payment-related data access."""

    def __init__(self, *, db: AsyncClient, plans_collection: str) -> None:
        self._db = db
        self._plans_collection = plans_collection

    # ── Subscription plan ─────────────────────────────────────────────────────

    async def get_plan(self, plan_id: str) -> dict[str, Any] | None:
        """Fetch a subscription plan document by its ID.

        Returns the plan data dict or None if not found.

        Firestore schema (subscription_plans/{plan_id}):
            category      : str      — e.g. "Christian"
            currency      : str      — e.g. "ETB"
            durationLabel : str      — e.g. "2 month"
            durationMonths: float
            isActive      : bool
            price         : float    ← used for amount validation
            sortOrder     : float
        """
        doc_ref = self._db.collection(self._plans_collection).document(plan_id)
        snapshot = await doc_ref.get()
        if not snapshot.exists:
            return None
        return snapshot.to_dict()

    # ── Transactions ──────────────────────────────────────────────────────────

    async def create_transaction(
        self,
        *,
        tx_ref: str,
        user_id: str,
        plan_id: str,
        amount: float,
        currency: str,
    ) -> None:
        """Create a new `pending` transaction document.

        Document ID = tx_ref (makes lookups on callback O(1)).
        """
        now = datetime.now(UTC)
        doc: dict[str, Any] = {
            "tx_ref": tx_ref,
            "user_id": user_id,
            "plan_id": plan_id,
            "amount": amount,
            "currency": currency,
            "status": "pending",
            "chapa_response": None,
            "created_at": now,
            "updated_at": now,
        }
        await self._db.collection(TRANSACTIONS_COLLECTION).document(tx_ref).set(doc)
        logger.info("Created pending transaction tx_ref=%s for user=%s", tx_ref, user_id)

    async def get_transaction(self, tx_ref: str) -> dict[str, Any] | None:
        """Fetch a transaction document by tx_ref. Returns None if not found."""
        doc_ref = self._db.collection(TRANSACTIONS_COLLECTION).document(tx_ref)
        snapshot = await doc_ref.get()
        if not snapshot.exists:
            return None
        return snapshot.to_dict()

    async def update_transaction_status(
        self,
        *,
        tx_ref: str,
        status: str,
        chapa_response: dict[str, Any] | None = None,
    ) -> None:
        """Update the status (and optional raw Chapa response) on a transaction.

        Args:
            tx_ref          : The unique transaction reference.
            status          : "success" | "failed"
            chapa_response  : Raw dict from Chapa verify endpoint.
        """
        updates: dict[str, Any] = {
            "status": status,
            "updated_at": datetime.now(UTC),
        }
        if chapa_response is not None:
            updates["chapa_response"] = chapa_response

        await self._db.collection(TRANSACTIONS_COLLECTION).document(tx_ref).update(updates)
        logger.info("Updated transaction tx_ref=%s to status=%s", tx_ref, status)

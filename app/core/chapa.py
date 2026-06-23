"""app/core/chapa.py — Async Chapa API client.

Wraps httpx.AsyncClient for all Chapa payment gateway calls.

Endpoints used:
  POST /v1/transaction/initialize  — Create a new checkout session
  GET  /v1/transaction/verify/{tx_ref} — Verify a completed transaction

Auth: Bearer token sent via Authorization header.
"""

import logging
from typing import Any

import httpx

from app.config import MySettings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class ChapaAPIError(Exception):
    """Raised when Chapa returns a non-2xx response or a failed status."""

    def __init__(self, *, message: str, status_code: int | None = None, raw: dict | None = None):
        self.message = message
        self.status_code = status_code
        self.raw = raw or {}
        super().__init__(message)


class ChapaClient:
    """Async client for the Chapa payment API.

    Usage (injected via FastAPI Depends):
        client: ChapaClient = Depends(get_chapa_client)
        result = await client.initialize_transaction(payload)
    """

    def __init__(self, *, secret_key: str, base_url: str) -> None:
        self._secret_key = secret_key
        self._base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._secret_key}",
            "Content-Type": "application/json",
        }

    async def initialize_transaction(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Initialise a payment and return Chapa's response.

        Chapa returns:
            {
                "message": "Hosted Link",
                "status": "success",
                "data": {"checkout_url": "https://checkout.chapa.co/..."}
            }

        Raises:
            ChapaAPIError — if the HTTP request fails or status != "success".
        """
        url = f"{self._base_url}/transaction/initialize"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            try:
                resp = await client.post(url, json=payload, headers=self._headers())
            except httpx.RequestError as exc:
                logger.error("Chapa initialize request failed: %s", exc)
                raise ChapaAPIError(message="Could not reach Chapa API") from exc

        if resp.status_code != 200:
            logger.error(
                "Chapa initialize returned HTTP %s: %s", resp.status_code, resp.text
            )
            raise ChapaAPIError(
                message="Chapa payment initialization failed",
                status_code=resp.status_code,
                raw=resp.json() if resp.content else {},
            )

        body: dict[str, Any] = resp.json()
        if body.get("status") != "success":
            raise ChapaAPIError(
                message=body.get("message", "Chapa initialization returned non-success"),
                status_code=resp.status_code,
                raw=body,
            )

        return body

    async def verify_transaction(self, tx_ref: str) -> dict[str, Any]:
        """Verify a transaction by its tx_ref.

        Chapa returns:
            {
                "message": "Payment Details",
                "status": "success",
                "data": {
                    "status": "success",
                    "amount": 100.0,
                    "currency": "ETB",
                    ...
                }
            }

        Raises:
            ChapaAPIError — if verification fails or HTTP error occurs.
        """
        url = f"{self._base_url}/transaction/verify/{tx_ref}"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            try:
                resp = await client.get(url, headers=self._headers())
            except httpx.RequestError as exc:
                logger.error("Chapa verify request failed for tx_ref=%s: %s", tx_ref, exc)
                raise ChapaAPIError(message="Could not reach Chapa API") from exc

        if resp.status_code != 200:
            logger.error(
                "Chapa verify returned HTTP %s for tx_ref=%s: %s",
                resp.status_code, tx_ref, resp.text,
            )
            raise ChapaAPIError(
                message="Chapa transaction verification failed",
                status_code=resp.status_code,
                raw=resp.json() if resp.content else {},
            )

        body: dict[str, Any] = resp.json()
        if body.get("status") != "success":
            raise ChapaAPIError(
                message=body.get("message", "Chapa verification returned non-success"),
                status_code=resp.status_code,
                raw=body,
            )

        return body

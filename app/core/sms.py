"""app/core/sms.py — AfroMessage SMS integration.

Provides an async client to send SMS messages using AfroMessage API.
"""

import logging
from typing import Any

import httpx
from app.config import MySettings
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

AFROMESSAGE_BASE_URL = "https://api.afromessage.com/api"

class AfroMessageClient:
    def __init__(self, api_key: str | None, sender_name: str, identifier: str | None = None) -> None:
        self.api_key = api_key
        self.sender_name = sender_name
        self.identifier = identifier

    async def send_sms(self, to: str, message: str, callback: str | None = None) -> dict[str, Any]:
        """Send an SMS using AfroMessage.

        Args:
            to: Recipient phone number (e.g., "+2519...").
            message: The message content to send.
            callback: Optional callback URL for status updates.

        Returns:
            The JSON response from AfroMessage API.

        Raises:
            HTTPException: If the SMS fails to send.
        """
        if not self.api_key:
            logger.error("AFROMESSAGE_API_KEY is not configured.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SMS service is not configured.",
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        
        params = {
            "to": to,
            "message": message,
            "sender": self.sender_name,
            "from": self.identifier,
        }
        if callback:
            params["callback"] = callback

        async with httpx.AsyncClient(base_url=AFROMESSAGE_BASE_URL) as client:
            try:
                response = await client.get("/send", headers=headers, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                logger.error("AfroMessage API error: %s - %s", exc.response.status_code, exc.response.text)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to send SMS via external provider.",
                ) from exc
            except httpx.RequestError as exc:
                logger.error("AfroMessage Request error: %s", str(exc))
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Could not reach SMS provider.",
                ) from exc

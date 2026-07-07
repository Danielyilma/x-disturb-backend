"""app/modules/auth/repositories/otp_repository.py — Data access for OTPs.

Stores OTPs in Firestore collection 'otp_codes'.
The document ID is the user's uid to enforce one active OTP per user.
"""

from datetime import datetime
from typing import Any

from google.cloud.firestore_v1.async_client import AsyncClient

from app.core.common.serializers import snapshot_to_dict

_COLLECTION = "otp_codes"


class OtpRepositoryImp:
    def __init__(self, *, db: AsyncClient) -> None:
        self._col = db.collection(_COLLECTION)

    async def save_otp(
        self, phone: str, code: str, expires_at: datetime
    ) -> dict[str, Any]:
        """Save an OTP for the phone, overwriting any existing one."""
        data = {
            "code": code,
            "phone": phone,
            "expires_at": expires_at,
        }
        # Use phone as document ID
        doc_ref = self._col.document(phone)
        await doc_ref.set(data)
        
        snapshot = await doc_ref.get()
        return snapshot_to_dict(snapshot)

    async def get_otp(self, phone: str) -> dict[str, Any] | None:
        """Retrieve the active OTP for a phone number."""
        snapshot = await self._col.document(phone).get()
        if not snapshot.exists:
            return None
        return snapshot_to_dict(snapshot)

    async def delete_otp(self, phone: str) -> bool:
        """Delete an OTP document."""
        doc_ref = self._col.document(phone)
        snapshot = await doc_ref.get()
        if not snapshot.exists:
            return False
        await doc_ref.delete()
        return True


async def get_otp_repository(db: AsyncClient) -> OtpRepositoryImp:
    """Factory for dependency injection."""
    return OtpRepositoryImp(db=db)

"""app/core/common/serializers.py — Shared Pydantic / Firestore helpers.

Firestore documents are returned as dicts (or DocumentSnapshot objects),
not ORM objects. These helpers standardize the conversion.
"""

from datetime import datetime

from google.cloud.firestore_v1 import DocumentSnapshot


def snapshot_to_dict(snapshot: DocumentSnapshot) -> dict:
    """Convert a Firestore DocumentSnapshot to a plain dict with `id` injected."""
    if not snapshot.exists:
        return {}
    data = snapshot.to_dict() or {}
    data["id"] = snapshot.id
    return data


def normalize_timestamps(data: dict) -> dict:
    """Convert Firestore DatetimeWithNanoseconds to standard Python datetime."""
    for key, value in data.items():
        if hasattr(value, "timestamp"):  # Firestore timestamp type
            data[key] = datetime.fromtimestamp(value.timestamp())
    return data

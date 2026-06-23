"""app/modules/example/repositories/example_repository.py — Data access layer.

Firestore adaptation of the blueprint's SQLAlchemy repository pattern:
  - `AsyncClient` replaces `AsyncSession`.
  - Firestore document IDs replace UUID primary keys (Firestore generates them).
  - No `flush()` / `commit()` — Firestore writes are atomic per operation.
  - `snapshot_to_dict()` injects the document ID as `id` in the returned dict.

Factory function `get_example_repository(db)` is the only public API,
consumed by dependency.py.
"""

from datetime import UTC, datetime

from google.cloud.firestore_v1.async_client import AsyncClient

from app.core.common.serializers import snapshot_to_dict

_COLLECTION = "examples"


class ExampleRepositoryImp:
    def __init__(self, *, db: AsyncClient) -> None:
        self._col = db.collection(_COLLECTION)

    async def get_by_id(self, example_id: str) -> dict | None:
        snapshot = await self._col.document(example_id).get()
        if not snapshot.exists:
            return None
        return snapshot_to_dict(snapshot)

    async def get_all(self) -> list[dict]:
        snapshots = self._col.stream()
        results = []
        async for snapshot in snapshots:
            results.append(snapshot_to_dict(snapshot))
        return results

    async def create(self, data: dict) -> dict:
        now = datetime.now(UTC)
        data["created_at"] = now
        data["updated_at"] = now
        # Firestore auto-generates the document ID
        _, doc_ref = await self._col.add(data)
        snapshot = await doc_ref.get()
        return snapshot_to_dict(snapshot)

    async def update(self, example_id: str, update_data: dict) -> dict | None:
        update_data["updated_at"] = datetime.now(UTC)
        doc_ref = self._col.document(example_id)
        await doc_ref.update(update_data)
        snapshot = await doc_ref.get()
        if not snapshot.exists:
            return None
        return snapshot_to_dict(snapshot)

    async def delete(self, example_id: str) -> bool:
        doc_ref = self._col.document(example_id)
        snapshot = await doc_ref.get()
        if not snapshot.exists:
            return False
        await doc_ref.delete()
        return True


# ── Factory — consumed by dependency.py ──────────────────────────────────────

async def get_example_repository(db: AsyncClient) -> ExampleRepositoryImp:
    return ExampleRepositoryImp(db=db)

"""app/modules/example/schemas/schemas.py — Input / output schemas.

Firestore adaptation:
  - Output schemas use `from_dict(data: dict)` instead of `from_entity(orm_obj)`
    because Firestore returns plain dicts, not ORM objects.
  - The Firestore document ID is injected as `id` by the repository layer.
"""

from datetime import datetime

from pydantic import BaseModel


# ── Input schema (request body) ───────────────────────────────────────────────

class ExampleCreateSchema(BaseModel):
    name: str
    description: str | None = None


class ExampleUpdateSchema(BaseModel):
    name: str | None = None
    description: str | None = None


# ── Output schema (response body) ─────────────────────────────────────────────

class ExampleOutputSchema(BaseModel):
    id: str
    name: str
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @staticmethod
    def from_dict(data: dict) -> "ExampleOutputSchema":
        """Convert a Firestore document dict (with injected `id`) to this schema.

        The repository is responsible for injecting `id` = snapshot.id
        before calling this method.
        """
        return ExampleOutputSchema(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

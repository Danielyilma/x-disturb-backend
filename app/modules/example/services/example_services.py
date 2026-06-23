"""app/modules/example/services/example_services.py — Business logic layer.

Rules (from blueprint):
  - Services are pure async functions, NOT classes.
  - All dependencies (repos, clients) are injected as arguments.
  - Services raise domain-specific exceptions, not HTTP exceptions.
  - Services call Schema.from_dict(data) to convert Firestore dicts to
    response schemas before returning.
"""

from app.modules.example.exceptions.exceptions import ExampleNotFoundError
from app.modules.example.repositories.example_repository import ExampleRepositoryImp
from app.modules.example.schemas.schemas import (
    ExampleCreateSchema,
    ExampleOutputSchema,
    ExampleUpdateSchema,
)


async def get_example(
    *,
    repo: ExampleRepositoryImp,
    example_id: str,
) -> ExampleOutputSchema:
    data = await repo.get_by_id(example_id)
    if data is None:
        raise ExampleNotFoundError()
    return ExampleOutputSchema.from_dict(data)


async def list_examples(
    *,
    repo: ExampleRepositoryImp,
) -> list[ExampleOutputSchema]:
    results = await repo.get_all()
    return [ExampleOutputSchema.from_dict(item) for item in results]


async def create_example(
    *,
    repo: ExampleRepositoryImp,
    schema: ExampleCreateSchema,
) -> ExampleOutputSchema:
    data = schema.model_dump(exclude_none=True)
    created = await repo.create(data)
    return ExampleOutputSchema.from_dict(created)


async def update_example(
    *,
    repo: ExampleRepositoryImp,
    example_id: str,
    schema: ExampleUpdateSchema,
) -> ExampleOutputSchema:
    update_data = schema.model_dump(exclude_none=True)
    updated = await repo.update(example_id, update_data)
    if updated is None:
        raise ExampleNotFoundError()
    return ExampleOutputSchema.from_dict(updated)


async def delete_example(
    *,
    repo: ExampleRepositoryImp,
    example_id: str,
) -> None:
    deleted = await repo.delete(example_id)
    if not deleted:
        raise ExampleNotFoundError()

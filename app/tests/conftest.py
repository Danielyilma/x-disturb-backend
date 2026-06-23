"""app/tests/conftest.py — Shared pytest fixtures.

Security note: test server MUST listen on 127.0.0.1 (localhost), never 0.0.0.0.
The AsyncClient is configured with base_url="http://127.0.0.1" to enforce this.

Fixtures:
  - app_instance: the FastAPI app with a mocked Firebase client
  - client: async HTTP test client (httpx.AsyncClient)
  - mock_firestore: MagicMock replacing the real Firestore AsyncClient
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import create_app


@pytest.fixture
def mock_firestore() -> MagicMock:
    """Return a MagicMock that stands in for the Firestore AsyncClient."""
    return MagicMock()


@pytest.fixture
def app_instance(mock_firestore: MagicMock):
    """FastAPI app with Firebase initialisation patched out."""
    with (
        patch("app.core.firebase._init_firebase", return_value=None),
        patch("app.core.firebase.firestore_async.client", return_value=mock_firestore),
        patch("app.core.firebase.storage.bucket", return_value=MagicMock()),
    ):
        return create_app()


@pytest.fixture
async def client(app_instance) -> AsyncGenerator[AsyncClient, None]:
    """Async test client bound to localhost (never 0.0.0.0)."""
    async with AsyncClient(
        transport=ASGITransport(app=app_instance),
        base_url="http://127.0.0.1",
    ) as ac:
        yield ac


# ── Example test (remove or move to a dedicated test file) ───────────────────

async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

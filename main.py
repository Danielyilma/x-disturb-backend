"""Entry point for the x-disturb backend.

Reads PORT from environment and starts the Uvicorn ASGI server.
Import `app` from app.main so the factory is only called once.
"""

import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # noqa: S104 — bind address controlled by infra/Docker
        port=port,
        reload=os.environ.get("ENVIRONMENT", "development") == "development",
    )

"""app/main.py — exposes the FastAPI `app` instance.

Called by the root main.py entrypoint and by uvicorn directly:
    uvicorn app.main:app
"""

from app.api import create_app

app = create_app()

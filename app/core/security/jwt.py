"""app/core/security/jwt.py — JWT token generation and decoding.

Security rules enforced:
  - Algorithm is hardcoded to the configured value — never derived from token.
  - 'none' algorithm is explicitly rejected.
  - 'exp' claim is always set and validated on decode.
  - JWT_SECRET is loaded from env. If absent in dev, an ephemeral random key
    is generated with a loud warning (NOT suitable for multi-instance deploy).
  - No hardcoded literal secrets anywhere.
"""

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi.security import OAuth2PasswordBearer

from app.config import MySettings
from app.core.security.auth_exceptions import AccessTokenExpiredError, InvalidTokenError

logger = logging.getLogger(__name__)

# OAuth2 scheme — tokenUrl matches the future user login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login")

# ── Secret resolution (env → ephemeral random) ────────────────────────────────
def _resolve_jwt_secret() -> str:
    if MySettings.JWT_SECRET:
        return MySettings.JWT_SECRET

    # TODO(security): JWT_SECRET env var is not set.
    # Generating an ephemeral secret — this instance will NOT share sessions
    # with other instances. Set JWT_SECRET in production.
    ephemeral = secrets.token_hex(32)
    logger.warning(
        "JWT_SECRET is not set. Using an ephemeral secret. "
        "Sessions will be invalidated on restart and are NOT shared across instances. "
        "Set JWT_SECRET env var for production deployments."
    )
    return ephemeral


_JWT_SECRET = _resolve_jwt_secret()
_ALGORITHM = MySettings.JWT_ALGORITHM


def generate_new_token(
    *,
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Generate a signed JWT with an expiry claim.

    Args:
        data: Payload claims to embed (e.g., {"sub": str(user_id)}).
        expires_delta: Token lifetime. Defaults to ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        Encoded JWT string.
    """
    if _ALGORITHM == "none":
        raise ValueError("JWT algorithm 'none' is not permitted.")

    payload = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=MySettings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload["exp"] = expire
    return jwt.encode(payload, _JWT_SECRET, algorithm=_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT.

    Raises:
        AccessTokenExpiredError: if the token is expired.
        InvalidTokenError: if the token is malformed or signature is invalid.
    """
    try:
        payload = jwt.decode(
            token,
            _JWT_SECRET,
            algorithms=[_ALGORITHM],  # hardcoded — never derived from token
            options={"require": ["exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AccessTokenExpiredError() from exc
    except jwt.PyJWTError as exc:
        raise InvalidTokenError() from exc
    return payload

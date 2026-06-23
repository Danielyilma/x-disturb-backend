"""app/core/security/password.py — Password hashing and verification using bcrypt.

TODO(security): Consider migrating to Argon2 (memory-hard) for stronger
protection against GPU-based attacks.
"""

import bcrypt


def hash_password(plain: str) -> str:
    """Hash a plain-text password with bcrypt (includes unique salt per call)."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if `plain` matches the bcrypt `hashed` password."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

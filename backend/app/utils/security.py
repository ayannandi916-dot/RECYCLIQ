from pwdlib import PasswordHash

import os
from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError

from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None
) -> str:
    """
    Generate a signed JWT access token.
    """
    secret_key = os.getenv("JWT_SECRET_KEY")
    algorithm = os.getenv("JWT_ALGORITHM", "HS256")

    if not secret_key:
        raise RuntimeError("JWT_SECRET_KEY is not configured!")

    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=30)
    )

    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        secret_key,
        algorithm=algorithm
    )


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.
    Raises InvalidTokenError if the token is invalid or expired.
    """
    secret_key = os.getenv("JWT_SECRET_KEY")
    algorithm = os.getenv("JWT_ALGORITHM", "HS256")

    if not secret_key:
        raise RuntimeError("JWT_SECRET_KEY is not configured!")

    return jwt.decode(
        token,
        secret_key,
        algorithms=[algorithm]
    )

# Initialise Argon2 password hashing
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """
    Convert a plain-text password into a secure hash.
    """
    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    """
    Verify whether the provided password matches the stored hash.
    """
    return password_hash.verify(plain_password, hashed_password)
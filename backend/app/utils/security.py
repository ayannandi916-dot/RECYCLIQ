import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from dotenv import load_dotenv
from pwdlib import PasswordHash
from jwt.exceptions import InvalidTokenError


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

# JWT configuration
DEFAULT_JWT_ISSUER = "recycliq-api"
DEFAULT_JWT_AUDIENCE = "recycliq-client"
DEFAULT_JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Initialise Argon2 password hashing
password_hash = PasswordHash.recommended()


def get_jwt_config():
    """
    Load and validate JWT configuration.
    """

    secret_key = os.getenv("JWT_SECRET_KEY")
    algorithm = os.getenv(
        "JWT_ALGORITHM",
        DEFAULT_JWT_ALGORITHM
    )

    issuer = os.getenv(
        "JWT_ISSUER",
        DEFAULT_JWT_ISSUER
    )

    audience = os.getenv(
        "JWT_AUDIENCE",
        DEFAULT_JWT_AUDIENCE
    )

    if not secret_key:
        raise RuntimeError("JWT_SECRET_KEY is not configured!")

    if algorithm != "HS256":
        raise RuntimeError("Unsupported JWT algorithm!")

    if not issuer or not audience:
        raise RuntimeError("JWT issuer or audience is not configured!")

    return secret_key, algorithm, issuer, audience


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None
) -> str:
    """
    Generate a signed JWT access token.
    """

    secret_key, algorithm, issuer, audience = get_jwt_config()

    to_encode = data.copy()

    now = datetime.now(timezone.utc)

    expire = now + (
        expires_delta
        or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    # Add protected JWT claims
    to_encode.update({
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": expire,
        "token_type": "access"
    })

    return jwt.encode(
        to_encode,
        secret_key,
        algorithm=algorithm
    )


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.
    """

    secret_key, algorithm, issuer, audience = get_jwt_config()

    payload = jwt.decode(
        token,
        secret_key,
        algorithms=[algorithm],
        issuer=issuer,
        audience=audience,
        options={
            "require": [
                "sub",
                "exp",
                "iat",
                "iss",
                "aud",
                "token_type"
            ]
        }
    )

    if payload.get("token_type") != "access":
        raise InvalidTokenError("Invalid token type")

    return payload


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

    return password_hash.verify(
        plain_password,
        hashed_password
    )
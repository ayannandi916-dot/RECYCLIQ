
from datetime import datetime, timedelta, timezone
from app.core.config import settings

import jwt

from pwdlib import PasswordHash
from jwt.exceptions import InvalidTokenError



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

    if not settings.jwt_secret_key:
        raise RuntimeError("JWT_SECRET_KEY is not configured!")

    if settings.jwt_algorithm != "HS256":
        raise RuntimeError("Unsupported JWT algorithm!")

    if not settings.jwt_issuer or not settings.jwt_audience:
        raise RuntimeError("JWT issuer or audience is not configured!")

    return (
        settings.jwt_secret_key,
        settings.jwt_algorithm,
        settings.jwt_issuer,
        settings.jwt_audience
    )


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None
) -> str:

    secret_key, algorithm, issuer, audience = get_jwt_config()

    to_encode = data.copy()

    now = datetime.now(timezone.utc)

    expire = now + (
        expires_delta or timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )
    )

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
    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:

    return password_hash.verify(
        plain_password,
        hashed_password
    )
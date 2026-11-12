from datetime import timedelta

import pytest
import jwt

from jwt.exceptions import InvalidTokenError

from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token
)


TEST_SECRET = "test-secret-key-for-recycliq-automated-tests"


@pytest.fixture(autouse=True)
def configure_test_jwt(monkeypatch):
    """Configure an isolated JWT secret for testing."""

    monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")


# 1. Password hashing
def test_password_hashing():
    password = "RecycliqTest@123"

    hashed = hash_password(password)

    assert hashed != password
    assert isinstance(hashed, str)


# 2. Correct password verification
def test_correct_password_verification():
    password = "RecycliqTest@123"

    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


# 3. Incorrect password verification
def test_incorrect_password_verification():
    hashed = hash_password("CorrectPassword@123")

    assert verify_password(
        "WrongPassword@123",
        hashed
    ) is False


# 4. JWT token creation and decoding
def test_jwt_token_creation_and_decoding():
    payload = {
        "sub": "test-user-123",
        "role": "user"
    }

    token = create_access_token(payload)

    decoded = decode_access_token(token)

    assert decoded["sub"] == "test-user-123"
    assert decoded["role"] == "user"
    assert "exp" in decoded


# 5. Custom token expiration
def test_custom_token_expiration():
    payload = {"sub": "test-user-123"}

    token = create_access_token(
        payload,
        expires_delta=timedelta(minutes=10)
    )

    decoded = decode_access_token(token)

    assert "exp" in decoded


# 6. Expired JWT rejection
def test_expired_token_rejection():
    token = create_access_token(
        {"sub": "test-user-123"},
        expires_delta=timedelta(seconds=-1)
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


# 7. Invalid JWT rejection
def test_invalid_token_rejection():
    with pytest.raises(InvalidTokenError):
        decode_access_token("invalid.token.value")


# 8. Missing JWT secret during token creation
def test_missing_secret_during_creation(monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY")

    with pytest.raises(RuntimeError):
        create_access_token({"sub": "test-user-123"})


# 9. Missing JWT secret during token decoding
def test_missing_secret_during_decoding(monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY")

    with pytest.raises(RuntimeError):
        decode_access_token("invalid.token.value")

# 10. Required JWT claims
def test_jwt_contains_required_claims():

    token = create_access_token({
        "sub": "test-user-123",
        "role": "user"
    })

    decoded = decode_access_token(token)

    assert decoded["iss"] == "recycliq-api"
    assert decoded["aud"] == "recycliq-client"
    assert decoded["token_type"] == "access"
    assert "iat" in decoded
    assert "exp" in decoded


# 11. Wrong issuer rejection
def test_wrong_issuer_rejected():

    token = jwt.encode(
        {
            "sub": "test-user-123",
            "iss": "wrong-issuer",
            "aud": "recycliq-client",
            "iat": 2000000000,
            "exp": 2100000000,
            "token_type": "access"
        },
        TEST_SECRET,
        algorithm="HS256"
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


# 12. Wrong audience rejection
def test_wrong_audience_rejected():

    token = jwt.encode(
        {
            "sub": "test-user-123",
            "iss": "recycliq-api",
            "aud": "wrong-audience",
            "iat": 2000000000,
            "exp": 2100000000,
            "token_type": "access"
        },
        TEST_SECRET,
        algorithm="HS256"
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


# 13. Invalid token type rejection
def test_invalid_token_type_rejected():

    token = jwt.encode(
        {
            "sub": "test-user-123",
            "iss": "recycliq-api",
            "aud": "recycliq-client",
            "iat": 2000000000,
            "exp": 2100000000,
            "token_type": "refresh"
        },
        TEST_SECRET,
        algorithm="HS256"
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


# 14. Missing required claim rejection
def test_missing_issuer_rejected():

    token = jwt.encode(
        {
            "sub": "test-user-123",
            "aud": "recycliq-client",
            "iat": 2000000000,
            "exp": 2100000000,
            "token_type": "access"
        },
        TEST_SECRET,
        algorithm="HS256"
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


# 15. Unsupported algorithm rejected
def test_unsupported_jwt_algorithm_rejected(monkeypatch):

    monkeypatch.setenv("JWT_ALGORITHM", "none")

    with pytest.raises(RuntimeError):
        create_access_token({
            "sub": "test-user-123"
        })
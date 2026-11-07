from sqlalchemy.orm import Session

from app.models import User
from app.schemas.auth import UserRegister, UserLogin
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token
)


def register_user(db: Session, user_data: UserRegister) -> User:
    """
    Register a new user.
    """

    # Check whether email already exists
    existing_user = db.query(User).filter(
        User.email == user_data.email
    ).first()

    if existing_user:
        raise ValueError("Email is already registered!")

    # Hash the password
    hashed_password = hash_password(user_data.password)

    # Create user object
    new_user = User(
        name=user_data.name,
        email=user_data.email,
        password_hash=hashed_password,
        role="user"
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


def login_user(db: Session, user_data: UserLogin) -> str:
    """
    Authenticate user and return JWT access token.
    """

    user = db.query(User).filter(
        User.email == user_data.email
    ).first()

    if not user:
        raise ValueError("Invalid email or password!")

    if not verify_password(
        user_data.password,
        user.password_hash
    ):
        raise ValueError("Invalid email or password!")

    # Generate JWT
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "role": user.role
        }
    )

    return access_token
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    UserResponse,
    TokenResponse
)
from app.services.auth_service import (
    register_user,
    login_user
)

from app.api.dependencies import get_current_user
from app.models import User




router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    try:
        user = register_user(db, user_data)

        return UserResponse(
            id=str(user.id),
            name=user.name,
            email=user.email,
            role=user.role
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error)
        )


@router.post(
    "/login",
    response_model=TokenResponse
)
def login(
    user_data: UserLogin,
    db: Session = Depends(get_db)
):
    try:
        access_token = login_user(db, user_data)

        return TokenResponse(
            access_token=access_token
        )

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password!"
        )

@router.get(
    "/me",
    response_model=UserResponse
)
def get_me(
    current_user: User = Depends(get_current_user)
):
    """
    Return the currently authenticated user's information.
    """

    return UserResponse(
        id=str(current_user.id),
        name=current_user.name,
        email=current_user.email,
        role=current_user.role
    )
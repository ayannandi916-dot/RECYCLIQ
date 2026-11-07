from fastapi import Depends, HTTPException, status
from typing import Callable

from app.models import User
from app.api.dependencies import get_current_user


def require_role(*allowed_roles: str) -> Callable:

    def role_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:

        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this resource."
            )

        return current_user

    return role_checker
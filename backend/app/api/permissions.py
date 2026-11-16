from typing import Callable

from fastapi import Depends, HTTPException, status

from app.models import User
from app.api.dependencies import get_current_user


VALID_ROLES = frozenset({"user", "recycler", "admin"})


def require_role(*allowed_roles: str) -> Callable:
    if not allowed_roles:
        raise ValueError("At least one allowed role must be specified.")

    invalid_roles = set(allowed_roles) - VALID_ROLES

    if invalid_roles:
        raise ValueError(
            f"Invalid role configuration: {', '.join(sorted(invalid_roles))}"
        )

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
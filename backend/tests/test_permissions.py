import pytest

from fastapi import HTTPException

from app.api.permissions import require_role


class MockUser:
    def __init__(self, role):
        self.role = role


# 1. Normal user allowed
def test_user_role_allowed():

    checker = require_role("user")

    user = MockUser("user")

    assert checker(user) is user


# 2. Recycler allowed
def test_recycler_role_allowed():

    checker = require_role("recycler")

    user = MockUser("recycler")

    assert checker(user) is user


# 3. Admin allowed
def test_admin_role_allowed():

    checker = require_role("admin")

    user = MockUser("admin")

    assert checker(user) is user


# 4. User cannot access admin-only resource
def test_user_denied_admin_access():

    checker = require_role("admin")

    user = MockUser("user")

    with pytest.raises(HTTPException) as exc:

        checker(user)

    assert exc.value.status_code == 403


# 5. Recycler cannot access admin-only resource
def test_recycler_denied_admin_access():

    checker = require_role("admin")

    user = MockUser("recycler")

    with pytest.raises(HTTPException) as exc:

        checker(user)

    assert exc.value.status_code == 403


# 6. Multiple roles allowed
def test_multiple_allowed_roles():

    checker = require_role("admin", "recycler")

    admin = MockUser("admin")
    recycler = MockUser("recycler")

    assert checker(admin) is admin
    assert checker(recycler) is recycler


# 7. Unrecognized role denied
def test_unrecognized_role_denied():

    checker = require_role("admin", "recycler")

    user = MockUser("guest")

    with pytest.raises(HTTPException) as exc:

        checker(user)

    assert exc.value.status_code == 403


# 8. No roles allowed
def test_no_roles_allowed():

    checker = require_role()

    user = MockUser("admin")

    with pytest.raises(HTTPException) as exc:

        checker(user)

    assert exc.value.status_code == 403


# 9. Returned user remains unchanged
def test_user_object_remains_unchanged():

    checker = require_role("user")

    user = MockUser("user")

    result = checker(user)

    assert result is user
    assert result.role == "user"
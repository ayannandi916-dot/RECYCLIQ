from uuid import uuid4

import pytest
from fastapi import status

from app.main import app
from app.models.user import User
from app.utils.security import hash_password, create_access_token
import re


def normalize_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)

def create_test_user(db_session, role="user"):
    user = User(
        name="Admin API Integration User",
        email=f"{uuid4()}@example.com",
        password_hash=hash_password("TestPassword123!"),
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def auth_headers(user):
    token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
    })
    return {"Authorization": f"Bearer {token}"}


ADMIN_READ_ENDPOINTS = [
    ("/admin/users", {}),
    ("/admin/centres", {}),
    ("/admin/analytics/overview", {}),
    ("/admin/analytics/scans", {}),
    ("/admin/analytics/recyclers", {}),
    ("/admin/analytics/centres", {}),
    ("/admin/analytics/objects", {}),
    ("/admin/analytics/activity", {}),
    ("/admin/audit-logs", {}),
    ("/admin/recycler/applications", {}),
]

ADMIN_RESOURCE_READ_ENDPOINTS = [
    "/admin/users/{resource_id}",
    "/admin/centres/{resource_id}",
]

ADMIN_MUTATION_ENDPOINTS = [
    ("PATCH", "/admin/users/{resource_id}/activate"),
    ("PATCH", "/admin/users/{resource_id}/deactivate"),
    ("PATCH", "/admin/centres/{resource_id}/activate"),
    ("PATCH", "/admin/centres/{resource_id}/deactivate"),
    ("POST", "/admin/recycler/applications/{resource_id}/approve"),
    ("POST", "/admin/recycler/applications/{resource_id}/reject"),
]

def test_all_admin_routers_are_registered():
    openapi_paths = app.openapi()["paths"]

    registered = {
        (method.upper(), normalize_path(path))
        for path, operations in openapi_paths.items()
        for method in operations
    }

    expected_routes = {
        ("GET", "/admin/users"),
        ("GET", "/admin/users/{user_id}"),
        ("PATCH", "/admin/users/{user_id}/activate"),
        ("PATCH", "/admin/users/{user_id}/deactivate"),
        ("GET", "/admin/centres"),
        ("GET", "/admin/centres/{centre_id}"),
        ("PATCH", "/admin/centres/{centre_id}/activate"),
        ("PATCH", "/admin/centres/{centre_id}/deactivate"),
        ("GET", "/admin/analytics/overview"),
        ("GET", "/admin/analytics/scans"),
        ("GET", "/admin/analytics/recyclers"),
        ("GET", "/admin/analytics/centres"),
        ("GET", "/admin/analytics/objects"),
        ("GET", "/admin/analytics/activity"),
        ("GET", "/admin/audit-logs"),
        ("GET", "/admin/recycler/applications"),
        ("POST", "/admin/recycler/applications/{application_id}/approve"),
        ("POST", "/admin/recycler/applications/{application_id}/reject"),
    }

    expected = {
        (method, normalize_path(path))
        for method, path in expected_routes
    }

    missing = expected - registered

    assert not missing, f"Missing admin routes: {missing}"

@pytest.mark.parametrize(
    ("path", "params"),
    ADMIN_READ_ENDPOINTS,
)
def test_admin_read_endpoints_are_accessible_to_admin(
    api_client,
    db_session,
    path,
    params,
):
    admin = create_test_user(db_session, role="admin")

    response = api_client.get(
        path,
        params=params,
        headers=auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK, (
        f"{path} returned {response.status_code}: {response.text}"
    )


@pytest.mark.parametrize(
    ("path", "params"),
    ADMIN_READ_ENDPOINTS,
)
@pytest.mark.parametrize("role", ["user", "recycler"])
def test_admin_read_endpoints_reject_non_admin_roles(
    api_client,
    db_session,
    path,
    params,
    role,
):
    account = create_test_user(db_session, role=role)

    response = api_client.get(
        path,
        params=params,
        headers=auth_headers(account),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN, (
        f"{role} accessed {path}: {response.status_code}"
    )


@pytest.mark.parametrize(
    ("path", "params"),
    ADMIN_READ_ENDPOINTS,
)
def test_admin_read_endpoints_reject_unauthenticated_requests(
    api_client,
    path,
    params,
):
    response = api_client.get(path, params=params)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize(
    "path_template",
    ADMIN_RESOURCE_READ_ENDPOINTS,
)
def test_admin_resource_routes_enforce_role_before_resource_lookup(
    api_client,
    db_session,
    path_template,
):
    user = create_test_user(db_session, role="user")
    path = path_template.format(resource_id=uuid4())

    response = api_client.get(path, headers=auth_headers(user))

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize(
    ("method", "path_template"),
    ADMIN_MUTATION_ENDPOINTS,
)
@pytest.mark.parametrize("role", ["user", "recycler"])
def test_admin_mutation_routes_reject_non_admin_roles(
    api_client,
    db_session,
    method,
    path_template,
    role,
):
    account = create_test_user(db_session, role=role)
    path = path_template.format(resource_id=uuid4())

    response = api_client.request(
        method,
        path,
        headers=auth_headers(account),
        json={"reason": "Integration test rejection"}
        if path.endswith("/reject")
        else None,
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize(
    ("method", "path_template"),
    ADMIN_MUTATION_ENDPOINTS,
)
def test_admin_mutation_routes_reach_resource_lookup(
    api_client,
    db_session,
    method,
    path_template,
):
    admin = create_test_user(db_session, role="admin")
    path = path_template.format(resource_id=uuid4())

    response = api_client.request(
        method,
        path,
        headers=auth_headers(admin),
        json={"reason": "Integration test rejection"}
        if path.endswith("/reject")
        else None,
    )

    # A 404 confirms the authenticated admin passed authorization and
    # reached the resource lookup for this deliberately unknown UUID.
    assert response.status_code == status.HTTP_404_NOT_FOUND

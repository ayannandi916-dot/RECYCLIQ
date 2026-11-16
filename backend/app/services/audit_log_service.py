import math
import re
import uuid
from datetime import datetime, date
from decimal import Decimal
from enum import Enum

from sqlalchemy.orm import Session

from app.models import User
from app.models.audit_log import AuditLog


# Sensitive field-name markers.
SENSITIVE_FIELD_MARKERS = {
    "password",
    "token",
    "secret",
    "apikey",
    "authorization",
    "authorisation",
    "otp",
    "credential",
    "privatekey",
    "cookie",
    "sessionid",
}


def _is_sensitive_field(key: str) -> bool:
    """
    Normalize field names and detect sensitive information.

    Handles snake_case, camelCase, hyphens and spaces.
    Preserves plural container names such as 'tokens'.
    """
    normalized = re.sub(
        r"[^a-z0-9]",
        "",
        str(key).casefold(),
    )

    for marker in SENSITIVE_FIELD_MARKERS:
        if marker == "token":
            if normalized == "token" or normalized.endswith("token"):
                return True
        elif marker in normalized:
            return True

    return False


def _make_json_safe(value):
    """
    Convert values into JSON-serializable representations.

    Sensitive fields are excluded recursively.
    """

    if isinstance(value, dict):
        return {
            str(key): _make_json_safe(item)
            for key, item in value.items()
            if not _is_sensitive_field(str(key))
        }

    if isinstance(value, (list, tuple)):
        return [_make_json_safe(item) for item in value]

    if isinstance(value, Enum):
        return _make_json_safe(value.value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, uuid.UUID):
        return str(value)

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if value is None or isinstance(value, (str, int, bool)):
        return value

    return str(value)


def log_admin_action(
    db: Session,
    admin: User,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID | None = None,
    old_values: dict | None = None,
    new_values: dict | None = None,
) -> AuditLog:
    """
    Add an administrative action to the audit log.

    This function does not commit the transaction.

    The calling service must commit the business operation
    and audit record together.
    """

    if admin.role != "admin":
        raise ValueError(
            "Only administrators can create admin audit logs."
        )

    if not action or len(action) > 50:
        raise ValueError("Invalid audit action.")

    if not resource_type or len(resource_type) > 50:
        raise ValueError("Invalid audit resource type.")

    if old_values is not None and not isinstance(old_values, dict):
        raise ValueError("old_values must be a dictionary.")

    if new_values is not None and not isinstance(new_values, dict):
        raise ValueError("new_values must be a dictionary.")

    audit_log = AuditLog(
        admin_id=admin.id,
        admin_email=admin.email,
        action=action.upper(),
        resource_type=resource_type.upper(),
        resource_id=resource_id,
        old_values=(
            _make_json_safe(old_values)
            if old_values is not None
            else None
        ),
        new_values=(
            _make_json_safe(new_values)
            if new_values is not None
            else None
        ),
    )

    db.add(audit_log)

    return audit_log
"""add user active status

Revision ID: 2d07cb0065a8
Revises: e390ea1639f4
Create Date: 2026-11-13 11:14:29.602258

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2d07cb0065a8'
down_revision: Union[str, Sequence[str], None] = 'e390ea1639f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    op.alter_column(
        "users",
        "is_active",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("users", "is_active")
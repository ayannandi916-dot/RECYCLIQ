"""add recycler ownership to recycling centres

Revision ID: dd8103025a09
Revises: e76e65a05ec5
Create Date: 2026-11-12 20:02:26.397797

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'dd8103025a09'
down_revision: Union[str, Sequence[str], None] = 'e76e65a05ec5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.add_column(
        'recycling_centres',
        sa.Column(
            'owner_id',
            sa.UUID(),
            nullable=True
        )
    )

    op.create_index(
        'ix_recycling_centres_owner_id',
        'recycling_centres',
        ['owner_id'],
        unique=False
    )

    op.create_foreign_key(
        'fk_recycling_centres_owner_id_users',
        'recycling_centres',
        'users',
        ['owner_id'],
        ['id'],
        ondelete='RESTRICT'
    )


def downgrade() -> None:

    op.drop_constraint(
        'fk_recycling_centres_owner_id_users',
        'recycling_centres',
        type_='foreignkey'
    )

    op.drop_index(
        'ix_recycling_centres_owner_id',
        table_name='recycling_centres'
    )

    op.drop_column(
        'recycling_centres',
        'owner_id'
    )
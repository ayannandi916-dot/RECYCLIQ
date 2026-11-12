"""add recycler applications

Revision ID: e390ea1639f4
Revises: dd8103025a09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e390ea1639f4'
down_revision: Union[str, Sequence[str], None] = 'dd8103025a09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'recycler_applications',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('business_name', sa.String(length=150), nullable=False),
        sa.Column('contact_number', sa.String(length=20), nullable=False),
        sa.Column('business_address', sa.Text(), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('state', sa.String(length=100), nullable=False),
        sa.Column('postal_code', sa.String(length=20), nullable=True),
        sa.Column('registration_number', sa.String(length=100), nullable=True),
        sa.Column('website', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('reviewed_by', sa.UUID(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name='ck_recycler_applications_status'
        ),
        sa.ForeignKeyConstraint(
            ['reviewed_by'],
            ['users.id'],
            ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['users.id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'user_id',
            name='uq_recycler_applications_user_id'
        )
    )


def downgrade() -> None:
    op.drop_table('recycler_applications')
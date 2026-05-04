"""fix uid sequence sync

Revision ID: c3d4e5f6a789
Revises: b2c3d4e5f678
Create Date: 2026-05-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c3d4e5f6a789'
down_revision: Union[str, None] = 'b2c3d4e5f678'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        SELECT setval('user_uid_seq', GREATEST((SELECT COALESCE(MAX(uid), 1000) FROM users), 1000))
    """)


def downgrade() -> None:
    pass

"""add uid to users

Revision ID: b2c3d4e5f678
Revises: 4a99fc87d523
Create Date: 2026-04-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f678'
down_revision: Union[str, None] = '4a99fc87d523'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('uid', sa.Integer(), nullable=True))
    op.execute("CREATE SEQUENCE IF NOT EXISTS user_uid_seq MINVALUE 1001 START WITH 1001")
    op.execute("UPDATE users SET uid = nextval('user_uid_seq') WHERE uid IS NULL")
    op.execute("ALTER TABLE users ALTER COLUMN uid SET DEFAULT nextval('user_uid_seq')")
    op.execute("ALTER TABLE users ALTER COLUMN uid SET NOT NULL")
    op.create_unique_constraint('uq_users_uid', 'users', ['uid'])


def downgrade() -> None:
    op.drop_constraint('uq_users_uid', 'users', type_='unique')
    op.drop_column('users', 'uid')
    op.execute("DROP SEQUENCE IF EXISTS user_uid_seq")

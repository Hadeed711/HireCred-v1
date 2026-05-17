"""add image_path and is_deleted to messages

Revision ID: e5f6a7b8c901
Revises: d4e5f6a7b890
Create Date: 2026-05-10 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6a7b8c901'
down_revision: Union[str, None] = 'd4e5f6a7b890'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('image_path', sa.String(length=500), nullable=True))
    op.add_column('messages', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('messages', 'is_deleted')
    op.drop_column('messages', 'image_path')

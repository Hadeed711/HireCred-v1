"""add cv fields to profiles

Revision ID: d4e5f6a7b890
Revises: c3d4e5f6a789
Create Date: 2026-05-09 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'd4e5f6a7b890'
down_revision: Union[str, None] = 'c3d4e5f6a789'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('profiles', sa.Column('cv_file_path', sa.String(length=500), nullable=True))
    op.add_column('profiles', sa.Column('cv_analysis', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('profiles', 'cv_analysis')
    op.drop_column('profiles', 'cv_file_path')

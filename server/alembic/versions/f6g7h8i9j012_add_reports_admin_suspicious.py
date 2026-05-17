"""add account_reports, is_admin, is_suspicious, cv_match, url_warnings

Revision ID: f6g7h8i9j012
Revises: e5f6a7b8c901
Create Date: 2026-05-14 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f6g7h8i9j012'
down_revision: Union[str, None] = 'e5f6a7b8c901'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users: is_admin ───────────────────────────────────────────────────────
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'))

    # ── credibility_scores: authenticity + CV match + URL warnings ────────────
    op.add_column('credibility_scores', sa.Column('is_suspicious', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('credibility_scores', sa.Column('authenticity_flags', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='[]'))
    op.add_column('credibility_scores', sa.Column('cv_match_score', sa.Integer(), nullable=True))
    op.add_column('credibility_scores', sa.Column('cv_match_warnings', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='[]'))
    op.add_column('credibility_scores', sa.Column('url_warnings', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='[]'))

    # ── account_reports table ─────────────────────────────────────────────────
    op.create_table(
        'account_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('reporter_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('reported_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('reason', sa.String(length=50), nullable=False),
        sa.Column('evidence_text', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('admin_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_account_reports_reported_user_id', 'account_reports', ['reported_user_id'])
    op.create_index('ix_account_reports_status', 'account_reports', ['status'])


def downgrade() -> None:
    op.drop_index('ix_account_reports_status', table_name='account_reports')
    op.drop_index('ix_account_reports_reported_user_id', table_name='account_reports')
    op.drop_table('account_reports')
    op.drop_column('credibility_scores', 'url_warnings')
    op.drop_column('credibility_scores', 'cv_match_warnings')
    op.drop_column('credibility_scores', 'cv_match_score')
    op.drop_column('credibility_scores', 'authenticity_flags')
    op.drop_column('credibility_scores', 'is_suspicious')
    op.drop_column('users', 'is_admin')

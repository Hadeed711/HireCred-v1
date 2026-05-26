"""add missing indexes for FKs and query-critical columns

Revision ID: a1b2c3d4e5f6
Revises: f6g7h8i9j012
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f6g7h8i9j012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # appreciations — critical for leaderboard aggregation and search ranking
    op.create_index('ix_appreciations_to_user_id', 'appreciations', ['to_user_id'])
    op.create_index('ix_appreciations_from_user_id', 'appreciations', ['from_user_id'])

    # credibility_scores — needed for leaderboard ORDER BY score and admin suspicious queries
    op.create_index('ix_credibility_scores_score', 'credibility_scores', ['score'])
    op.create_index('ix_credibility_scores_is_suspicious', 'credibility_scores', ['is_suspicious'])

    # proof_signals — needed for scoring pipeline (loads all signals per profile)
    op.create_index('ix_proof_signals_profile_id', 'proof_signals', ['profile_id'])

    # messages — needed for inbox sender/receiver queries and unread counts
    op.create_index('ix_messages_sender_id', 'messages', ['sender_id'])
    op.create_index('ix_messages_receiver_id', 'messages', ['receiver_id'])
    op.create_index('ix_messages_is_read', 'messages', ['is_read'])

    # account_reports — needed for admin queries
    op.create_index('ix_account_reports_reporter_id', 'account_reports', ['reporter_id'])
    op.create_index('ix_account_reports_created_at', 'account_reports', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_account_reports_created_at', table_name='account_reports')
    op.drop_index('ix_account_reports_reporter_id', table_name='account_reports')
    op.drop_index('ix_messages_is_read', table_name='messages')
    op.drop_index('ix_messages_receiver_id', table_name='messages')
    op.drop_index('ix_messages_sender_id', table_name='messages')
    op.drop_index('ix_proof_signals_profile_id', table_name='proof_signals')
    op.drop_index('ix_credibility_scores_is_suspicious', table_name='credibility_scores')
    op.drop_index('ix_credibility_scores_score', table_name='credibility_scores')
    op.drop_index('ix_appreciations_from_user_id', table_name='appreciations')
    op.drop_index('ix_appreciations_to_user_id', table_name='appreciations')

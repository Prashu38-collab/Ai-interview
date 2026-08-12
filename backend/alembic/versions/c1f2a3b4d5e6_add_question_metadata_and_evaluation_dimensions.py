"""add question metadata and evaluation dimensions

Revision ID: c1f2a3b4d5e6
Revises: 49a7fb55da73
Create Date: 2026-08-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1f2a3b4d5e6'
down_revision: Union[str, Sequence[str], None] = '49a7fb55da73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- questions: rich metadata + follow-up link -------------------------
    op.add_column('questions', sa.Column('concept', sa.String(length=120), nullable=True))
    op.add_column('questions', sa.Column('intent', sa.String(length=40), nullable=True))
    op.add_column('questions', sa.Column('core_requirements', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column('questions', sa.Column('optional_depth_points', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column('questions', sa.Column('common_misconceptions', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column('questions', sa.Column('follow_up_of', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_questions_follow_up_of', 'questions', 'questions', ['follow_up_of'], ['id'], ondelete='SET NULL')
    op.create_index('ix_questions_follow_up_of', 'questions', ['follow_up_of'])

    # --- evaluations: structured dimensions + observability ---------------
    op.add_column('evaluations', sa.Column('answer_status', sa.String(length=30), nullable=False, server_default='on_topic'))
    op.add_column('evaluations', sa.Column('relevance_score', sa.Float(), nullable=False, server_default='0'))
    op.add_column('evaluations', sa.Column('understanding_score', sa.Float(), nullable=False, server_default='0'))
    op.add_column('evaluations', sa.Column('correctness_score', sa.Float(), nullable=False, server_default='0'))
    op.add_column('evaluations', sa.Column('completeness_score', sa.Float(), nullable=False, server_default='0'))
    op.add_column('evaluations', sa.Column('reasoning_score', sa.Float(), nullable=False, server_default='0'))
    op.add_column('evaluations', sa.Column('satisfied_requirements', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column('evaluations', sa.Column('partial_requirements', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column('evaluations', sa.Column('missing_requirements', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column('evaluations', sa.Column('technical_errors', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column('evaluations', sa.Column('misconceptions', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column('evaluations', sa.Column('contradictions', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column('evaluations', sa.Column('recommended_topics', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column('evaluations', sa.Column('follow_up_question', sa.Text(), nullable=False, server_default=''))
    op.add_column('evaluations', sa.Column('follow_up_concept', sa.String(length=120), nullable=False, server_default=''))
    op.add_column('evaluations', sa.Column('confidence', sa.Float(), nullable=False, server_default='0.5'))
    op.add_column('evaluations', sa.Column('evaluator_version', sa.String(length=40), nullable=False, server_default=''))
    op.add_column('evaluations', sa.Column('prompt_version', sa.String(length=40), nullable=False, server_default=''))
    op.add_column('evaluations', sa.Column('model_version', sa.String(length=120), nullable=False, server_default=''))
    op.add_column('evaluations', sa.Column('evaluation_latency_ms', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_questions_follow_up_of', table_name='questions')
    op.drop_constraint('fk_questions_follow_up_of', 'questions', type_='foreignkey')
    op.drop_column('questions', 'follow_up_of')
    op.drop_column('questions', 'common_misconceptions')
    op.drop_column('questions', 'optional_depth_points')
    op.drop_column('questions', 'core_requirements')
    op.drop_column('questions', 'intent')
    op.drop_column('questions', 'concept')

    op.drop_column('evaluations', 'evaluation_latency_ms')
    op.drop_column('evaluations', 'model_version')
    op.drop_column('evaluations', 'prompt_version')
    op.drop_column('evaluations', 'evaluator_version')
    op.drop_column('evaluations', 'confidence')
    op.drop_column('evaluations', 'follow_up_concept')
    op.drop_column('evaluations', 'follow_up_question')
    op.drop_column('evaluations', 'recommended_topics')
    op.drop_column('evaluations', 'contradictions')
    op.drop_column('evaluations', 'misconceptions')
    op.drop_column('evaluations', 'technical_errors')
    op.drop_column('evaluations', 'missing_requirements')
    op.drop_column('evaluations', 'partial_requirements')
    op.drop_column('evaluations', 'satisfied_requirements')
    op.drop_column('evaluations', 'reasoning_score')
    op.drop_column('evaluations', 'completeness_score')
    op.drop_column('evaluations', 'correctness_score')
    op.drop_column('evaluations', 'understanding_score')
    op.drop_column('evaluations', 'relevance_score')
    op.drop_column('evaluations', 'answer_status')

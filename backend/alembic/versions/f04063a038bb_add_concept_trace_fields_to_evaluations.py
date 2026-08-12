"""add mentioned/demonstrated concept fields to evaluations

Revision ID: f04063a038bb
Revises: f04063a037ca
Create Date: 2026-08-12 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f04063a038bb'
down_revision: Union[str, Sequence[str], None] = 'f04063a037ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('evaluations', sa.Column('mentioned_concepts', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column('evaluations', sa.Column('demonstrated_concepts', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('evaluations', 'demonstrated_concepts')
    op.drop_column('evaluations', 'mentioned_concepts')

"""widen question intent column

Revision ID: f04063a037ca
Revises: c1f2a3b4d5e6
Create Date: 2026-08-11 21:27:56.272820

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f04063a037ca'
down_revision: Union[str, Sequence[str], None] = 'c1f2a3b4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Widen the intent column so planner intents (up to ~53 chars) fit."""
    op.alter_column("questions", "intent", type_=sa.String(255), existing_type=sa.String(40), nullable=True)


def downgrade() -> None:
    """Restore the original 40-char intent column."""
    op.alter_column("questions", "intent", type_=sa.String(40), existing_type=sa.String(255), nullable=True)

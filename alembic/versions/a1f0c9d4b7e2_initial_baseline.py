"""initial baseline (no tables yet)

Revision ID: a1f0c9d4b7e2
Revises:
Create Date: 2026-07-07

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "a1f0c9d4b7e2"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Baseline revision: creates nothing. Future phases add tables on top of this.
    pass


def downgrade() -> None:
    pass

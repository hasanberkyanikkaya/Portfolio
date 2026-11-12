"""add positions and realized_trades tables

Revision ID: c4d8e2f7a913
Revises: a1f0c9d4b7e2
Create Date: 2026-07-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d8e2f7a913"
down_revision: Union[str, None] = "a1f0c9d4b7e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=16, scale=6), nullable=False),
        sa.Column("purchase_price", sa.Numeric(precision=16, scale=4), nullable=False),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_positions_ticker"), "positions", ["ticker"])

    op.create_table(
        "realized_trades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=16, scale=6), nullable=False),
        sa.Column("purchase_price", sa.Numeric(precision=16, scale=4), nullable=False),
        sa.Column("sale_price", sa.Numeric(precision=16, scale=4), nullable=False),
        sa.Column("sale_date", sa.Date(), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_realized_trades_ticker"), "realized_trades", ["ticker"])


def downgrade() -> None:
    op.drop_index(op.f("ix_realized_trades_ticker"), table_name="realized_trades")
    op.drop_table("realized_trades")
    op.drop_index(op.f("ix_positions_ticker"), table_name="positions")
    op.drop_table("positions")

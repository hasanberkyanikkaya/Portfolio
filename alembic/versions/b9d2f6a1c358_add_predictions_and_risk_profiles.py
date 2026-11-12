"""add predictions and risk_profiles tables

Revision ID: b9d2f6a1c358
Revises: e7b3a5c2d941
Create Date: 2026-07-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b9d2f6a1c358"
down_revision: Union[str, None] = "e7b3a5c2d941"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("algorithm", sa.String(length=32), nullable=False),
        sa.Column("prediction_date", sa.Date(), nullable=False),
        sa.Column("predicted_direction", sa.String(length=8), nullable=False),
        sa.Column("price_at_prediction", sa.Numeric(precision=16, scale=4), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("evaluation_date", sa.Date(), nullable=True),
        sa.Column("price_at_evaluation", sa.Numeric(precision=16, scale=4), nullable=True),
        sa.Column("actual_return_pct", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ticker", "algorithm", "prediction_date", name="uq_predictions_ticker_algo_date"
        ),
    )
    op.create_index(op.f("ix_predictions_ticker"), "predictions", ["ticker"])
    op.create_index(op.f("ix_predictions_status"), "predictions", ["status"])

    op.create_table(
        "risk_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("horizon", sa.String(length=8), nullable=False),
        sa.Column("loss_tolerance", sa.String(length=8), nullable=False),
        sa.Column("capital_share", sa.String(length=8), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("profile", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("risk_profiles")
    op.drop_index(op.f("ix_predictions_status"), table_name="predictions")
    op.drop_index(op.f("ix_predictions_ticker"), table_name="predictions")
    op.drop_table("predictions")

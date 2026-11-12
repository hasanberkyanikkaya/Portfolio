"""add daily_reports table

Revision ID: e7b3a5c2d941
Revises: c4d8e2f7a913
Create Date: 2026-07-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7b3a5c2d941"
down_revision: Union[str, None] = "c4d8e2f7a913"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("report_type", sa.String(length=16), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_type", "report_date", name="uq_daily_reports_type_date"),
    )
    op.create_index(op.f("ix_daily_reports_report_type"), "daily_reports", ["report_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_daily_reports_report_type"), table_name="daily_reports")
    op.drop_table("daily_reports")

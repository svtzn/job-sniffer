"""filter vacancy status

Revision ID: 988f56587717
Revises: 5cc014aa5f96
Create Date: 2026-11-17 16:52:15.981767

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "988f56587717"
down_revision: str | Sequence[str] | None = "5cc014aa5f96"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """hidden (bool) -> status (seen / notified / hidden)."""
    with op.batch_alter_table("filter_vacancies", schema=None) as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(length=16), server_default="seen", nullable=False))
        batch_op.create_index(batch_op.f("ix_filter_vacancies_status"), ["status"], unique=False)

    # перенос старых пометок в статус
    op.execute("UPDATE filter_vacancies SET status = 'notified' WHERE notified_at IS NOT NULL")
    op.execute("UPDATE filter_vacancies SET status = 'hidden' WHERE hidden")

    with op.batch_alter_table("filter_vacancies", schema=None) as batch_op:
        batch_op.drop_column("hidden")


def downgrade() -> None:
    with op.batch_alter_table("filter_vacancies", schema=None) as batch_op:
        batch_op.add_column(sa.Column("hidden", sa.Boolean(), server_default=sa.false(), nullable=False))

    op.execute("UPDATE filter_vacancies SET hidden = (status = 'hidden')")

    with op.batch_alter_table("filter_vacancies", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_filter_vacancies_status"))
        batch_op.drop_column("status")

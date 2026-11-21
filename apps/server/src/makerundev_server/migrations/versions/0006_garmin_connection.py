import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "garmin_connection",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("api_key", sa.Text(), nullable=False),
        sa.Column("token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("newest_synced", sa.DateTime(), nullable=True),
        sa.Column("backfill_before", sa.DateTime(), nullable=True),
        sa.Column("backfill_done", sa.Boolean(), nullable=False),
        sa.Column("syncing", sa.Boolean(), nullable=False),
        sa.Column("sync_message", sa.String(length=255), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("imported", sa.Integer(), nullable=False),
        sa.Column("matched", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.JSON(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_garmin_connection_single_row"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("garmin_connection")

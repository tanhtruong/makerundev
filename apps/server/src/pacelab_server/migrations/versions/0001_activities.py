import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "activities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("source_format", sa.String(length=8), nullable=False),
        sa.Column("sport", sa.String(length=32), nullable=False),
        sa.Column("device", sa.String(length=128), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("distance_m", sa.Float(), nullable=False),
        sa.Column("elapsed_s", sa.Float(), nullable=False),
        sa.Column("moving_s", sa.Float(), nullable=False),
        sa.Column("pace_s_per_km", sa.Float(), nullable=True),
        sa.Column("avg_heart_rate", sa.Float(), nullable=True),
        sa.Column("max_heart_rate", sa.Float(), nullable=True),
        sa.Column("elevation_gain_m", sa.Float(), nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sha256"),
    )
    op.create_index("ix_activities_start_time", "activities", ["start_time"])


def downgrade() -> None:
    op.drop_index("ix_activities_start_time", table_name="activities")
    op.drop_table("activities")

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "athlete_settings",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("max_hr", sa.Integer(), nullable=False),
        sa.Column("resting_hr", sa.Integer(), nullable=False),
        sa.Column("trimp_coefficients", sa.String(length=8), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("zone_model", sa.String(length=32), nullable=False),
        sa.Column("zone_thresholds", sa.JSON(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_athlete_settings_single_row"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("activities", schema=None) as batch_op:
        batch_op.add_column(sa.Column("trimp", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("activities", schema=None) as batch_op:
        batch_op.drop_column("trimp")

    op.drop_table("athlete_settings")

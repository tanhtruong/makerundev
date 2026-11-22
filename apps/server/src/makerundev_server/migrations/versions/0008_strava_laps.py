from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE activities SET laps = NULL WHERE external_source = 'strava' AND sha256 IS NULL"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE activities SET laps = '[]'"
        " WHERE external_source = 'strava' AND sha256 IS NULL AND laps IS NULL"
    )

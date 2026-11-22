import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("activities", schema=None) as batch_op:
        batch_op.add_column(sa.Column("name", sa.String(length=255), nullable=True))
    op.execute(
        "UPDATE activities"
        " SET name = NULLIF(TRIM(filename, ' ' || char(9) || char(10) || char(13)), '')"
        " WHERE sha256 IS NULL AND external_source = 'strava' AND filename != 'Strava activity'"
    )


def downgrade() -> None:
    with op.batch_alter_table("activities", schema=None) as batch_op:
        batch_op.drop_column("name")

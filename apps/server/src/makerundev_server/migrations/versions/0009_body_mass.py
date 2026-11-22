import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("athlete_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("body_mass_kg", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("athlete_settings", schema=None) as batch_op:
        batch_op.drop_column("body_mass_kg")

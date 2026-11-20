import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("activities", schema=None) as batch_op:
        batch_op.add_column(sa.Column("laps", sa.JSON(none_as_null=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("activities", schema=None) as batch_op:
        batch_op.drop_column("laps")

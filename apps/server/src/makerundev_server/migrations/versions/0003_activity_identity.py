import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("activities", schema=None) as batch_op:
        batch_op.add_column(sa.Column("storage_key", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("external_source", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("external_id", sa.String(length=32), nullable=True))
        batch_op.alter_column("sha256", existing_type=sa.String(length=64), nullable=True)

    op.execute("UPDATE activities SET storage_key = sha256")

    with op.batch_alter_table("activities", schema=None) as batch_op:
        batch_op.alter_column("storage_key", existing_type=sa.String(length=64), nullable=False)
        batch_op.create_unique_constraint("uq_activities_storage_key", ["storage_key"])
        batch_op.create_unique_constraint(
            "uq_activities_external", ["external_source", "external_id"]
        )


def downgrade() -> None:
    op.execute("DELETE FROM activities WHERE sha256 IS NULL")

    with op.batch_alter_table("activities", schema=None) as batch_op:
        batch_op.drop_constraint("uq_activities_external", type_="unique")
        batch_op.drop_constraint("uq_activities_storage_key", type_="unique")
        batch_op.alter_column("sha256", existing_type=sa.String(length=64), nullable=False)
        batch_op.drop_column("external_id")
        batch_op.drop_column("external_source")
        batch_op.drop_column("storage_key")

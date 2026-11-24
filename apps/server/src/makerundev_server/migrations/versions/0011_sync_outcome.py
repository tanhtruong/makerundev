import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | None = None
depends_on: str | None = None

SHARED = {
    "up_to_date": "Up to date.",
    "failed": "The sync stopped on an unexpected error. See the server log.",
    "interrupted": "The last sync was interrupted. Sync again to continue.",
}
MESSAGES = {
    "strava_connection": {
        **SHARED,
        "paused_short": "Paused at Strava's 15-minute rate limit."
        " Sync again in a quarter of an hour.",
        "paused_daily": "Paused at Strava's daily rate limit. Sync again after midnight UTC.",
        "rejected": "Strava no longer accepts this connection. Disconnect and connect again.",
        "unreachable": "Strava could not be reached. Sync again later.",
    },
    "garmin_connection": {
        **SHARED,
        "paused": "Garmin asked to slow down. Sync again later.",
        "rejected": "Garmin no longer accepts this key: it has expired or was revoked."
        " Create a new one in Garmin Connect under Settings, Personal API Key,"
        " and save it below.",
        "unreachable": "Garmin could not be reached. Sync again later.",
    },
}
GARMIN_PAUSE = "Garmin asked to slow down.%"


def upgrade() -> None:
    for table, messages in MESSAGES.items():
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column("sync_outcome", sa.String(length=32), nullable=True))
            batch_op.add_column(sa.Column("resume_at", sa.DateTime(), nullable=True))
        for outcome, message in messages.items():
            op.execute(
                sa.text(
                    f"UPDATE {table} SET sync_outcome = :outcome WHERE sync_message = :message"
                ).bindparams(outcome=outcome, message=message)
            )
    op.execute(
        sa.text(
            "UPDATE garmin_connection SET sync_outcome = 'paused' WHERE sync_message LIKE :pause"
        ).bindparams(pause=GARMIN_PAUSE)
    )
    for table in MESSAGES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("sync_message")


def downgrade() -> None:
    for table, messages in MESSAGES.items():
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column("sync_message", sa.String(length=255), nullable=True))
        for outcome, message in messages.items():
            op.execute(
                sa.text(
                    f"UPDATE {table} SET sync_message = :message WHERE sync_outcome = :outcome"
                ).bindparams(outcome=outcome, message=message)
            )
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("resume_at")
            batch_op.drop_column("sync_outcome")

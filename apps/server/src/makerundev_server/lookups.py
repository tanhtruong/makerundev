from fastapi import HTTPException

from makerundev_server.db import ActivityRow
from makerundev_server.store import Store


def activity_or_404(store: Store, activity_id: int) -> ActivityRow:
    row = store.get(activity_id)
    if row is None:
        raise HTTPException(status_code=404, detail="activity not found")
    return row

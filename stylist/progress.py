"""Per-request progress only reports stages actually entered by the engine."""
from contextvars import ContextVar

events: ContextVar = ContextVar("stylist_progress", default=None)


def report(stage, message):
    queue = events.get()
    if queue is not None:
        queue.put_nowait({"stage": stage, "message": message})

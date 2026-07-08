"""Shared "replace-oldest-when-full" queue helper.

Used everywhere a producer must never block (RTL-SDR reads, the asyncio
event loop) and a slow consumer should lose stale data rather than cause
backpressure. Works with both `queue.Queue` and `multiprocessing.Queue`
since both raise `queue.Full` / `queue.Empty` from put_nowait/get_nowait.
"""

import queue


def drain_queue(q) -> None:
    """Discard everything currently queued, without blocking."""
    while True:
        try:
            q.get_nowait()
        except queue.Empty:
            return


def put_dropping_oldest(q, item) -> bool:
    """Returns True if an existing item had to be dropped to make room."""
    try:
        q.put_nowait(item)
        return False
    except queue.Full:
        try:
            q.get_nowait()
        except queue.Empty:
            pass
        try:
            q.put_nowait(item)
        except queue.Full:
            pass  # lost a race with another producer; fine, it's droppable data
        return True

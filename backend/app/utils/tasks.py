"""
Background task registry.

asyncio keeps only a weak reference to tasks, so a bare `asyncio.create_task()`
whose result is discarded can be garbage-collected mid-run. Every fire-and-forget
coroutine goes through `spawn()`, which holds a strong reference until the task
finishes and logs any exception that would otherwise vanish silently.
"""
import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)

_tasks: set[asyncio.Task] = set()


def _on_done(task: asyncio.Task) -> None:
    _tasks.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("Background task %s crashed: %r", task.get_name(), exc, exc_info=exc)


def spawn(coro: Coroutine[Any, Any, Any], name: str | None = None) -> asyncio.Task:
    task = asyncio.create_task(coro, name=name)
    _tasks.add(task)
    task.add_done_callback(_on_done)
    return task


async def cancel_all() -> None:
    """Cancel outstanding tasks on shutdown."""
    for task in list(_tasks):
        task.cancel()
    if _tasks:
        await asyncio.gather(*_tasks, return_exceptions=True)

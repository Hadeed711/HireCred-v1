"""
In-process background task manager for credibility rescoring.

Why this exists (instead of bare `asyncio.create_task`):

1. **Garbage-collection safety** — asyncio only keeps a weak reference to
   tasks. A fire-and-forget `create_task()` whose result is never awaited can
   be garbage-collected mid-execution, silently dropping the rescore. We keep
   strong references until completion.

2. **Deduplication / coalescing** — a user editing their profile fires many
   saves in a burst (bio, skills, portfolio...). Each save used to spawn its
   own full pipeline run (LLM call + URL checks). Now: one debounced run per
   user; requests arriving while a run is in flight set a "dirty" flag and
   trigger exactly one follow-up run against the latest data.

3. **Bounded concurrency** — a local Ollama instance effectively serves one
   generation at a time on CPU. Unbounded concurrent scoring requests queue
   inside Ollama, time out at our 10 s ceiling, and everything degrades to the
   rule-based fallback. A semaphore keeps the pipeline healthy under load.

Production equivalent: this module is the seam where a real job queue goes.
Swap `schedule_rescore()`'s body for `queue.enqueue("rescore", user_id)` and
run the same pipeline in Celery / RQ / arq / SQS workers — the call sites
don't change. (See INFRASTRUCTURE.md → "Background jobs".)
"""
import asyncio
import logging
import uuid

logger = logging.getLogger(__name__)

# On a CPU-only Ollama box more than 2 concurrent generations just thrash.
MAX_CONCURRENT_SCORING = 2
# Burst of saves within this window collapses into a single scoring run.
DEBOUNCE_SECONDS = 2.0

_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCORING)
_tasks: dict[uuid.UUID, asyncio.Task] = {}      # strong refs — prevents GC
_dirty: set[uuid.UUID] = set()                  # rerun requested while running
_stats = {"scheduled": 0, "coalesced": 0, "completed": 0, "failed": 0}


def schedule_rescore(user_id: uuid.UUID) -> None:
    """Schedule a credibility rescore for a user (debounced + deduplicated).

    Safe to call on every save; at most one pipeline run is in flight per
    user, and at most one follow-up run is queued behind it.
    """
    existing = _tasks.get(user_id)
    if existing is not None and not existing.done():
        # A run is pending or in flight. If it's still in its debounce sleep
        # it will pick up the new data anyway; if it's mid-compute, mark dirty
        # so exactly one follow-up run happens afterwards.
        _dirty.add(user_id)
        _stats["coalesced"] += 1
        return

    _stats["scheduled"] += 1
    task = asyncio.create_task(_run_rescore(user_id))
    _tasks[user_id] = task
    task.add_done_callback(lambda t, uid=user_id: _on_done(uid, t))


async def _run_rescore(user_id: uuid.UUID) -> None:
    from src.services.credibility_service import compute_and_save_score

    await asyncio.sleep(DEBOUNCE_SECONDS)
    # Anything scheduled during the debounce window is absorbed by this run —
    # the pipeline reads the latest committed data.
    _dirty.discard(user_id)
    async with _semaphore:
        await compute_and_save_score(user_id)


def _on_done(user_id: uuid.UUID, task: asyncio.Task) -> None:
    _tasks.pop(user_id, None)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        _stats["failed"] += 1
        logger.error("Background rescore failed for user %s: %s", user_id, exc)
    else:
        _stats["completed"] += 1

    if user_id in _dirty:
        _dirty.discard(user_id)
        schedule_rescore(user_id)


def schedule_fraud_check(user_id: uuid.UUID) -> None:
    """Run fraud detection in the background, strictly AFTER any pending
    rescore for the same user.

    Ordering matters: `compute_and_save_score` UPSERTs the entire score row
    (including fraud fields), while fraud detection applies a penalty on top
    of it. If fraud ran first, the rescore would silently erase its result.
    """
    async def _run() -> None:
        from src.services.fraud_service import run_fraud_detection
        # Wait out the rescore (including a possible dirty re-run).
        for _ in range(3):
            rescore_task = _tasks.get(user_id)
            if rescore_task is None or rescore_task.done():
                break
            try:
                await asyncio.wait_for(
                    asyncio.gather(rescore_task, return_exceptions=True),
                    timeout=90,
                )
            except asyncio.TimeoutError:
                break
        async with _semaphore:
            await run_fraud_detection(user_id)

    key = uuid.uuid5(user_id, "fraud")  # separate slot from rescore tasks
    existing = _tasks.get(key)
    if existing is not None and not existing.done():
        return  # one queued fraud pass already covers the latest data
    task = asyncio.create_task(_run())
    _tasks[key] = task
    task.add_done_callback(lambda t, k=key: _tasks.pop(k, None))


def queue_stats() -> dict:
    """Exposed via /health/queue for observability."""
    return {
        **_stats,
        "in_flight": sum(1 for t in _tasks.values() if not t.done()),
        "dirty_pending": len(_dirty),
        "max_concurrent": MAX_CONCURRENT_SCORING,
        "debounce_seconds": DEBOUNCE_SECONDS,
    }

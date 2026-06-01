"""Anchor-history retention purge job (TASK-006).

GDPR + AML floor: 7 years from ``occurred_at`` (the wall-clock timestamp
of the transition at the aggregate — NOT ``recorded_at`` at the
projection, which can drift on backfill). Configurable via
``Settings.history_retention_days``.

The job is a tiny asyncio task scheduled to run every N seconds
(``history_retention_purge_interval_seconds``). It computes ``cutoff =
now() - retention_days`` and deletes every row with ``occurred_at <
cutoff``. The DELETE is unconstrained on ``transition_kind`` — the
PSEUDONYMISED row IS subject to the same floor as any other transition,
because by construction the projection has no PII and the row is the
durable lineage trace, not the right-to-be-forgotten target.

The job never crashes the worker: any exception is logged and the next
tick re-tries.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import structlog

from ...application.ports import RetentionPurger

log = structlog.get_logger()


class RetentionPurgeJob:
    """Scheduled background task for the anchor-history retention floor.

    ``retention_days`` defaults to 2557 (7 GDPR years — 7 * 365 + 2
    leap-day allowance, matching the existing audit-log convention).
    Tests inject a much smaller value (e.g. 0 for "everything older
    than now is purged").
    """

    def __init__(
        self,
        *,
        purger: RetentionPurger,
        retention_days: int,
        interval_seconds: float,
    ) -> None:
        if retention_days < 0:
            raise ValueError("retention_days must be >= 0")
        self._purger = purger
        self._retention = timedelta(days=retention_days)
        self._interval = interval_seconds
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None

    @property
    def retention(self) -> timedelta:
        return self._retention

    async def start(self) -> None:
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="anchor-history-retention-purge")
        log.info(
            "retention_purge.started",
            retention_days=self._retention.days,
            interval_seconds=self._interval,
        )

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log.info("retention_purge.stopped")

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self.run_once()
            except Exception:  # noqa: BLE001 — job must never crash the worker
                log.exception("retention_purge.run_failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval)
            except asyncio.TimeoutError:
                continue

    async def run_once(self) -> int:
        """Compute the cutoff and run one purge pass. Returns the number
        of rows deleted (also surfaced via the structured log line).
        """
        cutoff = datetime.now(timezone.utc) - self._retention
        deleted = await self._purger.purge_older_than(cutoff)
        log.info(
            "retention_purge.batch",
            cutoff=cutoff.isoformat(),
            deleted=deleted,
            retention_days=self._retention.days,
        )
        return deleted

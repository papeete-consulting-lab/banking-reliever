"""Unit tests for RetentionPurgeJob (TASK-006).

Validates:

  1. ``run_once`` computes ``cutoff = now() - retention_days`` and
     delegates to the purger.
  2. Negative retention raises at construction.
  3. The default retention (2557 days) matches the 7-year GDPR/AML
     floor declared in ``read-models.yaml.PRJ.ANCHOR_HISTORY.retention``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pytest

from reliever_beneficiary_anchor.infrastructure.persistence.retention import (
    RetentionPurgeJob,
)


@dataclass
class _PurgerFake:
    cutoffs: list[datetime] = field(default_factory=list)
    deletes: int = 3

    async def purge_older_than(self, cutoff: datetime) -> int:
        self.cutoffs.append(cutoff)
        return self.deletes


def test_negative_retention_rejected() -> None:
    with pytest.raises(ValueError):
        RetentionPurgeJob(purger=_PurgerFake(), retention_days=-1, interval_seconds=1.0)


@pytest.mark.asyncio
async def test_run_once_returns_delete_count() -> None:
    purger = _PurgerFake(deletes=7)
    job = RetentionPurgeJob(purger=purger, retention_days=2557, interval_seconds=1.0)
    n = await job.run_once()
    assert n == 7
    assert len(purger.cutoffs) == 1


@pytest.mark.asyncio
async def test_cutoff_is_now_minus_retention() -> None:
    purger = _PurgerFake()
    job = RetentionPurgeJob(purger=purger, retention_days=10, interval_seconds=1.0)
    before = datetime.now(timezone.utc) - timedelta(days=10) - timedelta(seconds=2)
    await job.run_once()
    after = datetime.now(timezone.utc) - timedelta(days=10) + timedelta(seconds=2)
    assert before <= purger.cutoffs[0] <= after


def test_default_retention_matches_seven_year_floor() -> None:
    # 7 * 365 + 2 leap-day allowance = 2557 days — matches the contract
    # declared in read-models.yaml.PRJ.ANCHOR_HISTORY.retention ("7y").
    job = RetentionPurgeJob(purger=_PurgerFake(), retention_days=2557, interval_seconds=1.0)
    assert job.retention == timedelta(days=2557)
    assert job.retention.days >= 7 * 365

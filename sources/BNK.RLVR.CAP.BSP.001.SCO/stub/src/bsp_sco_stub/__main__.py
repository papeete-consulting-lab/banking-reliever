"""Entry point — `python -m bsp_sco_stub` or `bsp-sco-stub`.

Runs an async loop that:
  1) loads canonical schemas from process/BNK.RLVR.CAP.BSP.001.SCO/schemas/
  2) connects to RabbitMQ and declares the owned exchange
  3) ticks at `STUB_CADENCE_PER_MIN` events / minute combined
  4) on each tick, builds + validates + publishes the next emission
     batch (CURRENT events may carry an atomic THRESHOLD companion)

Setting `STUB_ACTIVE=false` (the default) keeps the loop alive but
publishes nothing — the connection is still established so misconfig
shows up immediately on startup.
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import signal
import sys
from contextlib import suppress

from .config import StubConfig
from .fixtures import make_case_pool, next_emissions
from .publisher import open_publisher
from .schema_validator import SchemaValidator


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s :: %(message)s"


def _setup_logging() -> None:
    level = os.environ.get("STUB_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format=LOG_FORMAT,
        stream=sys.stdout,
    )
    # aio-pika is chatty at DEBUG; keep it at WARNING by default.
    logging.getLogger("aio_pika").setLevel(logging.WARNING)
    logging.getLogger("aiormq").setLevel(logging.WARNING)


async def _run(cfg: StubConfig) -> None:
    log = logging.getLogger("bsp_sco_stub")
    log.info("BNK.RLVR.CAP.BSP.001.SCO development stub starting.")
    log.info(
        "config: active=%s cadence=%.2f/min threshold_p=%.3f "
        "exchange=%s schemas=%s rabbit=%s",
        cfg.active,
        cfg.cadence_per_minute,
        cfg.threshold_probability,
        cfg.exchange_name,
        cfg.schemas_dir,
        cfg.rabbitmq_url,
    )

    validator = SchemaValidator(cfg.schemas_dir)
    log.info(
        "Loaded %d canonical RVT schemas: %s",
        len(validator.loaded),
        ", ".join(sorted(validator.loaded)),
    )

    rng = random.Random()
    pool = make_case_pool(size=cfg.case_pool_size, rng=rng)
    log.info("Synthetic case pool: %d cases.", len(pool))

    period_seconds = 60.0 / cfg.cadence_per_minute if cfg.cadence_per_minute > 0 else 60.0
    log.info("Tick period ≈ %.2fs.", period_seconds)

    stop_event = asyncio.Event()

    def _request_stop(*_: object) -> None:
        log.info("Stop signal received — winding down.")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, _request_stop)

    async with open_publisher(cfg=cfg, validator=validator) as publisher:
        if not cfg.active:
            log.warning(
                "STUB_ACTIVE=false — exchange declared but no events will "
                "be published. Set STUB_ACTIVE=true to enable publication."
            )

        while not stop_event.is_set():
            tick_at = loop.time() + period_seconds
            if cfg.active:
                emissions = next_emissions(pool=pool, cfg=cfg, rng=rng)
                await publisher.publish_emissions(emissions)

            # Sleep until the next tick OR until shutdown — whichever first.
            remaining = max(0.0, tick_at - loop.time())
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                pass

    log.info(
        "Shutdown complete. published=%d rejected_by_schema=%d",
        publisher.stats.published,
        publisher.stats.rejected_by_schema,
    )


def main() -> None:
    _setup_logging()
    try:
        cfg = StubConfig.from_env()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(2)

    try:
        asyncio.run(_run(cfg))
    except KeyboardInterrupt:  # pragma: no cover
        pass


if __name__ == "__main__":  # pragma: no cover
    main()

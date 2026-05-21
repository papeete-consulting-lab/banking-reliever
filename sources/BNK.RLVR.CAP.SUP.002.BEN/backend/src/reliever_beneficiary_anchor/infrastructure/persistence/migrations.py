"""Tiny migration runner. Reads every ``.sql`` file from ``migrations/`` in
lexicographic order and applies it inside a transaction.

Real deployments would use a tool like alembic or sqitch. TASK-002 keeps
things minimal — the migration files are versioned by filename prefix.
"""

from __future__ import annotations

from pathlib import Path

import structlog
from psycopg import AsyncConnection

log = structlog.get_logger()


async def apply_migrations(conn: AsyncConnection, migrations_dir: Path) -> None:
    sql_files = sorted(p for p in migrations_dir.glob("*.sql"))
    if not sql_files:
        raise RuntimeError(f"No migration files found in {migrations_dir}")
    for path in sql_files:
        sql = path.read_text()
        log.info("apply_migration", file=path.name)
        async with conn.cursor() as cur:
            await cur.execute(sql)  # type: ignore[arg-type]
        # Each file is itself wrapped in BEGIN/COMMIT.

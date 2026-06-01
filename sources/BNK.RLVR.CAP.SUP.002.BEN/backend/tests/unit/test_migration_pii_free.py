"""Structural assertion that the anchor_history projection is PII-free
(TASK-006 — DoD invariant).

This test reads the SQL migration text and asserts that:

  1. The ``CREATE TABLE anchor_history`` block exists.
  2. The columns enumerated by ``read-models.yaml.PRJ.ANCHOR_HISTORY.fields``
     are all present.
  3. None of the four PII columns from the anchor / anchor_directory
     write-side tables appears in the anchor_history block.
  4. The composite primary key ``(internal_id, revision)`` is declared.

The structural check is intentionally textual — it catches a future
developer adding ``last_name TEXT`` to the migration the same way a
``information_schema``-walking integration test would, but without
requiring a live PostgreSQL connection. The integration test sibling
under ``tests/integration/test_anchor_history_integration.py``
re-asserts the same invariant against a real database to defend against
any DDL drift the textual check might miss.
"""

from __future__ import annotations

import re
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
_MIGRATION = _MIGRATIONS_DIR / "003_anchor_history.sql"

_FORBIDDEN_PII_COLS = ["last_name", "first_name", "date_of_birth", "contact_details"]
_REQUIRED_COLS = [
    "internal_id",
    "revision",
    "transition_kind",
    "command_id",
    "right_exercise_id",
    "actor",
    "occurred_at",
]


def _extract_create_block(sql: str) -> str:
    """Return the text between ``CREATE TABLE`` for ``anchor_history``
    and the closing ``);``. Fails if the block can't be located.
    """
    match = re.search(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?anchor_history\s*\((.*?)\);",
        sql,
        re.DOTALL | re.IGNORECASE,
    )
    assert match is not None, "anchor_history CREATE TABLE block not found"
    return match.group(1)


def test_migration_file_exists() -> None:
    assert _MIGRATION.exists(), f"migration not found: {_MIGRATION}"


def test_required_columns_present_in_create_table() -> None:
    block = _extract_create_block(_MIGRATION.read_text())
    block_lower = block.lower()
    for col in _REQUIRED_COLS:
        assert re.search(rf"\b{col}\b", block_lower), (
            f"required column {col!r} missing from anchor_history CREATE TABLE block"
        )


def test_pii_columns_absent_from_anchor_history() -> None:
    """Structural PII-free invariant — the four PII column names MUST NOT
    appear in the CREATE TABLE block for anchor_history.
    """
    block = _extract_create_block(_MIGRATION.read_text())
    block_lower = block.lower()
    for forbidden in _FORBIDDEN_PII_COLS:
        assert not re.search(rf"\b{forbidden}\b", block_lower), (
            f"PII column {forbidden!r} forbidden in anchor_history — "
            f"the projection is PII-free by construction."
        )


def test_composite_primary_key_declared() -> None:
    block = _extract_create_block(_MIGRATION.read_text())
    block_lower = block.lower()
    assert re.search(
        r"primary\s+key\s*\(\s*internal_id\s*,\s*revision\s*\)",
        block_lower,
    ), "anchor_history must declare PRIMARY KEY (internal_id, revision)"


def test_right_exercise_id_invariant_constraint_present() -> None:
    """``right_exercise_id`` is set ONLY on PSEUDONYMISED rows — enforced
    at the database layer (CHECK constraint).
    """
    sql = _MIGRATION.read_text().lower()
    assert "chk_anchor_history_right_exercise_id_only_on_pseudonymised" in sql
    assert "pseudonymised" in sql and "right_exercise_id" in sql

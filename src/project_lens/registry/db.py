"""SQLite 연결 및 마이그레이션 러너.

ORM 없이 표준 라이브러리 sqlite3만 사용한다 (docs/DATA_MODEL.md 결정 사항).
"""

from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path

from project_lens.config import db_path

_MIGRATIONS_PACKAGE = "project_lens.registry.migrations"


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS _migrations (
            filename    TEXT PRIMARY KEY,
            applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    applied = {row["filename"] for row in conn.execute("SELECT filename FROM _migrations")}

    migration_files = sorted(
        f for f in resources.files(_MIGRATIONS_PACKAGE).iterdir() if f.name.endswith(".sql")
    )
    for migration_file in migration_files:
        if migration_file.name in applied:
            continue
        conn.executescript(migration_file.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO _migrations (filename) VALUES (?)", (migration_file.name,)
        )
    conn.commit()

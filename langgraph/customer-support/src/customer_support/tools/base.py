from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Sequence

_DB_PATH: Path | None = None


def set_db_path(path: Path | str) -> None:
    global _DB_PATH
    _DB_PATH = Path(path)


def get_db_path() -> Path:
    if _DB_PATH is None:
        raise RuntimeError("Database path is not configured. Call set_db_path first.")
    return _DB_PATH


def connect() -> sqlite3.Connection:
    return sqlite3.connect(get_db_path())


def rows_to_dicts(cursor: sqlite3.Cursor, rows: Sequence[sqlite3.Row]) -> List[dict]:
    column_names = [column[0] for column in cursor.description]
    return [dict(zip(column_names, row)) for row in rows]


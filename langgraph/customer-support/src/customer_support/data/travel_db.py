from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

TRAVEL_DB_URL = (
    "https://storage.googleapis.com/benchmarks-artifacts/travel-db/travel2.sqlite"
)
DEFAULT_DB_NAME = "travel2.sqlite"
DEFAULT_BACKUP_NAME = "travel2.backup.sqlite"
DEFAULT_ENV_VAR = "CUSTOMER_SUPPORT_DATA_DIR"
DEFAULT_STORAGE_SUBPATH = ".cache/customer_support"


def _default_dir() -> Path:
    custom = os.environ.get(DEFAULT_ENV_VAR)
    if custom:
        return Path(custom).expanduser()
    return Path.home() / DEFAULT_STORAGE_SUBPATH


def get_default_storage_dir() -> Path:
    return _default_dir()


def _data_dir(path: Optional[Path | str] = None) -> Path:
    if path is not None:
        return Path(path).expanduser()
    return _default_dir()


def download_database(
    *,
    overwrite: bool = False,
    target_dir: Optional[Path] = None,
) -> Path:
    directory = _data_dir(target_dir)
    directory.mkdir(parents=True, exist_ok=True)
    db_path = directory / DEFAULT_DB_NAME
    backup_path = directory / DEFAULT_BACKUP_NAME

    if overwrite or not db_path.exists():
        response = requests.get(TRAVEL_DB_URL, timeout=60)
        response.raise_for_status()
        with open(db_path, "wb") as f:
            f.write(response.content)
        shutil.copy(db_path, backup_path)
    elif not backup_path.exists():
        shutil.copy(db_path, backup_path)

    return db_path


def update_dates(
    db_path: Path,
    *,
    backup_path: Optional[Path] = None,
) -> Path:
    database = Path(db_path)
    backup = backup_path or database.with_name(DEFAULT_BACKUP_NAME)
    if not backup.exists():
        raise FileNotFoundError(
            f"Backup database not found at {backup}. Run download_database first."
        )

    shutil.copy(backup, database)
    conn = sqlite3.connect(database)

    try:
        tables = pd.read_sql(
            "SELECT name FROM sqlite_master WHERE type='table';", conn
        ).name.tolist()

        table_frames = {
            table_name: pd.read_sql(f"SELECT * FROM {table_name}", conn)
            for table_name in tables
        }

        flights = table_frames["flights"]
        example_time = pd.to_datetime(
            flights["actual_departure"].replace("\\N", pd.NaT)
        ).max()
        current_time = pd.to_datetime("now").tz_localize(example_time.tz)
        time_diff = current_time - example_time

        bookings = table_frames["bookings"]
        bookings["book_date"] = (
            pd.to_datetime(bookings["book_date"].replace("\\N", pd.NaT), utc=True)
            + time_diff
        )
        table_frames["bookings"] = bookings

        datetime_columns = [
            "scheduled_departure",
            "scheduled_arrival",
            "actual_departure",
            "actual_arrival",
        ]
        for column in datetime_columns:
            flights[column] = (
                pd.to_datetime(flights[column].replace("\\N", pd.NaT)) + time_diff
            )

        for table_name, df in table_frames.items():
            df.to_sql(table_name, conn, if_exists="replace", index=False)
    finally:
        conn.commit()
        conn.close()

    return database


def prepare_database(
    *,
    overwrite: bool = False,
    target_dir: Optional[Path] = None,
) -> Path:
    db_path = download_database(overwrite=overwrite, target_dir=target_dir)
    return update_dates(db_path)


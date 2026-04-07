"""
SQLite storage layer for registry snapshots.

Handles creating the database, persisting snapshots, listing them,
loading them back, and deleting them.
"""

from __future__ import annotations

import os
import platform
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from regtracker.config import DEFAULT_DB_DIR, DEFAULT_DB_PATH
from regtracker.snapshot import RegistryEntry, SnapshotResult


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS snapshots (
    id          TEXT PRIMARY KEY,
    label       TEXT NOT NULL,
    hive        TEXT NOT NULL,
    root_path   TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    hostname    TEXT NOT NULL,
    os_version  TEXT NOT NULL,
    username    TEXT NOT NULL,
    entry_count INTEGER NOT NULL DEFAULT 0,
    keys_scanned INTEGER NOT NULL DEFAULT 0,
    keys_denied  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id TEXT NOT NULL,
    key_path    TEXT NOT NULL,
    value_name  TEXT NOT NULL,
    value_type  INTEGER NOT NULL,
    value_data  TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entries_snapshot_id ON entries(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_entries_key_path    ON entries(snapshot_id, key_path);
"""


# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------

def _ensure_db_dir() -> None:
    """Create the database directory if it doesn't exist."""
    os.makedirs(DEFAULT_DB_DIR, exist_ok=True)


def _get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get a database connection, creating the schema if needed."""
    _ensure_db_dir()
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA_SQL)
    return conn


# ---------------------------------------------------------------------------
# Snapshot metadata dataclass
# ---------------------------------------------------------------------------

class SnapshotMeta:
    """Lightweight metadata about a stored snapshot (no entries loaded)."""

    def __init__(
        self,
        id: str,
        label: str,
        hive: str,
        root_path: str,
        timestamp: str,
        hostname: str,
        os_version: str,
        username: str,
        entry_count: int,
        keys_scanned: int,
        keys_denied: int,
    ):
        self.id = id
        self.label = label
        self.hive = hive
        self.root_path = root_path
        self.timestamp = timestamp
        self.hostname = hostname
        self.os_version = os_version
        self.username = username
        self.entry_count = entry_count
        self.keys_scanned = keys_scanned
        self.keys_denied = keys_denied


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def save_snapshot(
    result: SnapshotResult,
    label: str,
    db_path: Optional[str] = None,
) -> str:
    """
    Persist a SnapshotResult to the database.

    Args:
        result: The scan result containing all registry entries.
        label: A human-readable label for this snapshot.
        db_path: Optional custom database path.

    Returns:
        The generated snapshot ID (UUID).
    """
    conn = _get_connection(db_path)
    snapshot_id = uuid.uuid4().hex[:12]  # 12-char short ID
    now = datetime.now(timezone.utc).isoformat()

    try:
        conn.execute(
            """
            INSERT INTO snapshots
                (id, label, hive, root_path, timestamp, hostname, os_version, username,
                 entry_count, keys_scanned, keys_denied)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                label,
                result.hive_name,
                result.root_path,
                now,
                platform.node(),
                platform.platform(),
                os.getlogin(),
                len(result.entries),
                result.keys_scanned,
                result.keys_denied,
            ),
        )

        # Batch insert entries for performance
        conn.executemany(
            """
            INSERT INTO entries (snapshot_id, key_path, value_name, value_type, value_data)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (snapshot_id, e.key_path, e.value_name, e.value_type, e.value_data)
                for e in result.entries
            ],
        )

        conn.commit()
    finally:
        conn.close()

    return snapshot_id


def list_snapshots(db_path: Optional[str] = None) -> list[SnapshotMeta]:
    """
    List all snapshots in the database, ordered by timestamp descending.

    Returns:
        List of SnapshotMeta objects.
    """
    conn = _get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, label, hive, root_path, timestamp, hostname, os_version,
                   username, entry_count, keys_scanned, keys_denied
            FROM snapshots
            ORDER BY timestamp DESC
            """
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    return [
        SnapshotMeta(
            id=row[0],
            label=row[1],
            hive=row[2],
            root_path=row[3],
            timestamp=row[4],
            hostname=row[5],
            os_version=row[6],
            username=row[7],
            entry_count=row[8],
            keys_scanned=row[9],
            keys_denied=row[10],
        )
        for row in rows
    ]


def load_snapshot_entries(
    snapshot_id: str,
    db_path: Optional[str] = None,
) -> list[RegistryEntry]:
    """
    Load all registry entries for a given snapshot ID.

    Args:
        snapshot_id: The snapshot ID to look up.

    Returns:
        List of RegistryEntry objects.

    Raises:
        ValueError: If the snapshot ID is not found.
    """
    conn = _get_connection(db_path)
    try:
        # Verify snapshot exists
        cursor = conn.execute(
            "SELECT id FROM snapshots WHERE id = ?", (snapshot_id,)
        )
        if cursor.fetchone() is None:
            raise ValueError(f"Snapshot '{snapshot_id}' not found in database.")

        cursor = conn.execute(
            """
            SELECT key_path, value_name, value_type, value_data
            FROM entries
            WHERE snapshot_id = ?
            ORDER BY key_path, value_name
            """,
            (snapshot_id,),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    return [
        RegistryEntry(
            key_path=row[0],
            value_name=row[1],
            value_type=row[2],
            value_data=row[3],
        )
        for row in rows
    ]


def get_snapshot_meta(
    snapshot_id: str,
    db_path: Optional[str] = None,
) -> Optional[SnapshotMeta]:
    """Get metadata for a single snapshot, or None if not found."""
    conn = _get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, label, hive, root_path, timestamp, hostname, os_version,
                   username, entry_count, keys_scanned, keys_denied
            FROM snapshots
            WHERE id = ?
            """,
            (snapshot_id,),
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    return SnapshotMeta(
        id=row[0],
        label=row[1],
        hive=row[2],
        root_path=row[3],
        timestamp=row[4],
        hostname=row[5],
        os_version=row[6],
        username=row[7],
        entry_count=row[8],
        keys_scanned=row[9],
        keys_denied=row[10],
    )


def delete_snapshot(
    snapshot_id: str,
    db_path: Optional[str] = None,
) -> bool:
    """
    Delete a snapshot and all its entries from the database.

    Returns:
        True if a snapshot was deleted, False if the ID was not found.
    """
    conn = _get_connection(db_path)
    try:
        cursor = conn.execute(
            "DELETE FROM snapshots WHERE id = ?", (snapshot_id,)
        )
        conn.commit()
        deleted = cursor.rowcount > 0
    finally:
        conn.close()

    return deleted

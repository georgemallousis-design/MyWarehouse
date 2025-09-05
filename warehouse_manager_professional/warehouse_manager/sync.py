"""
Backup and sync helpers.

These functions are import safe and have no side effects until called.
They operate on the database file defined in config or passed in.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
import logging


LOGGER = logging.getLogger(__name__)


def create_backup(db_path: str, backups_dir: str, keep: int = 1) -> str:
    """
    Create a timestamped copy of the database in backups_dir.
    Returns the path to the backup file. Keeps only the latest `keep` backups.
    """
    backup_dir = Path(backups_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d%H%M%S")
    backup_name = f"{Path(db_path).stem}_{timestamp}.db"
    backup_path = backup_dir / backup_name
    try:
        shutil.copy2(db_path, backup_path)
        LOGGER.info("Backup created: %s", backup_path)
    except Exception as exc:
        LOGGER.error("Failed to create backup: %s", exc)
        return ""
    cleanup_old_backups(backups_dir, keep)
    return str(backup_path)


def cleanup_old_backups(backups_dir: str, keep: int = 1) -> None:
    """
    Remove old backups, keeping only the most recent `keep` files.
    """
    backup_dir = Path(backups_dir)
    if not backup_dir.is_dir():
        return
    backups = sorted(backup_dir.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[keep:]:
        try:
            old.unlink()
            LOGGER.info("Removed old backup %s", old)
        except Exception as exc:
            LOGGER.warning("Failed to remove backup %s: %s", old, exc)

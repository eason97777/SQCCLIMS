"""Automatic SQLite backup on startup using the online backup API.

Paths are read from ``app.config`` at call time so ``configure_paths()`` is
respected. Failures never propagate out of startup.
"""
import logging
import sqlite3
from datetime import datetime

import app.config as config


logger = logging.getLogger("sqcclims")


def backup_database(keep=10):
    try:
        db_path = config.DB_PATH
        if not db_path.exists() or db_path.stat().st_size == 0:
            return None

        backups_dir = config.DATA_DIR / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = backups_dir / f"sample_testing_{timestamp}.db"

        src_conn = sqlite3.connect(db_path)
        try:
            dest_conn = sqlite3.connect(dest)
            try:
                src_conn.backup(dest_conn)
            finally:
                dest_conn.close()
        finally:
            src_conn.close()

        logger.info("db backup written: %s", dest)
        _prune_backups(backups_dir, keep)
        return dest
    except Exception as exc:
        logger.warning("db backup failed: %s", exc)
        return None


def _prune_backups(backups_dir, keep):
    backups = sorted(
        backups_dir.glob("sample_testing_*.db"),
        key=lambda path: path.name,
    )
    for old in backups[:-keep] if keep > 0 else backups:
        try:
            old.unlink()
        except OSError as exc:
            logger.warning("failed to prune old backup %s: %s", old, exc)

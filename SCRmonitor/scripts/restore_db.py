#!/usr/bin/env python3
"""Restore the SQLite database from a backup snapshot.

Backups are written by ``app/backup.py`` to ``<data-dir>/backups/``. This is the
*restore* half of that feature: list available snapshots, pick one, and swap it
in safely.

Safety measures:
  * The server MUST be stopped first (the database must not be in use). The
    script makes a best-effort check and refuses if the DB looks locked.
  * The current live database is snapshotted to ``backups/pre_restore_*.db``
    before being overwritten, so a restore is itself reversible.
  * The WAL sidecar files (``-wal`` / ``-shm``) are removed after the swap, so
    the restored copy is never merged with stale write-ahead frames.

Usage:
    python3 scripts/restore_db.py --list
    python3 scripts/restore_db.py --latest
    python3 scripts/restore_db.py --file sample_testing_20260615_152640.db
    python3 scripts/restore_db.py --latest --data-dir /path/to/data --yes
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Make the app package importable (this script lives in <app>/scripts/).
APP_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_ROOT))

import app.config as config  # noqa: E402


def human_size(num: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024:
            return f"{num:.0f}{unit}"
        num /= 1024
    return f"{num:.0f}TB"


def list_backups(backups_dir: Path):
    if not backups_dir.exists():
        return []
    return sorted(
        backups_dir.glob("sample_testing_*.db"),
        key=lambda p: p.name,
    )


def print_backups(backups):
    if not backups:
        print("No backups found.")
        return
    print(f"{'#':>2}  {'file':40}  {'size':>8}")
    for i, b in enumerate(backups):
        print(f"{i:>2}  {b.name:40}  {human_size(b.stat().st_size):>8}")


def db_is_locked(db_path: Path) -> bool:
    """Best-effort: try to take an exclusive lock; if it fails, the DB is busy.

    Note: an *idle* server may not hold a lock, so this can miss a running
    server. It is a guard, not a guarantee — stop the server before restoring.
    """
    if not db_path.exists():
        return False
    try:
        conn = sqlite3.connect(str(db_path), timeout=1.0)
        try:
            conn.execute("BEGIN EXCLUSIVE")
            conn.execute("ROLLBACK")
            return False
        finally:
            conn.close()
    except sqlite3.OperationalError:
        return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default=None, help="data directory (else JIQT_DATA_DIR / default)")
    parser.add_argument("--list", action="store_true", help="list available backups and exit")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--latest", action="store_true", help="restore the most recent backup")
    group.add_argument("--file", default=None, help="restore a specific backup filename")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args()

    config.configure_paths(args.data_dir)
    db_path = config.DB_PATH
    backups_dir = config.DATA_DIR / "backups"
    backups = list_backups(backups_dir)

    if args.list or (not args.latest and not args.file):
        print(f"data dir : {config.DATA_DIR}")
        print(f"live db  : {db_path}")
        print(f"backups  : {backups_dir}\n")
        print_backups(backups)
        if not args.list:
            print("\nChoose one with --latest or --file <name>.")
        return 0

    if not backups:
        print(f"No backups in {backups_dir}; nothing to restore.", file=sys.stderr)
        return 1

    # Resolve which backup to restore.
    if args.latest:
        chosen = backups[-1]
    else:
        chosen = backups_dir / args.file
        if not chosen.exists():
            print(f"Backup not found: {chosen}", file=sys.stderr)
            return 1

    # Safety: refuse if the DB looks in use.
    if db_is_locked(db_path):
        print(
            f"The database at {db_path} appears to be in use.\n"
            "Stop the server before restoring.",
            file=sys.stderr,
        )
        return 2

    print(f"About to restore:\n  from : {chosen}\n  into : {db_path}")
    if db_path.exists():
        print("  (the current database will first be snapshotted to backups/pre_restore_*.db)")
    if not args.yes:
        reply = input("Proceed? [y/N] ").strip().lower()
        if reply not in ("y", "yes"):
            print("Aborted.")
            return 0

    # Snapshot the current live DB first, so the restore is reversible.
    if db_path.exists() and db_path.stat().st_size > 0:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safety = backups_dir / f"pre_restore_{stamp}.db"
        backups_dir.mkdir(parents=True, exist_ok=True)
        try:
            src = sqlite3.connect(str(db_path))
            try:
                dst = sqlite3.connect(str(safety))
                try:
                    src.backup(dst)
                finally:
                    dst.close()
            finally:
                src.close()
            print(f"Current database saved to: {safety}")
        except Exception as exc:  # noqa: BLE001
            print(f"WARNING: could not snapshot current db ({exc}); continuing.", file=sys.stderr)

    # Swap the backup in and clear stale WAL sidecars.
    shutil.copy2(chosen, db_path)
    for sidecar in (Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        try:
            sidecar.unlink(missing_ok=True)
        except OSError:
            pass

    print(f"\nRestored. Live database is now {chosen.name}.")
    print("Start the server to use it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

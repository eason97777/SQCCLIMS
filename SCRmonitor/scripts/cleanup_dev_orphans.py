import argparse
import shutil
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "sample_testing.db"
RAW_UPLOAD_ROOT = ROOT / "data" / "uploads" / "raw_data"

COUNT_SQL = {
    "processing_jobs_null_raw_data_id": "SELECT COUNT(*) FROM processing_jobs WHERE raw_data_id IS NULL",
    "parsed_data_null_raw_data_id": "SELECT COUNT(*) FROM parsed_data WHERE raw_data_id IS NULL",
    "raw_data_files_orphan_raw_data": """
        SELECT COUNT(*)
        FROM raw_data_files rdf
        LEFT JOIN raw_data rd ON rd.id = rdf.raw_data_id
        WHERE rd.id IS NULL
    """,
    "parsed_data_orphan_raw_data": """
        SELECT COUNT(*)
        FROM parsed_data pd
        LEFT JOIN raw_data rd ON rd.id = pd.raw_data_id
        WHERE pd.raw_data_id IS NOT NULL AND rd.id IS NULL
    """,
    "processing_jobs_orphan_raw_data": """
        SELECT COUNT(*)
        FROM processing_jobs pj
        LEFT JOIN raw_data rd ON rd.id = pj.raw_data_id
        WHERE pj.raw_data_id IS NOT NULL AND rd.id IS NULL
    """,
}

DELETE_SQL = {
    "processing_jobs_null_raw_data_id": "DELETE FROM processing_jobs WHERE raw_data_id IS NULL",
    "parsed_data_null_raw_data_id": "DELETE FROM parsed_data WHERE raw_data_id IS NULL",
    "raw_data_files_orphan_raw_data": """
        DELETE FROM raw_data_files
        WHERE raw_data_id NOT IN (SELECT id FROM raw_data)
    """,
    "parsed_data_orphan_raw_data": """
        DELETE FROM parsed_data
        WHERE raw_data_id IS NOT NULL
          AND raw_data_id NOT IN (SELECT id FROM raw_data)
    """,
    "processing_jobs_orphan_raw_data": """
        DELETE FROM processing_jobs
        WHERE raw_data_id IS NOT NULL
          AND raw_data_id NOT IN (SELECT id FROM raw_data)
    """,
}


def fetch_counts(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {}
    for key, sql in COUNT_SQL.items():
        counts[key] = int(conn.execute(sql).fetchone()[0])
    return counts


def referenced_upload_dirs(conn: sqlite3.Connection) -> set[Path]:
    refs = set()
    for row in conn.execute("SELECT raw_data_code, storage_path FROM raw_data"):
        raw_data_code, storage_path = row
        if raw_data_code:
            refs.add((RAW_UPLOAD_ROOT / raw_data_code).resolve())
        if storage_path:
            refs.add((ROOT / storage_path).resolve())
    return refs


def orphan_upload_dirs(conn: sqlite3.Connection) -> list[Path]:
    if not RAW_UPLOAD_ROOT.exists():
        return []

    refs = referenced_upload_dirs(conn)
    orphans = []
    for item in RAW_UPLOAD_ROOT.iterdir():
        if item.is_dir() and item.resolve() not in refs:
            orphans.append(item)
    return sorted(orphans)


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean development orphan Raw Data records.")
    parser.add_argument("--apply", action="store_true", help="Actually delete orphan records and directories.")
    args = parser.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        before = fetch_counts(conn)
        orphans = orphan_upload_dirs(conn)

        print("mode:", "apply" if args.apply else "dry-run")
        print("before:")
        for key, value in before.items():
            print(f"  {key}: {value}")
        print("orphan_upload_dirs:")
        for path in orphans:
            print(f"  {path}")
        if not orphans:
            print("  none")

        if args.apply:
            for sql in DELETE_SQL.values():
                conn.execute(sql)
            conn.commit()

            raw_root = RAW_UPLOAD_ROOT.resolve()
            for path in orphans:
                resolved = path.resolve()
                if str(resolved).startswith(str(raw_root)) and resolved.exists():
                    shutil.rmtree(resolved, ignore_errors=True)

        after = fetch_counts(conn)
        remaining_orphans = orphan_upload_dirs(conn)

        print("after:")
        for key, value in after.items():
            print(f"  {key}: {value}")
        print("remaining_orphan_upload_dirs:")
        for path in remaining_orphans:
            print(f"  {path}")
        if not remaining_orphans:
            print("  none")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Regression smoke test for the SQCCLIMS backend.

Boots the server against a throwaway temp data directory (so the real
database is never touched), waits until it answers, exercises the key
read endpoints plus one create round-trip, then shuts the server down.

This is the loop's green-light oracle during the repo restructure: run it
before any change to capture a baseline, and after every change to prove
that no endpoint or core behaviour regressed.

Usage:
    python3 tests/smoke_test.py                 # auto-detect entrypoint
    python3 tests/smoke_test.py --server PATH    # explicit entrypoint
    python3 tests/smoke_test.py --port 8765      # fixed port

Exit code 0 = PASS, non-zero = FAIL.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP_ROOT = HERE.parent  # the SQCCLIMS app dir that contains server.py / app/


def find_entrypoint(explicit: str | None) -> Path:
    """Locate the server entrypoint, tolerating the restructure.

    Before the restructure the entrypoint is server.py; after it there may
    be a thin server.py or a run.py / app/main.py. We accept any of them so
    the same harness works across the whole loop.
    """
    if explicit:
        p = Path(explicit).resolve()
        if not p.exists():
            sys.exit(f"entrypoint not found: {p}")
        return p
    for candidate in ("server.py", "run.py", "main.py", "app/main.py"):
        p = APP_ROOT / candidate
        if p.exists():
            return p
    sys.exit("could not find a server entrypoint (looked for server.py/run.py/main.py)")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def http_get(url: str, timeout: float = 5.0):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, body


def http_post(url: str, payload: dict, timeout: float = 5.0):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, body


def http_delete(url: str, timeout: float = 5.0):
    req = urllib.request.Request(url, method="DELETE")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, body


def http_post_status(url: str, payload: dict, timeout: float = 10.0):
    """POST returning (status, body) even on a 4xx/5xx response, so the
    concurrency case can assert on contention/error status codes."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


# GET endpoints that must answer 200 with a JSON body on an empty database.
READ_ENDPOINTS = [
    "/api/summary",
    "/api/samples",
    "/api/test-data",
    "/api/raw-data",
    "/api/parsed-data",
    "/api/processing-jobs",
    "/api/mes-route-templates",
    "/api/characterization-files",
    "/api/performance-datasets",
    "/api/process-results",
]


def split_sql_statements(sql: str):
    """Yield complete SQL statements, honouring sqlite3.complete_statement so
    multi-line CTE/UPDATE statements stay intact. Mirrors the app's
    iter_sql_statements without importing app internals."""
    buffer: list[str] = []
    for line in sql.splitlines():
        buffer.append(line)
        candidate = "\n".join(buffer).strip()
        if candidate and sqlite3.complete_statement(candidate):
            yield candidate
            buffer = []
    remainder = "\n".join(buffer).strip()
    if remainder:
        yield remainder


def check_legacy_duplicate_migration() -> tuple[list[str], list[str]]:
    """003-concurrency-safety AC-006: seed duplicate sample_uids in a scratch DB,
    apply migrations/006_*.sql, and assert the duplicates are renumbered (earliest
    UID of each set preserved, all UIDs distinct, unique index created)."""
    passes: list[str] = []
    failures: list[str] = []
    mig = APP_ROOT / "migrations" / "006_samples_uid_unique.sql"
    if not mig.exists():
        return passes, [f"migration not found: {mig}"]
    try:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE samples (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "sample_uid TEXT NOT NULL DEFAULT '', created_at TEXT)"
        )
        seed = [
            ("SMP-2026-000001", "2026-01-01T10:00"),  # earliest -> keep
            ("SMP-2026-000001", "2026-01-02T10:00"),  # dup -> renumber
            ("SMP-2026-000001", "2026-01-03T10:00"),  # dup -> renumber
            ("SMP-2026-000002", "2026-01-04T10:00"),  # no dup
            ("", "2026-01-01T00:00"),                  # blank legacy
            ("", "2026-01-02T00:00"),                  # blank legacy (no collide)
        ]
        for uid, ca in seed:
            conn.execute("INSERT INTO samples (sample_uid, created_at) VALUES (?, ?)", (uid, ca))
        conn.commit()

        conn.execute("BEGIN")
        for stmt in split_sql_statements(mig.read_text(encoding="utf-8")):
            conn.execute(stmt)
        conn.execute("COMMIT")

        uids = [r["sample_uid"] for r in conn.execute(
            "SELECT sample_uid FROM samples WHERE sample_uid != '' ORDER BY id")]
        earliest = conn.execute("SELECT sample_uid FROM samples WHERE id = 1").fetchone()["sample_uid"]
        has_index = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_samples_uid_unique'"
        ).fetchone() is not None

        if len(uids) == len(set(uids)):
            passes.append("legacy-duplicate migration: all sample_uids distinct after renumber")
        else:
            failures.append(f"legacy-duplicate migration left duplicates: {uids}")
        if earliest == "SMP-2026-000001":
            passes.append("legacy-duplicate migration: earliest UID preserved")
        else:
            failures.append(f"earliest UID changed to {earliest} (expected SMP-2026-000001)")
        if has_index:
            passes.append("legacy-duplicate migration: idx_samples_uid_unique created")
        else:
            failures.append("idx_samples_uid_unique not created")
        conn.close()
    except Exception as exc:  # noqa: BLE001
        failures.append(f"legacy-duplicate migration raised {type(exc).__name__}: {exc}")
    return passes, failures


def check_measurements_view() -> tuple[list[str], list[str]]:
    """004 Phase 1 (AC-004/AC-006): apply migrations/007_measurements_view.sql to a
    scratch DB seeded with manual (test_data) and parsed (parsed_records) rows and
    assert the `measurements` view UNIONs both sources, derives the parsed
    metric_name per data_type (cd_sem composed from side/direction/row_group;
    resistance -> literal), excludes NULL numeric_value, and disambiguates the
    overlapping source ids via (source, source_row_id)."""
    passes: list[str] = []
    failures: list[str] = []
    mig = APP_ROOT / "migrations" / "007_measurements_view.sql"
    if not mig.exists():
        return passes, [f"migration not found: {mig}"]
    try:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE test_data (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "sample_id INTEGER, test_name TEXT, metric_name TEXT, numeric_value REAL, "
            "unit TEXT, measured_at TEXT, created_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE parsed_records (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "sample_id INTEGER, data_type TEXT, numeric_value REAL, side TEXT, "
            "direction TEXT, row_group TEXT, created_at TEXT)"
        )
        conn.execute(
            "INSERT INTO test_data (sample_id, test_name, metric_name, numeric_value, "
            "unit, measured_at, created_at) VALUES (1, 'resistance', 'Rs', 12.5, 'ohm', 't', 't')"
        )
        conn.executemany(
            "INSERT INTO parsed_records (sample_id, data_type, numeric_value, side, "
            "direction, row_group, created_at) VALUES (?, ?, ?, ?, ?, ?, 't')",
            [
                (1, "resistance", 34.0, "", "", ""),      # id=1: overlaps the manual id
                (1, "cd_sem", 5.0, "left", "x", "row1"),  # id=2: composed metric label
                (1, "cd_sem", None, "left", "x", "row2"), # id=3: NULL value -> excluded
            ],
        )
        conn.commit()

        conn.execute("BEGIN")
        for stmt in split_sql_statements(mig.read_text(encoding="utf-8")):
            conn.execute(stmt)
        conn.execute("COMMIT")

        rows = list(conn.execute(
            "SELECT source, source_row_id, metric_name, numeric_value "
            "FROM measurements ORDER BY source, source_row_id"))
        got = [(r["source"], r["source_row_id"], r["metric_name"], r["numeric_value"]) for r in rows]

        if ("manual", 1, "Rs", 12.5) in got:
            passes.append("measurements view: manual (test_data) row unioned")
        else:
            failures.append(f"measurements view missing manual row: {got}")

        parsed_metrics = sorted(m for s, _, m, _ in got if s == "parsed")
        if parsed_metrics == ["cd_sem/left/x row1", "resistance"]:
            passes.append("measurements view: parsed metric_name derived (cd_sem composed, resistance literal)")
        else:
            failures.append(f"measurements view parsed metric_name wrong: {parsed_metrics}")

        if len(got) == 3 and all(v is not None for _, _, _, v in got):
            passes.append("measurements view: NULL numeric_value excluded")
        else:
            failures.append(f"measurements view did not exclude NULL numeric_value: {got}")

        idents = {(s, i) for s, i, _, _ in got}
        if ("manual", 1) in idents and ("parsed", 1) in idents:
            passes.append("measurements view: overlapping ids disambiguated by source")
        else:
            failures.append(f"measurements view identity not disambiguated: {idents}")
        conn.close()
    except Exception as exc:  # noqa: BLE001
        failures.append(f"measurements view check raised {type(exc).__name__}: {exc}")
    return passes, failures


def check_artifacts_view() -> tuple[list[str], list[str]]:
    """004 Phase 2a (AC-007): apply migrations/008_artifacts_view.sql to a scratch
    DB seeded with a raw_data row and a performance_datasets row, and assert the
    `artifacts` view UNIONs both, maps the performance branch into raw_data's shape
    (PERF-<id> code, total_bytes->total_size, storage_dir->storage_path,
    collected_at->measured_at, orphan fields -> json_object metadata_json), and
    disambiguates the overlapping ids via (source, source_row_id)."""
    passes: list[str] = []
    failures: list[str] = []
    mig = APP_ROOT / "migrations" / "008_artifacts_view.sql"
    if not mig.exists():
        return passes, [f"migration not found: {mig}"]
    try:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE samples (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                     "sample_uid TEXT, sample_display_code TEXT)")
        conn.execute(
            "CREATE TABLE raw_data (id INTEGER PRIMARY KEY AUTOINCREMENT, sample_id INTEGER, "
            "sample_uid TEXT, sample_display_code TEXT, raw_data_code TEXT, raw_data_name TEXT, "
            "data_type TEXT, data_category TEXT, source_type TEXT, instrument TEXT, operator TEXT, "
            "measured_at TEXT, parser_status TEXT, status TEXT, file_count INTEGER, total_size INTEGER, "
            "storage_path TEXT, metadata_json TEXT, notes TEXT, created_at TEXT, updated_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE performance_datasets (id INTEGER PRIMARY KEY AUTOINCREMENT, sample_id INTEGER, "
            "aliquot_code TEXT, dataset_name TEXT, test_type TEXT, data_format TEXT, source_folder_name TEXT, "
            "storage_dir TEXT, file_count INTEGER, total_bytes INTEGER, collected_at TEXT, operator TEXT, "
            "status TEXT, notes TEXT, created_at TEXT)"
        )
        conn.execute("INSERT INTO samples (sample_uid, sample_display_code) VALUES ('SMP-2026-000001', 'WFR-1')")
        conn.execute("INSERT INTO raw_data (sample_id, raw_data_code, raw_data_name, data_type, "
                     "data_category, file_count, total_size, created_at, updated_at) "
                     "VALUES (1, 'RD-1', 'res', 'resistance', 'electrical', 2, 1024, 't', 't')")
        conn.execute("INSERT INTO performance_datasets (sample_id, aliquot_code, dataset_name, test_type, "
                     "data_format, source_folder_name, storage_dir, file_count, total_bytes, collected_at, "
                     "operator, status, notes, created_at) "
                     "VALUES (1, 'AQ-9', 'perf-run', 'iv', 'csv', 'fld', 'perf/x', 3, 2048, '2026-07-02', "
                     "'ana', 'p', 'n', 't')")
        conn.commit()

        conn.execute("BEGIN")
        for stmt in split_sql_statements(mig.read_text(encoding="utf-8")):
            conn.execute(stmt)
        conn.execute("COMMIT")

        rows = {r["source"]: dict(r) for r in conn.execute(
            "SELECT source, source_row_id, raw_data_code, data_type, total_size, "
            "storage_path, measured_at, metadata_json FROM artifacts")}

        rd = rows.get("raw_data", {})
        if rd.get("raw_data_code") == "RD-1" and rd.get("source_row_id") == 1:
            passes.append("artifacts view: raw_data branch projected 1:1")
        else:
            failures.append(f"artifacts view raw_data branch wrong: {rd}")

        pf = rows.get("performance", {})
        if (pf.get("raw_data_code") == "PERF-1" and pf.get("data_type") == "performance"
                and pf.get("total_size") == 2048 and pf.get("storage_path") == "perf/x"
                and pf.get("measured_at") == "2026-07-02"):
            passes.append("artifacts view: performance branch mapped into raw_data shape")
        else:
            failures.append(f"artifacts view performance mapping wrong: {pf}")

        try:
            md = json.loads(pf.get("metadata_json") or "{}")
        except (TypeError, ValueError):
            md = {}
        if md == {"aliquot_code": "AQ-9", "test_type": "iv", "data_format": "csv", "source_folder_name": "fld"}:
            passes.append("artifacts view: performance orphan fields folded into metadata_json")
        else:
            failures.append(f"artifacts view metadata_json fold wrong: {md}")

        idents = {(r["source"], r["source_row_id"]) for r in conn.execute(
            "SELECT source, source_row_id FROM artifacts")}
        if ("raw_data", 1) in idents and ("performance", 1) in idents:
            passes.append("artifacts view: overlapping ids disambiguated by source")
        else:
            failures.append(f"artifacts view identity not disambiguated: {idents}")
        conn.close()
    except Exception as exc:  # noqa: BLE001
        failures.append(f"artifacts view check raised {type(exc).__name__}: {exc}")
    return passes, failures


def wait_until_ready(base: str, proc: subprocess.Popen, timeout: float = 25.0) -> None:
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        if proc.poll() is not None:
            out = (proc.stdout.read() if proc.stdout else "") or ""
            raise SystemExit(f"server exited early (code {proc.returncode}):\n{out}")
        try:
            status, _ = http_get(base + "/api/summary", timeout=2.0)
            if status == 200:
                return
        except (urllib.error.URLError, ConnectionError, OSError) as exc:
            last_err = exc
            time.sleep(0.4)
    raise SystemExit(f"server did not become ready within {timeout}s (last: {last_err})")


def run() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default=None, help="path to server entrypoint")
    parser.add_argument("--port", type=int, default=None, help="fixed port (default: random free port)")
    args = parser.parse_args()

    entrypoint = find_entrypoint(args.server)
    port = args.port or free_port()
    base = f"http://127.0.0.1:{port}"

    failures: list[str] = []
    passes: list[str] = []

    # In-process migration check (no server needed): AC-006 legacy-duplicate
    # renumber + unique index.
    mig_passes, mig_failures = check_legacy_duplicate_migration()
    passes.extend(mig_passes)
    failures.extend(mig_failures)

    # 004 Phase 1: the measurements read model (in-process; no server needed).
    mv_passes, mv_failures = check_measurements_view()
    passes.extend(mv_passes)
    failures.extend(mv_failures)

    # 004 Phase 2a: the artifacts read model (in-process; no server needed).
    av_passes, av_failures = check_artifacts_view()
    passes.extend(av_passes)
    failures.extend(av_failures)

    with tempfile.TemporaryDirectory(prefix="sqcclims-smoke-") as tmp:
        env = dict(os.environ)
        env["LIMS_DATA_DIR"] = tmp
        env["LIMS_HOST"] = "127.0.0.1"
        env["PORT"] = str(port)
        # Disable auth for the smoke test if the app honours this flag (added
        # during the restructure); harmless on the pre-restructure server.
        env["LIMS_AUTH_DISABLED"] = "1"

        print(f"[smoke] entrypoint = {entrypoint}")
        print(f"[smoke] temp data dir = {tmp}")
        print(f"[smoke] port = {port}")

        proc = subprocess.Popen(
            [sys.executable, str(entrypoint),
             "--host", "127.0.0.1", "--port", str(port), "--data-dir", tmp],
            cwd=str(APP_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            wait_until_ready(base, proc)
            print("[smoke] server is ready\n")

            # 1) Read endpoints --------------------------------------------
            for path in READ_ENDPOINTS:
                try:
                    status, body = http_get(base + path)
                    json.loads(body)  # must be valid JSON
                    if status == 200:
                        passes.append(f"GET {path} -> 200")
                    else:
                        failures.append(f"GET {path} -> {status} (expected 200)")
                except Exception as exc:  # noqa: BLE001 - report any failure
                    failures.append(f"GET {path} raised {type(exc).__name__}: {exc}")

            # 2) Create round-trip: a sample -------------------------------
            created_code = None
            try:
                payload = {
                    "sample_code": "SMOKE",
                    "name": "smoke-sample",
                    "category": "test",
                    "batch": "B1",
                }
                status, body = http_post(base + "/api/samples", payload)
                if status in (200, 201):
                    created = json.loads(body)
                    created_id = created.get("id")
                    passes.append(f"POST /api/samples -> {status}")
                else:
                    failures.append(f"POST /api/samples -> {status} (expected 200/201)")
            except Exception as exc:  # noqa: BLE001
                failures.append(f"POST /api/samples raised {type(exc).__name__}: {exc}")

            # 3) Verify the sample is listed -------------------------------
            try:
                status, body = http_get(base + "/api/samples")
                rows = json.loads(body)
                count = len(rows) if isinstance(rows, list) else len(rows.get("items", []))
                if count >= 1:
                    passes.append("GET /api/samples reflects created sample")
                else:
                    failures.append("created sample not reflected in /api/samples list")
            except Exception as exc:  # noqa: BLE001
                failures.append(f"sample readback raised {type(exc).__name__}: {exc}")

            # 3b) 004 Phase 1: Analysis (/api/process) reads the measurements view.
            # Seed a manual measurement on the sample, run stats, and assert the
            # persisted result carries source_count (the repointed, view-backed path).
            if created_id is not None:
                try:
                    http_post(base + "/api/test-data", {
                        "sample_id": created_id, "test_name": "resistance",
                        "metric_name": "Rs", "numeric_value": "12.5", "unit": "ohm",
                    })
                    status, body = http_post(base + "/api/process", {
                        "method": "stats", "sample_id": created_id,
                    })
                    result_row = json.loads(body)
                    result = json.loads(result_row.get("result_json", "{}"))
                    if status in (200, 201) and "source_count" in result:
                        passes.append("POST /api/process (view-backed Analysis) -> source_count present")
                    else:
                        failures.append(f"/api/process view-backed path -> {status} / {result}")
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"/api/process check raised {type(exc).__name__}: {exc}")

            # 4) Cascade-preview endpoint ----------------------------------
            if created_id is not None:
                try:
                    status, body = http_get(base + f"/api/samples/{created_id}/delete-preview")
                    preview = json.loads(body)
                    if status == 200 and "files_total" in preview and "parsed_records" in preview:
                        passes.append("GET /api/samples/{id}/delete-preview -> 200 with counts")
                    else:
                        failures.append(f"delete-preview -> {status} / unexpected body {preview}")
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"delete-preview raised {type(exc).__name__}: {exc}")

            # 5) Delete round-trip (exercises backup + file cleanup + audit)
            if created_id is not None:
                try:
                    status, body = http_delete(base + f"/api/samples/{created_id}")
                    if status in (200, 204):
                        passes.append(f"DELETE /api/samples/{{id}} -> {status}")
                        # confirm it is gone from the list
                        _, lb = http_get(base + "/api/samples")
                        rows = json.loads(lb)
                        items = rows if isinstance(rows, list) else rows.get("items", [])
                        if not any(r.get("id") == created_id for r in items):
                            passes.append("deleted sample no longer listed")
                        else:
                            failures.append("deleted sample still appears in list")
                    else:
                        failures.append(f"DELETE /api/samples/{{id}} -> {status} (expected 200/204)")
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"DELETE raised {type(exc).__name__}: {exc}")

            # 6) Concurrency case (003-concurrency-safety AC-001/002/003) ---
            # Fire N simultaneous POST /api/samples with distinct identities;
            # assert every response is 2xx (zero 500s/503s) and every returned
            # sample_uid is DISTINCT. Exercises busy_timeout + BEGIN IMMEDIATE +
            # the UID-collision retry loop and the unique index.
            try:
                n = 10

                def create_one(i):
                    payload = {
                        "sample_code": "CONC",
                        "name": "conc-sample",
                        "category": "test",
                        "batch": f"C{i:03d}",  # distinct -> distinct display code
                    }
                    return http_post_status(base + "/api/samples", payload)

                with ThreadPoolExecutor(max_workers=n) as pool:
                    results = list(pool.map(create_one, range(n)))

                statuses = [s for s, _ in results]
                bad = [s for s in statuses if s not in (200, 201)]
                uids = []
                for s, b in results:
                    if s in (200, 201):
                        try:
                            uids.append(json.loads(b).get("sample_uid"))
                        except Exception:  # noqa: BLE001
                            pass

                if bad:
                    failures.append(
                        f"concurrent POST /api/samples: {len(bad)}/{n} non-2xx "
                        f"(statuses={statuses})"
                    )
                else:
                    passes.append(f"concurrent POST /api/samples: all {n} -> 2xx")

                if len(uids) == n and len(set(uids)) == n and all(uids):
                    passes.append(f"concurrent creates yielded {n} DISTINCT sample_uids")
                else:
                    failures.append(
                        f"concurrent sample_uids not all-distinct/present: "
                        f"{len(set(uids))} distinct of {len(uids)} (n={n})"
                    )
            except Exception as exc:  # noqa: BLE001
                failures.append(f"concurrency case raised {type(exc).__name__}: {exc}")

        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    # Report -----------------------------------------------------------------
    print("\n=== SMOKE RESULTS ===")
    for p in passes:
        print(f"  PASS  {p}")
    for f in failures:
        print(f"  FAIL  {f}")
    print(f"\n{len(passes)} passed, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())

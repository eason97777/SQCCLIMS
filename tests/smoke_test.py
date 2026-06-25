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

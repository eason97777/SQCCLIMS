#!/usr/bin/env python3
"""Regression smoke test for the SCRmonitor backend.

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
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP_ROOT = HERE.parent  # the SCRmonitor app dir that contains server.py / app/


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

    with tempfile.TemporaryDirectory(prefix="scrmonitor-smoke-") as tmp:
        env = dict(os.environ)
        env["JIQT_DATA_DIR"] = tmp
        env["JIQT_HOST"] = "127.0.0.1"
        env["PORT"] = str(port)
        # Disable auth for the smoke test if the app honours this flag (added
        # during the restructure); harmless on the pre-restructure server.
        env["JIQT_AUTH_DISABLED"] = "1"

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
                    created_code = created.get("sample_display_code") or created.get("sample_uid")
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

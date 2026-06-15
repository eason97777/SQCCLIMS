#!/usr/bin/env python3
"""Thin entrypoint for the sample testing center backend.

The implementation lives in the ``app`` package; this module only parses
arguments / environment, configures paths, prepares directories, initialises
the database, runs migrations, and starts the HTTP server.
"""
import argparse
import os
from http.server import ThreadingHTTPServer

import app.config as config
from app.backup import backup_database
from app.logging_setup import setup_logging
from app.migrations import init_db, run_migrations
from app.http.handler import AppHandler


def main():
    parser = argparse.ArgumentParser(description="Sample testing information management center")
    parser.add_argument("--host", default=os.environ.get("LIMS_HOST", "0.0.0.0"))
    parser.add_argument("--port", default=int(os.environ.get("PORT", "8000")), type=int)
    parser.add_argument("--data-dir", default=os.environ.get("LIMS_DATA_DIR"), help="Directory for database, uploads, outputs, backups and logs")
    args = parser.parse_args()

    config.configure_paths(args.data_dir)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = setup_logging()
    init_db()
    run_migrations()
    backup_database()
    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    logger.info("starting server host=%s port=%s db=%s", args.host, args.port, config.DB_PATH)
    print(f"Serving sample testing center at http://{args.host}:{args.port}")
    print(f"SQLite database: {config.DB_PATH}")

    # Write a pidfile so restore tooling can reliably detect a running server.
    # It is removed on clean shutdown; a lingering pidfile after a crash is
    # acceptable (restore_db.py verifies the PID is actually alive).
    pidfile = config.DATA_DIR / "server.pid"
    try:
        pidfile.write_text(str(os.getpid()), encoding="utf-8")
    except OSError as exc:
        logger.warning("could not write pidfile %s: %s", pidfile, exc)

    try:
        server.serve_forever()
    finally:
        try:
            pidfile.unlink(missing_ok=True)
        except OSError:
            pass


if __name__ == "__main__":
    main()

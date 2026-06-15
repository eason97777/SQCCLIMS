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
from app.migrations import init_db, run_migrations
from app.http.handler import AppHandler


def main():
    parser = argparse.ArgumentParser(description="Sample testing information management center")
    parser.add_argument("--host", default=os.environ.get("JIQT_HOST", "0.0.0.0"))
    parser.add_argument("--port", default=int(os.environ.get("PORT", "8000")), type=int)
    parser.add_argument("--data-dir", default=os.environ.get("JIQT_DATA_DIR"), help="Directory for database, uploads, outputs, backups and logs")
    args = parser.parse_args()

    config.configure_paths(args.data_dir)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    run_migrations()
    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    print(f"Serving sample testing center at http://{args.host}:{args.port}")
    print(f"SQLite database: {config.DB_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()

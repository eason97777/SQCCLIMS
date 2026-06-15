"""Append-only, content-addressed upload archive.

Every file accepted by an upload endpoint is copied into a content-addressed
archive keyed by its SHA-256 hash. Identical content is stored once (dedup),
while every upload event is recorded in an append-only manifest for
traceability. Archiving is a best-effort side-effect: it must never break an
upload, so all failures are swallowed (logged) and ``None`` is returned.

Config paths are read at call time (``config.ARCHIVE_DIR``) so the
``configure_paths()`` runtime reassignment is respected.
"""
import json
import logging
import shutil
from pathlib import Path

import app.config as config
from app.storage import file_sha256
from app.validation import now_iso


logger = logging.getLogger("sqcclims")


def archive_file(src_path, sha256=None, original_filename=None, source=None):
    try:
        src = Path(src_path).resolve()
        if not src.exists():
            logger.warning("archive_file: source does not exist: %s", src)
            return None

        if not sha256:
            sha256 = file_sha256(src)

        name_for_ext = original_filename or src.name
        extension = Path(name_for_ext).suffix

        archive_dir = config.ARCHIVE_DIR
        dest_dir = archive_dir / sha256[:2]
        dest = dest_dir / (sha256 + extension)
        dest_dir.mkdir(parents=True, exist_ok=True)

        if not dest.exists():
            shutil.copy2(src, dest)

        try:
            stored_path = str(dest.relative_to(archive_dir))
        except ValueError:
            stored_path = str(dest)

        manifest_entry = {
            "sha256": sha256,
            "original_filename": original_filename,
            "stored_path": stored_path,
            "source": source,
            "archived_at": now_iso(),
        }
        manifest_path = archive_dir / "manifest.jsonl"
        with manifest_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(manifest_entry, ensure_ascii=False) + "\n")

        return dest
    except Exception as exc:  # noqa: BLE001 - archiving must never break an upload
        logger.warning("archive_file failed for %s: %s", src_path, exc)
        return None

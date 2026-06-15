#!/usr/bin/env python3
"""Recover a file from the upload archive back to a chosen location.

The upload archive (``app/archive.py``) is content-addressed: every accepted
file is copied to ``ARCHIVE_DIR/<sha[:2]>/<sha><ext>`` and recorded in an
append-only ``ARCHIVE_DIR/manifest.jsonl``. That feature has capture but no
restore; this script is the missing restore half.

It is strictly read-only with respect to the archive: it never deletes or
modifies anything under ARCHIVE_DIR, it only copies a blob out.

Usage:
    # List everything in the archive (optionally filter by filename substring):
    python3 scripts/restore_file.py --list
    python3 scripts/restore_file.py --list --name report

    # Restore by SHA (most precise) to the current directory:
    python3 scripts/restore_file.py --sha <hash>

    # Restore by original filename (exact or substring) to a chosen path:
    python3 scripts/restore_file.py --name results.csv --out /tmp/recovered.csv
    python3 scripts/restore_file.py --name results.csv --out /tmp/  # dir -> uses original name

    # Overwrite an existing destination:
    python3 scripts/restore_file.py --sha <hash> --out existing.bin --force
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

# Make the app package importable (this script lives in <app>/scripts/).
APP_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_ROOT))

import app.config as config  # noqa: E402


def load_manifest(manifest_path: Path):
    """Return a list of manifest entries (dicts), oldest first.

    Malformed lines are skipped with a warning rather than aborting the whole
    listing, since the manifest is append-only and a partial write could in
    principle leave a trailing broken line.
    """
    entries = []
    if not manifest_path.exists():
        return entries
    with manifest_path.open("r", encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                print(
                    f"WARNING: skipping malformed manifest line {lineno}.",
                    file=sys.stderr,
                )
    return entries


def filter_by_name(entries, name: str, exact: bool = False):
    needle = name.lower()
    out = []
    for e in entries:
        original = (e.get("original_filename") or "")
        haystack = original.lower()
        if (haystack == needle) if exact else (needle in haystack):
            out.append(e)
    return out


def print_entries(entries):
    if not entries:
        print("No matching archive entries.")
        return
    print(f"{'sha256':64}  {'archived_at':25}  {'source':12}  original_filename")
    for e in entries:
        sha = (e.get("sha256") or "")
        archived_at = (e.get("archived_at") or "")
        source = (e.get("source") or "")
        original = (e.get("original_filename") or "")
        print(f"{sha:64}  {archived_at:25}  {source:12}  {original}")


def resolve_blob_path(entry, archive_dir: Path) -> Path:
    """Resolve the on-disk blob for a manifest entry.

    Prefers the recorded ``stored_path`` (relative to ARCHIVE_DIR), falling
    back to reconstructing it from the sha + extension of the original name.
    """
    stored = entry.get("stored_path")
    if stored:
        candidate = Path(stored)
        if not candidate.is_absolute():
            candidate = archive_dir / candidate
        if candidate.exists():
            return candidate
    sha = entry.get("sha256") or ""
    ext = Path(entry.get("original_filename") or "").suffix
    return archive_dir / sha[:2] / (sha + ext)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--data-dir", default=None, help="data directory (else JIQT_DATA_DIR / default)")
    parser.add_argument("--list", action="store_true", help="list manifest entries and exit")
    parser.add_argument("--name", default=None, help="select/filter by original_filename (substring)")
    parser.add_argument("--sha", default=None, help="select by exact sha256 hash")
    parser.add_argument("--out", default=None, help="destination file path or directory (default: cwd/<original_filename>)")
    parser.add_argument("--force", action="store_true", help="overwrite an existing destination")
    args = parser.parse_args()

    config.configure_paths(args.data_dir)
    archive_dir = config.ARCHIVE_DIR
    manifest_path = archive_dir / "manifest.jsonl"
    entries = load_manifest(manifest_path)

    # --list mode: show entries (optionally filtered by --name) and exit.
    if args.list:
        print(f"data dir : {config.DATA_DIR}")
        print(f"archive  : {archive_dir}")
        print(f"manifest : {manifest_path}\n")
        shown = filter_by_name(entries, args.name) if args.name else entries
        print_entries(shown)
        return 0

    if not entries:
        print(f"No archive manifest entries in {manifest_path}; nothing to restore.", file=sys.stderr)
        return 1

    # Selection: --sha (precise) or --name (exact-or-substring).
    if not args.sha and not args.name:
        print("Specify what to restore with --sha <hash> or --name <filename>, or use --list.", file=sys.stderr)
        return 1

    chosen = None
    if args.sha:
        matches = [e for e in entries if (e.get("sha256") or "") == args.sha]
        if not matches:
            print(f"No archive entry with sha256 {args.sha}.", file=sys.stderr)
            return 1
        chosen = matches[-1]  # most recent manifest record for this content
    else:
        # Try exact filename match first, fall back to substring.
        matches = filter_by_name(entries, args.name, exact=True)
        if not matches:
            matches = filter_by_name(entries, args.name, exact=False)
        if not matches:
            print(f"No archive entry whose filename matches '{args.name}'.", file=sys.stderr)
            return 1
        # Disambiguate by distinct content (sha).
        distinct_shas = {e.get("sha256") for e in matches}
        if len(distinct_shas) > 1:
            print(
                f"'{args.name}' matches multiple distinct files; "
                "re-run with --sha <hash> to choose one:\n",
                file=sys.stderr,
            )
            print_entries(matches)
            return 1
        chosen = matches[-1]

    blob = resolve_blob_path(chosen, archive_dir)
    if not blob.exists():
        print(f"Archived blob is missing on disk: {blob}", file=sys.stderr)
        return 1

    # Resolve the destination.
    original = chosen.get("original_filename") or (chosen.get("sha256") or "restored")
    if args.out:
        dest = Path(args.out).expanduser()
        if dest.is_dir() or args.out.endswith(("/", "\\")):
            dest = dest / original
    else:
        dest = Path.cwd() / original
    dest = dest.resolve()

    if dest.exists() and not args.force:
        print(f"Destination already exists: {dest}\nUse --force to overwrite.", file=sys.stderr)
        return 1

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(blob, dest)

    print("Restored a file from the archive:")
    print(f"  sha256   : {chosen.get('sha256')}")
    print(f"  original : {original}")
    print(f"  from     : {blob}")
    print(f"  to       : {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

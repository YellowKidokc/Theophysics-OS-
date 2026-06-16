"""Background inventory runner for FIS.

This scans paths, folder structure, extensions, and organization findings into
the shared SQLite cache. It does not classify content and does not change files.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from sorter_cache import scan_inventory


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a background FIS inventory scan.")
    parser.add_argument("root", help="Folder to inventory.")
    parser.add_argument("--max", type=int, default=1000000, help="Maximum files to cache.")
    parser.add_argument("--top-only", action="store_true", help="Do not scan recursively.")
    parser.add_argument("--follow-links", action="store_true", help="Follow symlinks/reparse links.")
    parser.add_argument("--hash", action="store_true", help="Compute and cache MD5 hashes while scanning.")
    args = parser.parse_args()

    started = time.perf_counter()
    result = scan_inventory(
        str(Path(args.root)),
        max_files=args.max,
        recursive=not args.top_only,
        follow_links=args.follow_links,
        compute_hash=args.hash,
    )
    elapsed = time.perf_counter() - started
    result["elapsed_seconds"] = round(elapsed, 2)
    result["files_per_second"] = round((result.get("file_count") or 0) / elapsed, 3) if elapsed else 0
    print(result)


if __name__ == "__main__":
    main()

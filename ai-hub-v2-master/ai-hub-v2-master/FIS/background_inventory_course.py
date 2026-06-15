"""Run segmented FIS inventory jobs one at a time.

Each path is registered as its own root before scanning so SQLite can keep the
cache segmented by source area.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from sorter_cache import register_root, scan_inventory


DEFAULT_ROOTS = [
    ("OD_B", r"B:\CLoud Accounts\OneDrive", "OneDrive on B drive"),
    ("Z_DRIVE", r"Z:\\", "Z drive"),
    ("T_DRIVE", r"T:\\", "T drive"),
    ("HP_DOCS", r"C:\Users\lowes\Documents", "HP Documents"),
    ("HP_DESKTOP", r"C:\Users\lowes\Desktop", "HP Desktop"),
]


def run_course(max_files: int, skip_existing_onedrive: bool) -> dict:
    started = time.perf_counter()
    results = []
    for code, path_text, label in DEFAULT_ROOTS:
        path = Path(path_text)
        root_record = register_root(code, str(path), label=label, purpose="segmented_inventory")
        if skip_existing_onedrive and code == "OD_B":
            results.append({"root_code": code, "path": str(path), "status": "registered_only", "root": root_record})
            print(json.dumps(results[-1], ensure_ascii=True), flush=True)
            continue
        if not path.exists():
            results.append({"root_code": code, "path": str(path), "status": "missing", "root": root_record})
            print(json.dumps(results[-1], ensure_ascii=True), flush=True)
            continue
        job_started = time.perf_counter()
        print(json.dumps({"root_code": code, "path": str(path), "status": "scan_started"}, ensure_ascii=True), flush=True)
        result = scan_inventory(str(path), max_files=max_files, recursive=True, follow_links=False)
        result["root_code"] = code
        result["elapsed_seconds"] = round(time.perf_counter() - job_started, 2)
        results.append(result)
        print(json.dumps(result, ensure_ascii=True), flush=True)
    return {
        "status": "complete",
        "root_count": len(DEFAULT_ROOTS),
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run segmented FIS inventory course.")
    parser.add_argument("--max-per-root", type=int, default=1000000)
    parser.add_argument("--skip-existing-onedrive", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_course(args.max_per_root, args.skip_existing_onedrive), ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()

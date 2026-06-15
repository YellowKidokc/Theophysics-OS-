"""Background FIS enrichment runner.

This classifies cached files and records progress in the shared SQLite cache.
It is additive: no files are moved, renamed, or deleted.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from auto_sort import classify_file
from naming_engine import NamingEngine, clean_filename
from preference_engine import get_auto_approve_threshold
from sorter_cache import (
    cache_classification,
    cached_file_paths,
    finish_scan,
    record_action,
    start_scan,
    update_action_status,
    update_scan_progress,
)


def short_summary(result: dict) -> str:
    if result.get("nlp_summary"):
        return str(result["nlp_summary"]).strip()
    keywords = [item.get("keyword") for item in result.get("keywords", [])[:4] if item.get("keyword")]
    domain = result.get("classification", {}).get("domain", "UNCATEGORIZED")
    if keywords:
        return f"{result.get('filename', 'This file')} appears related to {', '.join(keywords)} in {domain}."
    return f"{result.get('filename', 'This file')} is a {result.get('ext') or 'file'} currently classified as {domain}."


def enrich(root: str, limit: int, use_nlp: bool, only_unclassified: bool, progress_every: int) -> dict:
    started = time.perf_counter()
    paths = cached_file_paths(root=root, limit=limit, only_unclassified=only_unclassified)
    action = record_action(
        "background_enrich",
        target_path=root,
        status="running",
        payload={
            "root": root,
            "limit": limit,
            "use_nlp": use_nlp,
            "only_unclassified": only_unclassified,
            "candidate_count": len(paths),
        },
    )
    scan_id = start_scan(root, mode="background_enrich", top_only=False, use_nlp=use_nlp)
    engine = NamingEngine()
    threshold = get_auto_approve_threshold()
    processed = 0
    errors = 0
    last_error = ""

    try:
        for filepath in paths:
            try:
                result = classify_file(filepath, use_nlp=use_nlp, use_markov=True)
                if "error" in result:
                    errors += 1
                    last_error = result["error"]
                    continue
                classification = result["classification"]
                file_info = {
                    "filename": result["filename"],
                    "ext": result["ext"],
                    "domain": classification["domain"],
                    "domain_code": classification.get("code", ""),
                    "keywords": [item["keyword"] for item in result.get("keywords", [])[:4]],
                }
                markov = result.get("markov_prediction") or {}
                entry = {
                    "filepath": result["filepath"],
                    "filename": result["filename"],
                    "ext": result["ext"],
                    "size": result["size"],
                    "baseline": clean_filename(result["filename"]),
                    "summary": short_summary(result),
                    "domain": classification["domain"],
                    "domain_code": classification.get("code", ""),
                    "confidence": classification.get("confidence", 0),
                    "source": classification.get("source", "yake"),
                    "matched": classification.get("matched", []),
                    "keywords": [item["keyword"] for item in result.get("keywords", [])[:8]],
                    "text_preview": result.get("text_preview", "")[:200],
                    "nlp_result": result.get("nlp_result"),
                    "nlp_summary": result.get("nlp_summary"),
                    "review": {
                        "needs_review": classification.get("confidence", 0) < threshold,
                        "reason": "confidence below threshold" if classification.get("confidence", 0) < threshold else "",
                    },
                    "names": {
                        "baseline": clean_filename(result["filename"]),
                        "presets": engine.preview_all_presets(file_info),
                    },
                    "markov": {
                        "domain": markov.get("domain"),
                        "confidence": markov.get("confidence"),
                        "training_size": markov.get("training_size", 0),
                    } if markov else {},
                }
                cache_classification(scan_id, entry)
                processed += 1
            except Exception as exc:
                errors += 1
                last_error = str(exc)

            if processed and processed % progress_every == 0:
                update_scan_progress(scan_id, processed)
                elapsed = time.perf_counter() - started
                rate = processed / elapsed if elapsed else 0
                print(f"[FIS] {processed}/{len(paths)} enriched at {rate:.2f} files/sec")

        elapsed = time.perf_counter() - started
        finish_scan(scan_id, processed, status="complete" if errors == 0 else "complete_with_errors", error=last_error or None)
        update_action_status(
            action["action_id"],
            "complete" if errors == 0 else "complete_with_errors",
            {"scan_id": scan_id, "processed": processed, "errors": errors, "elapsed_seconds": round(elapsed, 2)},
        )
        return {
            "action_code": action["action_code"],
            "scan_id": scan_id,
            "root": root,
            "candidate_count": len(paths),
            "processed": processed,
            "errors": errors,
            "elapsed_seconds": round(elapsed, 2),
            "files_per_second": round(processed / elapsed, 3) if elapsed else 0,
        }
    except KeyboardInterrupt:
        elapsed = time.perf_counter() - started
        finish_scan(scan_id, processed, status="interrupted", error="Interrupted by user or process stop.")
        update_action_status(
            action["action_id"],
            "interrupted",
            {"scan_id": scan_id, "processed": processed, "errors": errors, "elapsed_seconds": round(elapsed, 2)},
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Run background FIS enrichment over cached files.")
    parser.add_argument("root", help="Root folder path already present in the cache.")
    parser.add_argument("--limit", type=int, default=250000, help="Maximum cached files to enrich.")
    parser.add_argument("--nlp", action="store_true", help="Use heavier NLP models on low-confidence readable files.")
    parser.add_argument("--all", action="store_true", help="Re-enrich files even if they already have classifications.")
    parser.add_argument("--progress-every", type=int, default=100, help="Update progress every N processed files.")
    args = parser.parse_args()
    result = enrich(
        str(Path(args.root)),
        limit=args.limit,
        use_nlp=args.nlp,
        only_unclassified=not args.all,
        progress_every=max(1, args.progress_every),
    )
    print(result)


if __name__ == "__main__":
    main()

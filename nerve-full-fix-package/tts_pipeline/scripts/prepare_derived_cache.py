"""
Prepare cached derived artifacts for Quartz + TTS.

Creates:
  - Quartz-ready markdown (clean title/body, no frontmatter)
  - TTS-ready normalized text
  - Manifest cache keyed by source file hash

This lets future publish runs skip unchanged files.
"""

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, UTC
from pathlib import Path

from tts_pipeline import (
    TextNormalizer,
    extract_front_matter,
    make_clean_markdown,
    prepare_body_for_tts,
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def strip_local_file_links(text: str) -> str:
    # [label](file:///C:/...)
    text = re.sub(r"\[([^\]]+)\]\(file:///[^\)]+\)", r"\1", text, flags=re.IGNORECASE)
    # [label](C:\... or O:\...)
    text = re.sub(r"\[([^\]]+)\]\([A-Za-z]:\\[^\)]+\)", r"\1", text, flags=re.IGNORECASE)
    return text


def parse_replacements(items: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            continue
        src, dst = item.split("=", 1)
        src = src.strip()
        dst = dst.strip()
        if src:
            out[src] = dst
    return out


def apply_replacements(text: str, replacements: dict[str, str]) -> str:
    if not replacements:
        return text
    out = text
    for source in sorted(replacements.keys(), key=len, reverse=True):
        out = re.sub(re.escape(source), replacements[source], out, flags=re.IGNORECASE)
    return out


def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "generated_at": None, "entries": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "entries" not in data:
            data["entries"] = {}
        return data
    except Exception:
        return {"version": 1, "generated_at": None, "entries": {}}


def save_manifest(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data["generated_at"] = datetime.now(UTC).isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare cached Quartz/TTS derived artifacts.")
    parser.add_argument("--source", required=True, help="Source root directory to scan for markdown.")
    parser.add_argument(
        "--out-base",
        default=None,
        help="Derived output base directory (default: ../CACHE/DERIVED from this script).",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Manifest file path (default: <out-base>/manifest.json).",
    )
    parser.add_argument("--prelude", default="Faith Through Physics. Theophysics Vault. By David Lowe")
    parser.add_argument(
        "--replace-name",
        action="append",
        default=["David Lowe=The Author", "David=The Author"],
        help="Replacement SOURCE=TARGET (repeatable).",
    )
    parser.add_argument(
        "--include",
        nargs="*",
        default=["*.md"],
        help="Glob patterns under source root.",
    )
    args = parser.parse_args()

    source_root = Path(args.source).resolve()
    if not source_root.exists():
        print(f"[ERROR] Source path not found: {source_root}")
        return 1

    script_dir = Path(__file__).parent
    out_base = Path(args.out_base).resolve() if args.out_base else (script_dir.parent / "CACHE" / "DERIVED")
    quartz_root = out_base / "quartz"
    tts_root = out_base / "tts"
    manifest_path = Path(args.manifest).resolve() if args.manifest else (out_base / "manifest.json")

    normalizer = TextNormalizer()
    replacements = parse_replacements(args.replace_name)
    manifest = load_manifest(manifest_path)
    entries = manifest.get("entries", {})

    files: list[Path] = []
    for pat in args.include:
        files.extend(source_root.rglob(pat))
    files = sorted({p for p in files if p.is_file()})

    processed = 0
    skipped = 0

    for src in files:
        rel = src.relative_to(source_root).as_posix()
        digest = sha256_file(src)
        entry = entries.get(rel, {})

        quartz_out = quartz_root / rel
        tts_out = tts_root / str(Path(rel).with_suffix(""))  # remove extension
        tts_out = tts_out.with_name(tts_out.name + "_tts.txt")

        if (
            entry.get("sha256") == digest
            and quartz_out.exists()
            and tts_out.exists()
        ):
            skipped += 1
            continue

        raw = src.read_text(encoding="utf-8", errors="ignore")
        title, body, _ = extract_front_matter(raw)

        quartz_text = make_clean_markdown(title, body)
        quartz_text = strip_local_file_links(quartz_text)

        tts_body = prepare_body_for_tts(body)
        tts_text = normalizer.normalize(tts_body)
        if args.prelude and args.prelude.strip():
            tts_text = f"{args.prelude.strip()}. {tts_text}".strip()
        tts_text = apply_replacements(tts_text, replacements)

        quartz_out.parent.mkdir(parents=True, exist_ok=True)
        tts_out.parent.mkdir(parents=True, exist_ok=True)
        quartz_out.write_text(quartz_text, encoding="utf-8")
        tts_out.write_text(tts_text, encoding="utf-8")

        stat = src.stat()
        entries[rel] = {
            "sha256": digest,
            "source_mtime_utc": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
            "quartz_output": str(quartz_out),
            "tts_output": str(tts_out),
            "updated_at_utc": datetime.now(UTC).isoformat(),
        }
        processed += 1

    manifest["entries"] = entries
    save_manifest(manifest_path, manifest)

    print("==============================================")
    print("DERIVED CACHE COMPLETE")
    print("==============================================")
    print(f"Source root: {source_root}")
    print(f"Out base:    {out_base}")
    print(f"Manifest:    {manifest_path}")
    print("----------------------------------------------")
    print(f"Files found: {len(files)}")
    print(f"Processed:   {processed}")
    print(f"Skipped:     {skipped}")
    print("==============================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


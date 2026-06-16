"""Unified engine adapters for the File Sorter Hub.

The hub keeps heavyweight systems optional. The GUI and API can inspect what is
available without forcing Postgres, Nexa models, or spaCy to be installed before
the main sorter opens.
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parent
FIS_ROOT = APP_ROOT / "file-intelligence-system-master"
ORGANIZER_ROOT = APP_ROOT / "Local-File-Organizer-main"


def baseline_filename(filename: str) -> str:
    path = Path(filename)
    ext = path.suffix.lower()
    stem = path.stem
    clean = re.sub(r"([a-z])([A-Z])", r"\1 \2", stem)
    clean = re.sub(r"[_\s.]+", "-", clean)
    clean = re.sub(r"[^a-zA-Z0-9\-]", "", clean)
    clean = re.sub(r"-+", "-", clean).strip("-").lower()
    return f"{clean or 'unnamed'}{ext}"


def _collect_files(target: Path, max_files: int) -> list[Path]:
    if target.is_file():
        return [target]

    files: list[Path] = []
    for root, _, names in os.walk(target):
        for name in names:
            if name.startswith("."):
                continue
            files.append(Path(root) / name)
            if len(files) >= max_files:
                return files
    return files


def baseline_rename_plan(path: str, max_files: int = 200) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {"error": f"Path not found: {path}"}

    files = _collect_files(target, max_files)
    planned_destinations: dict[str, str] = {}
    operations = []
    counts = {"would_rename": 0, "already_clean": 0, "collision": 0}

    for file_path in files:
        baseline = baseline_filename(file_path.name)
        destination = file_path.with_name(baseline)
        destination_key = str(destination).lower()

        if baseline == file_path.name:
            status = "already_clean"
            reason = "Already matches the baseline rule."
        elif destination.exists() and destination.resolve() != file_path.resolve():
            status = "collision"
            reason = "A file with the baseline name already exists."
        elif destination_key in planned_destinations:
            status = "collision"
            reason = "Another file in this scan wants the same baseline name."
        else:
            status = "would_rename"
            reason = "Safe candidate for the baseline rename pass."
            planned_destinations[destination_key] = str(file_path)

        counts[status] += 1
        operations.append(
            {
                "filepath": str(file_path),
                "filename": file_path.name,
                "baseline": baseline,
                "destination": str(destination),
                "status": status,
                "reason": reason,
            }
        )

    return {
        "path": str(target),
        "mode": "dry_run",
        "rule": "lowercase + hyphens + lowercase extension",
        "count": len(operations),
        "counts": counts,
        "operations": operations,
    }


def _has_file(path: Path) -> bool:
    return path.exists() and path.is_file()


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _engine_status() -> list[dict[str, Any]]:
    return [
        {
            "id": "sorter_v3",
            "name": "File Sorter v3",
            "status": "ready",
            "role": "Primary GUI, domain classifier, naming previews, preference learning",
            "path": str(APP_ROOT),
            "entry": "api_server.py",
            "notes": "This is the active shell of the unified app.",
        },
        {
            "id": "file_intelligence",
            "name": "File Intelligence System",
            "status": "available" if _has_file(FIS_ROOT / "fis" / "pipeline.py") else "missing",
            "role": "Advanced classification, rename queue, BIL, browser/hotkey hooks",
            "path": str(FIS_ROOT),
            "entry": "fis/pipeline.py",
            "notes": "Heavy features require Postgres and optional NLP engines. Wrapped as phase-2 optional.",
        },
        {
            "id": "local_file_organizer",
            "name": "Local File Organizer",
            "status": "available" if _has_file(ORGANIZER_ROOT / "file_utils.py") else "missing",
            "role": "File content readers and future model-based organizing",
            "path": str(ORGANIZER_ROOT),
            "entry": "main.py",
            "notes": "Model-based organizing requires Nexa/Tesseract. Lightweight readers are usable now.",
        },
    ]


def hub_status() -> dict[str, Any]:
    optional_packages = {
        "yake": _module_available("yake"),
        "sklearn": _module_available("sklearn"),
        "yaml": _module_available("yaml"),
        "fitz": _module_available("fitz"),
        "docx": _module_available("docx"),
        "pandas": _module_available("pandas"),
        "pptx": _module_available("pptx"),
        "nexa": _module_available("nexa"),
        "psycopg2": _module_available("psycopg2"),
        "spacy": _module_available("spacy"),
    }
    return {
        "name": "File Sorter Hub",
        "status": "ready",
        "root": str(APP_ROOT),
        "engines": _engine_status(),
        "optional_packages": optional_packages,
        "retire_later_candidates": [
            "Separate launchers inside file-intelligence-system-master",
            "Standalone Local-File-Organizer CLI once hub routes cover it",
            "Duplicate JSX prototypes after the HTML shell is replaced",
        ],
    }


def organizer_preview(path: str, max_files: int = 50) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {"error": f"Path not found: {path}"}

    if str(ORGANIZER_ROOT) not in sys.path:
        sys.path.insert(0, str(ORGANIZER_ROOT))

    try:
        from file_utils import collect_file_paths, read_file_data, separate_files_by_type
    except Exception as exc:
        files = []
        if target.is_file():
            files = [target]
        else:
            for root, _, names in os.walk(target):
                for name in names:
                    if not name.startswith("."):
                        files.append(Path(root) / name)
                    if len(files) >= max_files:
                        break
                if len(files) >= max_files:
                    break
        text_exts = {".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".py", ".html", ".css", ".js"}
        previews = []
        for file_path in files:
            if file_path.suffix.lower() not in text_exts:
                continue
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                text = ""
            previews.append(
                {
                    "filepath": str(file_path),
                    "filename": file_path.name,
                    "baseline": baseline_filename(file_path.name),
                    "characters_read": len(text),
                    "preview": text[:500],
                }
            )
            if len(previews) >= 10:
                break
        return {
            "path": str(target),
            "total_files_sampled": len(files),
            "image_files": len([f for f in files if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".bmp"}]),
            "text_like_files": len([f for f in files if f.suffix.lower() in text_exts]),
            "preview_count": len(previews),
            "previews": previews,
            "note": f"Fallback preview used because Local Organizer optional imports are unavailable: {exc}",
        }

    files = collect_file_paths(str(target))[:max_files]
    image_files, text_files = separate_files_by_type(files)
    previews = []
    for file_path in text_files[:10]:
        text = read_file_data(file_path) or ""
        previews.append(
            {
                "filepath": file_path,
                "filename": os.path.basename(file_path),
                "baseline": baseline_filename(os.path.basename(file_path)),
                "characters_read": len(text),
                "preview": text[:500],
            }
        )

    return {
        "path": str(target),
        "total_files_sampled": len(files),
        "image_files": len(image_files),
        "text_like_files": len(text_files),
        "preview_count": len(previews),
        "previews": previews,
        "note": "This uses the Local File Organizer readers without loading Nexa models.",
    }


def fis_text_classify(text: str) -> dict[str, Any]:
    if not text.strip():
        return {"error": "text is required"}
    if str(FIS_ROOT) not in sys.path:
        sys.path.insert(0, str(FIS_ROOT))

    try:
        from fis.nlp.classifier import FISClassifier
        from fis.nlp.engines import YakeEngine, text_to_slug
    except Exception as exc:
        return {
            "status": "unavailable",
            "error": str(exc),
            "note": "Install File Intelligence optional NLP dependencies before enabling this route.",
        }

    try:
        yake = YakeEngine()
        keywords = yake.extract(text)
        classifier = FISClassifier()
        result = classifier.classify(text, keywords, [])
        result["slug"] = text_to_slug(keywords, 20)
        result["keywords"] = [k["keyword"] for k in keywords]
        return {"status": "ok", "result": result}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def rename_preview(path: str, max_files: int = 50) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {"error": f"Path not found: {path}"}

    try:
        from naming_engine import NamingEngine, clean_filename
    except Exception as exc:
        return {"error": f"Rename engine unavailable: {exc}"}

    files = [target] if target.is_file() else [
        Path(root) / name
        for root, _, names in os.walk(target)
        for name in names
        if not name.startswith(".")
    ]
    engine = NamingEngine()
    previews = []
    for file_path in files[:max_files]:
        text = _quick_extract_text(file_path)
        keywords = _quick_keywords(text)
        slug = "-".join(keywords[:4]) if keywords else clean_filename(file_path.name).rsplit(".", 1)[0]
        file_info = {
            "filename": file_path.name,
            "ext": file_path.suffix,
            "domain": "UNCATEGORIZED",
            "domain_code": "UC",
            "keywords": keywords,
        }
        previews.append(
            {
                "filepath": str(file_path),
                "filename": file_path.name,
                "baseline": baseline_filename(file_path.name),
                "baseline_rule": "lowercase + hyphens",
                "slug": slug,
                "keywords": keywords,
                "presets": engine.preview_all_presets(file_info),
            }
        )

    return {"path": str(target), "count": len(previews), "previews": previews}


def _quick_extract_text(file_path: Path, max_chars: int = 5000) -> str:
    text_exts = {
        ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx", ".css", ".html",
        ".json", ".yaml", ".yml", ".xml", ".csv", ".bat", ".sh", ".ps1",
        ".sql", ".rs", ".go", ".lean", ".toml", ".cfg", ".ini", ".log",
    }
    if file_path.suffix.lower() not in text_exts:
        return ""
    try:
        return file_path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except Exception:
        return ""


def _quick_keywords(text: str, top_n: int = 6) -> list[str]:
    stops = {
        "the", "and", "for", "that", "this", "with", "from", "have", "what",
        "when", "into", "your", "file", "files", "class", "style", "return",
        "const", "function", "import", "export", "true", "false", "none",
    }
    counts: dict[str, int] = {}
    for word in re.findall(r"\b[a-zA-Z]{4,}\b", text.lower()):
        if word in stops:
            continue
        counts[word] = counts.get(word, 0) + 1
    return [word for word, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:top_n]]


def manual_scan(path: str) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {"error": f"Path not found: {path}"}
    try:
        from manual_sort import find_duplicates, scan_directory
    except Exception as exc:
        return {"error": f"Manual sorter unavailable: {exc}"}

    stats = scan_directory(str(target))
    dupes = find_duplicates(str(target), by="name")
    file_previews = [
        {
            "filepath": f["path"],
            "filename": f["name"],
            "ext": f["ext"],
            "size": f["size"],
            "baseline": baseline_filename(f["name"]),
        }
        for f in stats["all_files"][:100]
    ]
    return {
        "root": stats["root"],
        "total_files": stats["total_files"],
        "total_size": stats["total_size"],
        "folder_count": stats["folder_count"],
        "kind_counts": stats["kind_counts"],
        "ext_counts": dict(list(stats["ext_counts"].items())[:20]),
        "file_previews": file_previews,
        "duplicate_name_groups": len(dupes),
        "duplicate_groups_preview": dupes[:10],
    }

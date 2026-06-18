"""
Intelligence Scorer — River FIS
Queries the scan cache, detects priorities, returns ordered action cards.

Usage:
    from intelligence_scorer import get_intelligence_cards
    cards = get_intelligence_cards("/path/to/folder")

Each card: {priority, rank, title, description, affected_count, risk, action_type, detail}

Schema match: sorter_cache.py tables — files, folders, classifications, decisions
"""

import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from sorter_cache import connect


def get_intelligence_cards(root_path: str, limit: int = 5) -> list[dict]:
    """Run all detectors, score, return top priority cards."""
    conn = connect()
    try:
        detectors = [
            detect_duplicates,
            detect_naming_chaos,
            detect_tiny_folders,
            detect_domain_clusters,
            detect_junk_files,
        ]
        cards = []
        for fn in detectors:
            try:
                result = fn(conn, root_path)
                if result and result["affected_count"] > 0:
                    cards.append(result)
            except Exception as e:
                print(f"[intelligence] {fn.__name__} error: {e}")
        cards.sort(key=lambda c: c["priority"])
        for i, card in enumerate(cards):
            card["rank"] = i + 1
        return cards[:limit]
    finally:
        conn.close()


def _path_filter(root_path: str) -> str:
    """Normalize root for LIKE matching."""
    p = root_path.rstrip("/\\")
    return p + "%"


# ── Priority 1: Duplicates ──────────────────────────────────────────

def detect_duplicates(conn: sqlite3.Connection, root_path: str) -> dict | None:
    """Find files with identical MD5 hashes."""
    like = _path_filter(root_path)
    rows = conn.execute("""
        SELECT md5_hash, filepath, filename, size
        FROM files
        WHERE filepath LIKE ? AND md5_hash IS NOT NULL AND md5_hash != ''
        ORDER BY md5_hash, filepath
    """, (like,)).fetchall()

    if not rows:
        return None

    groups = defaultdict(list)
    for r in rows:
        groups[r["md5_hash"]].append({
            "path": r["filepath"],
            "name": r["filename"],
            "size": r["size"] or 0,
        })

    dups = {h: fs for h, fs in groups.items() if len(fs) > 1}
    if not dups:
        return None

    extras = sum(len(fs) - 1 for fs in dups.values())
    waste = sum(sum(f["size"] for f in fs[1:]) for fs in dups.values())
    waste_mb = round(waste / (1024 * 1024), 1)

    return {
        "priority": 1,
        "title": "Clean duplicate files",
        "description": (
            f"River found {len(dups)} groups of identical files "
            f"({extras} extras, ~{waste_mb} MB). "
            f"Extras move to archive-review. Originals stay untouched."
        ),
        "affected_count": extras,
        "risk": "low",
        "action_type": "duplicate_archive",
        "detail": {"groups": len(dups), "extras": extras, "waste_mb": waste_mb},
    }


# ── Priority 2: Naming chaos ────────────────────────────────────────

def detect_naming_chaos(conn: sqlite3.Connection, root_path: str) -> dict | None:
    """Find files with spaces, mixed case, or special characters."""
    like = _path_filter(root_path)
    rows = conn.execute("""
        SELECT file_id, filename, filepath
        FROM files
        WHERE filepath LIKE ?
    """, (like,)).fetchall()

    if not rows:
        return None

    problems = []
    for r in rows:
        stem = Path(r["filename"]).stem
        issues = []
        if " " in stem:
            issues.append("spaces")
        if stem != stem.lower() and any(c.isupper() for c in stem):
            issues.append("mixed_case")
        if re.search(r'[^a-zA-Z0-9._\-]', stem):
            issues.append("special_chars")
        if len(stem) > 80:
            issues.append("too_long")
        if issues:
            problems.append({"file_id": r["file_id"], "issues": issues})

    if not problems:
        return None

    pct = round(100 * len(problems) / len(rows))
    breakdown = dict(Counter(i for p in problems for i in p["issues"]))

    return {
        "priority": 2,
        "title": "Fix file names",
        "description": (
            f"{len(problems)} of {len(rows)} files ({pct}%) have naming issues. "
            f"River will apply lowercase + hyphens. Preview before any rename."
        ),
        "affected_count": len(problems),
        "risk": "low",
        "action_type": "rename_baseline",
        "detail": {
            "total_files": len(rows),
            "problem_files": len(problems),
            "issue_breakdown": breakdown,
        },
    }


# ── Priority 3: Domain clustering ───────────────────────────────────

def detect_domain_clusters(conn: sqlite3.Connection, root_path: str) -> dict | None:
    """Find classified files of the same domain scattered across folders."""
    like = _path_filter(root_path)
    rows = conn.execute("""
        SELECT f.file_id, f.filename, f.filepath, f.parent_path,
               c.domain, c.domain_code, c.confidence
        FROM files f
        JOIN classifications c ON c.file_id = f.file_id
        WHERE f.filepath LIKE ?
          AND c.domain IS NOT NULL
    """, (like,)).fetchall()

    if not rows:
        return None

    domain_folders = defaultdict(lambda: defaultdict(list))
    for r in rows:
        domain = r["domain_code"] or r["domain"] or "unknown"
        folder = r["parent_path"] or "root"
        domain_folders[domain][folder].append(r["filename"])

    scattered = {}
    for domain, folders in domain_folders.items():
        if len(folders) >= 2:
            total = sum(len(fs) for fs in folders.values())
            if total >= 3:
                scattered[domain] = {"folders": len(folders), "files": total}

    if not scattered:
        return None

    top = max(scattered, key=lambda d: scattered[d]["files"])
    t = scattered[top]

    return {
        "priority": 3,
        "title": "Group related files",
        "description": (
            f"{len(scattered)} topics are spread across multiple folders. "
            f"Biggest: '{top}' has {t['files']} files in {t['folders']} folders. "
            f"River can create a hub without moving originals."
        ),
        "affected_count": sum(s["files"] for s in scattered.values()),
        "risk": "low",
        "action_type": "create_hub",
        "detail": {"scattered_domains": scattered, "top_domain": top},
    }


# ── Priority 4: Tiny folders ────────────────────────────────────────

def detect_tiny_folders(conn: sqlite3.Connection, root_path: str) -> dict | None:
    """Find folders with 0-1 files."""
    like = _path_filter(root_path)

    # Use the folders table directly
    rows = conn.execute("""
        SELECT folder_path, folder_name, file_count
        FROM folders
        WHERE folder_path LIKE ? AND file_count <= 1
    """, (like,)).fetchall()

    if not rows or len(rows) < 2:
        return None

    total = conn.execute("""
        SELECT COUNT(*) FROM folders WHERE folder_path LIKE ?
    """, (like,)).fetchone()[0]

    return {
        "priority": 4,
        "title": "Merge tiny folders",
        "description": (
            f"{len(rows)} of {total} folders have 1 or fewer files. "
            f"River can merge these into parent folders or group by type."
        ),
        "affected_count": len(rows),
        "risk": "medium",
        "action_type": "merge_tiny",
        "detail": {
            "tiny_folders": [r["folder_name"] for r in rows[:20]],
            "total_folders": total,
        },
    }


# ── Priority 5: Junk / temp files ───────────────────────────────────

def detect_junk_files(conn: sqlite3.Connection, root_path: str) -> dict | None:
    """Find temp, system, and junk files."""
    like = _path_filter(root_path)
    rows = conn.execute("""
        SELECT file_id, filename, filepath, size
        FROM files
        WHERE filepath LIKE ?
    """, (like,)).fetchall()

    if not rows:
        return None

    JUNK_NAMES = {'thumbs.db', 'desktop.ini', '.ds_store'}
    JUNK_EXT = {'.tmp', '.bak', '.log', '.err', '.pyc', '.swp',
                '.swo', '.crdownload', '.partial'}

    junk = []
    for r in rows:
        name = r["filename"].lower()
        ext = Path(name).suffix.lower()
        reason = ""
        if name in JUNK_NAMES:
            reason = "system_file"
        elif name.startswith("~$") or name.startswith("~"):
            reason = "temp_lock"
        elif ext in JUNK_EXT:
            reason = "junk_extension"
        if reason:
            junk.append({"file_id": r["file_id"], "size": r["size"] or 0, "reason": reason})

    if not junk:
        return None

    size_mb = round(sum(j["size"] for j in junk) / (1024 * 1024), 1)

    return {
        "priority": 5,
        "title": "Quarantine junk files",
        "description": (
            f"{len(junk)} temp/system files found (~{size_mb} MB). "
            f"Safe to quarantine. Nothing will be deleted."
        ),
        "affected_count": len(junk),
        "risk": "low",
        "action_type": "quarantine_junk",
        "detail": {
            "by_reason": dict(Counter(j["reason"] for j in junk)),
            "total_size_mb": size_mb,
        },
    }


# ── API handler ──────────────────────────────────────────────────────

def handle_intelligence_request(query: dict) -> dict:
    """Handle GET /api/intelligence?path=... from the UI."""
    root = query.get("path", [""])[0]
    if not root:
        return {"ok": False, "errors": ["path parameter required"]}
    cards = get_intelligence_cards(root)
    return {
        "ok": True,
        "data": {"root": root, "cards": cards, "total_priorities": len(cards)},
    }

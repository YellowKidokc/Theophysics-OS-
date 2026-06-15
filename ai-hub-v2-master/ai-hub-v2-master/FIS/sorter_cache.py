"""SQLite cache for File Sorter Hub scans, predictions, and decisions."""

from __future__ import annotations

import json
import hashlib
import os
import random
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parent
DEFAULT_DB_DIR = Path(r"\\192.168.2.50\brain\09_DATABASES\FIS")
DB_DIR = Path(os.environ.get("FIS_DATABASE_DIR", DEFAULT_DB_DIR))
DB_PATH = DB_DIR / "sorter_cache.sqlite"


def ensure_database_dir() -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def md5_file(path: Path, chunk_size: int = 1024 * 1024) -> tuple[str | None, str]:
    digest = hashlib.md5()
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError:
        return None, "error"
    return digest.hexdigest(), "ok"


def connect() -> sqlite3.Connection:
    ensure_database_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            PRAGMA journal_mode = WAL;

            CREATE TABLE IF NOT EXISTS scan_runs (
                scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_path TEXT NOT NULL,
                mode TEXT NOT NULL DEFAULT 'sort',
                top_only INTEGER DEFAULT 0,
                use_nlp INTEGER DEFAULT 0,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                file_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'running',
                error TEXT
            );

            CREATE TABLE IF NOT EXISTS files (
                file_id INTEGER PRIMARY KEY AUTOINCREMENT,
                filepath TEXT NOT NULL UNIQUE,
                filename TEXT NOT NULL,
                parent_path TEXT,
                ext TEXT,
                size INTEGER,
                mtime REAL,
                md5_hash TEXT,
                hash_algo TEXT,
                hash_status TEXT,
                hashed_at TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS folders (
                folder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                folder_path TEXT NOT NULL UNIQUE,
                folder_name TEXT NOT NULL,
                parent_path TEXT,
                depth INTEGER DEFAULT 0,
                file_count INTEGER DEFAULT 0,
                child_folder_count INTEGER DEFAULT 0,
                total_size INTEGER DEFAULT 0,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                last_scanned TEXT
            );

            CREATE TABLE IF NOT EXISTS classifications (
                classification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER,
                file_id INTEGER NOT NULL,
                domain TEXT,
                domain_code TEXT,
                confidence REAL,
                source TEXT,
                matched_json TEXT,
                keywords_json TEXT,
                text_preview TEXT,
                names_json TEXT,
                markov_json TEXT,
                payload_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(scan_id) REFERENCES scan_runs(scan_id),
                FOREIGN KEY(file_id) REFERENCES files(file_id)
            );

            CREATE TABLE IF NOT EXISTS decisions (
                decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER,
                filename TEXT,
                extension TEXT,
                proposed_domain TEXT,
                final_domain TEXT,
                confidence REAL,
                action TEXT,
                source TEXT,
                keywords_json TEXT,
                payload_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(file_id) REFERENCES files(file_id)
            );

            CREATE TABLE IF NOT EXISTS root_registry (
                root_id INTEGER PRIMARY KEY AUTOINCREMENT,
                root_code TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL,
                root_path TEXT NOT NULL,
                purpose TEXT,
                status TEXT DEFAULT 'planned',
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS action_log (
                action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_code TEXT UNIQUE,
                action_type TEXT NOT NULL,
                root_code TEXT,
                target_path TEXT,
                status TEXT DEFAULT 'planned',
                payload_json TEXT,
                created_at TEXT NOT NULL,
                finished_at TEXT,
                note TEXT
            );

            CREATE TABLE IF NOT EXISTS organization_findings (
                finding_id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER,
                finding_type TEXT NOT NULL,
                path TEXT,
                title TEXT NOT NULL,
                evidence TEXT,
                suggested_action TEXT,
                weight INTEGER DEFAULT 5,
                risk TEXT DEFAULT 'low',
                requires_approval INTEGER DEFAULT 1,
                payload_json TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                FOREIGN KEY(scan_id) REFERENCES scan_runs(scan_id)
            );

            CREATE INDEX IF NOT EXISTS idx_files_parent_path ON files(parent_path);
            CREATE INDEX IF NOT EXISTS idx_files_ext ON files(ext);
            CREATE INDEX IF NOT EXISTS idx_files_last_seen ON files(last_seen);
            CREATE INDEX IF NOT EXISTS idx_folders_parent_path ON folders(parent_path);
            CREATE INDEX IF NOT EXISTS idx_scan_runs_mode_started ON scan_runs(mode, started_at);
            CREATE INDEX IF NOT EXISTS idx_action_log_root_code ON action_log(root_code);
            CREATE INDEX IF NOT EXISTS idx_action_log_type_status ON action_log(action_type, status);
            CREATE INDEX IF NOT EXISTS idx_findings_scan_weight ON organization_findings(scan_id, weight);
            CREATE INDEX IF NOT EXISTS idx_findings_type_status ON organization_findings(finding_type, status);
            """
        )
        decision_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(decisions)").fetchall()
        }
        if "payload_json" not in decision_columns:
            conn.execute("ALTER TABLE decisions ADD COLUMN payload_json TEXT")
        file_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(files)").fetchall()
        }
        for column, definition in {
            "md5_hash": "TEXT",
            "hash_algo": "TEXT",
            "hash_status": "TEXT",
            "hashed_at": "TEXT",
        }.items():
            if column not in file_columns:
                conn.execute(f"ALTER TABLE files ADD COLUMN {column} {definition}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_files_md5_hash ON files(md5_hash)")


def _format_action_code(action_id: int) -> str:
    return f"{action_id:05d}"


def record_action(
    action_type: str,
    root_code: str = "",
    target_path: str = "",
    status: str = "planned",
    payload: dict[str, Any] | None = None,
    note: str = "",
) -> dict[str, Any]:
    init_db()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO action_log (
                action_type, root_code, target_path, status, payload_json, created_at, note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action_type,
                root_code,
                target_path,
                status,
                json.dumps(payload or {}, ensure_ascii=True),
                now_iso(),
                note,
            ),
        )
        action_id = int(cur.lastrowid)
        action_code = _format_action_code(action_id)
        conn.execute(
            "UPDATE action_log SET action_code = ? WHERE action_id = ?",
            (action_code, action_id),
        )
        row = conn.execute("SELECT * FROM action_log WHERE action_id = ?", (action_id,)).fetchone()
    return dict(row)


def update_action_status(
    action_id: int,
    status: str,
    payload: dict[str, Any] | None = None,
    note: str = "",
) -> None:
    with connect() as conn:
        current = conn.execute("SELECT payload_json FROM action_log WHERE action_id = ?", (action_id,)).fetchone()
        merged: dict[str, Any] = {}
        if current and current["payload_json"]:
            try:
                merged = json.loads(current["payload_json"])
            except json.JSONDecodeError:
                merged = {}
        if payload:
            merged.update(payload)
        conn.execute(
            """
            UPDATE action_log
            SET status = ?, payload_json = ?, finished_at = ?, note = COALESCE(NULLIF(?, ''), note)
            WHERE action_id = ?
            """,
            (status, json.dumps(merged, ensure_ascii=True), now_iso(), note, action_id),
        )


def register_root(root_code: str, root_path: str, label: str = "", purpose: str = "") -> dict[str, Any]:
    init_db()
    code = root_code.strip().upper()
    path = str(Path(root_path))
    timestamp = now_iso()
    status = "ready" if Path(path).exists() else "planned"
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO root_registry (root_code, label, root_path, purpose, status, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(root_code) DO UPDATE SET
                label=excluded.label,
                root_path=excluded.root_path,
                purpose=excluded.purpose,
                status=excluded.status,
                last_seen=excluded.last_seen
            """,
            (code, label or code, path, purpose, status, timestamp, timestamp),
        )
        row = conn.execute("SELECT * FROM root_registry WHERE root_code = ?", (code,)).fetchone()
    record_action(
        "root_registered",
        root_code=code,
        target_path=path,
        status="complete",
        payload={"label": label or code, "purpose": purpose, "root_status": status},
    )
    return dict(row)


def seed_demo_roots(base_path: str = r"C:\Users\lowes\OneDrive") -> list[dict[str, Any]]:
    base = Path(base_path)
    seeds = [
        ("A", base / "A", "A demo intake", "Current demo scan and review folder"),
        ("B", base / "B", "B bucket", "Second-pass bucket for B/BS material"),
        ("C", base / "C", "C bucket", "Third-pass bucket for C/CS material"),
    ]
    return [register_root(code, str(path), label, purpose) for code, path, label, purpose in seeds]


def list_roots() -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM root_registry
            ORDER BY root_code
            """
        ).fetchall()
    return [dict(row) for row in rows]


def recent_actions(limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM action_log
            ORDER BY action_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    actions = []
    for row in rows:
        record = dict(row)
        try:
            record["payload"] = json.loads(record.pop("payload_json") or "{}")
        except json.JSONDecodeError:
            record["payload"] = {}
        actions.append(record)
    return actions


def start_scan(scan_path: str, mode: str = "sort", top_only: bool = False, use_nlp: bool = False) -> int:
    init_db()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO scan_runs (scan_path, mode, top_only, use_nlp, started_at, status)
            VALUES (?, ?, ?, ?, ?, 'running')
            """,
            (scan_path, mode, int(top_only), int(use_nlp), now_iso()),
        )
        return int(cur.lastrowid)


def finish_scan(scan_id: int, file_count: int, status: str = "complete", error: str | None = None) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE scan_runs
            SET finished_at = ?, file_count = ?, status = ?, error = ?
            WHERE scan_id = ?
            """,
            (now_iso(), file_count, status, error, scan_id),
        )


def update_scan_progress(scan_id: int, file_count: int, status: str = "running") -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE scan_runs
            SET file_count = ?, status = ?
            WHERE scan_id = ?
            """,
            (file_count, status, scan_id),
        )


def upsert_file(filepath: str, compute_hash: bool = False) -> int:
    path = Path(filepath)
    try:
        stat = path.stat()
        size = stat.st_size
        mtime = stat.st_mtime
    except OSError:
        size = None
        mtime = None
    timestamp = now_iso()
    md5_hash = None
    hash_status = None
    hashed_at = None
    if compute_hash and size is not None:
        md5_hash, hash_status = md5_file(path)
        hashed_at = timestamp
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO files (
                filepath, filename, parent_path, ext, size, mtime,
                md5_hash, hash_algo, hash_status, hashed_at, first_seen, last_seen
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(filepath) DO UPDATE SET
                filename=excluded.filename,
                parent_path=excluded.parent_path,
                ext=excluded.ext,
                size=excluded.size,
                mtime=excluded.mtime,
                md5_hash=COALESCE(excluded.md5_hash, files.md5_hash),
                hash_algo=COALESCE(excluded.hash_algo, files.hash_algo),
                hash_status=COALESCE(excluded.hash_status, files.hash_status),
                hashed_at=COALESCE(excluded.hashed_at, files.hashed_at),
                last_seen=excluded.last_seen
            """,
            (
                str(path), path.name, str(path.parent), path.suffix.lower(), size, mtime,
                md5_hash, "md5" if compute_hash else None, hash_status, hashed_at, timestamp, timestamp,
            ),
        )
        row = conn.execute("SELECT file_id FROM files WHERE filepath = ?", (str(path),)).fetchone()
        return int(row["file_id"])


def _upsert_file_in_conn(conn: sqlite3.Connection, path: Path, timestamp: str, compute_hash: bool = False) -> int:
    try:
        stat = path.stat()
        size = stat.st_size
        mtime = stat.st_mtime
    except OSError:
        size = None
        mtime = None

    md5_hash = None
    hash_status = None
    hashed_at = None
    if compute_hash and size is not None:
        md5_hash, hash_status = md5_file(path)
        hashed_at = timestamp

    conn.execute(
        """
        INSERT INTO files (
            filepath, filename, parent_path, ext, size, mtime,
            md5_hash, hash_algo, hash_status, hashed_at, first_seen, last_seen
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(filepath) DO UPDATE SET
            filename=excluded.filename,
            parent_path=excluded.parent_path,
            ext=excluded.ext,
            size=excluded.size,
            mtime=excluded.mtime,
            md5_hash=COALESCE(excluded.md5_hash, files.md5_hash),
            hash_algo=COALESCE(excluded.hash_algo, files.hash_algo),
            hash_status=COALESCE(excluded.hash_status, files.hash_status),
            hashed_at=COALESCE(excluded.hashed_at, files.hashed_at),
            last_seen=excluded.last_seen
        """,
        (
            str(path), path.name, str(path.parent), path.suffix.lower(), size, mtime,
            md5_hash, "md5" if compute_hash else None, hash_status, hashed_at, timestamp, timestamp,
        ),
    )
    row = conn.execute("SELECT file_id FROM files WHERE filepath = ?", (str(path),)).fetchone()
    return int(row["file_id"])


def _upsert_folder_in_conn(
    conn: sqlite3.Connection,
    path: Path,
    timestamp: str,
    file_count: int = 0,
    child_folder_count: int = 0,
    total_size: int = 0,
    scanned: bool = False,
) -> int:
    parts = path.parts
    depth = max(len(parts) - 1, 0)
    conn.execute(
        """
        INSERT INTO folders (
            folder_path, folder_name, parent_path, depth, file_count,
            child_folder_count, total_size, first_seen, last_seen, last_scanned
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(folder_path) DO UPDATE SET
            folder_name=excluded.folder_name,
            parent_path=excluded.parent_path,
            depth=excluded.depth,
            file_count=excluded.file_count,
            child_folder_count=excluded.child_folder_count,
            total_size=excluded.total_size,
            last_seen=excluded.last_seen,
            last_scanned=COALESCE(excluded.last_scanned, folders.last_scanned)
        """,
        (
            str(path),
            path.name or str(path),
            str(path.parent) if path.parent != path else None,
            depth,
            file_count,
            child_folder_count,
            total_size,
            timestamp,
            timestamp,
            timestamp if scanned else None,
        ),
    )
    row = conn.execute("SELECT folder_id FROM folders WHERE folder_path = ?", (str(path),)).fetchone()
    return int(row["folder_id"])


def scan_inventory(
    scan_path: str,
    max_files: int = 10000,
    recursive: bool = True,
    follow_links: bool = False,
    compute_hash: bool = False,
) -> dict[str, Any]:
    init_db()
    target = Path(scan_path)
    if not target.exists():
        return {"error": f"Path not found: {scan_path}"}

    root_code = ""
    for root in list_roots():
        try:
            if str(target).lower().startswith(str(Path(root["root_path"])).lower()):
                root_code = root["root_code"]
                break
        except TypeError:
            continue
    action = record_action(
        "inventory_scan",
        root_code=root_code,
        target_path=str(target),
        status="running",
        payload={"recursive": recursive, "follow_links": follow_links, "max_files": max_files, "compute_hash": compute_hash},
    )
    scan_id = start_scan(str(target), mode="inventory", top_only=not recursive, use_nlp=False)
    timestamp = now_iso()
    file_total = 0
    folder_total = 0
    skipped = 0
    total_size = 0
    ext_counts: dict[str, int] = {}
    stopped_at_limit = False

    try:
        with connect() as conn:
            if target.is_file():
                _upsert_folder_in_conn(conn, target.parent, timestamp, scanned=True)
                _upsert_file_in_conn(conn, target, timestamp, compute_hash=compute_hash)
                file_total = 1
                total_size = target.stat().st_size if target.exists() else 0
                ext_counts[target.suffix.lower() or "(none)"] = 1
            else:
                seen_real_paths = set()
                for root, dirs, names in os.walk(target, followlinks=follow_links):
                    root_path = Path(root)
                    try:
                        real_path = str(root_path.resolve()).lower()
                    except OSError:
                        real_path = str(root_path).lower()
                    if real_path in seen_real_paths:
                        dirs[:] = []
                        continue
                    seen_real_paths.add(real_path)

                    if not recursive:
                        dirs[:] = []

                    visible_names = [name for name in names if not name.startswith(".")]
                    child_dirs = [name for name in dirs if not name.startswith(".")]
                    dirs[:] = child_dirs

                    folder_size = 0
                    folder_file_count = 0
                    for name in visible_names:
                        if file_total >= max_files:
                            stopped_at_limit = True
                            break
                        file_path = root_path / name
                        try:
                            stat = file_path.stat()
                            if not file_path.is_file():
                                continue
                        except OSError:
                            skipped += 1
                            continue

                        _upsert_file_in_conn(conn, file_path, timestamp, compute_hash=compute_hash)
                        file_total += 1
                        folder_file_count += 1
                        folder_size += stat.st_size
                        total_size += stat.st_size
                        ext = file_path.suffix.lower() or "(none)"
                        ext_counts[ext] = ext_counts.get(ext, 0) + 1

                    _upsert_folder_in_conn(
                        conn,
                        root_path,
                        timestamp,
                        file_count=folder_file_count,
                        child_folder_count=len(child_dirs),
                        total_size=folder_size,
                        scanned=True,
                    )
                    folder_total += 1

                    if stopped_at_limit:
                        break
    except Exception as exc:
        finish_scan(scan_id, file_total, status="error", error=str(exc))
        update_action_status(action["action_id"], "error", {"scan_id": scan_id, "file_count": file_total}, str(exc))
        return {"error": str(exc), "scan_id": scan_id}

    opportunity_report = analyze_organization_opportunities(str(target), scan_id=scan_id, limit=5)
    finish_scan(scan_id, file_total, status="partial" if stopped_at_limit else "complete")
    update_action_status(
        action["action_id"],
        "partial" if stopped_at_limit else "complete",
        {
            "scan_id": scan_id,
            "file_count": file_total,
            "folder_count": folder_total,
            "finding_count": opportunity_report["finding_count"],
            "skipped": skipped,
            "stopped_at_limit": stopped_at_limit,
            "compute_hash": compute_hash,
        },
    )
    return {
        "action_code": action["action_code"],
        "scan_id": scan_id,
        "path": str(target),
        "mode": "inventory",
        "recursive": recursive,
        "follow_links": follow_links,
        "compute_hash": compute_hash,
        "file_count": file_total,
        "folder_count": folder_total,
        "total_size": total_size,
        "skipped": skipped,
        "stopped_at_limit": stopped_at_limit,
        "ext_counts": dict(sorted(ext_counts.items(), key=lambda item: (-item[1], item[0]))[:25]),
        "finding_count": opportunity_report["finding_count"],
        "top_findings": opportunity_report["top_findings"],
    }


def cache_classification(scan_id: int, entry: dict[str, Any]) -> None:
    file_id = upsert_file(entry["filepath"])
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO classifications (
                scan_id, file_id, domain, domain_code, confidence, source,
                matched_json, keywords_json, text_preview, names_json, markov_json,
                payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scan_id,
                file_id,
                entry.get("domain"),
                entry.get("domain_code"),
                entry.get("confidence"),
                entry.get("source"),
                json.dumps(entry.get("matched", []), ensure_ascii=True),
                json.dumps(entry.get("keywords", []), ensure_ascii=True),
                entry.get("text_preview"),
                json.dumps(entry.get("names", {}), ensure_ascii=True),
                json.dumps(entry.get("markov", {}), ensure_ascii=True),
                json.dumps(entry, ensure_ascii=True),
                now_iso(),
            ),
        )


def cache_decision(decision: dict[str, Any]) -> None:
    filepath = decision.get("filepath")
    file_id = upsert_file(filepath) if filepath else None
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO decisions (
                file_id, filename, extension, proposed_domain, final_domain,
                confidence, action, source, keywords_json, payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id,
                decision.get("filename"),
                decision.get("ext") or decision.get("extension"),
                decision.get("proposed_domain"),
                decision.get("final_domain"),
                decision.get("confidence"),
                decision.get("action"),
                decision.get("source"),
                json.dumps(decision.get("keywords", []), ensure_ascii=True),
                json.dumps(decision, ensure_ascii=True),
                now_iso(),
            ),
        )


PROTECTED_FOLDER_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "_gsdata_",
    ".synologyworkingdirectory",
    "@eadir",
    "models",
    "05_models",
    "09_databases",
    "database",
    "databases",
}

PROJECT_SEED_FILES = {
    "readme",
    "readme.md",
    "pyproject.toml",
    "package.json",
    "requirements.txt",
    "config.json",
    "setup.py",
    "cargo.toml",
    "go.mod",
}

ARCHIVE_RESIDUE_TERMS = (
    "export",
    "backup",
    "archive",
    "old",
    "copy",
    "final-final",
    "_gsdata_",
    "changed files",
    ".trash",
    "attachments",
)

VAGUE_NAMES = {"new folder", "stuff", "all", "misc", "untitled", "temp", "tmp"}
UNKNOWN_EXTENSIONS = {".tmp", ".bak", ".old", ".part", ".crdownload", ".download", ".dat", ".bin"}


def _like_root(root: str) -> str:
    return root.rstrip("\\/") + "%"


def _finding(
    finding_type: str,
    path: str,
    title: str,
    evidence: str,
    suggested_action: str,
    weight: int,
    risk: str = "low",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "finding_type": finding_type,
        "path": path,
        "title": title,
        "evidence": evidence,
        "suggested_action": suggested_action,
        "weight": weight,
        "risk": risk,
        "requires_approval": True,
        "payload": payload or {},
    }


def _bad_name_reason(name: str) -> str:
    stem = Path(name).stem if "." in name else name
    lower = stem.lower().strip()
    if lower in VAGUE_NAMES:
        return "Name is too vague to explain what belongs here."
    if len(stem) >= 12 and re.fullmatch(r"[a-fA-F0-9_-]+", stem):
        return "Name looks like a hash or generated ID."
    if re.search(r"!{2,}|[#@$%^&*]{2,}", stem):
        return "Name has punctuation noise."
    if re.search(r"(^|[\s_-])(aaa+|111+|000+)([\s_-]|$)", lower):
        return "Name looks like a priority hack."
    letters = [ch for ch in stem if ch.isalpha()]
    if len(letters) >= 5 and "".join(letters).isupper():
        return "Name is all caps."
    if "  " in name or re.search(r"[_\s-]{3,}", name):
        return "Name has spacing or separator chaos."
    return ""


def store_organization_findings(scan_id: int | None, findings: list[dict[str, Any]]) -> None:
    init_db()
    timestamp = now_iso()
    with connect() as conn:
        if scan_id is not None:
            conn.execute("DELETE FROM organization_findings WHERE scan_id = ?", (scan_id,))
        conn.executemany(
            """
            INSERT INTO organization_findings (
                scan_id, finding_type, path, title, evidence, suggested_action,
                weight, risk, requires_approval, payload_json, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            [
                (
                    scan_id,
                    item["finding_type"],
                    item.get("path", ""),
                    item["title"],
                    item.get("evidence", ""),
                    item.get("suggested_action", "review"),
                    int(item.get("weight", 5)),
                    item.get("risk", "low"),
                    1 if item.get("requires_approval", True) else 0,
                    json.dumps(item.get("payload", {}), ensure_ascii=True),
                    timestamp,
                )
                for item in findings
            ],
        )


def recent_organization_findings(
    root: str = "",
    scan_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    init_db()
    clauses: list[str] = []
    values: list[Any] = []
    if scan_id is not None:
        clauses.append("scan_id = ?")
        values.append(scan_id)
    if root:
        clauses.append("path LIKE ?")
        values.append(_like_root(root))
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM organization_findings
            {where}
            ORDER BY weight DESC, finding_id DESC
            LIMIT ?
            """,
            (*values, limit),
        ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        try:
            item["payload"] = json.loads(item.pop("payload_json") or "{}")
        except json.JSONDecodeError:
            item["payload"] = {}
        item["requires_approval"] = bool(item.get("requires_approval"))
        return_item = item
        out.append(return_item)
    return out


def grouped_organization_findings(root: str = "", min_weight: int = 3) -> dict[str, Any]:
    init_db()
    findings = recent_organization_findings(root=root, limit=2000)
    filtered = [item for item in findings if int(item.get("weight") or 0) >= min_weight]
    tiers: dict[str, dict[str, Any]] = {}
    for item in filtered:
        weight = int(item.get("weight") or 0)
        key = str(weight)
        if key not in tiers:
            tiers[key] = {
                "weight": weight,
                "title": _weight_title(weight),
                "status": "auto_approved" if weight == 10 else "needs_review",
                "findings": [],
                "counts": {},
            }
        tiers[key]["findings"].append(item)
        ftype = item.get("finding_type") or "finding"
        tiers[key]["counts"][ftype] = tiers[key]["counts"].get(ftype, 0) + 1
    ordered = [tiers[key] for key in sorted(tiers.keys(), key=lambda value: -int(value))]
    return {
        "root": root,
        "min_weight": min_weight,
        "finding_count": len(filtered),
        "tiers": ordered,
    }


def _weight_title(weight: int) -> str:
    if weight == 10:
        return "Safety check"
    if weight == 9:
        return "Protected project work"
    if weight == 8:
        return "High-value cleanup"
    if weight == 7:
        return "Metadata and unknowns"
    if weight == 6:
        return "Organization opportunities"
    if weight == 5:
        return "Tiny or empty folders"
    if weight == 4:
        return "Old inactive items"
    if weight == 3:
        return "Large space users"
    return "Review items"


def decide_organization_finding(
    finding_id: int | None,
    action: str,
    schema: str = "baseline",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    init_db()
    valid = {"approve", "skip", "disapprove", "defer", "auto_approve"}
    if action not in valid:
        return {"error": f"Unsupported action: {action}"}
    status_map = {
        "approve": "approved",
        "skip": "skipped",
        "disapprove": "disapproved",
        "defer": "deferred",
        "auto_approve": "auto_approved",
    }
    status = status_map[action]
    finding = None
    with connect() as conn:
        if finding_id:
            finding = conn.execute(
                "SELECT * FROM organization_findings WHERE finding_id = ?",
                (finding_id,),
            ).fetchone()
            if not finding:
                return {"error": f"Finding not found: {finding_id}"}
            conn.execute(
                "UPDATE organization_findings SET status = ? WHERE finding_id = ?",
                (status, finding_id),
            )
    action_record = record_action(
        "finding_decision",
        target_path=dict(finding)["path"] if finding else "",
        status="complete",
        payload={
            "finding_id": finding_id,
            "decision": action,
            "status": status,
            "schema": schema,
            **(payload or {}),
        },
    )
    return {
        "ok": True,
        "finding_id": finding_id,
        "decision": action,
        "status": status,
        "schema": schema,
        "action_code": action_record["action_code"],
    }


def cached_folder_summary(root: str) -> dict[str, Any]:
    init_db()
    root_text = str(Path(root))
    root_like = _like_root(root_text)
    with connect() as conn:
        counts = {
            "total_files": conn.execute(
                "SELECT COUNT(*) AS c FROM files WHERE filepath LIKE ?", (root_like,)
            ).fetchone()["c"],
            "folder_count": conn.execute(
                "SELECT COUNT(*) AS c FROM folders WHERE folder_path LIKE ?", (root_like,)
            ).fetchone()["c"],
            "total_size": conn.execute(
                "SELECT COALESCE(SUM(size), 0) AS c FROM files WHERE filepath LIKE ?", (root_like,)
            ).fetchone()["c"],
        }
        ext_rows = conn.execute(
            """
            SELECT COALESCE(NULLIF(ext, ''), '(none)') AS ext, COUNT(*) AS count
            FROM files
            WHERE filepath LIKE ?
            GROUP BY COALESCE(NULLIF(ext, ''), '(none)')
            ORDER BY count DESC, ext
            LIMIT 20
            """,
            (root_like,),
        ).fetchall()
        duplicate_rows = conn.execute(
            """
            SELECT LOWER(filename) AS name_key, size, COUNT(*) AS count
            FROM files
            WHERE filepath LIKE ? AND size IS NOT NULL
            GROUP BY LOWER(filename), size
            HAVING COUNT(*) > 1
            """,
            (root_like,),
        ).fetchall()
        finding_rows = conn.execute(
            """
            SELECT finding_type, COUNT(*) AS count, MAX(weight) AS max_weight
            FROM organization_findings
            WHERE path LIKE ?
            GROUP BY finding_type
            ORDER BY max_weight DESC, count DESC
            LIMIT 12
            """,
            (root_like,),
        ).fetchall()
        latest = conn.execute(
            """
            SELECT scan_id, scan_path, file_count, status, started_at, finished_at
            FROM scan_runs
            WHERE scan_path = ? AND mode = 'inventory'
            ORDER BY scan_id DESC
            LIMIT 1
            """,
            (root_text,),
        ).fetchone()
    return {
        "source": "sqlite_cache",
        "path": root_text,
        **counts,
        "duplicate_name_groups": len(duplicate_rows),
        "kind_counts": {row["ext"]: row["count"] for row in ext_rows},
        "finding_types": [dict(row) for row in finding_rows],
        "latest_inventory_scan": dict(latest) if latest else None,
    }


def _baseline_slug(name: str) -> str:
    path = Path(name)
    stem = path.stem if path.suffix else name
    suffix = path.suffix.lower()
    clean = stem.lower()
    clean = re.sub(r"[^a-z0-9]+", "-", clean)
    clean = re.sub(r"-+", "-", clean).strip("-")
    return (clean or "unnamed") + suffix


def cached_rename_plan(root: str, limit: int = 200) -> dict[str, Any]:
    init_db()
    root_text = str(Path(root))
    rows = recent_cached_files(limit=limit, root=root_text)
    operations = []
    counts = {"would_rename": 0, "already_clean": 0, "collision": 0}
    seen: set[str] = set()
    for row in rows:
        filename = row.get("filename") or Path(row.get("filepath", "")).name
        baseline = _baseline_slug(filename)
        status = "already_clean" if filename == baseline else "would_rename"
        key = str(Path(row.get("parent_path", "") or Path(row.get("filepath", "")).parent) / baseline).lower()
        if key in seen:
            status = "collision"
        seen.add(key)
        counts[status] = counts.get(status, 0) + 1
        operations.append(
            {
                "filepath": row.get("filepath"),
                "filename": filename,
                "baseline": baseline,
                "status": status,
                "source": "sqlite_cache",
            }
        )
    return {
        "source": "sqlite_cache",
        "path": root_text,
        "counts": counts,
        "operations": operations,
        "limit": limit,
    }


def _rename_schema_label(schema: str) -> str:
    labels = {
        "baseline": "Baseline",
        "date_schema": "Date First",
        "domain_schema": "Domain + Topic",
        "johnny_decimal": "Johnny Decimal",
        "para": "PARA",
    }
    return labels.get(schema, schema.replace("_", " ").title())


def _format_schema_name(filename: str, schema: str) -> str:
    baseline = _baseline_slug(filename)
    path = Path(baseline)
    stem = path.stem if path.suffix else baseline
    suffix = path.suffix
    today = datetime.now().strftime("%Y-%m-%d")
    if schema == "date_schema":
        return f"{today}-{baseline}"
    if schema == "domain_schema":
        return f"general__{stem}__file{suffix}"
    if schema == "johnny_decimal":
        return f"20.01-{baseline}"
    if schema == "para":
        return f"projects__{baseline}"
    return baseline


def _slug_parts(filename: str, max_parts: int = 5) -> list[str]:
    stem = Path(filename).stem if Path(filename).suffix else filename
    parts = [
        part
        for part in re.split(r"[^a-z0-9]+", stem.lower())
        if part and part not in {"a", "an", "the", "new", "copy", "final", "old"}
    ]
    return parts[:max_parts] or ["unnamed"]


def _infer_domain_slug(filename: str, parent_path: str = "") -> str:
    text = f"{filename} {parent_path}".lower()
    checks = [
        ("development", ("python", "script", "code", "repo", "github", "autohotkey", "ahk", "programming", "agent")),
        ("trading", ("trading", "market", "investing", "stocks", "crypto", "chart", "candlestick")),
        ("documents", ("pdf", "doc", "paper", "letter", "contract", "readme", "notes")),
        ("data", ("csv", "xlsx", "sheet", "database", "sqlite", "export")),
        ("media", ("image", "png", "jpg", "video", "screenshot", "photo")),
        ("brain_system", ("brain", "river", "fis", "nlp", "folderbrain")),
        ("reference", ("ebook", "book", "guide", "manual", "research")),
    ]
    for domain, terms in checks:
        if any(term in text for term in terms):
            return domain
    return "general"


def _rename_suggestions(filename: str, parent_path: str, schema: str) -> dict[str, str]:
    baseline = _format_schema_name(filename, "baseline")
    active = _format_schema_name(filename, schema)
    domain = _infer_domain_slug(filename, parent_path)
    parts = _slug_parts(filename, max_parts=5)
    ext = Path(baseline).suffix
    topic = "-".join(parts)
    kind = "folder" if not ext else ext.lstrip(".") or "file"
    david = f"{domain}__{topic}__{kind}{ext if ext and not topic.endswith(ext.lstrip('.')) else ''}"
    river_topic = "-".join(parts[:4])
    river = f"{domain}__{river_topic}__v01{ext}"
    return {
        "selected": active,
        "baseline": baseline,
        "david_domain_slug": david,
        "river_nlp": river,
    }


def _rename_weirdness(name: str, evidence: str = "") -> int:
    stem = Path(name).stem if "." in name else name
    score = 0
    if _bad_name_reason(name):
        score += 40
    if re.search(r"!{2,}|[#@$%^&*]{2,}", stem):
        score += 20
    if re.search(r"(^|[\s_-])(aaa+|111+|000+)([\s_-]|$)", stem.lower()):
        score += 18
    if len(stem) >= 12 and re.fullmatch(r"[a-fA-F0-9_-]+", stem):
        score += 16
    if "  " in name or re.search(r"[_\s-]{3,}", name):
        score += 14
    letters = [ch for ch in stem if ch.isalpha()]
    if len(letters) >= 5 and "".join(letters).isupper():
        score += 12
    if "(copy" in name.lower() or "final final" in name.lower():
        score += 10
    if evidence:
        score += min(10, len(evidence) // 12)
    return score


def _sample_target_size(total: int) -> int:
    if total <= 200:
        return total
    if total <= 1000:
        return 70
    if total <= 10000:
        return 90
    if total <= 100000:
        return 120
    return 160


def cached_rename_sample(root: str, schema: str = "baseline", seed: int = 0) -> dict[str, Any]:
    init_db()
    root_text = str(Path(root))
    root_like = _like_root(root_text)
    allowed_schemas = {"baseline", "date_schema", "domain_schema", "johnny_decimal", "para"}
    schema = schema if schema in allowed_schemas else "baseline"

    with connect() as conn:
        finding_rows = conn.execute(
            """
            SELECT finding_id, finding_type, path, title, evidence, weight, risk, payload_json
            FROM organization_findings
            WHERE path LIKE ?
              AND finding_type IN ('bad_name', 'bad_folder_name')
              AND status = 'pending'
            ORDER BY weight DESC, finding_id DESC
            LIMIT 5000
            """,
            (root_like,),
        ).fetchall()
        file_rows_by_path = {
            row["filepath"]: row
            for row in conn.execute(
                """
                SELECT filepath, filename, parent_path, ext, size
                FROM files
                WHERE filepath LIKE ?
                """,
                (root_like,),
            ).fetchall()
        }

    candidates: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for row in finding_rows:
        path_text = row["path"] or ""
        if not path_text or path_text.lower() in seen_paths:
            continue
        seen_paths.add(path_text.lower())
        file_row = file_rows_by_path.get(path_text)
        filename = (file_row["filename"] if file_row else Path(path_text).name) or Path(path_text).name
        parent_path = (file_row["parent_path"] if file_row else str(Path(path_text).parent)) or ""
        new_name = _format_schema_name(filename, schema)
        suggestions = _rename_suggestions(filename, parent_path, schema)
        candidates.append(
            {
                "id": f"finding-{row['finding_id']}",
                "finding_id": row["finding_id"],
                "kind": "folder" if row["finding_type"] == "bad_folder_name" else "file",
                "filepath": path_text,
                "path": path_text,
                "parent_path": parent_path,
                "filename": filename,
                "original": filename,
                "new_name": new_name,
                "suggested": new_name,
                "suggestions": suggestions,
                "status": "would_rename" if filename != new_name else "already_clean",
                "reason": row["evidence"] or row["title"],
                "weight": int(row["weight"] or 8),
                "risk": row["risk"] or "low",
                "ext": (Path(filename).suffix.lower() or "(folder)" if row["finding_type"] == "bad_folder_name" else Path(filename).suffix.lower() or "(none)"),
                "score": _rename_weirdness(filename, row["evidence"] or ""),
                "selected": True,
                "editable": True,
            }
        )

    if not candidates:
        fallback = cached_rename_plan(root_text, limit=500)
        for op in fallback.get("operations", []):
            if op.get("status") == "already_clean":
                continue
            filename = op.get("filename") or Path(op.get("filepath", "")).name
            parent_path = str(Path(op.get("filepath", "")).parent)
            new_name = _format_schema_name(filename, schema)
            suggestions = _rename_suggestions(filename, parent_path, schema)
            candidates.append(
                {
                    "id": f"path-{hashlib.sha1((op.get('filepath') or filename).encode('utf-8', 'ignore')).hexdigest()[:12]}",
                    "kind": "file",
                    "filepath": op.get("filepath"),
                    "path": op.get("filepath"),
                    "parent_path": parent_path,
                    "filename": filename,
                    "original": filename,
                    "new_name": new_name,
                    "suggested": new_name,
                    "suggestions": suggestions,
                    "status": op.get("status"),
                    "reason": "Baseline rule would change this name.",
                    "weight": 8,
                    "risk": "low",
                    "ext": Path(filename).suffix.lower() or "(none)",
                    "score": _rename_weirdness(filename, "Baseline rule would change this name."),
                    "selected": True,
                    "editable": True,
                }
            )

    new_path_keys: set[str] = set()
    for item in candidates:
        key = str(Path(item["parent_path"] or "") / item["new_name"]).lower()
        if key in new_path_keys:
            item["status"] = "collision"
            item["score"] += 30
            item["reason"] = f"{item['reason']} Possible name collision."
        new_path_keys.add(key)

    total = len(candidates)
    target_size = _sample_target_size(total)
    rng = random.Random(seed)
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    def take(group_id: str, title: str, rows: list[dict[str, Any]], count: int) -> dict[str, Any]:
        picked: list[dict[str, Any]] = []
        for row in rows:
            if len(picked) >= count:
                break
            if row["id"] in selected_ids:
                continue
            selected_ids.add(row["id"])
            copied = dict(row)
            copied["sample_group"] = group_id
            picked.append(copied)
            selected.append(copied)
        return {"id": group_id, "title": title, "rows": picked}

    groups: list[dict[str, Any]] = []
    if total <= 200:
        groups.append(
            {
                "id": "all",
                "title": "All Rename Candidates",
                "rows": sorted(candidates, key=lambda row: (-row["score"], row["filename"].lower())),
            }
        )
        selected = groups[0]["rows"]
    else:
        by_score = sorted(candidates, key=lambda row: (-row["score"], row["filename"].lower()))
        groups.append(take("worst", "Worst Names", by_score, min(40, max(20, target_size // 3))))

        alpha_rows = []
        alpha_seen: set[str] = set()
        for row in sorted(candidates, key=lambda item: item["filename"].lower()):
            first = re.sub(r"[^a-z0-9]", "#", row["filename"].lower()[:1] or "#")
            if first not in alpha_seen:
                alpha_seen.add(first)
                alpha_rows.append(row)
        groups.append(take("alphabet", "Alphabetical Spread", alpha_rows, 36))

        ext_rows = []
        ext_seen: set[str] = set()
        for row in sorted(candidates, key=lambda item: (item["ext"], -item["score"])):
            if row["ext"] not in ext_seen:
                ext_seen.add(row["ext"])
                ext_rows.append(row)
        groups.append(take("extension", "Extension Coverage", ext_rows, 24))

        folder_rows = []
        folder_seen: set[str] = set()
        for row in sorted(candidates, key=lambda item: (item["parent_path"].lower(), -item["score"])):
            parent = row["parent_path"].lower()
            if parent not in folder_seen:
                folder_seen.add(parent)
                folder_rows.append(row)
        groups.append(take("folder", "Folder Coverage", folder_rows, 24))

        remaining = [row for row in candidates if row["id"] not in selected_ids]
        rng.shuffle(remaining)
        groups.append(take("random", "Random Spot Check", remaining, max(0, target_size - len(selected))))
        groups = [group for group in groups if group["rows"]]

    return {
        "source": "sqlite_cache",
        "path": root_text,
        "schema": schema,
        "schema_label": _rename_schema_label(schema),
        "mode": "all" if total <= 200 else "sample",
        "total_candidates": total,
        "sample_size": len(selected),
        "selected_count": len(selected),
        "confirmation_required": total > 10000,
        "groups": groups,
        "counts": {
            "would_rename": sum(1 for item in candidates if item["status"] == "would_rename"),
            "already_clean": sum(1 for item in candidates if item["status"] == "already_clean"),
            "collision": sum(1 for item in candidates if item["status"] == "collision"),
        },
        "seed": seed,
    }


def analyze_organization_opportunities(
    root: str,
    scan_id: int | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    init_db()
    root_text = str(Path(root))
    root_like = _like_root(root_text)
    findings: list[dict[str, Any]] = []

    with connect() as conn:
        protected_rows = conn.execute(
            """
            SELECT folder_path, folder_name
            FROM folders
            WHERE folder_path LIKE ?
            """,
            (root_like,),
        ).fetchall()
        for row in protected_rows:
            name = (row["folder_name"] or "").lower()
            if name in PROTECTED_FOLDER_NAMES:
                findings.append(
                    _finding(
                        "protected_system_folder",
                        row["folder_path"],
                        "Protected/system folder found",
                        f"{row['folder_name']} should not be moved, merged, or archived automatically.",
                        "protect",
                        10,
                        "high",
                    )
                )

        project_rows = conn.execute(
            """
            SELECT parent_path, GROUP_CONCAT(filename, ', ') AS markers, COUNT(*) AS marker_count
            FROM files
            WHERE filepath LIKE ? AND LOWER(filename) IN ({})
            GROUP BY parent_path
            LIMIT 50
            """.format(",".join("?" for _ in PROJECT_SEED_FILES)),
            (root_like, *PROJECT_SEED_FILES),
        ).fetchall()
        for row in project_rows:
            findings.append(
                _finding(
                    "project_seed",
                    row["parent_path"],
                    "Project seed found",
                    f"Contains {row['markers']}; treat as possible active work even if small.",
                    "protect_project_seed",
                    9,
                    "medium",
                    {"marker_count": row["marker_count"]},
                )
            )

        dup_rows = conn.execute(
            """
            SELECT filename, size, COUNT(*) AS count,
                   GROUP_CONCAT(filepath, CHAR(10)) AS paths
            FROM files
            WHERE filepath LIKE ? AND size IS NOT NULL
            GROUP BY LOWER(filename), size
            HAVING COUNT(*) > 1
            ORDER BY count DESC
            LIMIT 15
            """,
            (root_like,),
        ).fetchall()
        for row in dup_rows:
            findings.append(
                _finding(
                    "duplicate_filename_size",
                    root_text,
                    "Possible duplicate files",
                    f"{row['count']} files share the name {row['filename']} and the same size.",
                    "duplicate_review",
                    8,
                    "medium",
                    {"filename": row["filename"], "size": row["size"], "paths": (row["paths"] or "").split("\n")[:12]},
                )
            )

        empty_tiny_rows = conn.execute(
            """
            SELECT folder_path, folder_name, file_count, child_folder_count, total_size
            FROM folders
            WHERE folder_path LIKE ?
              AND LOWER(folder_name) NOT IN ({})
            ORDER BY (file_count + child_folder_count), total_size
            LIMIT 80
            """.format(",".join("?" for _ in PROTECTED_FOLDER_NAMES)),
            (root_like, *PROTECTED_FOLDER_NAMES),
        ).fetchall()
        for row in empty_tiny_rows:
            item_count = int(row["file_count"] or 0) + int(row["child_folder_count"] or 0)
            if item_count == 0:
                findings.append(
                    _finding(
                        "empty_folder",
                        row["folder_path"],
                        "Empty folder found",
                        "No cached files or child folders were found here.",
                        "delete_later_review",
                        5,
                    )
                )
            elif item_count <= 2 and int(row["total_size"] or 0) < 1024 * 1024:
                findings.append(
                    _finding(
                        "tiny_folder",
                        row["folder_path"],
                        "Tiny folder found",
                        f"Only {item_count} cached item(s), so it may be a combine/archive candidate unless it is a project seed.",
                        "combine_or_archive_review",
                        5,
                    )
                )

        bad_file_rows = conn.execute(
            """
            SELECT filepath, filename
            FROM files
            WHERE filepath LIKE ?
            ORDER BY last_seen DESC
            LIMIT 500
            """,
            (root_like,),
        ).fetchall()
        for row in bad_file_rows:
            reason = _bad_name_reason(row["filename"])
            if reason:
                findings.append(
                    _finding(
                        "bad_name",
                        row["filepath"],
                        "Rename candidate found",
                        reason,
                        "rename_preview",
                        8,
                    )
                )

        bad_folder_rows = conn.execute(
            """
            SELECT folder_path, folder_name
            FROM folders
            WHERE folder_path LIKE ?
            LIMIT 500
            """,
            (root_like,),
        ).fetchall()
        for row in bad_folder_rows:
            reason = _bad_name_reason(row["folder_name"])
            if reason:
                findings.append(
                    _finding(
                        "bad_folder_name",
                        row["folder_path"],
                        "Folder rename candidate found",
                        reason,
                        "rename_preview",
                        8,
                    )
                )

        archive_rows = conn.execute(
            """
            SELECT filepath, filename
            FROM files
            WHERE filepath LIKE ?
            LIMIT 700
            """,
            (root_like,),
        ).fetchall()
        for row in archive_rows:
            lower_path = row["filepath"].lower()
            if any(term in lower_path for term in ARCHIVE_RESIDUE_TERMS):
                findings.append(
                    _finding(
                        "archive_export_residue",
                        row["filepath"],
                        "Archive/export residue found",
                        "Name or path looks like backup, export, copy, old, or attachment residue.",
                        "archive_review",
                        7,
                    )
                )

        unknown_rows = conn.execute(
            """
            SELECT filepath, filename, ext
            FROM files
            WHERE filepath LIKE ?
              AND (ext = '' OR ext IS NULL OR LOWER(ext) IN ({}) OR LENGTH(filename) >= 28)
            LIMIT 80
            """.format(",".join("?" for _ in UNKNOWN_EXTENSIONS)),
            (root_like, *UNKNOWN_EXTENSIONS),
        ).fetchall()
        for row in unknown_rows:
            findings.append(
                _finding(
                    "unknown_file",
                    row["filepath"],
                    "Unknown file needs review",
                    f"{row['filename']} has little readable identity or an uncommon extension.",
                    "unknown_review",
                    7,
                )
            )

        sidecar_rows = conn.execute(
            """
            SELECT folder_path
            FROM folders
            WHERE folder_path LIKE ?
            ORDER BY last_scanned DESC
            LIMIT 150
            """,
            (root_like,),
        ).fetchall()
        for row in sidecar_rows:
            folder_path = Path(row["folder_path"])
            if not (folder_path / ".folderbrain.json").exists():
                findings.append(
                    _finding(
                        "missing_folderbrain_metadata",
                        row["folder_path"],
                        "Folderbrain metadata missing",
                        "This folder does not have a .folderbrain.json sidecar yet.",
                        "create_folderbrain_sidecar",
                        7,
                    )
                )

        large_rows = conn.execute(
            """
            SELECT folder_path, total_size
            FROM folders
            WHERE folder_path LIKE ? AND total_size >= ?
            ORDER BY total_size DESC
            LIMIT 20
            """,
            (root_like, 500 * 1024 * 1024),
        ).fetchall()
        for row in large_rows:
            findings.append(
                _finding(
                    "large_space_user",
                    row["folder_path"],
                    "Large space user found",
                    f"Cached folder size is about {round((row['total_size'] or 0) / (1024 * 1024), 1)} MB.",
                    "storage_review",
                    3,
                )
            )

    cluster_data = cached_theme_clusters(root=root_text, min_folders=2, limit=8)
    for cluster in cluster_data.get("suggestions", []):
        findings.append(
            _finding(
                "single_theme_cluster",
                root_text,
                "Single theme appears in multiple places",
                cluster.get("summary", "Theme appears across multiple folders."),
                cluster.get("decision", "create_hub"),
                6,
                "low",
                cluster,
            )
        )

    findings = sorted(findings, key=lambda item: (-item["weight"], item["finding_type"], item["path"]))
    deduped: list[dict[str, Any]] = []
    seen = set()
    for item in findings:
        key = (item["finding_type"], item["path"], item["title"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    store_organization_findings(scan_id, deduped)
    return {
        "scan_id": scan_id,
        "root": root_text,
        "finding_count": len(deduped),
        "top_findings": deduped[:limit],
        "weights": {
            "protected_system_folder": 10,
            "project_seed": 9,
            "duplicate_filename_size": 8,
            "bad_name": 8,
            "archive_export_residue": 7,
            "missing_folderbrain_metadata": 7,
            "unknown_file": 7,
            "single_theme_cluster": 6,
            "tiny_folder": 5,
            "empty_folder": 5,
            "large_space_user": 3,
        },
    }


def cache_nlp_result(entry: dict[str, Any]) -> None:
    file_id = upsert_file(entry["filepath"])
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO classifications (
                scan_id, file_id, domain, domain_code, confidence, source,
                matched_json, keywords_json, text_preview, names_json, markov_json,
                payload_json, created_at
            )
            VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id,
                entry.get("domain"),
                entry.get("domain_code"),
                entry.get("confidence"),
                entry.get("source"),
                "[]",
                "[]",
                entry.get("nlp_summary"),
                "{}",
                "{}",
                json.dumps(entry, ensure_ascii=True),
                now_iso(),
            ),
        )


def cache_status() -> dict[str, Any]:
    init_db()
    with connect() as conn:
        latest = conn.execute(
            "SELECT * FROM scan_runs ORDER BY scan_id DESC LIMIT 1"
        ).fetchone()
        counts = {
            "scan_runs": conn.execute("SELECT COUNT(*) AS c FROM scan_runs").fetchone()["c"],
            "files": conn.execute("SELECT COUNT(*) AS c FROM files").fetchone()["c"],
            "folders": conn.execute("SELECT COUNT(*) AS c FROM folders").fetchone()["c"],
            "classifications": conn.execute("SELECT COUNT(*) AS c FROM classifications").fetchone()["c"],
            "decisions": conn.execute("SELECT COUNT(*) AS c FROM decisions").fetchone()["c"],
            "roots": conn.execute("SELECT COUNT(*) AS c FROM root_registry").fetchone()["c"],
            "actions": conn.execute("SELECT COUNT(*) AS c FROM action_log").fetchone()["c"],
            "findings": conn.execute("SELECT COUNT(*) AS c FROM organization_findings").fetchone()["c"],
            "total_size": conn.execute("SELECT COALESCE(SUM(size), 0) AS c FROM files").fetchone()["c"],
        }
        domain_rows = conn.execute(
            """
            SELECT domain, COUNT(*) AS count
            FROM classifications
            WHERE classification_id IN (
                SELECT MAX(classification_id) FROM classifications GROUP BY file_id
            )
            GROUP BY domain
            ORDER BY count DESC
            LIMIT 12
            """
        ).fetchall()
        ext_rows = conn.execute(
            """
            SELECT COALESCE(NULLIF(ext, ''), '(none)') AS ext, COUNT(*) AS count
            FROM files
            GROUP BY COALESCE(NULLIF(ext, ''), '(none)')
            ORDER BY count DESC, ext
            LIMIT 12
            """
        ).fetchall()
        inventory_rows = conn.execute(
            """
            SELECT scan_id, scan_path, started_at, finished_at, file_count, status
            FROM scan_runs
            WHERE mode = 'inventory'
            ORDER BY scan_id DESC
            LIMIT 5
            """
        ).fetchall()
        finding_rows = conn.execute(
            """
            SELECT finding_type, COUNT(*) AS count, MAX(weight) AS max_weight
            FROM organization_findings
            GROUP BY finding_type
            ORDER BY max_weight DESC, count DESC, finding_type
            LIMIT 12
            """
        ).fetchall()
        action_rows = conn.execute(
            """
            SELECT action_type, status, COUNT(*) AS count
            FROM action_log
            GROUP BY action_type, status
            ORDER BY count DESC, action_type
            LIMIT 12
            """
        ).fetchall()
    return {
        "database": str(DB_PATH),
        "counts": counts,
        "latest_scan": dict(latest) if latest else None,
        "domains": [dict(row) for row in domain_rows],
        "extensions": [dict(row) for row in ext_rows],
        "inventory_scans": [dict(row) for row in inventory_rows],
        "finding_types": [dict(row) for row in finding_rows],
        "action_types": [dict(row) for row in action_rows],
    }


def recent_cached_files(limit: int = 100, root: str = "", query: str = "", ext: str = "") -> list[dict[str, Any]]:
    init_db()
    clauses = []
    args: list[Any] = []
    if root:
        clauses.append("f.filepath LIKE ?")
        clean_root = root.rstrip("\\")
        args.append(f"{clean_root}%")
    if query:
        clauses.append("(f.filename LIKE ? OR f.parent_path LIKE ?)")
        args.extend([f"%{query}%", f"%{query}%"])
    if ext:
        clauses.append("f.ext = ?")
        args.append(ext if ext.startswith(".") else f".{ext}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    args.append(limit)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT f.filepath, f.filename, f.ext, f.size, f.mtime,
                   f.md5_hash, f.hash_algo, f.hash_status, f.hashed_at, f.last_seen,
                   c.domain, c.domain_code, c.confidence, c.source,
                   c.keywords_json, c.names_json, c.payload_json, c.created_at
            FROM files f
            LEFT JOIN classifications c ON c.classification_id = (
                SELECT MAX(classification_id)
                FROM classifications c2
                WHERE c2.file_id = f.file_id
            )
            {where}
            ORDER BY c.created_at DESC
            LIMIT ?
            """,
            args,
        ).fetchall()
    results = []
    for row in rows:
        record = dict(row)
        for key in ["keywords_json", "names_json", "payload_json"]:
            try:
                record[key.replace("_json", "")] = json.loads(record.pop(key) or "{}")
            except json.JSONDecodeError:
                record[key.replace("_json", "")] = {}
        results.append(record)
    return results


def cached_file_paths(root: str = "", limit: int = 500, only_unclassified: bool = False) -> list[str]:
    init_db()
    clauses = []
    args: list[Any] = []
    if root:
        clean_root = root.rstrip("\\")
        clauses.append("f.filepath LIKE ?")
        args.append(f"{clean_root}%")
    if only_unclassified:
        clauses.append(
            """
            NOT EXISTS (
                SELECT 1 FROM classifications c
                WHERE c.file_id = f.file_id
            )
            """
        )
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    args.append(limit)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT f.filepath
            FROM files f
            {where}
            ORDER BY f.last_seen DESC
            LIMIT ?
            """,
            args,
        ).fetchall()
    return [row["filepath"] for row in rows]


def cached_folder_children(folder_path: str, limit: int = 300) -> dict[str, Any]:
    init_db()
    target = Path(folder_path)
    with connect() as conn:
        folder = conn.execute("SELECT * FROM folders WHERE folder_path = ?", (str(target),)).fetchone()
        folders = conn.execute(
            """
            SELECT folder_path, folder_name, parent_path, file_count, child_folder_count, total_size, last_scanned
            FROM folders
            WHERE parent_path = ?
            ORDER BY folder_name
            LIMIT ?
            """,
            (str(target), limit),
        ).fetchall()
        files = conn.execute(
            """
            SELECT filepath, filename, ext, size, mtime, last_seen
            FROM files
            WHERE parent_path = ?
            ORDER BY filename
            LIMIT ?
            """,
            (str(target), limit),
        ).fetchall()
    return {
        "folder": dict(folder) if folder else {"folder_path": str(target), "folder_name": target.name},
        "folders": [dict(row) for row in folders],
        "files": [dict(row) for row in files],
    }


def _root_code_for_path(conn: sqlite3.Connection, target: str) -> str | None:
    rows = conn.execute(
        "SELECT root_code, root_path FROM root_registry ORDER BY LENGTH(root_path) DESC"
    ).fetchall()
    clean_target = target.rstrip("\\/")
    for row in rows:
        clean_root = str(row["root_path"]).rstrip("\\/")
        if clean_target == clean_root or clean_target.startswith(clean_root + "\\") or clean_target.startswith(clean_root + "/"):
            return row["root_code"]
    return None


def _tokens_from_text(value: str, limit: int = 12) -> list[str]:
    stop = {
        "the", "and", "for", "with", "from", "this", "that", "file", "files",
        "folder", "copy", "new", "old", "final", "data", "all", "more",
        "documents", "document", "image", "images", "users", "lowes", "onedrive",
        "desktop", "downloads", "pictures",
    }
    tokens = []
    for token in re.findall(r"[a-zA-Z][a-zA-Z0-9]{2,}", value.lower()):
        if token not in stop and token not in tokens:
            tokens.append(token)
        if len(tokens) >= limit:
            break
    return tokens


def _folder_slug(folder_name: str, keywords: list[str], domain: str) -> str:
    pieces = [domain.lower()] if domain and domain.lower() not in {"unknown", "uncategorized"} else []
    pieces.extend(keywords[:5] or _tokens_from_text(folder_name, 5))
    raw = "-".join(pieces or ["folder"])
    clean = re.sub(r"[^a-z0-9]+", "-", raw.lower())
    return re.sub(r"-+", "-", clean).strip("-") or "folder"


def _folder_summary_sentence(folder_name: str, domain: str, files: int, folders: int, keywords: list[str]) -> str:
    domain_text = domain if domain and domain != "unknown" else "uncategorized"
    topic = ", ".join(keywords[:4]) if keywords else "mixed files"
    return f"{folder_name} looks like a {domain_text} folder with {files} cached file(s), {folders} cached subfolder(s), and signals around {topic}."


def _domain_from_inferred_slug(slug: str) -> tuple[str, str, float]:
    mapping = {
        "development": ("DEVELOPMENT", "DV", 62.0),
        "trading": ("DATA_TRADING", "DT", 68.0),
        "documents": ("DOCUMENTS", "DC", 55.0),
        "data": ("DATA_TRADING", "DT", 54.0),
        "media": ("MEDIA", "MD", 58.0),
        "brain_system": ("AI_ML", "AI", 60.0),
        "reference": ("DOCUMENTS", "DC", 54.0),
    }
    return mapping.get(slug, ("unknown", None, 0.0))


def folderbrain_summary(folder_path: str) -> dict[str, Any]:
    init_db()
    target = Path(folder_path)
    target_text = str(target)
    clean_root = target_text.rstrip("\\/")
    like_root = f"{clean_root}%"
    with connect() as conn:
        folder = conn.execute("SELECT * FROM folders WHERE folder_path = ?", (target_text,)).fetchone()
        root_code = _root_code_for_path(conn, target_text)
        inventory = {
            "files": conn.execute("SELECT COUNT(*) AS c FROM files WHERE filepath LIKE ?", (like_root,)).fetchone()["c"],
            "folders": conn.execute("SELECT COUNT(*) AS c FROM folders WHERE folder_path LIKE ?", (like_root,)).fetchone()["c"],
            "scans": conn.execute("SELECT COUNT(*) AS c FROM scan_runs WHERE scan_path LIKE ?", (like_root,)).fetchone()["c"],
            "decisions": conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM decisions d
                LEFT JOIN files f ON f.file_id = d.file_id
                WHERE f.filepath LIKE ? OR d.filename LIKE ?
                """,
                (like_root, f"%{target.name}%"),
            ).fetchone()["c"],
        }
        ext_rows = conn.execute(
            """
            SELECT LOWER(REPLACE(COALESCE(NULLIF(ext, ''), '(none)'), '.', '')) AS ext, COUNT(*) AS count
            FROM files
            WHERE filepath LIKE ?
            GROUP BY LOWER(REPLACE(COALESCE(NULLIF(ext, ''), '(none)'), '.', ''))
            ORDER BY count DESC, ext
            LIMIT 12
            """,
            (like_root,),
        ).fetchall()
        latest_scan = conn.execute(
            """
            SELECT scan_id, scan_path, started_at, finished_at, file_count, status
            FROM scan_runs
            WHERE scan_path LIKE ?
            ORDER BY scan_id DESC
            LIMIT 1
            """,
            (like_root,),
        ).fetchone()
        domain_rows = conn.execute(
            """
            SELECT c.domain, c.domain_code, COUNT(*) AS count,
                   ROUND(AVG(COALESCE(c.confidence, 0)), 1) AS confidence
            FROM classifications c
            JOIN files f ON f.file_id = c.file_id
            WHERE f.filepath LIKE ?
              AND c.classification_id IN (
                SELECT MAX(c2.classification_id)
                FROM classifications c2
                GROUP BY c2.file_id
              )
            GROUP BY c.domain, c.domain_code
            ORDER BY count DESC, confidence DESC
            LIMIT 8
            """,
            (like_root,),
        ).fetchall()
        keyword_rows = conn.execute(
            """
            SELECT c.keywords_json
            FROM classifications c
            JOIN files f ON f.file_id = c.file_id
            WHERE f.filepath LIKE ?
              AND c.keywords_json IS NOT NULL
              AND c.classification_id IN (
                SELECT MAX(c2.classification_id)
                FROM classifications c2
                GROUP BY c2.file_id
              )
            LIMIT 250
            """,
            (like_root,),
        ).fetchall()
        finding_rows = conn.execute(
            """
            SELECT finding_type, COUNT(*) AS count, MAX(weight) AS weight
            FROM organization_findings
            WHERE path LIKE ?
            GROUP BY finding_type
            ORDER BY weight DESC, count DESC
            LIMIT 8
            """,
            (like_root,),
        ).fetchall()
        name_rows = conn.execute(
            """
            SELECT filename AS name FROM files
            WHERE filepath LIKE ?
            ORDER BY size DESC
            LIMIT 300
            """,
            (like_root,),
        ).fetchall()
        child_folder_rows = conn.execute(
            """
            SELECT folder_name AS name FROM folders
            WHERE folder_path LIKE ?
            LIMIT 120
            """,
            (like_root,),
        ).fetchall()
    keyword_counts: dict[str, int] = {}
    for row in keyword_rows:
        try:
            values = json.loads(row["keywords_json"] or "[]")
        except json.JSONDecodeError:
            values = []
        for value in values:
            key = str(value).lower().strip()
            if len(key) < 3:
                continue
            keyword_counts[key] = keyword_counts.get(key, 0) + 1
    if not keyword_counts:
        keyword_source = " ".join([target.name, *[row["name"] for row in child_folder_rows], *[row["name"] for row in name_rows]])
        keyword_counts = {}
        for token in _tokens_from_text(keyword_source, 30):
            keyword_counts[token] = keyword_counts.get(token, 0) + 1
    keywords = [
        key for key, _count in sorted(keyword_counts.items(), key=lambda pair: (-pair[1], pair[0]))[:12]
    ]
    dominant_domains = [dict(row) for row in domain_rows]
    top_domain = dominant_domains[0]["domain"] if dominant_domains else "unknown"
    top_domain_code = dominant_domains[0].get("domain_code") if dominant_domains else None
    top_confidence = float(dominant_domains[0].get("confidence") or 0) if dominant_domains else 0.0
    inferred_slug = _infer_domain_slug(
        " ".join([target.name, *keywords[:12], *[row["name"] for row in child_folder_rows[:20]]]),
        target_text,
    )
    inferred_domain, inferred_code, inferred_confidence = _domain_from_inferred_slug(inferred_slug)
    if (top_domain in {"unknown", "UNCATEGORIZED"} or top_confidence < inferred_confidence) and inferred_domain != "unknown":
        top_domain = inferred_domain
        top_domain_code = inferred_code
        top_confidence = inferred_confidence
        if not dominant_domains or dominant_domains[0].get("domain") != inferred_domain:
            dominant_domains.insert(
                0,
                {
                    "domain": inferred_domain,
                    "domain_code": inferred_code,
                    "count": 0,
                    "confidence": inferred_confidence,
                    "source": "folder_name_inference",
                },
            )
    mixed_domains = len([row for row in dominant_domains if row.get("domain") and row.get("domain") != "UNCATEGORIZED"]) > 1
    slug = _folder_slug(target.name, keywords, top_domain)
    folder_id = f"FOLD_{hashlib.sha1(target_text.lower().encode('utf-8')).hexdigest()[:10].upper()}"
    summary = {
        "schema": "folderbrain.v1",
        "folder_id": folder_id,
        "folder_path": target_text,
        "folder_name": target.name,
        "path": target_text,
        "root": root_code,
        "state": "cached" if folder or inventory["files"] or inventory["folders"] else "uncached",
        "summary": _folder_summary_sentence(target.name, top_domain, inventory["files"], inventory["folders"], keywords),
        "slug": slug,
        "keywords": keywords,
        "tags": [tag for tag in [top_domain.lower() if top_domain else "", *keywords[:5]] if tag and tag != "unknown"],
        "inventory": inventory,
        "top_extensions": {row["ext"]: row["count"] for row in ext_rows},
        "dominant_domains": dominant_domains,
        "classification": {
            "domain": top_domain,
            "domain_code": top_domain_code,
            "theme": keywords[0] if keywords else None,
            "confidence": top_confidence,
            "source": "sqlite_cache_folder_rollup",
            "needs_review": top_confidence < 70 or mixed_domains,
            "review_reason": "mixed domains" if mixed_domains else "low confidence" if top_confidence < 70 else "",
        },
        "route": {
            "suggested_folder": "",
            "move_as_unit": not mixed_domains,
            "split_recommended": mixed_domains,
            "keep_in_place": True,
        },
        "findings": [dict(row) for row in finding_rows],
        "history": {
            "generated_at": now_iso(),
            "generator": "FIS folderbrain",
            "database": str(DB_PATH),
        },
        "actions": {
            "available": [
                "classify_for_review",
                "find_themes",
                "rename_preview",
                "write_folderbrain",
                "archive_review",
            ]
        },
        "last_scan": latest_scan["finished_at"] or latest_scan["started_at"] if latest_scan else None,
        "last_scan_status": latest_scan["status"] if latest_scan else None,
    }
    if folder:
        summary["folder"] = {
            "name": folder["folder_name"],
            "file_count": folder["file_count"],
            "child_folder_count": folder["child_folder_count"],
            "total_size": folder["total_size"],
            "last_scanned": folder["last_scanned"],
        }
    return summary


def write_folderbrain(folder_path: str) -> dict[str, Any]:
    target = Path(folder_path)
    if not target.exists() or not target.is_dir():
        return {"error": f"Folder not found: {folder_path}"}
    summary = folderbrain_summary(folder_path)
    action = record_action(
        "write_folderbrain",
        root_code=summary.get("root"),
        target_path=str(target),
        status="running",
        payload={"sidecar": ".folderbrain.json"},
    )
    sidecar = target / ".folderbrain.json"
    try:
        sidecar.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
    except Exception as exc:
        update_action_status(action["action_id"], "error", {"sidecar": str(sidecar)}, str(exc))
        return {"error": str(exc), "action_code": action["action_code"], "sidecar": str(sidecar)}
    update_action_status(action["action_id"], "complete", {"sidecar": str(sidecar)})
    return {"action_code": action["action_code"], "sidecar": str(sidecar), "summary": summary}


def write_folderbrains(root: str, limit: int = 500, overwrite: bool = True) -> dict[str, Any]:
    init_db()
    root_text = str(Path(root))
    root_like = _like_root(root_text)
    action = record_action(
        "write_folderbrains",
        target_path=root_text,
        status="running",
        payload={"sidecar": ".folderbrain.json", "limit": limit, "overwrite": overwrite},
    )
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT folder_path
            FROM folders
            WHERE folder_path LIKE ?
            ORDER BY LENGTH(folder_path), folder_path
            LIMIT ?
            """,
            (root_like, limit),
        ).fetchall()
    written: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    for row in rows:
        folder_path = Path(row["folder_path"])
        sidecar = folder_path / ".folderbrain.json"
        if sidecar.exists() and not overwrite:
            skipped.append({"folder": str(folder_path), "reason": "exists"})
            continue
        if not folder_path.exists() or not folder_path.is_dir():
            skipped.append({"folder": str(folder_path), "reason": "missing"})
            continue
        try:
            summary = folderbrain_summary(str(folder_path))
            sidecar.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
            written.append({"folder": str(folder_path), "sidecar": str(sidecar)})
        except Exception as exc:
            errors.append({"folder": str(folder_path), "error": str(exc)})
    status = "error" if errors else "complete"
    update_action_status(
        action["action_id"],
        status,
        {"written": len(written), "skipped": len(skipped), "errors": len(errors)},
    )
    return {
        "action_code": action["action_code"],
        "root": root_text,
        "sidecar": ".folderbrain.json",
        "written_count": len(written),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "written": written[:25],
        "skipped": skipped[:25],
        "errors": errors[:25],
    }


def cached_theme_clusters(root: str = "", min_folders: int = 2, limit: int = 12) -> dict[str, Any]:
    init_db()
    root_filter = root.rstrip("\\")
    clauses = []
    args: list[Any] = []
    if root_filter:
        clauses.append("f.filepath LIKE ?")
        args.append(f"{root_filter}%")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""

    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT f.filepath, f.filename, f.parent_path, f.ext, f.size,
                   c.domain, c.domain_code, c.confidence
            FROM files f
            LEFT JOIN classifications c ON c.classification_id = (
                SELECT MAX(classification_id)
                FROM classifications c2
                WHERE c2.file_id = f.file_id
            )
            {where}
            LIMIT 5000
            """,
            args,
        ).fetchall()

    ext_themes = {
        "PDFs": {".pdf"},
        "ebooks": {".epub", ".mobi", ".azw", ".azw3", ".fb2", ".pdf"},
        "images": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tiff"},
        "programming": {".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".sql", ".ps1", ".bat", ".ahk", ".json", ".yaml", ".yml"},
        "AutoHotkey": {".ahk"},
        "archives": {".zip", ".7z", ".rar", ".tar", ".gz"},
    }
    alias_themes = {
        "autohotkey": ["ahk", "auto hot key", "auto-hot-key", "auto hotkey", "auto-hotkey", "autohotkey"],
        "programming": ["progaimng", "programing", "programming"],
        "attachment": ["attache", "attach", "attachment", "attachments"],
        "archive/export": ["archive", "archives", "export", "exports", "trash", "gsdata", "changed files"],
        "investing": ["investing", "daily market", "patterns search", "pattern search"],
        "books/library": ["ebook", "ebooks", "epub", "pdfs", "anthony robbins", "awaken the giant"],
        "emotions/affirmations": ["emotions", "affirmations"],
    }
    common_words = {
        "files", "file", "folder", "new", "old", "copy", "backup", "misc",
        "temp", "data", "docs", "documents", "export", "exports", "archive",
        "changed", "training", "pre", "daily", "all",
    }

    def add_candidate(bucket: dict[str, dict[str, Any]], key: str, row: sqlite3.Row, kind: str) -> None:
        item = bucket.setdefault(
            key,
            {
                "theme": key,
                "kind": kind,
                "decision": "review",
                "file_count": 0,
                "total_size": 0,
                "folders": {},
                "extensions": {},
            },
        )
        item["file_count"] += 1
        item["total_size"] += row["size"] or 0
        parent = row["parent_path"] or ""
        item["folders"][parent] = item["folders"].get(parent, 0) + 1
        ext = row["ext"] or "(none)"
        item["extensions"][ext] = item["extensions"].get(ext, 0) + 1

    candidates: dict[str, dict[str, Any]] = {}
    for row in rows:
        ext = (row["ext"] or "").lower()
        for theme, exts in ext_themes.items():
            if ext in exts:
                add_candidate(candidates, theme, row, "extension")

        domain = row["domain"]
        if domain and domain != "UNCATEGORIZED":
            add_candidate(candidates, domain, row, "learned domain")

        parent_name = Path(row["parent_path"] or "").name.lower()
        combined_name = f"{parent_name} {(row['filename'] or '').lower()}".replace("_", " ")
        combined_spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", combined_name)
        combined_slug = re.sub(r"[^a-z0-9]+", " ", combined_spaced.lower())
        for theme, aliases in alias_themes.items():
            if any(alias in combined_slug for alias in aliases):
                add_candidate(candidates, theme, row, "alias")

        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9]{2,}", parent_name):
            token = token.lower()
            if token not in common_words:
                add_candidate(candidates, token, row, "folder name")

    suggestions = []
    for item in candidates.values():
        folder_count = len(item["folders"])
        if folder_count < min_folders:
            continue
        top_folders = sorted(item["folders"].items(), key=lambda pair: (-pair[1], pair[0]))[:8]
        top_exts = sorted(item["extensions"].items(), key=lambda pair: (-pair[1], pair[0]))[:8]
        if item["theme"] == "archive/export":
            decision = "archive"
            recommendation = "Keep out of active work; review as archive/export/system residue before deleting anything."
        elif folder_count > 1 and item["kind"] in {"alias", "learned domain", "extension"}:
            decision = "create_hub"
            recommendation = "Create a shared hub or review view first; do not merge automatically."
        elif item["kind"] == "folder name":
            decision = "separate"
            recommendation = "Keep separate for now; create a shared theme view before moving anything."
        elif item["theme"] in {"PDFs", "ebooks", "images", "archives"}:
            decision = "create_hub"
            recommendation = "Usually keep source folders separate; consider a reviewed collection folder or tag."
        else:
            decision = "create_hub"
            recommendation = "Keep separate folders, but review as one theme cluster."
        suggestions.append(
            {
                "theme": item["theme"],
                "kind": item["kind"],
                "decision": decision,
                "file_count": item["file_count"],
                "folder_count": folder_count,
                "total_size": item["total_size"],
                "extensions": [{"ext": ext, "count": count} for ext, count in top_exts],
                "folders": [{"path": path, "count": count} for path, count in top_folders],
                "summary": f"{item['theme']} appears across {folder_count} folders with {item['file_count']} cached files.",
                "recommendation": recommendation,
            }
        )

    suggestions.sort(key=lambda item: (-item["folder_count"], -item["file_count"], item["theme"]))
    return {
        "root": root,
        "file_sample": len(rows),
        "min_folders": min_folders,
        "suggestions": suggestions[:limit],
    }

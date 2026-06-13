"""Twice-daily Postgres sync for FAP local logs.

The watcher path should stay fast. It can write local JSONL immediately, and
this sync lane can push durable movement records to Postgres on a schedule.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

try:
    import psycopg2
    HAS_PG = True
except ImportError:
    HAS_PG = False

from engines.pipeline.pipeline_engine import DDL

LOG_DIRS = [
    Path(os.environ.get("FAP_LOG_DIR", r"D:\FAP\logs")),
    Path(os.environ.get("FAP_ENGINE_LOG_DIR", r"D:\BIL\data\fap_logs")),
]
REPORT_DIR = Path(os.environ.get("FAP_SYNC_REPORT_DIR", r"D:\BIL\data\fap_sync"))
PG_DSN = os.environ.get("FAP_PG_DSN", "")


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "postgres_available": HAS_PG,
        "log_files_seen": [],
        "records_seen": 0,
        "records_synced": 0,
        "status": "not_started",
        "error": "",
    }

    for folder in LOG_DIRS:
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.jsonl")):
            report["log_files_seen"].append(str(path))
            try:
                with path.open("r", encoding="utf-8", errors="replace") as f:
                    report["records_seen"] += sum(1 for line in f if line.strip())
            except Exception as exc:
                report["error"] += f"{path}: {exc}; "

    if not PG_DSN:
        report["status"] = "skipped_no_fap_pg_dsn"
    elif not HAS_PG:
        report["status"] = "skipped_no_psycopg2"
    else:
        try:
            conn = psycopg2.connect(PG_DSN)
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(DDL)
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS fap.sync_events (
                        id SERIAL PRIMARY KEY,
                        source_file TEXT NOT NULL,
                        source_record JSONB NOT NULL,
                        synced_at TIMESTAMPTZ DEFAULT NOW()
                    );
                    """
                )
                for folder in LOG_DIRS:
                    if not folder.exists():
                        continue
                    for path in sorted(folder.glob("*.jsonl")):
                        with path.open("r", encoding="utf-8", errors="replace") as f:
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue
                                try:
                                    payload = json.loads(line)
                                except Exception:
                                    payload = {"raw": line, "parse_error": True}
                                cur.execute(
                                    "INSERT INTO fap.sync_events (source_file, source_record) VALUES (%s, %s::jsonb)",
                                    (str(path), json.dumps(payload)),
                                )
                                report["records_synced"] += 1
            conn.close()
            report["status"] = "synced"
        except Exception as exc:
            err = str(exc)
            if "no password supplied" in err.lower() or "fe_sendauth" in err.lower():
                report["status"] = "blocked_pg_auth"
            else:
                report["status"] = "failed"
            report["error"] = err

    out = REPORT_DIR / f"FAP_POSTGRES_SYNC_{stamp}.json"
    latest = REPORT_DIR / "FAP_POSTGRES_SYNC.latest.json"
    text = json.dumps(report, indent=2)
    out.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    print(f"FAP Postgres sync status: {report['status']}")
    print(f"Records seen: {report['records_seen']}")
    print(f"Records synced: {report['records_synced']}")
    print(f"Report: {out}")
    return 0 if report["status"] in {"synced", "skipped_no_psycopg2", "blocked_pg_auth"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

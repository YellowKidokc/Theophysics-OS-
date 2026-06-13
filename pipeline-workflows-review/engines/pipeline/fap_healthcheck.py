"""Health check for the Folder Automations & Pipelines engine."""

from __future__ import annotations

import importlib
import json
import os
import py_compile
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("FAP_REPO_ROOT", Path(__file__).resolve().parents[2]))
PIPELINE = ROOT / "engines" / "pipeline"
REPORTS = Path(os.environ.get("FAP_HEALTH_REPORT_DIR", r"D:\BIL\data\fap_health"))
sys.path.insert(0, str(ROOT))

REQUIRED_FILES = [
    "station_base.py",
    "pipeline_engine.py",
    "fap_boot.py",
    "fap_schema.sql",
    "llm_hub.py",
    "fap_postgres_sync.py",
    "fap_dashboard.html",
    "stations/classifier.py",
    "stations/media_transformer.py",
]


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []

    for rel in REQUIRED_FILES:
        path = PIPELINE / rel
        rows.append({"check": f"exists:{rel}", "status": "OK" if path.exists() else "FAIL", "detail": str(path)})
        if path.suffix == ".py" and path.exists():
            try:
                py_compile.compile(str(path), doraise=True)
                rows.append({"check": f"compile:{rel}", "status": "OK", "detail": str(path)})
            except Exception as exc:
                rows.append({"check": f"compile:{rel}", "status": "FAIL", "detail": str(exc)})

    for module in [
        "engines.pipeline.pipeline_engine",
        "engines.pipeline.station_base",
        "engines.pipeline.llm_hub",
        "engines.pipeline.fap_postgres_sync",
        "engines.pipeline.stations.classifier",
        "engines.pipeline.stations.media_transformer",
    ]:
        try:
            importlib.import_module(module)
            rows.append({"check": f"import:{module}", "status": "OK", "detail": module})
        except Exception as exc:
            rows.append({"check": f"import:{module}", "status": "FAIL", "detail": str(exc)})

    for folder in [
        Path(r"D:\FAP"),
        Path(r"D:\FAP\intake"),
        Path(r"D:\FAP\classified"),
        Path(r"D:\FAP\media-routed"),
        Path(r"D:\FAP\lossless"),
        Path(r"D:\FAP\vectorized"),
        Path(r"D:\FAP\graded"),
        Path(r"D:\FAP\axiom-mapped"),
        Path(r"D:\FAP\output"),
        Path(r"D:\FAP\_review"),
        Path(r"D:\FAP\_rejected"),
        Path(r"D:\FAP\wiki"),
        Path(r"D:\FAP\_queue"),
        Path(r"D:\FAP\logs"),
    ]:
        folder.mkdir(parents=True, exist_ok=True)
        rows.append({"check": "folder", "status": "OK" if folder.exists() else "FAIL", "detail": str(folder)})

    counts = Counter(row["status"] for row in rows)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status_counts": dict(counts),
        "rows": rows,
    }
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = REPORTS / f"FAP_HEALTH_{stamp}.json"
    md_path = REPORTS / f"FAP_HEALTH_{stamp}.md"
    latest = REPORTS / "FAP_HEALTH.latest.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# FAP Health Report",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- OK: {counts.get('OK', 0)}",
        f"- FAIL: {counts.get('FAIL', 0)}",
        "",
        "| Check | Status | Detail |",
        "|---|---|---|",
    ]
    for row in rows:
        lines.append(f"| {row['check']} | {row['status']} | `{row['detail']}` |")
    text = "\n".join(lines) + "\n"
    md_path.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")

    print(f"FAP health report: {md_path}")
    print(f"Status counts: {dict(counts)}")
    return 1 if counts.get("FAIL", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())

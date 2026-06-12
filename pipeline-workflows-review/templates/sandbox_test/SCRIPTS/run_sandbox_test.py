"""Run the Phase 0 sandbox-file-intake workflow against copied sample files."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = REPO_ROOT / "templates" / "sandbox_test"
SAMPLES = REPO_ROOT / "tests" / "fixtures"


def copytree_template(dest: Path) -> None:
    shutil.copytree(TEMPLATE, dest, ignore=shutil.ignore_patterns("STATUS.json", "MANIFEST.json", "*.tmp"))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="forge-sandbox-") as tmp:
        packet = Path(tmp) / "sandbox_packet"
        copytree_template(packet)
        source_files = sorted(p for p in SAMPLES.iterdir() if p.is_file())
        while len(source_files) < 5:
            extra = packet / f"generated_sample_{len(source_files) + 1}.txt"
            extra.write_text(f"Generated sandbox sample {len(source_files) + 1}\n", encoding="utf-8")
            source_files.append(extra)
        originals = {p: p.read_bytes() for p in source_files[:5] if p.exists()}
        for sample in source_files[:5]:
            shutil.copy2(sample, packet / "INPUT" / sample.name)

        manifest = packet / "MANIFEST.json"
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "orchestrator.py"),
            "sandbox-file-intake",
            str(packet),
            "--manifest",
            str(manifest),
            "--dry-run",
            "--no-resume",
        ]
        result = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
        status_path = packet / "STATUS.json"
        checks = {
            "orchestrator_exit_zero": result.returncode == 0,
            "status_written": status_path.exists(),
            "manifest_updated": manifest.exists(),
            "originals_untouched": all(p.read_bytes() == data for p, data in originals.items()),
        }
        if status_path.exists():
            status = json.loads(status_path.read_text(encoding="utf-8"))
            checks["workflow_completed"] = status.get("status") == "completed"
            checks["stages_recorded"] = len(status.get("history", [])) == 4
        print(json.dumps({"packet": str(packet), "checks": checks, "stdout": result.stdout, "stderr": result.stderr}, indent=2))
        return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())

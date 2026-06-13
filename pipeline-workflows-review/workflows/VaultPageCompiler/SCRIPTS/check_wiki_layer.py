from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "CONFIG" / "wiki_compiler.example.json"


def main() -> int:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    workspace = Path(cfg["workspace"])
    raw_dir = Path(cfg["raw_dir"])
    wiki_dir = Path(cfg["wiki_dir"])
    command = cfg["command"]

    print(f"workspace: {workspace}")
    print(f"workspace_exists: {workspace.exists()}")
    print(f"raw_exists: {raw_dir.exists()}")
    print(f"wiki_exists: {wiki_dir.exists()}")
    print(f"command_on_path: {shutil.which(command) or 'missing'}")

    if shutil.which(command):
        result = subprocess.run(
            [command, "--version"],
            cwd=workspace if workspace.exists() else None,
            text=True,
            capture_output=True,
            check=False,
        )
        print((result.stdout or result.stderr).strip())

    if raw_dir.exists():
        raw_files = sorted(p.name for p in raw_dir.glob("*") if p.is_file())
        print(f"raw_files: {len(raw_files)}")
        for name in raw_files[:20]:
            print(f"  raw/{name}")

    drafts = wiki_dir / ".drafts"
    if drafts.exists():
        draft_files = sorted(p.name for p in drafts.glob("*.md"))
        print(f"draft_files: {len(draft_files)}")
        for name in draft_files[:20]:
            print(f"  wiki/.drafts/{name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "templates" / "workflow_packet"
WORKFLOWS = REPO / "workflows"


def copy_template(name: str) -> Path:
    target = WORKFLOWS / name
    if target.exists():
        raise SystemExit(f"Workflow already exists: {target}")
    shutil.copytree(TEMPLATE, target)
    for path in target.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace("WORKFLOW_NAME", name), encoding="utf-8")
    for folder in ["INPUT", "OUTPUT", "REVIEW", "ARCHIVE", "ERROR", "LOGS"]:
        gitkeep = target / folder / ".gitkeep"
        gitkeep.parent.mkdir(parents=True, exist_ok=True)
        gitkeep.write_text("", encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a workflow packet from the standard template.")
    parser.add_argument("name", help="Workflow packet name, for example PaperGrading")
    args = parser.parse_args()
    target = copy_template(args.name)
    print(f"Created {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

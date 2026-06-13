from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def ensure_dirs() -> None:
    for name in ["INPUT", "OUTPUT", "REVIEW", "ARCHIVE", "ERROR", "CONFIG", "PROMPTS", "SCRIPTS", "LOGS"]:
        (ROOT / name).mkdir(exist_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["pipeline", "stage"], default="stage")
    args = parser.parse_args()
    ensure_dirs()
    inputs = sorted((ROOT / "INPUT").glob("*"))
    log = ROOT / "LOGS" / "last_run.log"
    log.write_text(
        f"mode={args.mode}\ninputs={len(inputs)}\nstatus=template-only\n",
        encoding="utf-8",
    )
    print(f"{ROOT.name}: {args.mode} run complete. Inputs found: {len(inputs)}")
    print("Template runner only. Replace with station calls.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ["INPUT", "OUTPUT", "REVIEW", "ARCHIVE", "ERROR", "CONFIG", "PROMPTS", "SCRIPTS", "LOGS"]


def main() -> int:
    print(f"Troubleshooting {ROOT.name}")
    ok = True
    for name in REQUIRED:
        path = ROOT / name
        exists = path.exists()
        print(f"{name}: {'OK' if exists else 'MISSING'}")
        ok = ok and exists
    print(f"Python: {sys.version.split()[0]}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

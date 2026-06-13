"""Validate local FORGE pipeline integration prerequisites."""
from __future__ import annotations

import argparse
import importlib.util
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "pipeline.config.json"
VALIDATED_CONFIG = REPO_ROOT / "pipeline.validated.config.json"


def check_import(module: str) -> dict:
    return {"name": module, "available": importlib.util.find_spec(module) is not None}


def check_path(label: str, value: str) -> dict:
    path = Path(value)
    return {"name": label, "path": value, "exists": path.exists()}


def check_http(name: str, url: str, timeout: float = 2.0) -> dict:
    try:
        request = Request(url.rstrip("/"), method="GET")
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - local endpoint validation
            return {"name": name, "url": url, "available": 200 <= response.status < 500, "status": response.status}
    except Exception as exc:
        return {"name": name, "url": url, "available": False, "error": str(exc)}


def check_tcp(name: str, host: str, port: int, timeout: float = 2.0) -> dict:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"name": name, "host": host, "port": port, "available": True}
    except OSError as exc:
        return {"name": name, "host": host, "port": port, "available": False, "error": str(exc)}


def validate(config_path: Path = DEFAULT_CONFIG, output_path: Path = VALIDATED_CONFIG) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    services = config.get("services", {})
    report = {
        "validated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "config_path": str(config_path),
        "paths": [check_path(name, value) for name, value in config.get("paths", {}).items()],
        "python_deps": [check_import(name) for name in ["watchdog", "psycopg2", "requests"]],
        "services": [
            check_http("ollama", services.get("ollama", "http://localhost:11434")),
            check_http("bil_server", services.get("bil_server", "http://localhost:8420")),
        ],
    }
    postgres = services.get("postgres", {})
    if postgres:
        report["services"].append(check_tcp("postgres", postgres.get("host", "localhost"), int(postgres.get("port", 5432))))

    report["summary"] = {
        "paths_existing": sum(1 for item in report["paths"] if item["exists"]),
        "paths_total": len(report["paths"]),
        "deps_available": sum(1 for item in report["python_deps"] if item["available"]),
        "deps_total": len(report["python_deps"]),
        "services_available": sum(1 for item in report["services"] if item["available"]),
        "services_total": len(report["services"]),
    }
    validated = dict(config)
    validated["validation"] = report
    output_path.write_text(json.dumps(validated, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate FORGE pipeline config, dependencies, and services.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output", default=str(VALIDATED_CONFIG))
    parser.add_argument("--strict", action="store_true", help="Return non-zero if any path/dependency/service check fails")
    args = parser.parse_args(argv)
    report = validate(Path(args.config), Path(args.output))
    print(json.dumps(report, indent=2))
    if args.strict:
        failed = any(not item["exists"] for item in report["paths"]) or any(not item["available"] for item in report["python_deps"] + report["services"])
        return 1 if failed else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

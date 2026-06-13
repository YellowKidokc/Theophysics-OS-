"""DAG orchestrator for FORGE workflow packets.

Runs workflow JSON definitions against packet folders while preserving originals.
The orchestrator is intentionally a thin integration layer: existing internal
stations and external X:\\Backside RUN.bat stations remain self-contained.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import requests
except ImportError:  # pragma: no cover - setup.py reports this explicitly
    requests = None

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engines.pipeline.external_adapter import ExternalStationAdapter
from engines.pipeline.station_base import Manifest, StationBase, StationVerdict

LOG = logging.getLogger("FORGE.orchestrator")
TERMINAL_RESULTS = {"pass", "skip", "review", "hold"}
FAILED_RESULTS = {"fail"}


@dataclass
class StageResult:
    stage: str
    station: str
    result: str
    score: float = 0.0
    notes: str = ""
    latency_ms: int = 0


class DryRunStation(StationBase):
    """Test/sandbox station that exercises orchestration without external side effects."""

    def __init__(self, name: str, input_dir: Path, output_dir: Path):
        super().__init__(name=name, input_dir=str(input_dir), output_dir=str(output_dir), file_extensions=["*"])

    def process(self, file_path: Path, manifest: Manifest) -> tuple[StationVerdict, float, str]:
        dest = self.output_dir / f"{file_path.name}.{self.name}.dryrun.json"
        dest.write_text(
            json.dumps(
                {
                    "station": self.name,
                    "source": str(file_path),
                    "file_hash": manifest.file_hash,
                    "processed_at": utcnow(),
                    "mode": "dry_run",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return StationVerdict.PASS, 1.0, "dry-run pass; no external station executed"


class Orchestrator:
    """Execute workflow DAGs for packet folders with STATUS/MANIFEST tracking."""

    def __init__(
        self,
        repo_root: Path | str = REPO_ROOT,
        registry_path: Path | str | None = None,
        config_path: Path | str | None = None,
        manifest_path: Path | str | None = None,
        dry_run: bool = False,
    ):
        self.repo_root = Path(repo_root)
        self.registry_path = Path(registry_path) if registry_path else self.repo_root / "stations" / "STATION_REGISTRY.json"
        self.config_path = Path(config_path) if config_path else self.repo_root / "pipeline.config.json"
        self.manifest_path = Path(manifest_path) if manifest_path else self.repo_root / "MANIFEST.json"
        self.dry_run = dry_run or os.environ.get("FORGE_DRY_RUN", "").lower() in {"1", "true", "yes"}
        self.registry = load_json(self.registry_path)
        self.config = load_json(self.config_path) if self.config_path.exists() else {}

    def run(self, workflow_file: Path | str, packet_dir: Path | str, resume: bool = True) -> dict[str, Any]:
        workflow_path = self._workflow_path(workflow_file)
        workflow = load_json(workflow_path)
        packet = Path(packet_dir)
        self._ensure_packet_contract(packet)
        self._configure_logging(packet)

        input_files = list(iter_packet_inputs(packet / "INPUT"))
        input_hash = compute_tree_hash(packet / "INPUT")
        status = self._load_or_create_status(packet, workflow, input_hash, resume)
        completed = {h["stage"] for h in status.get("history", []) if h.get("result") in TERMINAL_RESULTS}
        stages = workflow.get("stages", [])
        self._validate_dag(stages)

        LOG.info("Starting workflow=%s packet=%s dry_run=%s", workflow["name"], packet, self.dry_run)
        while True:
            pending = [s for s in stages if s["name"] not in completed]
            if not pending:
                status["status"] = "completed"
                status["completed_at"] = utcnow()
                break

            ready = [s for s in pending if all(dep in completed for dep in s.get("depends_on", []))]
            if not ready:
                self._record_error(status, "orchestrator", "No runnable stages; unresolved dependencies")
                status["status"] = "failed"
                break

            # Run all currently-ready stages concurrently. This supports explicit
            # parallel stages and independent DAG branches without changing the contract.
            with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(ready))) as executor:
                futures = [executor.submit(self._run_stage, stage, packet, input_files, workflow, input_hash) for stage in ready]
                for future in concurrent.futures.as_completed(futures):
                    stage, results = future.result()
                    result = combine_results(results)
                    history = {
                        "stage": stage["name"],
                        "entered_at": utcnow(),
                        "exited_at": utcnow(),
                        "result": result.result,
                        "score": result.score,
                        "notes": result.notes,
                        "latency_ms": result.latency_ms,
                    }
                    status.setdefault("history", []).append(history)
                    status["current_stage"] = stage["name"]
                    status["updated_at"] = utcnow()
                    completed.add(stage["name"])
                    self._write_status(packet, status)
                    self._update_manifest(packet, workflow["name"], stage["name"], status, input_files)

                    if result.result == "fail":
                        self._record_error(status, stage["name"], result.notes)
                        action = stage.get("on_error", "stop")
                        if action == "stop":
                            status["status"] = "failed"
                            self._write_status(packet, status)
                            self._update_manifest(packet, workflow["name"], stage["name"], status, input_files)
                            return status
                        if action == "skip":
                            LOG.warning("Stage %s failed; on_error=skip", stage["name"])
                        else:
                            LOG.warning("Stage %s failed; on_error=continue", stage["name"])

                    if result.result in {"review", "hold"}:
                        status["status"] = result.result

        self._write_status(packet, status)
        self._update_manifest(packet, workflow["name"], status.get("current_stage", "completed"), status, input_files)
        LOG.info("Finished workflow=%s status=%s", workflow["name"], status["status"])
        return status

    def _run_stage(
        self,
        stage: dict[str, Any],
        packet: Path,
        input_files: list[Path],
        workflow: dict[str, Any],
        input_hash: str,
    ) -> tuple[dict[str, Any], list[StageResult]]:
        started = time.perf_counter()
        station_names = stage.get("stations") if stage.get("parallel") else None
        station_names = station_names or [stage["station"]]
        results: list[StageResult] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(station_names))) as executor:
            futures = [executor.submit(self._run_station_for_files, name, stage, packet, input_files, workflow, input_hash) for name in station_names]
            for future in concurrent.futures.as_completed(futures):
                results.extend(future.result())

        if stage.get("llm_gate", {}).get("enabled"):
            gate = self._run_llm_gate(stage, packet)
            results.append(gate)

        elapsed = int((time.perf_counter() - started) * 1000)
        for result in results:
            if not result.latency_ms:
                result.latency_ms = elapsed
        return stage, results

    def _run_station_for_files(
        self,
        station_name: str,
        stage: dict[str, Any],
        packet: Path,
        input_files: list[Path],
        workflow: dict[str, Any],
        input_hash: str,
    ) -> list[StageResult]:
        try:
            station = self._station(station_name, packet)
        except Exception as exc:
            return [StageResult(stage["name"], station_name, "fail", 0.0, f"station setup failed: {type(exc).__name__}: {exc}")]
        stage_results = []
        if not input_files:
            input_files = [packet / "INPUT"]
        for file_path in input_files:
            manifest = Manifest(
                file_path=str(file_path),
                file_hash=Manifest.compute_hash(str(file_path)) if file_path.is_file() else input_hash,
                pipeline_name=workflow["name"],
                current_station=station_name,
                metadata={"packet": str(packet), "stage": stage["name"]},
            )
            start = time.perf_counter()
            try:
                verdict, score, notes = station.process(file_path, manifest)
                result = verdict.value
            except Exception as exc:  # station boundary: capture, do not crash the whole runner
                result, score, notes = "fail", 0.0, f"{type(exc).__name__}: {exc}"
            stage_results.append(
                StageResult(
                    stage=stage["name"],
                    station=station_name,
                    result=result,
                    score=float(score or 0.0),
                    notes=f"{station_name}: {notes}",
                    latency_ms=int((time.perf_counter() - start) * 1000),
                )
            )
        return stage_results

    def _station(self, station_name: str, packet: Path) -> StationBase:
        if self.dry_run:
            return DryRunStation(station_name, packet / "INPUT", packet / "OUTPUT")
        entry = self.registry.get("stations", {}).get(station_name)
        if not entry:
            raise ValueError(f"Station {station_name!r} not found in {self.registry_path}")
        return ExternalStationAdapter.from_registry(station_name, registry_path=str(self.registry_path), config_path=str(self.config_path))

    def _run_llm_gate(self, stage: dict[str, Any], packet: Path) -> StageResult:
        gate = stage.get("llm_gate", {})
        engine = gate.get("engine", "ollama:phi4")
        prompt = gate.get("prompt", "Return pass or review.")
        ollama_url = self.config.get("services", {}).get("ollama", "http://localhost:11434")
        model = engine.split(":", 1)[1] if ":" in engine else self.config.get("services", {}).get("ollama_model", "phi4")
        if self.dry_run:
            return StageResult(stage["name"], "llm_gate", "pass", 1.0, "dry-run llm gate skipped")
        if requests is None:
            return StageResult(stage["name"], "llm_gate", "review", 0.0, "requests unavailable for Ollama gate")
        try:
            response = requests.post(
                f"{ollama_url.rstrip('/')}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=60,
            )
            response.raise_for_status()
            text = response.json().get("response", "").strip()
            verdict = "pass" if text and "reject" not in text.lower() and "fail" not in text.lower() else "review"
            (packet / "LOGS" / f"{stage['name']}.llm_gate.json").write_text(json.dumps({"prompt": prompt, "response": text}, indent=2), encoding="utf-8")
            return StageResult(stage["name"], "llm_gate", verdict, 1.0 if verdict == "pass" else 0.5, text[:500])
        except Exception as exc:
            return StageResult(stage["name"], "llm_gate", "review", 0.0, f"Ollama gate unavailable: {exc}")

    def _workflow_path(self, workflow_file: Path | str) -> Path:
        path = Path(workflow_file)
        if path.exists():
            return path
        if not path.suffix:
            path = path.with_suffix(".json")
        candidate = self.repo_root / "workflows" / path.name
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Workflow not found: {workflow_file}")

    def _ensure_packet_contract(self, packet: Path) -> None:
        for folder in ["INPUT", "OUTPUT", "REVIEW", "ARCHIVE", "ERROR", "CONFIG", "PREFS", "PROMPTS", "SCRIPTS", "LOGS"]:
            (packet / folder).mkdir(parents=True, exist_ok=True)

    def _configure_logging(self, packet: Path) -> None:
        LOG.setLevel(logging.INFO)
        if not LOG.handlers:
            LOG.addHandler(logging.StreamHandler())
        file_handler = logging.FileHandler(packet / "LOGS" / "orchestrator.log", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        LOG.addHandler(file_handler)

    def _load_or_create_status(self, packet: Path, workflow: dict[str, Any], input_hash: str, resume: bool) -> dict[str, Any]:
        status_path = packet / "STATUS.json"
        if resume and status_path.exists():
            return load_json(status_path)
        return {
            "packet_id": packet.name,
            "workflow": workflow["name"],
            "current_stage": "pending",
            "status": "active",
            "started_at": utcnow(),
            "completed_at": None,
            "input_hash": input_hash,
            "history": [],
            "errors": [],
            "checkpoints": {},
        }

    def _write_status(self, packet: Path, status: dict[str, Any]) -> None:
        atomic_write_json(packet / "STATUS.json", status)

    def _update_manifest(self, packet: Path, workflow: str, stage: str, status: dict[str, Any], input_files: list[Path]) -> None:
        manifest = load_json(self.manifest_path) if self.manifest_path.exists() else {"updated_at": utcnow(), "packets": []}
        packets = [p for p in manifest.get("packets", []) if p.get("id") != packet.name]
        packets.append(
            {
                "id": packet.name,
                "workflow": workflow,
                "current_stage": stage,
                "status": status.get("status", "active"),
                "created_at": status.get("started_at", utcnow()),
                "updated_at": utcnow(),
                "file_count": len(input_files),
                "input_hash": status.get("input_hash", ""),
            }
        )
        manifest["packets"] = packets
        manifest["updated_at"] = utcnow()
        manifest["summary"] = {state: sum(1 for p in packets if p.get("status") == state) for state in ["active", "completed", "failed", "review", "hold"]}
        atomic_write_json(self.manifest_path, manifest)

    def _record_error(self, status: dict[str, Any], stage: str, error: str) -> None:
        status.setdefault("errors", []).append({"stage": stage, "error": error, "timestamp": utcnow()})

    def _validate_dag(self, stages: list[dict[str, Any]]) -> None:
        names = {s["name"] for s in stages}
        for stage in stages:
            missing = [d for d in stage.get("depends_on", []) if d not in names]
            if missing:
                raise ValueError(f"Stage {stage['name']} depends on unknown stage(s): {missing}")


def combine_results(results: list[StageResult]) -> StageResult:
    if not results:
        return StageResult("unknown", "none", "skip", 1.0, "no inputs")
    order = ["fail", "hold", "review", "pass", "skip"]
    chosen_result = min((r.result for r in results), key=lambda r: order.index(r) if r in order else 99)
    score = min((r.score for r in results), default=0.0)
    notes = "; ".join(r.notes for r in results if r.notes)[:2000]
    return StageResult(results[0].stage, ",".join(sorted({r.station for r in results})), chosen_result, score, notes, sum(r.latency_ms for r in results))


def iter_packet_inputs(input_dir: Path) -> Iterable[Path]:
    return sorted(p for p in input_dir.rglob("*") if p.is_file() and p.name not in {"STATUS.json", "MANIFEST.json"})


def compute_tree_hash(path: Path) -> str:
    h = hashlib.sha256()
    if path.is_file():
        h.update(path.read_bytes())
    elif path.exists():
        for file_path in iter_packet_inputs(path):
            h.update(str(file_path.relative_to(path)).encode("utf-8"))
            with file_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    h.update(chunk)
    return h.hexdigest()[:16]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path | str) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def atomic_write_json(path: Path | str, data: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a FORGE workflow DAG for a packet folder.")
    parser.add_argument("workflow", help="Workflow name or path, e.g. sandbox-file-intake or workflows/paper-analysis.json")
    parser.add_argument("packet", help="Packet folder containing INPUT/OUTPUT/... folders")
    parser.add_argument("--registry", default=None, help="Override STATION_REGISTRY.json path")
    parser.add_argument("--config", default=None, help="Override pipeline.config.json path")
    parser.add_argument("--manifest", default=None, help="Override MANIFEST.json path")
    parser.add_argument("--no-resume", action="store_true", help="Ignore existing STATUS.json")
    parser.add_argument("--dry-run", action="store_true", help="Exercise DAG/status/manifest without running external stations")
    args = parser.parse_args(argv)

    orchestrator = Orchestrator(registry_path=args.registry, config_path=args.config, manifest_path=args.manifest, dry_run=args.dry_run)
    status = orchestrator.run(args.workflow, args.packet, resume=not args.no_resume)
    print(json.dumps({"packet_id": status["packet_id"], "workflow": status["workflow"], "status": status["status"]}, indent=2))
    return 0 if status.get("status") in {"completed", "review", "hold"} else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

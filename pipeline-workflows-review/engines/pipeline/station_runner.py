"""Station runner contract between pipeline engine and stations."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from .station_base import Manifest, Signal, SignalType, StationBase, StationVerdict
from scripts.resolve_preferences import resolve


class StationRunner:
    """Execute station processing with standardized logs + signal draining."""

    def __init__(self, workflow_name: str = "PaperGrading", log_dir: str | None = None):
        self.workflow_name = workflow_name
        self.log_dir = Path(log_dir or "logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        station: StationBase,
        file_path: Path,
        manifest: Manifest,
        profile_name: str | None = None,
        overrides: dict | None = None,
        signal_handler: Callable[[Signal], None] | None = None,
    ) -> tuple[StationVerdict, float, str, list[Signal]]:
        """Run one station and return verdict tuple plus drained signals."""
        preferences = resolve(self.workflow_name, profile_name=profile_name, overrides=overrides)
        started = time.perf_counter()
        try:
            verdict, score, notes = station.process(file_path, manifest)
        except Exception as exc:  # noqa: BLE001
            station.emit_signal(SignalType.ERROR, f"Station runner error: {exc}")
            verdict, score, notes = StationVerdict.FAIL, 0.0, f"Runner captured exception: {exc}"

        latency_ms = int((time.perf_counter() - started) * 1000)
        signals = station.drain_signals()
        if signal_handler:
            for signal in signals:
                signal_handler(signal)

        run_log = {
            "timestamp": datetime.utcnow().isoformat(),
            "station_name": station.name,
            "file_path": str(file_path),
            "verdict": verdict.value,
            "score": score,
            "notes": notes,
            "latency_ms": latency_ms,
            "preferences": preferences,
            "signals": [signal.to_dict() for signal in signals],
        }
        with (self.log_dir / "station_runs.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(run_log) + "\n")
        return verdict, score, notes, signals

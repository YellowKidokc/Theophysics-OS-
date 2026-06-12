"""
external_adapter.py — Bridge between pipeline engine and X:\\Backside stations.

The pipeline engine has its own station implementations in engines/pipeline/stations/.
The REAL stations live on X:\\Backside with RUN.bat files and 23/47 passing canary.

This adapter wraps an external station's RUN.bat into a StationBase subclass
so the pipeline engine can run both internal Python stations AND external
Backside stations through the same interface.

Usage:
    from engines.pipeline.external_adapter import ExternalStationAdapter

    station = ExternalStationAdapter.from_registry("claim-extractor")
    engine.register_station(station, pipeline_name="paper-analysis")
"""

import json
import subprocess
import shutil
import logging
import hashlib
from pathlib import Path
from typing import Optional
from datetime import datetime

from .station_base import StationBase, StationVerdict, Manifest, SignalType

logger = logging.getLogger("FORGE.adapter")


class ExternalStationAdapter(StationBase):
    """
    Wraps an X:\\Backside station with RUN.bat into a StationBase-compatible object.
    The pipeline engine sees it as just another station.
    """

    def __init__(
        self,
        name: str,
        station_path: str,
        input_dir: str,
        output_dir: str,
        has_run_bat: bool = True,
        file_extensions: Optional[list] = None,
        timeout_seconds: int = 300,
        **kwargs,
    ):
        super().__init__(
            name=name,
            input_dir=input_dir,
            output_dir=output_dir,
            file_extensions=file_extensions or ["*"],
            **kwargs,
        )
        self.station_path = Path(station_path)
        self.has_run_bat = has_run_bat
        self.timeout_seconds = timeout_seconds
        self.run_bat = self.station_path / "RUN.bat"

    @classmethod
    def from_registry(
        cls,
        station_name: str,
        registry_path: str = None,
        config_path: str = None,
    ) -> "ExternalStationAdapter":
        """
        Build an adapter from STATION_REGISTRY.json entry.

        Args:
            station_name: Key in the registry
            registry_path: Path to STATION_REGISTRY.json
            config_path: Path to pipeline.config.json
        """
        if registry_path is None:
            # Default: look relative to this file's repo root
            repo_root = Path(__file__).resolve().parent.parent.parent
            registry_path = repo_root / "stations" / "STATION_REGISTRY.json"

        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)

        entry = registry.get("stations", {}).get(station_name)
        if not entry:
            raise ValueError(f"Station '{station_name}' not found in registry")

        station_path = Path(entry["path"])
        input_dir = str(station_path / "INPUT")
        output_dir = str(station_path / "OUTPUT")
        # Some stations use DROP_PAPERS_HERE instead of INPUT
        if not Path(input_dir).exists():
            alt_input = station_path / "DROP_PAPERS_HERE"
            if alt_input.exists():
                input_dir = str(alt_input)
            else:
                # Create INPUT if nothing exists
                Path(input_dir).mkdir(parents=True, exist_ok=True)

        if not Path(output_dir).exists():
            Path(output_dir).mkdir(parents=True, exist_ok=True)

        return cls(
            name=station_name,
            station_path=str(station_path),
            input_dir=input_dir,
            output_dir=output_dir,
            has_run_bat=entry.get("has_run_bat", True),
        )

    def process(self, file_path: Path, manifest: Manifest) -> tuple[StationVerdict, float, str]:
        """
        Run the external station's RUN.bat against the input file.

        Strategy:
        1. Copy file into station's INPUT dir (nothing original destroyed)
        2. Run RUN.bat
        3. Check OUTPUT dir for results
        4. Return verdict based on what happened
        """
        if not self.has_run_bat or not self.run_bat.exists():
            self.emit_signal(
                SignalType.ERROR,
                f"Station {self.name} has no RUN.bat at {self.run_bat}",
            )
            return StationVerdict.FAIL, 0.0, f"No RUN.bat found at {self.station_path}"

        # 1. Copy input file to station's INPUT dir (NEVER move originals)
        station_input = self.station_path / "INPUT"
        station_input.mkdir(parents=True, exist_ok=True)
        dest_file = station_input / file_path.name
        shutil.copy2(str(file_path), str(dest_file))

        # 2. Check idempotency — has this exact file been processed before?
        archive = self.station_path / "ARCHIVE"
        if archive.exists():
            file_hash = Manifest.compute_hash(str(file_path))
            for archived in archive.iterdir():
                if archived.is_file():
                    try:
                        if Manifest.compute_hash(str(archived)) == file_hash:
                            return (
                                StationVerdict.PASS,
                                1.0,
                                f"Idempotency: already processed (hash={file_hash})",
                            )
                    except Exception:
                        continue

        # 3. Run RUN.bat
        try:
            result = subprocess.run(
                ["cmd.exe", "/d", "/c", str(self.run_bat)],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                cwd=str(self.station_path),
            )
            exit_code = result.returncode
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
        except subprocess.TimeoutExpired:
            self.emit_signal(
                SignalType.ERROR,
                f"Station {self.name} timed out after {self.timeout_seconds}s",
            )
            return StationVerdict.HOLD, 0.0, f"Timeout after {self.timeout_seconds}s"
        except Exception as e:
            self.emit_signal(SignalType.ERROR, f"Station {self.name} execution error: {e}")
            return StationVerdict.FAIL, 0.0, f"Execution error: {e}"

        # 4. Check for output
        station_output = self.station_path / "OUTPUT"
        output_files = list(station_output.glob("*")) if station_output.exists() else []
        new_outputs = [f for f in output_files if f.is_file()]

        if exit_code == 0:
            notes = f"Exit 0. stdout={stdout[:200]}" if stdout else "Exit 0. No stdout."
            if stderr:
                notes += f" stderr={stderr[:200]}"
            self.emit_signal(SignalType.READY, f"{self.name} completed: {file_path.name}")
            return StationVerdict.PASS, 1.0, notes
        elif exit_code == 2:
            # Convention: exit 2 = needs review
            return StationVerdict.REVIEW, 0.5, f"Exit 2 (review). {stdout[:200]}"
        else:
            self.emit_signal(
                SignalType.ERROR,
                f"{self.name} failed with exit {exit_code}: {stderr[:200]}",
            )
            return StationVerdict.FAIL, 0.0, f"Exit {exit_code}. stderr={stderr[:200]}"

    def __repr__(self):
        return f"<ExternalStation:{self.name} path={self.station_path} run_bat={self.has_run_bat}>"
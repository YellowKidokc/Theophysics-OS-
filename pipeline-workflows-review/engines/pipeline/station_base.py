"""
station_base.py — Base class for all pipeline station processors.

Every station is a plugin. It declares:
  - what it watches (input folder)
  - what it produces (output folder or next station)
  - how it scores (pass/fail/review threshold)
  - what it does (process method)

Stations can emit SIGNALS upstream:
  - GAP: "nothing covers axiom 47"
  - DUPLICATE: "this is 92% similar to paper X"
  - QUALITY: "this paper scored below threshold"
  - READY: "this paper passed all stations"
"""

import os
import json
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional
from pathlib import Path


class StationVerdict(Enum):
    PASS = "pass"           # advance to next station
    FAIL = "fail"           # reject / kick back
    REVIEW = "review"       # gray zone — kick to David
    LOOP = "loop"           # send back to a previous station
    HOLD = "hold"           # park it — waiting on dependency


class SignalType(Enum):
    GAP = "gap"             # missing coverage detected
    DUPLICATE = "duplicate" # near-duplicate found
    QUALITY = "quality"     # quality alert
    READY = "ready"         # paper completed pipeline
    ERROR = "error"         # processing error
    UPSTREAM = "upstream"   # generic upstream signal


@dataclass
class Signal:
    signal_type: SignalType
    source_station: str
    message: str
    payload: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        d = asdict(self)
        d["signal_type"] = self.signal_type.value
        return d


@dataclass
class Manifest:
    """Tracks a document's journey through the pipeline."""
    file_path: str
    file_hash: str
    pipeline_name: str
    current_station: str
    history: list = field(default_factory=list)
    scores: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "active"  # active | completed | failed | review

    def record_station(self, station_name: str, verdict: StationVerdict,
                       score: float = 0.0, notes: str = ""):
        self.history.append({
            "station": station_name,
            "verdict": verdict.value,
            "score": score,
            "notes": notes,
            "timestamp": datetime.now().isoformat(),
        })
        self.scores[station_name] = score
        self.updated_at = datetime.now().isoformat()

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def compute_hash(file_path: str) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()[:16]


class StationBase(ABC):
    """
    Base class for pipeline stations.
    Subclass this, implement process(), register with PipelineEngine.
    """

    def __init__(self, name: str, input_dir: str, output_dir: str,
                 fail_dir: Optional[str] = None,
                 review_dir: Optional[str] = None,
                 threshold_pass: float = 0.7,
                 threshold_fail: float = 0.3,
                 file_extensions: Optional[list] = None):
        self.name = name
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.fail_dir = Path(fail_dir) if fail_dir else self.input_dir / "_rejected"
        self.review_dir = Path(review_dir) if review_dir else self.input_dir / "_review"
        self.threshold_pass = threshold_pass
        self.threshold_fail = threshold_fail
        self.file_extensions = file_extensions or ["*"]
        self.signals: list[Signal] = []

        # Ensure dirs exist
        for d in [self.input_dir, self.output_dir, self.fail_dir, self.review_dir]:
            d.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def process(self, file_path: Path, manifest: Manifest) -> tuple[StationVerdict, float, str]:
        """
        Process a file at this station.

        Returns:
            (verdict, score, notes)
            - verdict: PASS/FAIL/REVIEW/LOOP/HOLD
            - score: 0.0-1.0 confidence
            - notes: what happened
        """
        ...

    def emit_signal(self, signal_type: SignalType, message: str, payload: dict = None):
        sig = Signal(
            signal_type=signal_type,
            source_station=self.name,
            message=message,
            payload=payload or {},
        )
        self.signals.append(sig)
        return sig

    def drain_signals(self) -> list[Signal]:
        signals = list(self.signals)
        self.signals.clear()
        return signals

    def accepts_file(self, file_path: Path) -> bool:
        if "*" in self.file_extensions:
            return True
        return file_path.suffix.lower() in self.file_extensions

    def __repr__(self):
        return f"<Station:{self.name} in={self.input_dir} out={self.output_dir}>"

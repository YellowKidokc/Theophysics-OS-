"""
correction_logger.py — Captures human correction events as structured training data.

Every time David fixes a misclassification, overrides a route, or corrects a verdict,
this logger writes a structured JSON event that feeds into BIL for preference learning.

The correction log IS the training data. Without it, the system never gets smarter.

Usage:
    from scripts.correction_logger import CorrectionLogger

    logger = CorrectionLogger()
    logger.log_correction(
        file_path="path/to/file.md",
        stage="classify",
        old_verdict="review", new_verdict="pass",
        old_route="REVIEW/", new_route="OUTPUT/vault/",
        reason="This is clearly a framework paper, classifier missed it"
    )
"""

import json
import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class CorrectionLogger:
    """Log human corrections as structured training data."""

    def __init__(
        self,
        log_dir: str = None,
        bil_endpoint: str = "http://localhost:8420",
        config_path: str = None,
    ):
        self.log_dir = Path(log_dir or os.environ.get(
            "FORGE_CORRECTION_LOG",
            str(Path(__file__).parent.parent / "logs" / "corrections"),
        ))
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.bil_endpoint = bil_endpoint
        self.log_file = self.log_dir / "corrections.jsonl"

    def _compute_hash(self, file_path: str) -> str:
        h = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()[:16]
        except FileNotFoundError:
            return "file_not_found"

    def log_correction(
        self,
        file_path: str,
        stage: str,
        old_verdict: Optional[str] = None,
        new_verdict: Optional[str] = None,
        old_route: Optional[str] = None,
        new_route: Optional[str] = None,
        old_domain: Optional[str] = None,
        new_domain: Optional[str] = None,
        old_subject: Optional[str] = None,
        new_subject: Optional[str] = None,
        reason: str = "",
        workflow: str = "",
    ) -> dict:
        """
        Log a single correction event.
        Returns the correction record.
        """
        event = {
            "event_type": "human_correction",
            "file_hash": self._compute_hash(file_path),
            "file_path": str(file_path),
            "timestamp": datetime.now().isoformat(),
            "workflow": workflow,
            "stage": stage,
            "corrections": {
                "old_verdict": old_verdict,
                "new_verdict": new_verdict,
                "old_route": old_route,
                "new_route": new_route,
                "old_domain": old_domain,
                "new_domain": new_domain,
                "old_subject": old_subject,
                "new_subject": new_subject,
            },
            "reason": reason,
            "bil_weight": 1.0,
        }

        # Write to local JSONL
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

        # Push to BIL if available
        self._push_to_bil(event)

        return event

    def _push_to_bil(self, event: dict):
        """Send correction to BIL server for immediate learning."""
        if not HAS_REQUESTS:
            return
        try:
            requests.post(
                f"{self.bil_endpoint}/bil/correction",
                json=event,
                timeout=5,
            )
        except Exception:
            pass  # BIL offline is fine — local log is the source of truth

    def get_corrections(self, limit: int = 100) -> list[dict]:
        """Read recent corrections from the log."""
        if not self.log_file.exists():
            return []
        corrections = []
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        corrections.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return corrections[-limit:]

    def get_stats(self) -> dict:
        """Summary stats on corrections logged."""
        corrections = self.get_corrections(limit=10000)
        stages = {}
        for c in corrections:
            stage = c.get("stage", "unknown")
            stages[stage] = stages.get(stage, 0) + 1
        return {
            "total_corrections": len(corrections),
            "by_stage": stages,
            "log_file": str(self.log_file),
        }
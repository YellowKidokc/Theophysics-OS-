"""Station 6: claim extraction and axiom mapping via LLMHub."""
from __future__ import annotations

import json
from pathlib import Path

from ..llm_hub import LLMHub
from ..station_base import Manifest, SignalType, StationBase, StationVerdict


class AxiomMapperStation(StationBase):
    """Submit mapping jobs then collect mappings + emit GAP/QUALITY signals."""

    def __init__(self, input_dir: str, output_dir: str, queue_dir: str | None = None, **kwargs):
        super().__init__("axiom-mapper", input_dir, output_dir, file_extensions=[".md", ".txt"], **kwargs)
        self.hub = LLMHub(queue_dir=queue_dir or "_queue")

    def process(self, file_path: Path, manifest: Manifest) -> tuple[StationVerdict, float, str]:
        sidecar = file_path.with_suffix(file_path.suffix + ".axioms.json")
        if not sidecar.exists():
            job_id = self.hub.submit("axiom-mapper", str(file_path), "extract_claims", backend="claude_api", priority="batch", input_text=file_path.read_text(encoding="utf-8")[:8000])
            sidecar.write_text(json.dumps({"job_id": job_id, "status": "submitted"}, indent=2), encoding="utf-8")
            return StationVerdict.HOLD, 0.0, f"submitted axiom-map job {job_id}"

        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        completed = Path(self.hub.queue_dir) / "completed" / f"{meta.get('job_id')}.json"
        if not completed.exists():
            return StationVerdict.HOLD, 0.0, "waiting for axiom mapping completion"

        payload = self._extract_payload(json.loads(completed.read_text(encoding="utf-8")))
        claims = payload.get("claims", [])
        mappings = payload.get("mappings", [])
        gaps = payload.get("gaps", [])
        contradictions = payload.get("contradictions", [])
        for gap in gaps:
            self.emit_signal(SignalType.GAP, f"Missing coverage for axiom {gap}", {"axiom": gap})
        for contradiction in contradictions:
            self.emit_signal(SignalType.QUALITY, f"Contradiction detected: {contradiction}", {"claim": contradiction})
        coverage = len({m.get('axiom') for m in mappings if isinstance(m, dict) and m.get('axiom')})
        breadth_score = min(0.6, coverage / 22)
        confidence = float(payload.get("confidence", 0.5))
        score = min(1.0, breadth_score + 0.4 * confidence)
        sidecar.write_text(json.dumps({"claims": claims, "mappings": mappings, "gaps": gaps, "contradictions": contradictions, "score": score}, indent=2), encoding="utf-8")
        verdict = StationVerdict.PASS if score >= self.threshold_pass else StationVerdict.REVIEW
        return verdict, score, "axiom mapping collected"

    def _extract_payload(self, job: dict) -> dict:
        if isinstance(job.get("result_json"), dict):
            return job["result_json"]
        text = str(job.get("result", "")).strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {}
        return {}

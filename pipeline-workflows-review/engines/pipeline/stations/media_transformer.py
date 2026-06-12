"""
media_transformer.py - Station: media intent and transformation routing.

This station does not perform heavy TTS/video/STT work directly. It decides
which transformation lane a document belongs to and writes a durable sidecar.
Heavy model work should be queued through the LLM/media hub so hot-folder
watchers stay responsive.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..station_base import Manifest, SignalType, StationBase, StationVerdict


LANES = {
    "text_lossless": {
        "extensions": {".md", ".txt", ".html", ".htm"},
        "keywords": [
            "paper",
            "article",
            "axiom",
            "theorem",
            "proof",
            "lossless",
            "json",
            "markdown",
        ],
    },
    "audio_tts": {
        "extensions": {".md", ".txt"},
        "keywords": [
            "tts",
            "voice",
            "read aloud",
            "script",
            "narration",
            "podcast",
            "mp3",
        ],
    },
    "audio_transcript": {
        "extensions": {".mp3", ".wav", ".m4a", ".aac", ".flac"},
        "keywords": ["transcribe", "audio", "speech", "recording"],
    },
    "video_package": {
        "extensions": {".mp4", ".mov", ".mkv", ".webm"},
        "keywords": ["video", "thumbnail", "caption", "shorts", "clip"],
    },
    "review": {
        "extensions": set(),
        "keywords": [],
    },
}


class MediaTransformStation(StationBase):
    """Classify a file into text/audio/video transformation lanes."""

    def __init__(self, input_dir: str, output_dir: str, lane_root: str | None = None, **kwargs):
        super().__init__(
            name="media-transform-router",
            input_dir=input_dir,
            output_dir=output_dir,
            file_extensions=[
                ".md",
                ".txt",
                ".html",
                ".htm",
                ".mp3",
                ".wav",
                ".m4a",
                ".aac",
                ".flac",
                ".mp4",
                ".mov",
                ".mkv",
                ".webm",
            ],
            **kwargs,
        )
        self.lane_root = Path(lane_root) if lane_root else self.output_dir
        for lane in LANES:
            (self.lane_root / lane).mkdir(parents=True, exist_ok=True)

    def process(self, file_path: Path, manifest: Manifest) -> tuple[StationVerdict, float, str]:
        text = self._read_sample(file_path)
        lane, confidence, reasons = self._choose_lane(file_path, text)

        manifest.metadata["media_lane"] = lane
        manifest.metadata["media_lane_confidence"] = confidence
        manifest.metadata["media_lane_reasons"] = reasons
        manifest.metadata["recommended_next_station"] = self._next_station_for_lane(lane)

        sidecar = file_path.with_suffix(file_path.suffix + ".media.json")
        sidecar.write_text(
            json.dumps(
                {
                    "file": str(file_path),
                    "lane": lane,
                    "confidence": confidence,
                    "reasons": reasons,
                    "recommended_next_station": manifest.metadata["recommended_next_station"],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        if lane == "review" or confidence < self.threshold_pass:
            self.emit_signal(
                SignalType.QUALITY,
                f"{file_path.name} needs media-routing review",
                {"lane": lane, "confidence": confidence, "reasons": reasons},
            )
            return (
                StationVerdict.REVIEW,
                confidence,
                f"Media route uncertain: {lane}; reasons={', '.join(reasons)}",
            )

        lane_dir = self.lane_root / lane
        self.output_dir = lane_dir
        return (
            StationVerdict.PASS,
            confidence,
            f"Media route: {lane}; next={manifest.metadata['recommended_next_station']}",
        )

    def _read_sample(self, file_path: Path) -> str:
        if file_path.suffix.lower() not in {".md", ".txt", ".html", ".htm"}:
            return ""
        try:
            raw = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""
        raw = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", raw)
        raw = re.sub(r"(?s)<[^>]+>", " ", raw)
        return re.sub(r"\s+", " ", raw).strip()[:5000]

    def _choose_lane(self, file_path: Path, text: str) -> tuple[str, float, list[str]]:
        suffix = file_path.suffix.lower()
        haystack = f"{file_path.name} {text[:3000]}".lower()
        scores: dict[str, float] = {}
        reasons: dict[str, list[str]] = {}

        for lane, spec in LANES.items():
            if lane == "review":
                continue
            score = 0.0
            lane_reasons = []
            if suffix in spec["extensions"]:
                score += 0.45
                lane_reasons.append(f"extension:{suffix}")
            hits = [kw for kw in spec["keywords"] if kw in haystack]
            if hits:
                score += min(0.45, 0.1 * len(hits))
                lane_reasons.extend(f"keyword:{kw}" for kw in hits[:5])
            if lane == "text_lossless" and suffix in {".md", ".txt", ".html", ".htm"}:
                score += 0.15
                lane_reasons.append("default_text_pipeline")
            scores[lane] = min(score, 1.0)
            reasons[lane] = lane_reasons

        if not scores:
            return "review", 0.0, ["no_supported_lane"]
        lane = max(scores, key=scores.get)
        confidence = scores[lane]
        if confidence < 0.3:
            return "review", confidence, reasons.get(lane, ["low_confidence"])
        return lane, confidence, reasons.get(lane, [])

    def _next_station_for_lane(self, lane: str) -> str:
        return {
            "text_lossless": "lossless-formatter",
            "audio_tts": "tts-generator",
            "audio_transcript": "stt-transcriber",
            "video_package": "video-packager",
            "review": "human-review",
        }.get(lane, "human-review")

"""Station 3: lossless text cleanup and normalization."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from ..station_base import Manifest, StationBase, StationVerdict


class LosslessFormatterStation(StationBase):
    """Clean STT artifacts and normalize markdown without semantic loss."""

    def __init__(self, input_dir: str, output_dir: str, **kwargs):
        super().__init__("lossless-formatter", input_dir, output_dir, file_extensions=[".md", ".txt"], **kwargs)

    def process(self, file_path: Path, manifest: Manifest) -> tuple[StationVerdict, float, str]:
        raw = file_path.read_text(encoding="utf-8", errors="replace")
        cleaned, edits = self._normalize(raw)
        sidecar_data = self._load_sidecar(file_path)
        title = self._infer_title(cleaned, file_path)
        frontmatter = self._frontmatter(title, file_path, cleaned, sidecar_data)
        output_text = frontmatter + cleaned.strip() + "\n"
        out_path = self.output_dir / f"{file_path.stem}.md"
        out_path.write_text(output_text, encoding="utf-8", newline="\n")
        ratio = edits / max(len(raw), 1)
        score = max(0.2, 1.0 - min(0.7, ratio * 4))
        verdict = StationVerdict.PASS if score >= self.threshold_pass else StationVerdict.REVIEW
        return verdict, score, f"lossless cleanup edits={edits} ratio={ratio:.3f}"

    def _normalize(self, text: str) -> tuple[str, int]:
        edits = 0
        out = text.replace("\r\n", "\n").replace("\r", "\n")
        out, n = re.subn(r"(?i)\b(um+|uh+)\b", "", out)
        edits += n
        out, n = re.subn(r"(?im)^\s*(okay|alright|you know),?\s*$", "", out)
        edits += n
        out, n = re.subn(r"\b(\w+)(\s+\1\b)+", r"\1", out, flags=re.IGNORECASE)
        edits += n
        out, n = re.subn(r"(?is)<(script|style).*?</\1>", "", out)
        edits += n
        out, n = re.subn(r"<[^>]+>", "", out)
        edits += n
        out = self._normalize_markdown(out)
        out, n = re.subn(r"[ \t]+\n", "\n", out)
        edits += n
        out, n = re.subn(r"\n{3,}", "\n\n", out)
        edits += n
        return out, edits

    def _normalize_markdown(self, text: str) -> str:
        lines = []
        for line in text.split("\n"):
            s = line.strip()
            if re.match(r"^#{1,6}\S", s):
                s = re.sub(r"^(#{1,6})(\S)", r"\1 \2", s)
            if re.match(r"^[-*+]\S", s):
                s = re.sub(r"^([-*+])(\S)", r"\1 \2", s)
            lines.append(s if s else "")
        return "\n".join(lines)

    def _load_sidecar(self, file_path: Path) -> dict:
        sidecar = file_path.with_suffix(file_path.suffix + ".fap.json")
        if not sidecar.exists():
            return {}
        try:
            return json.loads(sidecar.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _infer_title(self, text: str, file_path: Path) -> str:
        for line in text.splitlines():
            if line.strip().startswith("#"):
                return line.lstrip("# ").strip()
            if line.strip():
                return line.strip()[:80]
        return file_path.stem

    def _frontmatter(self, title: str, file_path: Path, text: str, sidecar_data: dict) -> str:
        today = datetime.now(UTC).date().isoformat()
        return (
            "---\n"
            f"title: \"{title}\"\n"
            f"date: {today}\n"
            f"word_count: {len(text.split())}\n"
            f"source_file: {file_path.name}\n"
            f"classification: {json.dumps(sidecar_data, ensure_ascii=False)}\n"
            "---\n\n"
        )

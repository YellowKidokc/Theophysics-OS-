"""Station 7: compile production Obsidian page from mapped paper."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..llm_hub import LLMHub
from ..station_base import Manifest, SignalType, StationBase, StationVerdict


class WikiCompilerStation(StationBase):
    """Compile a 7-layer Obsidian page using async LLMHub layers."""

    def __init__(self, input_dir: str, output_dir: str, queue_dir: str | None = None, **kwargs):
        super().__init__("wiki-compiler", input_dir, output_dir, file_extensions=[".md", ".txt"], **kwargs)
        self.hub = LLMHub(queue_dir=queue_dir or "_queue")

    def process(self, file_path: Path, manifest: Manifest) -> tuple[StationVerdict, float, str]:
        """Submit/collect layer jobs and compile final page when ready."""
        text = file_path.read_text(encoding="utf-8", errors="replace")
        jobs = self._submit_layer_jobs(file_path, text)
        layers = self._collect_layer_jobs(jobs)
        if any(v is None for v in layers.values()):
            return StationVerdict.HOLD, 0.0, "waiting for wiki layer jobs"

        frontmatter = self._build_frontmatter(file_path, manifest)
        page = self._assemble_page(frontmatter, text, layers)
        out_file = self.output_dir / f"{file_path.stem}.md"
        out_file.write_text(page, encoding="utf-8")
        self.emit_signal(SignalType.READY, f"Compiled vault page {out_file.name}", {"path": str(out_file)})
        return StationVerdict.PASS, 0.9, "wiki compiled"

    def _build_frontmatter(self, file_path: Path, manifest: Manifest) -> dict[str, Any]:
        return {
            "title": file_path.stem,
            "source_file": file_path.name,
            "epistemic_state": manifest.metadata.get("epistemic_state", "hypothesis"),
            "axiom_mappings": manifest.metadata.get("axioms", {}),
            "scores": manifest.scores,
            "pipeline_history": manifest.history,
        }

    def _submit_layer_jobs(self, file_path: Path, text: str) -> dict[str, str]:
        state_file = file_path.with_suffix(file_path.suffix + ".wiki_jobs.json")
        if state_file.exists():
            return json.loads(state_file.read_text(encoding="utf-8"))
        jobs = {
            "layer1": self.hub.submit("wiki-compiler", str(file_path), "executive_summary", backend="claude_api", priority="batch", input_text=text[:5000]),
            "layer2": self.hub.submit("wiki-compiler", str(file_path), "plain_language", backend="claude_api", priority="batch", input_text=text[:5000]),
            "layer4": self.hub.submit("wiki-compiler", str(file_path), "grade_paper", backend="claude_api", priority="batch", input_text=text[:5000]),
            "layer5": self.hub.submit("wiki-compiler", str(file_path), "vault_page_compiler", backend="claude_api", priority="batch", input_text=text[:5000]),
            "layer7": self.hub.submit("wiki-compiler", str(file_path), "vault_page_compiler", backend="claude_api", priority="batch", input_text=text[:5000]),
        }
        state_file.write_text(json.dumps(jobs, indent=2), encoding="utf-8")
        return jobs

    def _collect_layer_jobs(self, jobs: dict[str, str]) -> dict[str, str | None]:
        content: dict[str, str | None] = {}
        for layer, job_id in jobs.items():
            completed = Path(self.hub.queue_dir) / "completed" / f"{job_id}.json"
            if not completed.exists():
                content[layer] = None
                continue
            job = json.loads(completed.read_text(encoding="utf-8"))
            content[layer] = str(job.get("result", "")).strip() or json.dumps(job.get("result_json", {}), indent=2)
        return content

    def _yaml_block(self, frontmatter: dict[str, Any]) -> str:
        lines = ["---"]
        for key, value in frontmatter.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
            else:
                lines.append(f"{key}: {value}")
        lines.append("---")
        return "\n".join(lines)

    def _assemble_page(self, frontmatter: dict[str, Any], text: str, layers: dict[str, str | None]) -> str:
        return (
            f"{self._yaml_block(frontmatter)}\n\n"
            f"## Layer 1: Executive Summary\n{layers['layer1']}\n\n"
            f"## Layer 2: Plain Language\n{layers['layer2']}\n\n"
            f"## Layer 3: The Paper\n{text}\n\n"
            f"## Layer 4: Academic Register\n{layers['layer4']}\n\n"
            f"## Layer 5: Knowledge Graph\n{layers['layer5']}\n\n"
            f"## Layer 6: Data Layer\n```json\n{json.dumps(frontmatter, indent=2)}\n```\n\n"
            f"## Layer 7: Impact Notes\n{layers['layer7']}\n"
        )

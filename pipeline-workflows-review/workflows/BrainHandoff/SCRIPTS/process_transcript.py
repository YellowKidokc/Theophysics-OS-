"""BrainHandoff transcript processor."""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from engines.pipeline.llm_hub import LLMHub
from engines.pipeline.station_base import Manifest
from engines.pipeline.stations.lossless_formatter import LosslessFormatterStation
from engines.pipeline.stations.vectorizer import VectorizerStation


def _safe_json(raw: str) -> dict:
    try:
        if raw.strip().startswith("{"):
            return json.loads(raw)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        return json.loads(m.group()) if m else {}
    except Exception:
        return {}


def process_file(file_path: Path, root: Path) -> dict:
    """Process one transcript through cleanup, summarize, mirror, vectorize, and archive."""
    out = root / "OUTPUT"
    archive = root / "ARCHIVE"
    logs = root / "LOGS"
    for p in [out, archive, logs]:
        p.mkdir(parents=True, exist_ok=True)

    text = file_path.read_text(encoding="utf-8", errors="replace")
    lossless = LosslessFormatterStation(str(root / "INPUT"), str(out / "cleaned"))
    manifest = Manifest(file_path=str(file_path), file_hash="-", pipeline_name="brain-handoff", current_station="lossless")
    lossless.process(file_path, manifest)
    cleaned_path = out / "cleaned" / f"{file_path.stem}.md"
    cleaned_text = cleaned_path.read_text(encoding="utf-8", errors="replace") if cleaned_path.exists() else text

    hub = LLMHub(queue_dir=str(root / "_queue"))
    job_id = hub.submit("brain-handoff", str(file_path), "summarize_session", backend="ollama", input_text=cleaned_text[:7000])
    summary = {
        "session_date": "",
        "participants": [],
        "duration_estimate": "medium",
        "key_decisions": [],
        "action_items": [],
        "open_threads": [],
        "framework_refs": {"laws": [], "axioms": [], "equations": [], "concepts": []},
        "summary": "Pending LLM completion",
        "quality_score": 0.5,
        "llm_job_id": job_id,
    }

    summary_json = out / f"{file_path.stem}_summary.json"
    summary_md = out / f"{file_path.stem}_summary.md"
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary_md.write_text(f"# Session Summary\n\n{summary['summary']}\n", encoding="utf-8")

    for env_key, default in [
        ("BRAIN_OLLAMA_DIR", r"X:\brain\ollama\session-handoffs"),
        ("VAULT_SESSIONS_DIR", r"X:\vault\AI Sessions"),
        ("FULL_CONV_DIR", r"Z:\Vault\AI-Chats History\full conversation"),
    ]:
        try:
            target = Path(os.environ.get(env_key, default))
            target.mkdir(parents=True, exist_ok=True)
            if env_key == "FULL_CONV_DIR":
                shutil.copy2(file_path, target / file_path.name)
            else:
                shutil.copy2(summary_md, target / summary_md.name)
        except Exception:
            pass

    try:
        vec = VectorizerStation(str(out), str(out / "vectorized"))
        vec.process(summary_md, manifest)
    except Exception:
        pass

    try:
        shutil.move(str(file_path), str(archive / file_path.name))
    except Exception:
        pass

    return {"file": file_path.name, "summary_json": str(summary_json), "summary_md": str(summary_md)}


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    results = [process_file(fp, root) for fp in (root / "INPUT").glob("*.*") if fp.suffix.lower() in {".md", ".txt", ".html"}]
    (root / "LOGS" / "process_log.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

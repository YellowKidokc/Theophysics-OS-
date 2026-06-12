"""Resolve layered FAP preferences."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = REPO_ROOT / "preferences" / "defaults.json"
PROFILES = REPO_ROOT / "preferences" / "profiles"
WORKFLOWS = REPO_ROOT / "workflows"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
        return data if isinstance(data, dict) else {}


def _deep_merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def resolve(
    workflow_name: str,
    profile_name: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge defaults + optional profile + workflow prefs + CLI overrides."""
    prefs = _read_json(DEFAULTS)
    if profile_name:
        prefs = _deep_merge(prefs, _read_json(PROFILES / f"{profile_name}.json"))
    prefs = _deep_merge(
        prefs,
        _read_json(WORKFLOWS / workflow_name / "PREFS" / "preferences.json"),
    )
    if overrides:
        prefs = _deep_merge(prefs, overrides)
    prefs = _deep_merge(MINIMUM_DEFAULTS, prefs)
    return prefs


MINIMUM_DEFAULTS = {"model_lane":"fast","llm_backend":"ollama","stt_cleanup_aggressiveness":0.5,"stop_for_review":True,"output_destinations":["vault"],"summary_detail_level":"standard","threshold_pass":0.7,"threshold_fail":0.3}

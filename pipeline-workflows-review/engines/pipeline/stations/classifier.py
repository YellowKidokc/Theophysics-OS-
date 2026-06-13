"""
classifier.py — Station 1: Intake Classification

Reads a file, determines what it IS:
  - Which of the 10 Laws does it touch?
  - Which axioms does it map to?
  - What's the 7Q classification?
  - Is it a paper, article, note, data, or code?

Uses Ollama for local classification when available,
falls back to heuristic keyword matching.
"""

import re
import json
from pathlib import Path
from typing import Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from ..station_base import StationBase, StationVerdict, Manifest, SignalType


# ── The 10 Laws keyword map ──────────────────────────────────────
LAW_KEYWORDS = {
    "L1_Gravitation": [
        "gravity", "curvature", "spacetime", "mass", "sin", "grace",
        "gravitational", "geodesic", "attraction", "weight",
    ],
    "L2_Motion": [
        "force", "acceleration", "momentum", "inertia", "newton",
        "will", "repentance", "conversion", "motion", "velocity",
    ],
    "L3_Electromagnetism": [
        "electromagnetic", "light", "photon", "maxwell", "charge",
        "truth", "deception", "witness", "glory", "doxa",
    ],
    "L4_StrongForce": [
        "strong force", "nuclear", "quark", "gluon", "yukawa",
        "love", "agape", "fruit", "captivity", "binding",
    ],
    "L5_Thermodynamics": [
        "entropy", "thermodynamic", "heat", "temperature", "energy",
        "judgment", "justice", "mercy", "free energy", "disorder",
    ],
    "L6_Information": [
        "shannon", "information", "channel", "bandwidth", "signal",
        "logos", "chaos", "noise", "encoding", "communication",
    ],
    "L7_Quantum": [
        "quantum", "superposition", "collapse", "measurement", "wave",
        "faith", "doubt", "observation", "uncertainty", "entangle",
    ],
    "L8_Relativity": [
        "relativity", "frame", "reference", "lorentz", "spacetime",
        "grace", "perspective", "invariant", "transformation",
    ],
    "L9_WeakForce": [
        "weak force", "decay", "parity", "symmetry breaking", "noether",
        "moral conservation", "atonement", "irreversible",
    ],
    "L10_Coherence": [
        "coherence", "chi", "χ", "decoherence", "alignment",
        "christ", "kingdom", "shalom", "unified", "master equation",
    ],
}

# ── Document type patterns ────────────────────────────────────────
DOC_TYPE_PATTERNS = {
    "paper": [r"abstract", r"introduction", r"methodology", r"conclusion",
              r"references", r"theorem", r"proof", r"lemma"],
    "article": [r"subscribe", r"read more", r"published", r"blog",
                r"series", r"part \d"],
    "note": [r"todo", r"idea", r"scratch", r"draft", r"rough"],
    "data": [r"\.csv", r"\.json", r"\.tsv", r"dataset", r"table"],
    "code": [r"def ", r"function", r"import ", r"class ", r"const "],
}


class ClassifierStation(StationBase):

    def __init__(self, input_dir: str, output_dir: str,
                 ollama_url: str = "http://localhost:11434/api/generate",
                 ollama_model: str = "mistral",
                 **kwargs):
        super().__init__(
            name="classifier",
            input_dir=input_dir,
            output_dir=output_dir,
            file_extensions=[".md", ".txt", ".html", ".htm", ".pdf", ".docx"],
            **kwargs
        )
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model

    def process(self, file_path: Path, manifest: Manifest) -> tuple:
        text = self._read_file(file_path)
        if not text:
            return (StationVerdict.FAIL, 0.0, "Could not read file")

        # Classify
        laws = self._detect_laws(text)
        doc_type = self._detect_doc_type(text, file_path)
        confidence = self._compute_confidence(laws, doc_type)

        # Try Ollama for richer classification
        ollama_result = self._ollama_classify(text[:2000])
        if ollama_result:
            manifest.metadata["ollama_classification"] = ollama_result
            confidence = min(1.0, confidence + 0.15)

        # Store classification in manifest
        manifest.metadata["laws"] = laws
        manifest.metadata["doc_type"] = doc_type
        manifest.metadata["word_count"] = len(text.split())

        # Write sidecar JSON
        sidecar = file_path.with_suffix(file_path.suffix + ".fap.json")
        with open(sidecar, "w") as f:
            json.dump({
                "laws": laws,
                "doc_type": doc_type,
                "confidence": confidence,
                "ollama": ollama_result,
            }, f, indent=2)

        if confidence >= self.threshold_pass:
            return (StationVerdict.PASS, confidence,
                    f"Classified as {doc_type}, Laws: {', '.join(laws[:3])}")
        elif confidence <= self.threshold_fail:
            return (StationVerdict.FAIL, confidence,
                    f"Low confidence classification: {doc_type}")
        else:
            return (StationVerdict.REVIEW, confidence,
                    f"Gray zone: {doc_type}, Laws: {', '.join(laws[:3])}")

    def _read_file(self, fp: Path) -> Optional[str]:
        try:
            if fp.suffix.lower() in [".md", ".txt", ".html", ".htm"]:
                return fp.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass
        return None

    def _detect_laws(self, text: str) -> list[str]:
        text_lower = text.lower()
        scores = {}
        for law, keywords in LAW_KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in text_lower)
            if hits > 0:
                scores[law] = hits
        return sorted(scores, key=scores.get, reverse=True)

    def _detect_doc_type(self, text: str, fp: Path) -> str:
        text_sample = text[:3000].lower()
        scores = {}
        for dtype, patterns in DOC_TYPE_PATTERNS.items():
            hits = sum(1 for p in patterns if re.search(p, text_sample))
            if hits > 0:
                scores[dtype] = hits
        if scores:
            return max(scores, key=scores.get)
        return "unknown"

    def _compute_confidence(self, laws: list, doc_type: str) -> float:
        score = 0.3  # base
        if laws:
            score += min(0.3, len(laws) * 0.1)
        if doc_type != "unknown":
            score += 0.2
        return min(1.0, score)

    def _ollama_classify(self, text_snippet: str) -> Optional[dict]:
        if not HAS_REQUESTS:
            return None
        prompt = (
            "Classify this document. Return ONLY valid JSON with keys: "
            "\"type\" (paper|article|note|data|code|unknown), "
            "\"topics\" (list of 3-5 topic tags), "
            "\"quality\" (0.0-1.0). "
            f"Document:\n{text_snippet[:1500]}"
        )
        try:
            r = requests.post(self.ollama_url, json={
                "model": self.ollama_model,
                "prompt": prompt,
                "stream": False,
            }, timeout=30)
            if r.ok:
                raw = r.json().get("response", "")
                # Try to parse JSON from response
                match = re.search(r'\{.*\}', raw, re.DOTALL)
                if match:
                    return json.loads(match.group())
        except Exception:
            pass
        return None

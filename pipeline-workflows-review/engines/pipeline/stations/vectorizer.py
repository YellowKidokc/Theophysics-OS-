"""Station 4: semantic chunking + embeddings + duplicate signaling."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

from ..station_base import Manifest, SignalType, StationBase, StationVerdict


class VectorizerStation(StationBase):
    """Chunk by paragraphs (~500 tokens) and embed via Infinity/local fallback."""

    def __init__(self, input_dir: str, output_dir: str, **kwargs):
        super().__init__("vectorizer", input_dir, output_dir, file_extensions=[".md", ".txt"], **kwargs)
        self.infinity_url = os.environ.get("INFINITY_URL", "http://localhost:7997/embed")

    def process(self, file_path: Path, manifest: Manifest) -> tuple[StationVerdict, float, str]:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        chunks = self._chunk_text(text)
        vectors, used_model = self._embed_chunks(chunks)
        sidecar = file_path.with_suffix(file_path.suffix + ".vectors.json")
        metadata = [{"position": i, "heading_context": self._heading_context(chunks, i)} for i in range(len(chunks))]
        sidecar.write_text(json.dumps({"chunks": chunks, "vectors": vectors, "metadata": metadata}, indent=2), encoding="utf-8")
        self._check_duplicates(file_path, vectors)
        (self.output_dir / file_path.name).write_text(text, encoding="utf-8")
        avg_len = sum(len(c.split()) for c in chunks) / max(len(chunks), 1)
        quality = 0.3 + min(0.35, len(chunks) / 20) + (0.2 if used_model else 0.05) + min(0.15, avg_len / 700)
        score = min(1.0, quality)
        verdict = StationVerdict.PASS if score >= self.threshold_pass else StationVerdict.REVIEW
        return verdict, score, f"vectorized chunks={len(chunks)} model={'endpoint' if used_model else 'fallback'}"

    def _chunk_text(self, text: str) -> list[str]:
        paras = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks, current, count = [], [], 0
        for para in paras:
            tokens = para.split()
            if count and count + len(tokens) > 500:
                chunks.append("\n\n".join(current))
                current, count = [], 0
            current.append(para)
            count += len(tokens)
        if current:
            chunks.append("\n\n".join(current))
        return chunks or [text[:3000]]

    def _embed_chunks(self, chunks: list[str]) -> tuple[list[list[float]], bool]:
        try:
            if requests is None:
                raise RuntimeError("requests unavailable")
            resp = requests.post(self.infinity_url, json={"input": chunks}, timeout=20)
            if resp.ok:
                data = resp.json()
                emb = data.get("data") or data.get("embeddings")
                if isinstance(emb, list) and emb:
                    if isinstance(emb[0], dict) and "embedding" in emb[0]:
                        return [e["embedding"] for e in emb], True
                    if isinstance(emb[0], list):
                        return emb, True
        except Exception:
            pass
        return [self._fallback_embed(c) for c in chunks], False

    def _fallback_embed(self, text: str) -> list[float]:
        vals = [0.0] * 16
        for i, tok in enumerate(text.split()[:300]):
            vals[i % 16] += (sum(ord(c) for c in tok) % 313) / 313
        norm = math.sqrt(sum(v * v for v in vals)) or 1.0
        return [v / norm for v in vals]

    def _check_duplicates(self, file_path: Path, vectors: list[list[float]]) -> None:
        index_path = self.output_dir / "_index.json"
        index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"documents": []}
        current = vectors[0] if vectors else [0.0] * 16
        for prior in index["documents"]:
            sim = self._cos(current, prior.get("embedding", []))
            if sim > 0.92:
                self.emit_signal(SignalType.DUPLICATE, f"Near duplicate of {prior.get('file')}", {"similarity": sim})
        index["documents"].append({"file": file_path.name, "embedding": current})
        index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    def _heading_context(self, chunks: list[str], pos: int) -> str:
        for line in chunks[pos].splitlines():
            if line.strip().startswith("#"):
                return line.strip().lstrip("# ")
        return ""

    def _cos(self, a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        n = min(len(a), len(b))
        return sum(a[i] * b[i] for i in range(n))

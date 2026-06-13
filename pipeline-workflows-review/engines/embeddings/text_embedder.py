"""
text_embedder.py
PIL embedding helper — calls the Infinity service running on the NAS.
Drop-in OpenAI-compatible /embeddings endpoint.
"""
import os

import requests

INFINITY_URL = os.environ.get("INFINITY_URL", "http://localhost:7997")
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def embed_text(text: str, model: str = DEFAULT_MODEL) -> list:
    r = requests.post(f"{INFINITY_URL}/embeddings", json={
        "input": [text],
        "model": model,
    }, timeout=10)
    r.raise_for_status()
    return r.json()["data"][0]["embedding"]


if __name__ == "__main__":
    import sys
    sample = sys.argv[1] if len(sys.argv) > 1 else "PIL embedding smoke test"
    try:
        vec = embed_text(sample)
        print(f"OK — dim={len(vec)} first8={vec[:8]}")
    except Exception as e:
        print(f"FAIL — {type(e).__name__}: {e}")
        sys.exit(1)

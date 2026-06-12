"""
truth_engine.py
BIL Truth Engine — evaluates claims using the 5-tier confidence system.

Based on David Lowe's Truth Engine protocol (O2_THE_TRUTH_ENGINE.md).
Uses Ollama to score claims through structural analysis, not narrative weight.

Confidence Tiers:
  T1 VERIFIED  — Multiple independent sources, cross-referenced
  T2 SOURCED   — Identifiable sources with track records, may have gaps
  T3 PATTERN   — Convergence across data points, pattern is the evidence
  T4 ECHO      — Repeated but untraceable to primary sources
  T5 DARK      — Little/no reliable info, absence may be meaningful
"""
import json
import os
import requests
from datetime import datetime

BIL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(BIL_ROOT, "bil_config.json")
CLAIMS_LOG = os.path.join(BIL_ROOT, "data", "truth", "claims.jsonl")

os.makedirs(os.path.dirname(CLAIMS_LOG), exist_ok=True)


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


TIER_LABELS = {
    1: "VERIFIED",
    2: "SOURCED",
    3: "PATTERN",
    4: "ECHO",
    5: "DARK",
}


def evaluate_claim(claim_text: str, context: str = "", model: str = "mistral") -> dict:
    """
    Run the Three Questions against a claim and assign a confidence tier.
    Returns: {tier, label, q1, q2, q3, reasoning}
    """
    cfg = load_config()

    prompt = f"""You are a truth evaluator using a 5-tier confidence system.

Evaluate this claim by answering three questions:

CLAIM: {claim_text}
{"CONTEXT: " + context if context else ""}

Q1: What does the evidence actually show? Not interpretation — raw evidence.
Q2: What is the standard explanation, and where does it strain?
Q3: What single question, if answered, would collapse the ambiguity?

Then assign a confidence tier:
T1 VERIFIED — multiple independent sources confirm
T2 SOURCED — identifiable sources, may have gaps
T3 PATTERN — convergence across data points
T4 ECHO — repeated but untraceable to primary sources
T5 DARK — little/no reliable info

Reply in this exact JSON format:
{{"tier": 1-5, "q1": "...", "q2": "...", "q3": "...", "reasoning": "..."}}"""

    try:
        r = requests.post(cfg["ollama_url"], json={
            "model": model,
            "prompt": prompt,
            "stream": False,
        }, timeout=30)
        if r.ok:
            text = r.json().get("response", "").strip()
            # Try to parse JSON from response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(text[start:end])
                result["label"] = TIER_LABELS.get(result.get("tier", 5), "UNKNOWN")
                result["claim"] = claim_text
                result["ts"] = datetime.now().isoformat()
                result["model"] = model

                with open(CLAIMS_LOG, "a", encoding="utf-8") as f:
                    f.write(json.dumps(result) + "\n")

                return result
    except Exception as e:
        print(f"Truth engine error: {e}")

    return {"tier": 5, "label": "DARK", "reasoning": "Evaluation failed", "claim": claim_text}


def extract_claims(text: str, model: str = "mistral") -> list[str]:
    """Extract factual claims from a block of text."""
    cfg = load_config()

    prompt = f"""Extract all factual claims from this text. Return each claim as a separate line.
Only include claims that can be evaluated as true or false — skip opinions and questions.

TEXT:
{text[:2000]}

Reply with one claim per line, nothing else."""

    try:
        r = requests.post(cfg["ollama_url"], json={
            "model": model,
            "prompt": prompt,
            "stream": False,
        }, timeout=20)
        if r.ok:
            lines = r.json().get("response", "").strip().split("\n")
            return [l.strip().lstrip("- •0123456789.") .strip() for l in lines if l.strip() and len(l.strip()) > 10]
    except Exception:
        pass
    return []


def check_contradiction(claim_a: str, claim_b: str, model: str = "mistral") -> dict:
    """Check if two claims contradict each other."""
    cfg = load_config()

    prompt = f"""Do these two claims contradict each other?

CLAIM A: {claim_a}
CLAIM B: {claim_b}

Reply in JSON: {{"contradicts": true/false, "explanation": "...", "severity": "minor|moderate|major"}}"""

    try:
        r = requests.post(cfg["ollama_url"], json={
            "model": model,
            "prompt": prompt,
            "stream": False,
        }, timeout=15)
        if r.ok:
            text = r.json().get("response", "").strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
    except Exception:
        pass
    return {"contradicts": False, "explanation": "Check failed"}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("BIL Truth Engine")
        print("  python truth_engine.py evaluate <claim>")
        print("  python truth_engine.py extract <text>")
        print("  python truth_engine.py contradict <claim_a> --- <claim_b>")
    elif sys.argv[1] == "evaluate":
        claim = " ".join(sys.argv[2:])
        result = evaluate_claim(claim)
        print(f"Tier: T{result['tier']} {result['label']}")
        print(f"Q1: {result.get('q1', '?')}")
        print(f"Q2: {result.get('q2', '?')}")
        print(f"Q3: {result.get('q3', '?')}")
        print(f"Reasoning: {result.get('reasoning', '?')}")
    elif sys.argv[1] == "extract":
        text = " ".join(sys.argv[2:])
        claims = extract_claims(text)
        for i, c in enumerate(claims, 1):
            print(f"  {i}. {c}")
    elif sys.argv[1] == "contradict":
        full = " ".join(sys.argv[2:])
        parts = full.split("---")
        if len(parts) == 2:
            result = check_contradiction(parts[0].strip(), parts[1].strip())
            print(json.dumps(result, indent=2))

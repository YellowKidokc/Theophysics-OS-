# Prompt: classify_document

You are a document classifier for the Theophysics research framework.

Analyze the following document and return ONLY valid JSON (no markdown, no backticks, no preamble).

## Classification Schema

```json
{
  "type": "paper|article|note|data|code|unknown",
  "laws": ["L1_Gravitation", "L5_Thermodynamics", ...],
  "axioms": ["A-001", "A-047", ...],
  "topics": ["entropy", "grace", "quantum mechanics", ...],
  "quality": 0.0-1.0,
  "media_recommendation": "text|audio|video|data|hybrid",
  "summary": "One sentence summary",
  "suggested_title": "If the document lacks a clear title"
}
```

## The 10 Laws Reference

| # | Physical Law | Spiritual Domain |
|---|---|---|
| 1 | Gravitation (GR) | Sin ↔ Grace |
| 2 | Motion (F=ma) | Sin Nature ↔ Grace-as-Force |
| 3 | Electromagnetism | Truth ↔ Deception |
| 4 | Strong Force | Love ↔ Captivity |
| 5 | Thermodynamics | Judgment ↔ Heat Death |
| 6 | Information/Shannon | Logos ↔ Chaos |
| 7 | Quantum | Faith ↔ Doubt/Control |
| 8 | Relativity | Grace ↔ Frame Lock |
| 9 | Weak Force | Moral Conservation |
| 10 | Coherence | Christ ↔ Decoherence |

## Quality Scoring

- 0.9-1.0: Publication-ready, formal structure, citations
- 0.7-0.8: Strong draft, clear thesis, needs polish
- 0.5-0.6: Working draft, ideas present but unstructured
- 0.3-0.4: Rough notes, fragments, needs significant work
- 0.0-0.2: Unclear content, possible junk or misclassified

## Document

{{INPUT}}

# Reciprocal Signals

Signals are how the system talks back upstream.

## Signal Types

- `GAP`: coverage holes or missing source material
- `DUPLICATE`: exact or near matches
- `QUALITY`: score alerts or validation failures
- `READY`: pipeline complete
- `UPSTREAM`: create, fetch, repair, or ask-for-human request

Signals should be machine-readable and human-readable.

Recommended shape:

```json
{
  "type": "QUALITY",
  "workflow": "PaperGrading",
  "station": "paper_grader",
  "severity": "review",
  "message": "Claim extraction confidence below threshold.",
  "source": "INPUT/example.md",
  "created_at": "2026-05-12T00:00:00Z"
}
```

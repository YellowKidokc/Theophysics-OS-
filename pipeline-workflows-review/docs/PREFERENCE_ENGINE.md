# Preference Engine

The preference layer observes and calibrates. It never blocks packet execution.

## Learning Chain

```text
River -> PPK -> Implicit
```

1. **River** performs online learning from immediate events and corrections.
2. **PPK** stores portable preference knowledge that can be reused across runs.
3. **Implicit** recalculates collaborative/relevance patterns from accumulated
   behavior.

## BIL Signal Weights

BIL consumes signals with different strengths. Human correction is the strongest
signal because it reflects an explicit override. Passive behavior is useful but
weaker.

Recommended weighting hierarchy:

| Signal | Meaning | Relative weight |
| --- | --- | --- |
| Human correction | Manual fix to verdict, route, domain, subject, or slug | 1.0 |
| Explicit rating | User marks output useful/not useful | 0.8 |
| Manual reroute | User changes destination | 0.7 |
| Reopen/reuse | Output is used again | 0.4 |
| Passive view | User opened or previewed result | 0.2 |

## Correction Data

`scripts/correction_logger.py` writes structured JSONL and attempts to push each
event to the BIL server. If BIL is offline, local JSONL remains the source of
truth and can be replayed later.

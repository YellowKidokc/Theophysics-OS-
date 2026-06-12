# Rubric Output Schema

Every exhaustively processed paper should produce two primary outputs:

- raw truth: `{paper_id}_RUBRIC.xlsx`
- polished front side: `{paper_id}_REPORT.html`

The Excel workbook is the complete machine/audit layer. The HTML report is the
consumer-facing, polished layer.

## Workbook Sheets

| Sheet | Station | Purpose |
| --- | --- | --- |
| Overview | all | paper id, title, word count, final score, verdict |
| Classification | classifier | Law scores, document type, concept class, confidence |
| Fact Check | fact_verify | claim, evidence, supported/refuted/insufficient |
| Math Check | math_verify | equation, parsed values, valid/invalid, error magnitude |
| Contradiction Check | contradiction_detect | statement pairs and contradiction/entailment/neutral |
| Timeline Check | timeline_verify | date/event references, source match, deviation |
| Quality Grade | paper_review | coherence, voice, cross-domain strength, publish readiness |
| Media Routing | media_router | HTML, TTS, video, thumbnail, archive routing decisions |
| Composite Scores | all | weighted score, threshold, verdict |

## Composite Score Defaults

| Metric | Weight |
| --- | ---: |
| Fact Check | 20 |
| Math | 15 |
| Contradiction | 15 |
| Cross-domain | 10 |
| Timeline | 10 |
| Classification | 10 |
| Coherence | 10 |
| Voice | 5 |
| Publish readiness | 5 |

## Verdict Thresholds

| Verdict | Score |
| --- | --- |
| PUBLISH | above 0.80 |
| REVISE | 0.60 to 0.80 |
| RESTRUCTURE | 0.40 to 0.60 |
| HOLD | below 0.40 |

## HTML Report

The HTML report should be a polished view over the same data:

- final verdict
- score bars
- strongest claims
- unresolved risks
- contradiction/timeline/math warnings
- expandable claim detail
- link back to the Excel workbook

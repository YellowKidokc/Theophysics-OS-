# Theophysics Vault — Page Architecture
# The anatomy of every finished page in the production vault.
# This is NOT folder structure. This is WHAT EVERY PAGE LOOKS LIKE.
# The page structure IS the product. Everything else is plumbing.

---

## THE SEVEN LAYERS + EPISTEMIC STATE

Every page in the production vault has seven layers, rendered as
collapsible sections in Obsidian. Not every layer is filled on
every page — but every page HAS every layer, even if some say
"[pending]". The structure is the skeleton. Content fills it over time.

### CRITICAL: EPISTEMIC STATE (from GPT convergence review)

Every page MUST declare its epistemic state in frontmatter:
```yaml
epistemic_state: hypothesis | partially_supported | mathematically_derived |
                 empirically_supported | unresolved | speculative | contradicted
```

Without this, the vault cannot distinguish a proven theorem from
a shower thought. This is the single most important metadata field
after paper_id.

### CRITICAL: LINK TYPES (prevents ontology collapse)

Not all connections are equal. The vault must distinguish:
- **depends_on:** load-bearing — this paper REQUIRES that axiom/law/paper
- **supports:** evidential — this paper provides evidence for that claim
- **relates_to:** associative — these concepts are connected but independent
- **contradicts:** tension — these claims are in tension (flagged for resolution)
- **supersedes:** versioning — this paper replaces that older version

---

### LAYER 0: FRONTMATTER (YAML — invisible to reader, visible to Dataview)

```yaml
---
title: "The Three-Constraint Model"
paper_id: GTQ-009
series: Genesis to Quantum
status: published | draft | review | stub
type: paper | article | note | thesis-unit | axiom | law
laws: [L5, L9, L10]
axioms: [A-012, A-047, A-103]
seven_q: Q3-Physical
rubric_score: 0.84
verdict: PUBLISH
fact_check_score: 0.92
math_score: 1.00
contradiction_score: 0.88
timeline_score: 0.95
voice_score: 0.72
cross_domain_score: 0.91
word_count: 4200
reading_level: 11.2
created: 2026-04-08
updated: 2026-05-11
author: POF 2828
ai_partners: [Opus, GPT]
tags: [justice, mercy, free-will, OT-NT, cross-domain]
provenance: extracted | inferred | mixed
related:
  - "[[GTQ-008]]"
  - "[[Law 5 — Thermodynamics]]"
  - "[[Axiom A-012]]"
---
```

This is the machine layer. Dataview queries pull from this.
The rubric scores come directly from the Excel output.
Every page is queryable by score, status, law, axiom, series, type.

---

### LAYER 1: EXECUTIVE SUMMARY (for the busy person)

> **One paragraph. Three sentences max.**
> What this paper claims, why it matters, what it changes.
> A CEO or a pastor should be able to read this and know
> whether to keep reading.

**Format:** Obsidian callout block
```markdown
> [!abstract] Executive Summary
> The OT and NT have one author. One equation — χ(t) — holds
> justice, mercy, and free will simultaneously across both
> testaments without contradiction. The "harsh God" problem
> dissolves when you stand in 1400 BC first.
```

---

### LAYER 2: PLAIN ENGLISH SUMMARY (for the everyday person)

> **The "explain it to me like I'm not a physicist" version.**
> No equations. No jargon. No citations. Just the idea,
> in David's voice, the way you'd explain it over coffee.
> 200-400 words. If your mom can't follow it, rewrite it.

**Format:** Regular prose under an H2 heading.

---

### LAYER 3: THE ARTICLE (the actual paper)

> **This is the thing you wrote.** The full paper, article,
> or thesis unit. David's voice. The argument, the evidence,
> the framework. This is what gets published on faiththruphysics.com
> or Substack. This is what the reader came for.

**Format:** Full prose. Includes equations (with the three-layer
equation presentation: equation → plain English → isomorphism proof).
Includes the Honest Audit section at the end.
Includes the Disclaimer.

---

### LAYER 4: ACADEMIC / FORMAL SUMMARY (for scholars)

> **The version a physicist or theologian reads.**
> Formal language. Citations. Methodology stated explicitly.
> Assumptions listed. Falsification criteria named.
> This is not David's voice — this is the framework speaking
> in the language academia expects.

**Format:** Structured with:
- Abstract (150 words)
- Key Claims (numbered)
- Methodology
- Evidence Summary (with citation keys)
- Limitations
- Falsification Criteria

---

### LAYER 5: CROSS-REFERENCE & WIKI LAYER

> **The connective tissue.** This is where the page becomes
> part of the VAULT, not just a standalone document.

**Contains:**
- **Related Laws:** `[[Law 5 — Thermodynamics]]` `[[Law 9 — Weak Force]]`
- **Related Axioms:** `[[Axiom A-012]]` `[[Axiom A-047]]`
- **Related Papers:** `[[GTQ-008]]` `[[GTQ-010]]`
- **Related Concepts:** `[[Grace]]` `[[Entropy]]` `[[Free Will]]`
- **Upstream (this paper depends on):** links to prerequisites
- **Downstream (depends on this paper):** links to papers that cite this
- **External References:** Wikipedia links, source papers, datasets
- **Contradicts / Tensions:** pages where this paper's claims are in tension with others (flagged by contradiction_detect)

**Format:** Obsidian callout blocks with wikilinks.
```markdown
> [!info] Cross-References
> **Laws:** [[Law 5]] [[Law 9]] [[Law 10]]
> **Axioms:** [[A-012]] [[A-047]] [[A-103]]
> **Series:** [[GTQ-008]] ← previous | next → [[GTQ-010]]
> **Concepts:** [[Grace]] [[Entropy]] [[Free Will]] [[Coherence]]
```

---

### LAYER 6: DATA & EVIDENCE LAYER

> **The receipts.** Raw data, rubric scores, pipeline output,
> source citations, experimental results. This is what you
> point to when someone says "prove it."

**Contains:**
- Rubric scores (pulled from Excel, rendered as a mini table)
- Fact check results (claims that were verified/flagged)
- Math check results (equations that were validated)
- Timeline verification results
- Source bibliography
- Links to raw data in Postgres / CSV / the bible warehouse
- Experimental correlations (if applicable — PEAR-LAB, GCP, PROP-COSMOS)

**Format:** Collapsible section with embedded data.
```markdown
> [!example]- Pipeline Rubric
> | Metric | Score |
> |--------|-------|
> | Fact Check | 0.92 |
> | Math | 1.00 |
> | Contradiction | 0.88 |
> | Timeline | 0.95 |
> | Coherence | 0.85 |
> | Voice | 0.72 |
> | Cross-Domain | 0.91 |
> | **COMPOSITE** | **0.84** |
> | **VERDICT** | **PUBLISH** |
```

---

### LAYER 7A: FRAMEWORK IMPACT

> **What this paper CHANGES.** Not what it says — what it
> does to the framework. Did it extend a Law? Resolve a
> tension? Close an open thread? Establish a new connection?
> This is the "before and after" layer.

**Format:**
```markdown
> [!success] Framework Impact
> **What this establishes:**
> - The OT/NT problem dissolves under the three-constraint model
> - Justice, mercy, and free will are not competing values but co-terms
>
> **What this suggests:**
> - The same constraint structure may apply to other theological tensions
> - The pace argument implies a testable claim about revelation sequencing
```

---

### LAYER 7B: OPEN OBLIGATIONS

> **What this paper does NOT prove and what must be tested next.**
> This is the honesty layer. Every paper overclaims unless it
> explicitly names what remains unresolved. This prevents
> ontology collapse — the vault stays epistemically stable
> because every page declares its own limits.

**Format:**
```markdown
> [!warning] Open Obligations
> **What this does NOT prove:**
> - The conquest of Canaan section is contestable — see honest audit
> - The pace argument assumes a specific model of human cognitive development
>
> **What must be tested next:**
> - Can the three-constraint model be applied to the Problem of Evil independently?
> - Does the timeline hold if we use secular dating instead of biblical?
> - The Canaanite child sacrifice scope is debated at the margins — deeper archaeological review needed
```

---

## HOW THE LAYERS MAP TO AUDIENCES

| Layer | Who reads it | Time to read |
|-------|-------------|--------------|
| 0. Frontmatter | Machines (Dataview, pipeline) | 0 sec |
| 1. Executive Summary | CEOs, pastors, casual visitors | 30 sec |
| 2. Plain English | Everyday people, David's mom | 2 min |
| 3. The Article | Readers, Substack subscribers | 10-20 min |
| 4. Academic Summary | Physicists, theologians, peer review | 5 min |
| 5. Cross-References | Vault navigators, AI partners | 1 min |
| 6. Data & Evidence | Skeptics, fact-checkers, David himself | variable |
| 7. Interpretation | Framework builders, future David | 3 min |

---

## HOW THIS CONNECTS TO THE PIPELINE

```
RAW INPUT (voice-to-text, draft, idea)
    ↓
FAP Pipeline (classify → lossless → fact check → math check
    → contradiction check → timeline check → grade → axiom map)
    ↓
EXCEL RUBRIC (9 sheets of raw metrics)
    ↓
HTML REPORT CARD (consumer-facing polished version)
    ↓
OBSIDIAN PAGE COMPILER (olw / LLM Wiki)
    ↓
PRODUCTION VAULT PAGE (all 7 layers populated)
    - Layer 0 frontmatter from rubric scores
    - Layer 1 executive summary from LLM (Ollama)
    - Layer 2 plain English from LLM (Ollama)
    - Layer 3 the article (David's original, cleaned by lossless station)
    - Layer 4 academic summary from LLM (Claude tier)
    - Layer 5 cross-references auto-generated by olw wiki compiler
    - Layer 6 data pulled from Excel rubric + Postgres
    - Layer 7 interpretation from LLM (Claude tier) + David's notes
```

The pipeline FILLS the page structure automatically.
David writes Layer 3. Everything else is generated, verified, and linked
by the system. David reviews and approves. The vault grows.

---

## THE OBSIDIAN TEMPLATE

Save as a template in the vault. Every new page starts from this.

```markdown
---
title: ""
paper_id: ""
series: ""
status: stub
type: paper
laws: []
axioms: []
seven_q: ""
rubric_score: 0.0
verdict: HOLD
created: {{date}}
updated: {{date}}
author: POF 2828
tags: []
---

> [!abstract] Executive Summary
> [pending]

## Plain English
[pending]

## Article
[pending — paste or write your draft here]

## Academic Summary
[pending — generated by pipeline]

> [!info] Cross-References
> [pending — generated by wiki compiler]

> [!example]- Pipeline Rubric
> [pending — generated by pipeline]

> [!success] Framework Impact
> **What this establishes:**
> [pending]
>
> **What this suggests:**
> [pending]

> [!warning] Open Obligations
> **What this does NOT prove:**
> [pending]
>
> **What must be tested next:**
> [pending]
```

---

## LOCKED AS PRODUCTION STANDARD

This page architecture was independently converged on by two AI systems
(Opus and GPT) in separate sessions on May 11-12, 2026. The 7-layer
structure with epistemic state tracking, link type classification,
and the 7A/7B split was confirmed by both as the correct canonical spec.

The audience flow is:
Machine → casual reader → normal person → David's argument →
academic reader → graph system → evidence audit → framework impact →
open obligations

This is THE standard. Every page in the production vault follows this.
Locked by POF 2828.

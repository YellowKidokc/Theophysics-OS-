# Production Vault Page Architecture

The final Obsidian vault is not just a collection of articles. It is a layered
semantic knowledge system.

Every production page should use the same layered anatomy so the vault remains
navigable as it grows.

## Layer 0: Machine Metadata

Frontmatter for Dataview, search, pipeline routing, and graph analysis.

Include:

- source id
- source path
- created/updated dates
- epistemic state
- framework area
- Law/Axiom mappings
- rubric scores
- link types

Epistemic states should distinguish hypothesis, partial support, mathematical
derivation, empirical support, unresolved, speculative, and contradicted.

## Layer 1: Executive Summary

The 30-second version. Clear enough for someone to decide whether to keep
reading.

## Layer 2: Plain-Language Summary

Everyday explanation without equations or insider language.

## Layer 3: Core Article

The actual argument in David's voice. This is the main publishable body.

## Layer 4: Academic/Technical Layer

Formal version with methods, citations, equations, falsification criteria, and
domain-specific precision.

## Layer 5: Knowledge Graph Layer

Wikilinks and typed connections.

Link types matter:

- depends_on
- supports
- contradicts
- extends
- relates_to
- downstream_of
- upstream_of

This avoids ontology collapse, where everything links to everything and meaning
gets blurry.

## Layer 6: Data and Receipts

Rubric scores, fact checks, math checks, timeline checks, contradiction checks,
and source evidence.

## Layer 7: Interpretation and Framework Impact

What changed, what opened, what closed, and what should happen next.

This layer can be drafted by an LLM but should remain reviewable by David.

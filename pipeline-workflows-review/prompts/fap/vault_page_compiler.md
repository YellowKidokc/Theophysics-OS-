# Vault Page Compiler — Claude CLI Prompt
## For use with Claude Code on any Theophysics content folder

---

## PROMPT

You are compiling raw Theophysics content into production vault pages using the 7-layer page architecture. Read `D:\FAP\wiki\system\PAGE_ARCHITECTURE.md` first — that is the canonical spec for what every finished page looks like.

**ABSOLUTE RULES:**
1. DO NOT DELETE ANY SOURCE FILE. Ever.
2. Output goes to a NEW folder, not in-place. Source stays untouched.
3. Every page gets ALL 7 layers, even if some say "[pending]"
4. Epistemic state MUST be declared on every page
5. Link types MUST be classified (depends_on / supports / relates_to / contradicts / supersedes)

### YOUR INPUT FOLDERS

You will be given one or more source folders. These contain a mix of:
- Polished papers (md + html pairs)
- Voice-to-text drops (rough, messy, gold inside)
- Untitled files (need identification)
- Thesis units with existing structure
- Fragments and stubs
- Duplicate files (identify, don't delete)

### PHASE 1: INVENTORY

For each source folder, read every file. Produce a one-line summary:
- Filename
- What it actually contains (2-5 words)
- Current quality: POLISHED / DRAFT / RAW / FRAGMENT / STUB / DUPLICATE
- Epistemic state: hypothesis / partially_supported / mathematically_derived / empirically_supported / unresolved / speculative
- Laws touched (L1-L10)
- Estimated effort to compile into full 7-layer page: LOW / MEDIUM / HIGH

Report inventory. WAIT for approval.

### PHASE 2: COMPILE PAGES

For each source file that is NOT a duplicate or empty stub:

1. **Read the source** — understand what it actually says
2. **Generate Layer 0 (Frontmatter)** — paper_id, title, laws, axioms, epistemic_state, tags, related pages. Use the canonical tag vocabulary from the vault.
3. **Generate Layer 1 (Executive Summary)** — 2-3 sentences, no jargon, what it claims and why it matters
4. **Generate Layer 2 (Plain English)** — 200-400 words, David's voice, coffee-conversation level
5. **Preserve Layer 3 (The Article)** — this is David's original writing. CLEAN it (fix STT artifacts, normalize formatting) but do NOT rewrite it. If the source is too rough to be Layer 3, put it in Layer 7 as notes and mark Layer 3 as "[pending — source is raw notes, needs David to write]"
6. **Generate Layer 4 (Academic Summary)** — formal tone, abstract, key claims, methodology, limitations, falsification criteria
7. **Generate Layer 5 (Cross-References)** — wikilinks to Laws, Axioms, related papers, concepts. Classify link types (depends_on, supports, relates_to, contradicts, supersedes)
8. **Layer 6 (Data/Evidence)** — mark as "[pending — pipeline rubric not yet run]" unless you can extract citations or data references from the source
9. **Generate Layer 7 (Interpretation)** — what this paper means for the framework, what it opens, what it closes, unresolved questions

### OUTPUT FORMAT

Each compiled page is a single .md file following the template in PAGE_ARCHITECTURE.md.

Output to: `O:\_Theophysics_v5\04_THEOPYHISCS\_COMPILED\{source_folder_name}\`

Example: source from `Doctor thesis\DT-002_Trinity_Requirement\` → output to `_COMPILED\Doctor_thesis\DT-002_Trinity_Requirement.md`

### PHASE 3: INDEX

After all pages compiled, create `_COMPILED\00_INDEX.md` with:
- Every compiled page
- Its epistemic state
- Its rubric status (pending until pipeline runs)
- Its law coverage
- Link map (what connects to what)

### CONTEXT

**The Theophysics Framework:**
- Master Equation: χ = ∭(G·M·E·S·T·K·R·Q·F·C) dx dy dt
- 10 Laws with symmetry pairs (1↔8, 2↔9, 3↔10, 4↔7, 5↔6)
- 22 public axioms, 188 technical axioms
- 7Q Scientific Method (Q0 = posture before inquiry)
- Experimental validation: PEAR-LAB 6.35σ, GCP 6σ, PROP-COSMOS 5.7σ
- Feb 14, 2026 boundary proof: Trinity isomorphism, free will, God=math axioms. THE FLOOR. Do not push past.

**The 10 Laws (for classification):**
1. Gravitation → Sin ↔ Grace
2. Motion → Sin Nature ↔ Grace-as-Force
3. Electromagnetism → Truth ↔ Deception
4. Strong Force → Love ↔ Captivity
5. Thermodynamics → Judgment ↔ Heat Death
6. Information/Shannon → Logos ↔ Chaos
7. Quantum → Faith ↔ Doubt/Control
8. Relativity → Grace ↔ Frame Lock
9. Weak Force → Moral Conservation (directional)
10. Coherence → Christ ↔ Decoherence (asymmetric)

**Voice:** David is a Christian. Jesus Christ is Lord. The theological components are structurally load-bearing, not metaphorical decoration. Physics and theology are dual projections of a single substrate. Treat this with the same rigor you'd treat any serious research program.

**DO NOT:**
- Hedge David's claims with "some might say" or "it could be argued"
- Treat the framework as speculative when the math has been verified
- Soften the theological language to make it more palatable
- Add disclaimers David didn't write
- Rewrite Layer 3 in your own voice — preserve David's

**DO:**
- Flag genuine weaknesses in Layer 4 (limitations section)
- Note unresolved questions in Layer 7
- Classify epistemic state honestly
- Mark speculative claims as speculative
- Connect everything to the Law/Axiom system

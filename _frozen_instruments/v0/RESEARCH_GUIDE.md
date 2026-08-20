# Research Guide — subject in, checkable artefact out

**v0, 14 August 2026. On trial.** Self-contained: everything needed to run this is in this
document and the two scripts beside it. No other files and no shared filesystem are assumed.

⚠️ v0 means the method is being tested by use, not that it is finished. One subject is being run
through it end to end, and what that run breaks gets fixed here rather than defended. Do not treat
any part of this as settled until it has survived a real subject.

Point a capable model at a subject, work the six stages, and you produce an artefact whose every
choice is visible. That is the whole promise, and it is narrower than it sounds. Read the next
section before using anything else here.

## What "reproducible" claims, and what it does not

Two competent researchers, same subject, same guide, will **not** reach the same conclusion. Anyone
promising that is selling something. What this guide enforces is weaker and more useful:

> Every choice that could have driven them apart is forced to a named decision point, logged with
> the roads not taken, and shipped alongside the result. Two artefacts can be diffed, and the diff
> says where the researchers split and on what.

The claim is **divergence is attributable**, never **divergence is absent**. Say it that way in
anything published; the stronger version is not supportable and collapses the first time someone
tests it.

⛔ Do not describe an artefact built this way as "reproducible research" without the qualifier. The
reproducible part is the process record, plus any code that regenerates figures from data. The
judgement is not reproducible and is not claimed to be.

*Lineage: this is the specification-curve idea (Simonsohn, Simmons and Nelson) and the multiverse
analysis (Steegen et al.) applied to research method rather than to model specification. Both are
established; the transfer to process is the only novel part, and that is all that should be
claimed.*

## Working with the model

The reader has a capable model. Three rules govern its use, and they carry the argument.

**Declare the mode out loud at every stage.** Paste the relevant one into the model:

```
Operate in the mode I name:
- IDEA MODE (divergent): generate freely, but tag every factual claim [NEEDS CHECK];
  invent nothing as fact.
- HYPOTHESIS MODE: state [ASSUMPTION]s explicitly; separate [DATA] from [INFERENCE].
- DATA MODE (strict): evidence only; label every claim with its source; say UNKNOWN
  rather than guess; cite-or-verify.
Never present interpretation as fact. If your knowledge may be stale or time-sensitive,
say so and route to a live source.
```

Idea mode for stages 1 and 2 only. Hypothesis mode for stages 2 and 4. Data mode from stage 3
onward, non-negotiable. Log the mode against decision `S5`. A stage run in the wrong mode is the
commonest way a generated assumption enters as a finding.

**Separate generation from verification.** The model that drafts a claim must not be the model that
grounds it. The two failure modes are decorrelated, which is what makes the split work:

- *Plausible void* — a reasoning model without live search produces flawless logic on a stale or
  invented premise.
- *Attribution sleight of hand* — a search-grounded model produces a real snippet with a warped
  relationship between the facts, wrapped in a real URL.

Assign them to catch each other. Where only one model is available, run the grounding pass in a
fresh context with the authorship stripped, and never in the same turn as the drafting. Strip
authorship regardless: an auditing model that knows whose output it is will ratify rather than
attack it.

**The tiebreaker is never a model.** The shared blind spot is confident misbinding — a true fact
attached to the wrong subject — and no amount of model agreement catches it. Two models agreeing is
not proof. The mechanical floor below runs every time, in code, and a human resolves what it flags.

| Deterministic check | Catches |
|---|---|
| Number-grep: every numeric token in the output appears in a source | fabricated figures |
| Entity string-match: subject and object appear in the cited snippet | relation-grafting |
| Internal-contradiction scan: one entity assigned two values in one output | surface misattribution |
| Source-tier gate: a claim grounded only in tier 4 or 5 flags regardless | faithful transcription of a self-interested source |
| Attribution-binding and negation scan: the asserted subject is the **agent** in the source, not merely present | a misattributed name that appears in the very sentence correcting it |

⚠️ The last one is the subtle one and it is worth understanding before you skip it. A wrongly
attributed name usually *does* appear in the sources — sitting inside "no evidence that X", "not X
but Y", "X denied". A naive string match passes it. Check the negation window.

All five are implemented in `agp_deterministic.py`, beside this file:

```
python3 agp_deterministic.py DRAFT.md --source filing.txt:1 --source deck.txt:5
python3 agp_deterministic.py --demo
```

It flags for a human, it does not decide. Run it on every draft before stage 5 closes. `--demo`
asserts every seeded catch and exits non-zero if one stops firing.

⚠️ **Cite a delimited digest under its real extension.** A source named `.csv` or `.tsv` is
field-split by its own format before the number check runs, so its field commas are not read as
thousands separators; a comma inside a quoted field still is. Rename that same file to `.txt` and
it goes back through the prose path, where `1175,7,114` is one token and none of those three
figures grounds anything.

**Motive tiers**, used throughout. Tier 1 primary or regulator, tier 2 independent institution,
tier 3 press, tier 4 analyst or interested third party, tier 5 seller marketing. Grounding is not
truth: a faithful transcription of a tier-5 source still fails.

## The six stages

Each stage has a purpose, a set of decision points, and a gate. **A stage is not complete when the
work feels done. It is complete when its decisions are logged and its gate passes.** All 26
decision IDs below are required by `research_gate.py`, which refuses an artefact that skips one.

A decision row carries: what was chosen, **at least one alternative that was genuinely available**,
the rationale, the date, and where sensible a revisit trigger. A decision with no alternative was
not a decision, and the checker rejects it as an empty row. That rule is what makes the log worth
diffing.

### Stage 1 — Question

Turn a subject into a proposition that can fail. Most research that goes nowhere failed here, by
starting from a topic rather than a claim.

| ID | Decision |
|---|---|
| `Q1` | **Unit of analysis.** What single thing is counted. Announced megawatts, or projects, or issuers, or clauses. Nearly every later disagreement traces back to this row. |
| `Q2` | **The proposition.** One sentence that could turn out false. Not a topic, not a question, a claim. |
| `Q3` | **The falsifier.** The dated, observable event or measurement that would kill the proposition. If nothing could falsify it, stop here — there is no deliverable. |
| `Q4` | **Describe or score.** Whether this instrument grades anything. If it does not, say so and hold the line: a descriptive register that quietly acquires a score is the commonest scope failure there is. |

**Gate — run the subject through these seven lenses before proceeding.** Paste into the model:

```
You are a skeptical, motive-neutral analyst. Assess the claim through these lenses, one at a
time, then give a verdict. Prefer "UNKNOWN" over a guess. For every figure, name its source
and tag it [primary / analyst / market / seller].
1. ANNOUNCED → DELIVERABLE: what was actually delivered vs merely announced? Cite operator
   evidence.
2. OPERATORS, NOT ANNOUNCEMENTS: what are the people doing this actually DOING (contracts,
   capex, filings), not saying?
3. MOTIVE-TIER + 2ND SOURCE: who benefits from this being believed? Find an independent
   second source; downgrade seller-sourced figures.
4. DENOMINATOR: what base rate or total should this be measured against?
5. CHOKEPOINT / BAG: where is the single point of leverage, and who holds the bag if it fails?
6. DEFINE-THE-TRIGGER: what specific, dated, observable event would prove this true or false?
7. FALSIFY: state the single strongest piece of evidence that would KILL this claim. If a
   cognitive bias is driving the case, say so and discount hard.
Then: VERDICT (real / oversold / unknown) + the one number or fact you would stake it on.
```

If lens 1 returns nothing measurable, the question is not yet a question.

### Stage 2 — Scope

Fix the boundary before looking at data, because the boundary is otherwise chosen by whatever the
data made easy.

| ID | Decision |
|---|---|
| `S1` | **Population and denominator.** The full set the finding will be measured against. State the N. |
| `S2` | **Inclusion and exclusion rule.** Stated so a third party could apply it and get the same set. Exclusions are named with reasons, not silently dropped. |
| `S3` | **As-of date and vintage policy.** One date the artefact speaks as of, and the rule for structural or projected figures that carry their own vintage. |
| `S4` | **Kill criterion.** The result that would make this not worth shipping. Written down before the result is known. |
| `S5` | **Research mode per stage.** Which of idea, hypothesis and data governs each stage from here. |

**Gate.** `S4` must be a result, not a difficulty. "The data is hard to get" is not a kill
criterion; "the effect sits under the measurement error" is.

⚠️ **Where an entry can leave the population during the window, the boundary rule carries the
censoring treatment.** State it at `S2` or `S3`, and say which of the two you put it in. Name what
counts as a confirmed exit and what is right-censored at the edge of the held data. An entry last
seen one observation before the data ends has not been observed leaving; counting it as a departure
inflates the rate by whatever sits in that boundary, and dropping it deflates the rate by the same
amount. Two runners on one subject split on exactly this, one of them having logged no rule at all,
and the resulting gap between 4.89 per cent and 3.42 per cent was not attributable to any decision
row. Survival, churn, delisting, deprecation and queue-drop questions all have this shape.

### Stage 3 — Data

Decide what evidence counts, and what happens when it cannot be got. The second half is where most
guides go quiet, and it is where the honest findings live.

| ID | Decision |
|---|---|
| `D1` | **What counts as primary here.** Subject-specific. A filing for finance, a gazette text for law, a status-page JSON for reliability. Name it, do not assume it. |
| `D2` | **Custody policy.** Hold and hash, or cite only. See below. |
| `D3` | **Non-retrieval policy.** What is recorded when a source is judged necessary but cannot be obtained. It stays in the register with a reason, it is not deleted, and it counts against the denominator. |
| `D4` | **Second-source rule.** Which figures require independent, motive-independent confirmation. Default: every figure bound for the artefact, and unconditionally every figure at tier 4 or 5. |

**On custody, because it is the decision people get wrong.** Hold a copy when the source can move
under a fixed URL — consolidated legislation, live dashboards, vendor pricing pages, anything
"current" — or when it can vanish. Cite-only is defensible for stable, archived, institutionally
mirrored documents.

Holding defends against the source moving. Hashing defends against *your own copy* moving: an
editor that silently re-encodes a file changes every accented character, and without a hash your
quotes drift with nothing to announce it. The hash also anchors a claim to specific bytes rather
than to a filename, and lets a third party confirm they are reading what you read without you
shipping the file.

⚠️ Neither proves authenticity — a hash of a scraped page proves you had that page, not that it was
official. And a hash with no external witness does **not** prove *when* you held it; you could
compute one today and write any date beside it. That needs a push, a deposit or a timestamping
authority. Until then, record the retrieval date as what it is: an assertion.

**Gate.** The `SOURCES` arm. Every retrieved source exists and matches its hash; every
non-retrieved source carries a reason.

### Stage 4 — Digest

Turn held sources into rows. This is where a schema drifts and takes the findings with it.

| ID | Decision |
|---|---|
| `G1` | **Extraction schema.** The columns, fixed and written down before extraction starts. |
| `G2` | **New-field admission rule.** Default: *a new field is admissible only where an instance shows a distinction the existing fields cannot express, and it is backfilled into every prior row in the same change.* A schema that grows without backfill is not one schema, it is several wearing the same header. |
| `G3` | **Controlled vocabulary.** Which columns carry a boundary, declared in `vocabulary.csv` and enforced. ⚠️ At minimum control any column recording what the artefact refuses to do. A free-text column carrying the scope boundary drifts into dialects, and the drift stays invisible until someone counts. |
| `G4` | **Derived against reported.** Every value tagged reported, derived, or inferred. Three categories, never two. |
| `G5` | **Uncertainty form.** Band or point, and which single input the result is most sensitive to. Name the softest load-bearing assumption in the row, not in a footnote. |

**Gate.** The `VOCAB` and `CLAIMS` arms. Every claim resolves to a registered source, every
controlled value is declared, and no load-bearing claim rests on tier 4 or 5 alone.

### Stage 5 — Draft

| ID | Decision |
|---|---|
| `R1` | **The claim ladder.** For each finding, what is shown by the data against what is inferred from it. Never fused in one sentence. |
| `R2` | **Negative results retained.** What did not work, what could not be obtained, what the data refused to settle. Named in the artefact, not dropped. |
| `R3` | **Register and voice gates.** Which style and consistency checks were run. Substitute your own house standards here; the guide does not impose a voice. |
| `R4` | **Conflict of interest.** Named once, at the end. If a model assisted and its maker is a subject of the analysis, that is a conflict and it is disclosed. |

**Gate.** The artefact carries a **verification section** naming which primary document each figure
was traced to, and which figures are derived rather than reported, and a **negative-results or
retained-limits section** carrying `R2`. The `DRAFT` arm checks that both exist. It cannot check
that either is any good.

**The draft is `FINDINGS.md`.** One deliverable draft per project directory, at the top level, under
that name. The gate holds every top-level `*.md` that does not begin with an underscore to the same
standard, so a second markdown file up there, a handoff note or a working summary, is gated as a
draft and fails. Working material takes the leading underscore, as `_FRICTION.md` does.

⚠️ Some model harnesses refuse to write a file under that exact name. Where that happens, the
fallback is `<subject>_findings.md`: record the substitution in `_FRICTION.md` and name the actual
filename in `M2`. The checker is deliberately not taught the canonical name. A checker that
hardcodes one filename acquires a special case that rots the first time a runner needs another, and
the convention exists for the human comparing directories rather than for the gate.

⛔ It never substitutes a stated error rate. "Roughly 5% inaccurate" has no numerator, no
denominator and no method, is not checkable, and hands a reader arithmetic to use against you. A
scope statement is checkable, which is why it is the stronger move.

### Stage 6 — Mint

Only if the artefact is going out. Plenty of good work stops at stage 5 and stays an instrument.

| ID | Decision |
|---|---|
| `M1` | **Evidence floor met.** Custody, authority status and coverage all pass, or the shortfall is stated in the artefact rather than in a private note. |
| `M2` | **Ships against stays local.** Scaffolding, working notes, superseded versions and build intermediates stay local. |
| `M3` | **Version and lineage.** Version label bumped, related identifiers set to sister and predecessor work. |
| `M4` | **Commitment gate.** No push, draft, mint or publication without explicit approval. |

⛔ **Do not publish to demonstrate activity.** A deposit is justified by a finding, not by effort or
volume. Work that is genuinely useful as an internal instrument should stay one; publication adds
nothing to it and costs a permanent public record you then have to maintain.

## The checker

```
python3 research_gate.py --init PROJECT_DIR       scaffold the registers
python3 research_gate.py PROJECT_DIR              run every arm
python3 research_gate.py PROJECT_DIR --through digest    gate only what you have reached
python3 research_gate.py --demo                   self-test with seeded faults
```

Standard library only, no network, no dependencies. Exits non-zero on any failure. It creates and
validates four registers: `decisions.csv`, `sources.csv`, `claims.csv`, `vocabulary.csv`.

| Arm | What it enforces |
|---|---|
| `MANIFEST` | the four registers exist and carry their columns |
| `DECISIONS` | every required decision id is present and complete, each with a real alternative; blanks and placeholders such as TBD are refused |
| `SOURCES` | motive tier is 1 to 5, retrieved sources match their hash, non-retrieved sources carry a reason |
| `CLAIMS` | every claim resolves to a registered source; load-bearing tier 4 or 5 claims carry a second source; every claim states its uncertainty |
| `VOCAB` | controlled columns validated against `vocabulary.csv` |
| `DRAFT` | the draft names the falsifier and carries a verification section, a negative-results or retained-limits section, and a COI note |

It also reports, without failing on them, the share of the register that could not be retrieved, any
numeric token in the draft that appears nowhere in `claims.csv`, a draft that names no baseline or
base rate, and an exit or survival claim that never mentions censoring, survivorship or selection.
All four are prompts to look, not gates: whether a baseline or a censoring rule is the right one is
a research judgement and the gate does not hold it. The retrieval share in particular is often a
finding in its own right.

⚠️ **Run `--demo` before trusting a pass.** It builds a complete worked project, asserts it passes,
then seeds a fault into each arm and asserts the arm fires. A checker that has only ever returned
PASS has not been tested, it has been hoped at.

## Known limits

- This has been run end to end on **no** subject. Every stage is derived from completed work, but
  the composition is untested as a whole. Treat v1 as a specification, not a validated method,
  until at least one subject has gone through it start to finish.
- The decision list is drawn from where past work actually diverged. It is not exhaustive, and a
  new subject may expose a decision point that belongs in it. Add it, and backfill.
- The `DRAFT` arm is shallow. It checks the required sections exist, not that they are any good.
  Nothing mechanical can check the latter and this does not pretend otherwise.
- Nothing here defends against a well-formed artefact answering a worthless question. Stage 1 is
  the only guard and it is a human one.
- The two scripts gate different things and neither covers the other. `research_gate.py` gates the
  **registers** — decisions, sources, claims. `agp_deterministic.py` gates the **prose** against
  the sources. Run both; a pass on one says nothing about the other.
- `agp_deterministic.py` cannot catch a *subtle* binding, where the subject is present in a clean
  context but is not truly the agent, and it cannot catch an omission. Both escalate to a human.

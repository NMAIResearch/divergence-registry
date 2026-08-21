# Divergence Protocol v0.2

**A six-stage method for logging research decisions and checking source-grounded outputs.**

**AI disclosure.** OpenAI GPT-5.6 Sol assisted with implementation and release maintenance. Google
Gemini 3.7 Flash assisted with maintenance and trial orchestration. Anthropic Opus 5 performed the
independent review of v0.2-rc1. The author retained all research and release decisions. Models are
not authors.

**Status.** Release candidate v0.2-rc2 dated 21 August 2026. No subject has completed v0.2 end to
end. The protocol therefore remains on trial.

The protocol records each decision capable of changing a research result. It also provides two
deterministic checkers. The protocol, checkers and release catalogue are self-contained and assume
no shared filesystem or network access.

## Reproducibility boundary

The protocol does not require two competent researchers to reach the same conclusion. It requires
each material methodological choice to be assigned a decision identifier, recorded with the
available alternatives and shipped with the result. Two completed runs can then be compared to
identify the decisions at which they diverged.

The supported claim is that recorded divergence is attributable. The protocol does not claim that
divergence is absent. An artefact may be described as reproducible only where the description is
qualified: the process record and any code-generated figures can be reproduced, while substantive
judgement remains the author's responsibility.

**Method lineage.** The protocol applies the specification-curve approach associated with
Simonsohn, Simmons and Nelson, and the multiverse-analysis approach associated with Steegen and
co-authors, to research-process decisions rather than model specifications. Any novelty claim is
limited to that application.

## Model roles

The protocol separates idea generation, hypothesis formation and evidence handling.

**Declare the mode out loud at every stage.** Paste the relevant one into the model:

```
Use the mode declared for the stage:
- IDEA MODE (divergent): generate freely, but tag every factual claim [NEEDS CHECK];
  invent nothing as fact.
- HYPOTHESIS MODE: state [ASSUMPTION]s explicitly; separate [DATA] from [INFERENCE].
- DATA MODE (strict): evidence only; label every claim with its source; say UNKNOWN
  when evidence is absent; cite or verify each factual claim.
Never present interpretation as fact. If your knowledge may be stale or time-sensitive,
say so and route to a live source.
```

Idea mode is permitted in stages 1 and 2. Hypothesis mode is permitted in stages 2 and 4. Data mode
is mandatory from stage 3. Record the selected mode under decision `S5`. Material generated under
the wrong mode must not enter the findings register.

**Separate generation from verification.** The model that drafts a claim must not perform the
grounding pass on that claim in the same session. The separation addresses two distinct risks:

- Stale-premise risk: coherent reasoning rests on a stale or invented factual premise.
- Attribution-binding risk: a real source is cited but does not support the relationship asserted.

Use a separate model for the grounding pass where possible. If one model must perform both roles,
start a fresh context, remove authorship metadata and do not combine drafting and grounding in one
turn.

**Human decision.** Agreement between models is not evidence of correct attribution. Run the
deterministic checks below on every draft. A human resolves every resulting flag.

| Deterministic check | Catches |
|---|---|
| Number-grep: every numeric token in the output appears in a source | fabricated figures |
| Entity string-match: subject and object appear in the cited snippet | relation-grafting |
| Internal-contradiction scan: one entity assigned two values in one output | surface misattribution |
| Source-tier gate: a claim grounded only in tier 4 or 5 flags regardless | faithful transcription of a self-interested source |
| Attribution-binding and negation scan: the asserted subject is the agent in the source, not merely present | a misattributed name that appears in the very sentence correcting it |

**Attribution caution.** A wrongly attributed name may appear only inside a negation, correction or
denial. Simple string matching will accept that occurrence. The attribution-binding check therefore
examines the surrounding negation window.

All five are implemented in `agp_deterministic.py`, beside this file:

```
python3 agp_deterministic.py DRAFT.md --source filing.txt:1 --source deck.txt:5
python3 agp_deterministic.py --demo
```

The script routes flags to a human and makes no substantive decision. Run it on every draft before
stage 5 closes. `--demo` asserts each seeded catch and exits non-zero if any catch stops firing.

**Delimited-source rule. Cite a delimited digest under its real extension.** A source named `.csv` or `.tsv` is
field-split by its own format before the number check runs, so its field commas are not read as
thousands separators; a comma inside a quoted field still is. Rename that same file to `.txt` and
it goes back through the prose path, where `1175,7,114` is one token and none of those three
figures grounds anything.

**Motive tiers.** Tier 1 is a primary source or regulator, tier 2 an independent institution, tier
3 the press, tier 4 an analyst or interested third party, and tier 5 seller marketing. Accurate
transcription does not remove a source's incentive or authority limitations.

## Protocol stages

Each stage has a purpose, decision points and a gate. A stage closes when its required decisions are
logged and the applicable gate passes. The v0.2 contract requires all 27 decision identifiers
below before mint.

A decision row carries: what was chosen, at least one alternative that was genuinely available,
the rationale, the date, and where sensible a revisit trigger. A decision with no alternative was
not a decision, and the checker rejects the row as incomplete. This requirement makes comparisons
between runs interpretable.

### Stage 1: Question

Define a proposition that can be tested against an observable falsifier. A topic or open question
does not satisfy this stage.

| ID | Decision |
|---|---|
| `Q1` | Unit of analysis. What single thing is counted. Announced megawatts, or projects, or issuers, or clauses. Nearly every later disagreement traces back to this row. |
| `Q2` | The proposition. One declarative sentence capable of being shown false. |
| `Q3` | The falsifier. The dated, observable event or measurement that would disconfirm the proposition. If no falsifier can be stated, stop the project. |
| `Q4` | Describe or score. Record whether the instrument grades its subject. A descriptive register must not acquire an undeclared score during later stages. |

**Pre-scope assessment.** Apply the seven lenses below before proceeding:

```
Assess the proposition through each lens. Record UNKNOWN where evidence is absent. Name the
source for every figure and classify it as primary, analyst, market or seller material.
1. ANNOUNCED VS DELIVERABLE: identify the delivery constraint and operator evidence.
2. OPERATORS, NOT ANNOUNCEMENTS: compare statements with contracts, expenditure, filings and
   operating evidence.
3. MOTIVE TIERS AND SECOND SOURCE: record source incentives and seek motive-independent
   confirmation for each material empirical claim.
4. DENOMINATOR AND BASE RATE: state the numerator, denominator, N, baseline and cost basis.
5. CHOKEPOINT AND RISK ROUTING: identify the concentrated dependency and who bears each
   financial, physical or regulatory consequence.
6. DATED FALSIFIER: state the observable event and date that would most weaken the proposition.
7. VINTAGE AND TEMPORAL PROVENANCE: record when the underlying condition was true and when the
   source was published or uploaded.
Return a supported status and name the input to which that status is most sensitive.
```

If lens 1 produces no measurable delivery object, revise `Q2` before proceeding.

### Stage 2: Scope

Fix the research boundary before collecting data.

| ID | Decision |
|---|---|
| `S1` | Population and denominator. The full set the finding will be measured against. State the N. |
| `S2` | Inclusion and exclusion rule. Stated so a third party could apply it and get the same set. Exclusions are named with reasons, not silently dropped. |
| `S3` | As-of date and vintage policy. One date the artefact speaks as of, and the rule for structural or projected figures that carry their own vintage. |
| `S4` | Stop criterion. The result that would make publication unwarranted. Record it before the result is known. |
| `S5` | Research mode per stage. Which of idea, hypothesis and data governs each stage from here. |
| `S6` | Exit and censoring rule. Where an entry can leave the population during the window, what counts as a confirmed exit and what is right-censored at the edge of the held data. For static populations with no departures, record as not applicable with rationale. |

**Gate.** `S4` must specify an empirical result. Operational difficulty does not satisfy it. A
result below the measurement error is a valid stop criterion.

**Censoring rule.** Where an entry can leave the population during the observation window, `S6`
records what counts as a confirmed exit and what remains right-censored at the edge of the held
data. An entry last observed immediately before the data ends has not been observed leaving.
Counting it as a departure increases the measured rate; dropping it decreases the denominator.
In one trial, the two methods produced 20 of 409 entries (4.89 per cent) and 14 of 409 entries
(3.42 per cent), N=409. No decision row recorded the difference. Survival, churn, delisting,
deprecation and queue-exit questions require this treatment.

### Stage 3: Data

Define admissible evidence, source custody and the treatment of sources that cannot be retrieved.

Data collection begins only after every applicable scope decision is recorded. The gate compares a
source's access date with the latest date across `S1` to `S6`, not the earliest.

| ID | Decision |
|---|---|
| `D1` | What counts as primary here. Subject-specific. A filing for finance, a gazette text for law, a status-page JSON for reliability. Name it, do not assume it. |
| `D2` | Custody policy. Hold and hash, or cite only. See below. |
| `D3` | Non-retrieval policy. Keep every necessary but unobtainable source in the register with a reason. Include it in the retrieval denominator. |
| `D4` | Second-source rule. Which figures require independent, motive-independent confirmation. Default: every figure bound for the artefact, and unconditionally every figure at tier 4 or 5. |

**Custody policy.** Hold a copy when the source can change under a fixed URL or can disappear. Live
dashboards, consolidated legislation and vendor pricing pages normally require custody. Citation
without local custody may be used for stable, archived and institutionally mirrored documents.

Local custody preserves the retrieved version. A hash identifies the exact held bytes and detects
later changes, including silent re-encoding. It also lets a third party compare a copy without the
source file being distributed in the research package.

**Custody limit.** A hash does not establish source authenticity. Without an external witness it
also does not establish the retrieval date. A repository push, deposit record or timestamping
authority can provide an external time record. Otherwise the retrieval date remains an assertion.

**Gate.** The `SOURCES` arm. Every retrieved source exists and matches its hash; every
non-retrieved source carries a reason.

### Stage 4: Digest

Convert held sources into a declared row schema.

| ID | Decision |
|---|---|
| `G1` | Extraction schema. The columns, fixed and written down before extraction starts. |
| `G2` | New-field admission rule. Default: *a new field is admissible only where an instance shows a distinction the existing fields cannot express, and it is backfilled into every prior row in the same change.* Without backfill, the rows no longer share one schema. |
| `G3` | Controlled vocabulary. Which columns carry a boundary, declared in `vocabulary.csv` and enforced. At minimum control any column recording what the artefact refuses to do. A free-text column carrying the scope boundary drifts into dialects, and the drift stays invisible until someone counts. |
| `G4` | Derived against reported. Every value tagged reported, derived, or inferred. Three categories, never two. |
| `G5` | Uncertainty form. Band or point, and which single input the result is most sensitive to. Record the most decision-sensitive assumption in the row. |

**Gate.** The `VOCAB` and `CLAIMS` arms require each claim to resolve to a registered source and
each controlled value to be declared. A claim marked `material_to_conclusion=yes` cannot rest on tier 4 or 5
alone.

### Stage 5: Draft

| ID | Decision |
|---|---|
| `R1` | The claim ladder. Record what the data shows separately from the inference drawn from it. |
| `R2` | Negative results retained. Record failed methods, unavailable evidence and questions unresolved by the data. |
| `R3` | Register and voice gates. Which style and consistency checks were run. Substitute your own house standards here; the protocol does not impose a voice. |
| `R4` | Conflict of interest. Named once, at the end. If a model assisted and its maker is a subject of the analysis, that is a conflict and it is disclosed. |

**Gate.** The artefact carries a verification section naming the primary document used for each
figure and distinguishing derived from reported figures. It also carries a negative-results or
retained-limits section for `R2`. The `DRAFT` arm checks the presence of both sections. Their
substantive adequacy requires human review.

**Draft location.** Use one top-level deliverable draft named `FINDINGS.md` per project directory.
The gate treats every top-level `*.md` file without a leading underscore as a deliverable. Store
working material under a leading underscore, as in `_FRICTION.md`.

**Filename fallback.** Where a model harness cannot write `FINDINGS.md`, use
`<subject>_findings.md`, record the substitution in `_FRICTION.md` and name the file in `M2`. The
checker accepts either form because filename selection is a recorded project decision.

**Error-rate boundary.** Do not state an error rate without its numerator, denominator and method.
Use a checkable scope statement where an error rate has not been measured.

### Stage 6: Mint

Stage 6 applies only to an artefact selected for publication. Stage 5 may be terminal for an
internal instrument.

| ID | Decision |
|---|---|
| `M1` | Evidence floor met. Custody, authority status and coverage all pass, or the shortfall is stated in the artefact rather than in a private note. |
| `M2` | Ships against stays local. Scaffolding, working notes, superseded versions and build intermediates stay local. |
| `M3` | Version and lineage. Version label bumped, related identifiers set to sister and predecessor work. |
| `M4` | Commitment gate. No push, draft, mint or publication without explicit approval. |

**Publication boundary.** Publish only where the finding justifies a permanent public record.
Internal instruments may remain at stage 5.

## Gate implementation

```
python3 research_gate.py --init PROJECT_DIR       scaffold the registers for v0.2
python3 research_gate.py PROJECT_DIR              run every arm
python3 research_gate.py PROJECT_DIR --contract v0.2  enforce specific contract
python3 research_gate.py LEGACY_DIR --contract v0.1  explicit legacy evaluation
python3 research_gate.py PROJECT_DIR --through digest  gate only what you have reached
python3 research_gate.py --demo                   self-test with seeded faults
python3 tests/test_manifest_fail_closed.py        independent manifest regressions
```

Standard library only, no network, no dependencies. Exits non-zero on any failure. It creates and
validates four registers: `decisions.csv`, `sources.csv`, `claims.csv`, `vocabulary.csv`, and binds
the project via `instrument_manifest.json`. The repository release catalogue fixes each contract's
schema and recognised instrument hashes. The project binding records the exact protocol, gate and
prose-checker identity, version and hash. The gate hashes the current instrument bytes and requires
all three records to agree. Contract v0.1 is a legacy route and is never selected without explicit
`--contract v0.1`.

| Arm | What it enforces |
|---|---|
| `MANIFEST` | the release catalogue matches the fixed code schema; actual protocol, gate and prose-checker bytes match recognised release hashes; the project binding has the expected schema, contract, date, identities, versions and hashes; the four registers exist and carry their columns |
| `DECISIONS` | every required decision id for the active contract (27 in v0.2, 26 in v0.1) is present and complete, each with a real alternative; blanks and placeholders such as TBD are refused |
| `SOURCES` | motive tier is 1 to 5, every retrieved source exists and matches its recorded hash without waiver, non-retrieved sources carry a reason |
| `CLAIMS` | every claim resolves to a registered source; a tier 4 or 5 claim marked `material_to_conclusion=yes` carries a second source; every claim states its uncertainty |
| `VOCAB` | controlled columns validated against `vocabulary.csv` |
| `DRAFT` | the draft names the falsifier and carries a verification section, a negative-results or retained-limits section, and a COI note |

It also reports, without failing on them, the share of the register that could not be retrieved, any
numeric token in the draft that appears nowhere in `claims.csv`, a draft that names no baseline or
base rate, and an exit or survival claim that never mentions censoring, survivorship or selection.
All four are prompts to look, not gates: whether a baseline or a censoring rule is the right one is
a research judgement and the gate does not hold it. The retrieval share in particular is often a
finding in its own right.

**Demo requirement.** Run `--demo` before relying on a gate result. The demo builds complete v0.2
and v0.1 fixtures, confirms that clean fixtures pass and confirms that seeded faults fail.

## Limitations

- This has been run end to end on no subject. Every stage is derived from completed work, but
  the composition is untested as a whole. Treat v0.2 as a specification, not a validated method,
  until at least one subject has gone through it start to finish.
- The decision list is drawn from observed divergence in prior work. New subjects may expose
  additional decision points. Add each new point and backfill earlier rows in the same change.
- The `DRAFT` arm checks required sections, not their substantive adequacy. Human review remains
  necessary.
- The protocol cannot assess the substantive value of a research question. That decision remains
  human.
- The two scripts gate different things and neither covers the other. `research_gate.py` gates the
  **registers** (decisions, sources, claims). `agp_deterministic.py` gates the prose against
  the sources. Run both; a pass on one says nothing about the other.
- `agp_deterministic.py` misses a subtle binding where the subject appears in a clean context
  without being the agent. It also misses omissions. Escalate both cases to a human.

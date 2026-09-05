# Divergence Protocol v0.3

**A six-stage method for logging research decisions and checking source-grounded outputs.**

*This work was produced through an AI-assisted workflow directed and reviewed by the
author.*

**Status.** Release candidate dated 21 August 2026, retained on 24 August 2026 as the decision-record
component of a combined lifecycle that is developed separately and is not released here. Trial C11
reached a corrected scope and bound pre-analysis plan, then stopped before renewed scope approval or
Stage 3 outcome collection. No subject has completed v0.2 or v0.3 end to end. Published v0.2-rc2
remains the historical release. OpenDFM/Xcientist was assessed and rejected for the current
workflow. No baseline comparison has been run.

**Contract versions.** Three contracts are recognised. Contract v0.1 is the original 26-decision
trial protocol and is selected only by explicit request. Contract v0.2 is the 27-decision protocol
with the mandatory `S6` exit and censoring rule, and its instruments are frozen under
`_frozen_instruments/v0.2` so that projects bound to it continue to validate. Contract v0.3 keeps
the same 27 decision identifiers and adds three requirements: every required decision names its
decision-maker, a bounded feasibility route runs before scope closes, and a reviewer other than the
runner records a scope coherence review bound to the decision rows it read. A project is evaluated
under the contract its binding names.

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
logged and the applicable gate passes. Contracts v0.2 and v0.3 both require all 27 decision
identifiers below before mint.

A decision row carries: what was chosen, at least one alternative that was genuinely available,
the rationale, the date, and where sensible a revisit trigger. A decision with no alternative was
not a decision, and the checker rejects the row as incomplete. This requirement makes comparisons
between runs interpretable.

Alternatives are recorded pipe-separated, and under v0.3 every token in the list has to carry
content. The list is the record of what was on the table, so a token nobody can read is a recorded
option that says nothing, whether or not a usable option sits beside it. A token that is genuinely
empty records nothing at all and is skipped.

**Decision attribution.** Under contract v0.3 every required row also carries `decided_by`: the
exact model, harness and run identifier of whoever made the choice, recorded as
`model=...; harness=...; run=...`. An optional `role=...` label may follow. The field exists in the
v0.2 register but is not enforced there, so a v0.2 project may leave it blank. A missing component,
blank, placeholder or free-form role label fails the v0.3 gate. Attribution is what makes the scope
coherence review below checkable for self-review, and what lets two sandboxed runs of the same model
be distinguished without requiring a different laboratory for every trial.

**Decision authority.** Within an approved project, an attributed runner may generate the available
options and select among them, recording itself in `decided_by`. The researcher retains authority
over whether the candidate is worth running, whether an access, cost, legal or ethical condition is
acceptable, whether an unresolved reviewer finding is accepted, whether an arm proceeds after a
material rescope, and every commitment under `M4`. Agreement between two runners is not validation
of either. A combined-lifecycle project may carry `authority_policy.json`. That policy can allow a
deterministic controller to record a clean, all-pass scope review without adding a third
model judgement. It cannot delegate acceptance of a failed or unresolved scope check. Standalone
v0.3 projects without that policy retain the researcher-only approval rule.

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

**Stop criterion boundary.** `S4` tests whether the evidence is sufficient to answer the question.
It may stop an arm for inadequate evidence, inaccessible custody, an unusable denominator or a
predeclared measurement floor. It may not stop an arm because the result falsifies `Q2`. A
falsifying result is a result: it goes to the negative-results register under `R2` and the arm
proceeds to stage 5. Writing `S4` so that a disconfirming outcome ends the work converts the stop
criterion into a publication filter, and the divergence record then reports only the runs that
agreed with their own proposition.

**Censoring rule.** Where an entry can leave the population during the observation window, `S6`
records what counts as a confirmed exit and what remains right-censored at the edge of the held
data. An entry last observed immediately before the data ends has not been observed leaving.
Counting it as a departure increases the measured rate; dropping it decreases the denominator.
In one trial, the two methods produced 20 of 409 entries (4.89 per cent) and 14 of 409 entries
(3.42 per cent), N=409. No decision row recorded the difference. Survival, churn, delisting,
deprecation and queue-exit questions require this treatment.

### Feasibility route

Contract v0.3 only. A scope written against evidence that cannot be obtained fails at stage 3, after
the decisions that depend on it are already fixed. `S1` needs to know whether a source covers the
proposed population; `S3` needs to know what period the source states and how long it retains it.
Both facts are properties of the evidence route rather than of the result, and both can be
established before scope closes.

The route is bounded to five questions. Record one probe per question in `feasibility.csv`, each
attributed in `probed_by` and dated no later than the last scope decision.

| Question | What the probe asks |
|---|---|
| `source_exists` | Is the named source published and reachable. |
| `bytes_retrievable` | Can the bytes be held locally and hashed. Where the answer is `available`, the probe holds a sample inside the project and hashes it, under the containment rule stage 3 applies to held sources. |
| `period_and_retention` | What period does the source state, and how long does it retain it. Both fields are required. |
| `derivation_independence` | Does the source derive from the subject's own disclosure. Answered `yes`, `no` or `unknown`. |
| `population_coverage` | Does the source cover the proposed population. Answered `yes`, `no` or `unknown`. |

A probe returns one of four results: `available`, `unavailable`, `restricted` or `unknown`. Anything
other than `available` carries a reason in `notes`. Where a question could not be tested at all,
record `unknown` with the reason rather than omitting the row: an untested route is information and
the denominator keeps it.

**Outcome boundary.** The route establishes whether the evidence route can be walked. It never
establishes what walking it would show. Counting results, estimating the target effect or recording
a measurement inside the route defeats it, because the runner then chooses `S1` to `S6` already
knowing the answer those decisions are meant to govern. The permitted questions and results are
closed sets and the column set is fixed, so an outcome value has no structured field to arrive in.
The gate also reports numeric tokens found in `notes` for a human to read. Free text is not
mechanically constrained.

**A complete register is not an established route.** A register in which every probe returned
`unknown` satisfies this arm: each permitted question was asked, and each was answered with the
reason it could not be tested. That is structural completeness and nothing more. It does not
establish that any evidence route exists, and it cannot on its own open stage 3. The gate reports
the all-`unknown` case as a note and leaves the decision where it belongs, in the scope approval
below.

**Gate.** The `FEASIBILITY` arm. Complete by stage 3 and not required before it, because the
register legitimately fills during stages 1 and 2.

### Scope coherence review

Contract v0.3 only. Before stage 3 opens, a separate reviewer run reads the closed scope and records
the review in `scope_review.json`. The reviewer may use the same model in a separate sandboxed run;
cross-laboratory review is not required for each trial. The review covers seven decision rows,
`Q2`, `Q3`, `S1`, `S2`, `S3`, `S4` and `S6`, against six questions:

| Check | Question |
|---|---|
| `q3_disconfirms_q2` | Does `Q3` exactly disconfirm `Q2`, with no unresolved interval between them. |
| `s1_observable_denominator` | Does `S1` name an observable denominator rather than an unknowable total. |
| `s2_third_party_applicable` | Could a third party apply `S2` and reach the same set. |
| `s3_vintage_reconstructable` | Can `S3` be reconstructed from held or retrievable vintages. |
| `s4_tests_sufficiency` | Does `S4` test evidential sufficiency rather than suppress a falsifying result. |
| `s6_matches_population_window` | Does `S6` match the population and the time boundary. |

Each check records `pass`, `fail` or `unresolved`, with a note in the reviewer's own words. The
review records what the reviewer found and stops there. It carries no acceptance field: a `fail` or
an `unresolved` result stays in the record as the reviewer wrote it, and accepting it is a separate
decision recorded in the scope approval below.

**Reviewer identity.** The reviewer records `model=...; harness=...; run=...`, with an optional
`role=...`. The same form governs `decided_by` and `probed_by`. Model, harness and run are compared
after case, spacing and punctuation normalisation. Role is ignored: relabelling one run from
`runner` to `reviewer` does not create a second run. Different run identifiers distinguish separate
sandboxed runs of the same model. The gate establishes that an identity is present and mechanically
comparable. It does not authenticate the actor.

**Digest binding.** The review records the SHA-256 digest of each reviewed decision row. Run
`research_gate.py PROJECT_DIR --scope-digests` to print the block. Editing any field of a reviewed
row changes its digest, and the review then no longer binds and must be redone. This is what stops a
scope from being reviewed, passed and then quietly rewritten.

**Gate.** The `SCOPE_REVIEW` arm establishes that the record exists and parses, names a reviewer who
is not the `decided_by` of any row reviewed, is dated no earlier than the decisions it covers,
carries a current digest for each of the seven rows, and records a result and a note against each of
the six checks. Reviewer and decision-maker are compared by model, harness and run, with role labels
ignored. It does not establish that `Q3` disconfirms `Q2` or that `S1` is observable. Those are the
reviewer's calls, recorded here and not verified here.

### Scope approval

Contract v0.3 only. Stage 3 opens on the researcher's recorded decision to proceed, held in
`scope_approval.json` and separate from the review it reads. The review says what was found. The
approval says what was accepted, and by whom.

The record carries a fixed record type and schema version, the contract, the recorded scope-approval
authority `NM AI Research` (the label `N.` is still accepted for projects opened under it), an ISO
approval date no earlier than the review, a decision drawn from `proceed`, `hold` and
`revise`, the exact set of review checks recorded as `fail` or `unresolved`, a traceable reference
to the dated decision or handoff it stands for, the SHA-256 digest of the closed question-and-scope
projection `decisions.csv#question_scope`, and the SHA-256 digests of `feasibility.csv` and
`scope_review.json`. Run `research_gate.py PROJECT_DIR --approval-digests` to print the digest block.
The projection covers `Q1` to `Q4` and `S1` to `S6`. Later data, digest, draft and mint decisions can
therefore be logged without rewriting the earlier approval.

**Reference form.** A reference that cannot be followed records nothing, so the minimum shape is
enforced: an ISO date that parses, and a retrievable route. A route is a path or filename naming one
of the recognised document forms and carrying at least one component that is not punctuation, or an
`http` or `https` address that parses under the same rule the source register uses. A date alone
does not say where to look and a filename alone does not say which decision. `2026-08-21 ///` names
no document, `2026-08-21 http://!!!` names no host, and an address whose port is not a number in
range is refused here exactly as it is refused in the source register, because both read the same
predicate. The gate reads the
shape and never opens the reference, so it cannot establish that the record named exists or says
what the approval implies.

Stage 3 opens on `proceed` and on nothing else. A missing, malformed, stale or non-proceed approval
fails closed, and an all-`unknown` feasibility register reaches stage 3 by this route or not at all.
Editing any question or scope decision row, `feasibility.csv` or `scope_review.json` changes its
bound digest, so a scope that moves after approval needs a fresh approval rather than a preserved
one. Editing a later-stage decision row does not. `--init` scaffolds
`_scope_approval_template.json` and never writes an approved record: a tool that scaffolds a
completed approval has approved the work itself.

**Gate.** The `SCOPE_APPROVAL` arm establishes that the record exists and parses, names the recorded
authority, carries a closed decision value, accepts exactly the checks the review left failed or
unresolved, names a traceable reference, and still matches the closed scope projection and two
files it binds.
It does not establish who created the record. There is no signature and no external witness here,
so the record is a recorded assertion bound to the bytes it approves, and binding it to the bytes is
what limits the damage that assertion can do.

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

**Source role and derivation.** Under v0.3 every source carries `source_role`, recording what the
source is authoritative for, separately from the incentive its motive tier records. A provider's
status page is direct evidence of what that provider disclosed. It is not direct evidence that every
underlying disruption did or did not occur. The two are different claims and one row cannot carry
both without saying which it supports.

`derived_from` records the source a row restates. A mirror of a disclosure is not motive-independent
confirmation of that disclosure, and the gate refuses a `second_source_id` that names any origin or
any derivative of the row's source. Derivation is transitive and the gate follows it to any depth:
if the register records that A restates B and B restates C, then A restates C, and C cannot serve as
A's second source. Two sources that agree because one copied the other agree at four removes exactly
as they do at one. A set of rows that all derive from each other has no origin, so nothing in it can
be traced to what it restates, and the gate refuses that too. Establish derivation before treating
agreement as confirmation.

Derivation also branches, so the test is the inclusive ancestor set: the source itself plus every
origin it records, to any depth. Two rows whose sets intersect reach the register from one origin.
Two mirrors of a single filing are neither ancestor nor descendant of each other, and they confirm
each other exactly as little as either confirms the filing. The gate refuses that pair and names the
shared origin and both derivation paths, so the runner can see the route rather than take the
refusal on trust.

**Source eligibility.** Under v0.3 every source row carries a title, a publisher and at least one
usable locator. A row nobody else can identify or reach cannot be looked up, and a reader cannot be
shown either the bytes it rests on or the exact route that was refused.

A locator is usable when it can be followed, which the gate defines mechanically rather than by the
column being filled in. A URL must parse as an absolute `http` or `https` address naming a host, and
the host is read as a hostname rather than as a network location, so `http://:80` and `http://user@`
name no host and are refused. The address must use the generic RFC 3986 URI character set, with
non-ASCII characters represented by valid percent-encoded octets. It must be free of whitespace,
control characters and backslashes, and must carry a port only where that port is a number inside
the permitted range. A parser will hand back a plausible looking host for `https://example.invalid/a b`,
for a backslash authority, for an incomplete escape such as `https://%GG/` and for a port of
`99999`, and none of these is an address anyone can follow. A source cited without custody therefore
carries a real URL, because the URL is the only route its reader has.

One predicate decides this everywhere the register records an address. The source locator, the
approval reference route and the feasibility evidence route each reach it, so an address refused in
one column is refused in all of them, and a field-specific URL rule is a defect rather than a local
convenience.

**Custody is containment.** Under v0.3 a `local_path` is resolved and must still land inside the
project directory, and must be a file. An absolute path elsewhere on the machine, a parent
traversal and a symlink inside the project pointing outside it are all refused. Bytes recorded as
held travel with the register to a third party; a path that leaves the project describes something
only the machine that ran the gate can see. Retrieved sources continue to require a local path and
a matching hash, now under the same containment rule.

The same containment rule applies to every v0.3 register, scope record, project binding and
top-level draft whose bytes the gate reads or hashes. A fixed project record supplied through a
symlink to bytes outside the project is not self-contained, even when its recorded hash agrees with
the external bytes. Legacy contracts retain their published path behaviour.

The same rule governs a feasibility probe that reports custody. A `bytes_retrievable` probe
answered `available` holds its sample inside the project, and the hash is taken from the resolved
contained file. Custody that means one thing in the source register and another in the feasibility
register is not custody.

The URL test is syntax. It establishes that the string has the selected URI shape. It does not open
a connection, and a well-formed address that resolves to nothing still passes.

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

**Claim identity.** Under v0.3 every claim row carries a `claim_id` unique within the register, and
`claim_text`. Two rows under one identifier make every later correction and evidence marker
ambiguous, and a claim with no content has nothing to verify. Both are cheap to refuse now and
undetectable once the register is in use.

**Claim eligibility.** A claim cannot cite a source whose `retrieval_status` is
`registered_not_retrieved`. The source stays in the register and in the retrieval denominator under
`D3`, and it belongs in the negative-results record, but text nobody obtained cannot be the ground
for extracted text.

**Claim-level corroboration.** Under v0.3 the second source required by `D4` is named on the claim
row, in `corroborating_source_id`, not on the source row. A source can carry several unrelated
statements, so one source-level identifier cannot establish confirmation of each of them. Where a
claim is marked `material_to_conclusion=yes` and its source sits at motive tier 4 or 5, the row
names a corroborating source that is registered, obtained rather than `registered_not_retrieved`,
reachable through a usable locator, not itself at tier 4 or 5, and independent of the primary source
under the same inclusive ancestor test the source register uses.

The reachability test repeats a check the `SOURCES` arm already makes of the register as a whole.
That is deliberate. A second source nobody can open confirms nothing, whichever arm happens to
notice, and this rule does not lean on another arm having fired.

These checks establish registered eligibility and recorded independence. They do not establish
semantic support. Whether the second source says the thing the claim says is a reviewer's call, and
no part of this gate reads for it.

**Gate.** The `VOCAB` and `CLAIMS` arms require each claim to resolve to a registered source and
each controlled value to be declared. A claim marked `material_to_conclusion=yes` cannot rest on tier 4 or 5
alone.

### Stage 5: Draft

| ID | Decision |
|---|---|
| `R1` | The claim ladder. Record what the data shows separately from the inference drawn from it. |
| `R2` | Negative results retained. Record failed methods, unavailable evidence and questions unresolved by the data. A result that falsifies `Q2` is recorded here and the draft proceeds. |
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
python3 research_gate.py --init PROJECT_DIR --contract v0.3  scaffold for v0.3
python3 research_gate.py PROJECT_DIR              run every arm
python3 research_gate.py PROJECT_DIR --contract v0.2  enforce specific contract
python3 research_gate.py LEGACY_DIR --contract v0.1  explicit legacy evaluation
python3 research_gate.py PROJECT_DIR --through digest  gate only what you have reached
python3 research_gate.py PROJECT_DIR --scope-digests   print the v0.3 review digest block
python3 research_gate.py PROJECT_DIR --approval-digests  print the v0.3 approval digest block
python3 research_gate.py --demo                   self-test with seeded faults
python3 tests/test_manifest_fail_closed.py        independent manifest regressions
```

Standard library only, no network, no dependencies. Exits non-zero on any failure. It creates and
validates four registers: `decisions.csv`, `sources.csv`, `claims.csv`, `vocabulary.csv`, and binds
the project via `instrument_manifest.json`. A v0.3 project also carries `feasibility.csv`,
`scope_review.json`, `scope_approval.json` and the two scaffolded templates
`_scope_review_template.json` and `_scope_approval_template.json`. The repository release catalogue
fixes each contract's schema and recognised instrument hashes. The project binding records the exact
protocol, gate and prose-checker identity, version and hash. The gate hashes the current instrument
bytes and requires all three records to agree. Contract v0.1 is a legacy route and is never selected
without explicit `--contract v0.1`.

**What counts as a filled field.** A field the gate requires is refused when it is empty, when it
holds a placeholder such as `TBD` or `n/a`, and when it holds punctuation alone. `!!!` is neither
empty nor a placeholder word, and it tells a reader nothing, so it is refused on the same footing.

Under v0.3 this governs every field whose arm requires content: decision `chosen`, `rationale` and
every alternative recorded in the pipe-separated list, not only the first one that counts towards
the requirement to record one; `source_id`, `source_role`, a
title, a publisher and the reason recorded against a source nobody obtained; claim `claim_id`,
`claim_text` and `uncertainty`; `probe_id`, a probe's `source_name`, the reason recorded against any
probe result other than `available`, `stated_period`, `retention_policy` and the record of where a
probe looked; every scope review note; and the approval reference. Contracts v0.1 and v0.2 keep the
older test, which refuses a blank and a placeholder and accepts punctuation. That difference is
deliberate: those contracts have a published boundary and projects bound to them continue to
validate unchanged.

`revisit_trigger` is not in the list. The protocol does not require it, and no arm checks it under
any contract.

A field carrying content is not thereby correct. The gate reads presence, never meaning.

| Arm | What it enforces |
|---|---|
| `MANIFEST` | the release catalogue matches the fixed code schema; actual protocol, gate and prose-checker bytes match recognised release hashes; the project binding has the expected schema, contract, date, identities, versions and hashes; the registers exist and carry their columns |
| `DECISIONS` | every required decision id for the active contract (27 in v0.2 and v0.3, 26 in v0.1) is present and complete, each with a real alternative; v0.3 also requires a `decided_by` that survives normalisation and content in every recorded alternative rather than in one of them; blanks, placeholders such as TBD, and punctuation that normalises to nothing are refused |
| `SOURCES` | motive tier is 1 to 5, every retrieved source exists and matches its recorded hash without waiver, non-retrieved sources carry a reason, `accessed_date` is an ISO date no earlier than the final scope decision; v0.3 also requires a `source_id`, `source_role`, title and publisher carrying content, and at least one usable locator, meaning an absolute `http` or `https` URL naming a host, free of whitespace, control characters and backslashes and carrying a port only where it is a number in range, or a `local_path` resolving to a file inside the project, refuses any origin, derivative or shared origin of a source as that source's second source at any derivation depth, and refuses a derivation loop |
| `CLAIMS` | every claim resolves to a registered source; a tier 4 or 5 claim marked `material_to_conclusion=yes` carries a second source; every claim states its uncertainty; v0.3 also requires a unique non-placeholder `claim_id` and `claim_text`, refuses a claim grounded in a source nobody obtained, and reads the second source from `corroborating_source_id` on the claim row, requiring it to be registered, obtained, reachable, outside tier 4 and 5, and independent of the primary source |
| `VOCAB` | controlled columns validated against `vocabulary.csv` |
| `DRAFT` | the draft names the falsifier and carries a verification section, a negative-results or retained-limits section, and a COI note |

Three further arms run on contract v0.3 only:

| Arm | What it enforces |
|---|---|
| `FEASIBILITY` | every probe carries a `probe_id` and a `source_name`, asks one of the five permitted questions, returns one of the four permitted outcome-free results with a reason against anything other than `available`, records where it looked through a usable url or an `evidence_locator`, names the model, harness and run that performed it, is dated no later than the last scope decision, and holds any bytes it claims to hold at a `local_path` that resolves to a file inside the project, hashed from that resolved file; all five questions are answered by stage 3 |
| `SCOPE_REVIEW` | the review record exists and parses, names a model, harness and run distinct from the decision-making run on every reviewed row, ignores role labels in that comparison, is dated no earlier than those rows, carries a current digest for each of the seven reviewed decisions, and records a result and a note against each of the six checks; acceptance recorded inside the review is refused |
| `SCOPE_APPROVAL` | the approval record exists and parses, names the recorded authority, carries a decision from the closed set and opens stage 3 on `proceed` alone, accepts exactly the checks the review left failed or unresolved, names a reference carrying a parsable ISO date and a retrievable route, is dated no earlier than the review, and still matches the digests of `decisions.csv#question_scope`, `feasibility.csv` and `scope_review.json` |

It also reports, without failing on them, the share of the register that could not be retrieved, any
numeric token in the draft that appears nowhere in `claims.csv`, a draft that names no baseline or
base rate, and an exit or survival claim that never mentions censoring, survivorship or selection.
All four are prompts to look, not gates: whether a baseline or a censoring rule is the right one is
a research judgement and the gate does not hold it. The retrieval share in particular is often a
finding in its own right.

**Demo requirement.** Run `--demo` before relying on a gate result. The demo builds complete v0.3,
v0.2 and v0.1 fixtures, confirms that clean fixtures pass and confirms that seeded faults fail. It
also confirms that a v0.2 project still passes under default invocation and that a v0.1 project
still passes under explicit legacy invocation, so a v0.3 change that breaks an earlier contract
fails the demo.

## Limitations

- This has been run end to end on no subject. Every stage is derived from completed work, but
  the composition is untested as a whole. Treat v0.2 and v0.3 as specifications, not validated
  methods, until at least one subject has gone through one of them start to finish.
- The v0.3 arms bind records to rows. They do not read meaning. `SCOPE_REVIEW` establishes that a
  reviewer other than the runner recorded a call against each check and that the call still binds
  to the rows it read. Whether the call is correct is a human judgement the gate does not hold.
- Identity checks establish that model, harness and run are present and mechanically comparable.
  A separate sandboxed run of the same model is permitted; a role-label change is not a separate
  run. Nothing in the toolchain authenticates an actor. `SCOPE_APPROVAL` establishes that a
  hash-bound record names the approving authority and matches the rows and the review it approves.
  It cannot establish that the named authority created it. The binding limits what a false assertion
  survives: it covers the
  question-and-scope rows as they stood, and any edit to a bound scope item requires a fresh
  approval.
- The claim-level second-source rule establishes registered eligibility and recorded independence:
  the corroborating source exists, was obtained, sits outside tier 4 and 5, and shares no recorded
  origin with the primary source. It does not establish that the second source supports the
  particular claim. That remains a reviewer's decision, and the gate records no opinion on it.
- The independence test reads the `derived_from` column. It establishes that the register does not
  contradict itself about derivation. A derivation left unrecorded is invisible to it.
- Locator and reference checks are syntax. A URL is tested for scheme, host, port form and
  forbidden characters, never fetched, so a well-formed address that leads nowhere passes. An
  approval reference is tested for a parsable date and a retrievable route, never opened, so a
  reference to a record that does not exist passes. Both establish that a reader has something to
  follow, not that following it arrives anywhere.
- Path containment is resolved at the time the gate runs. It establishes that the recorded path
  lands inside the project on this filesystem now. A file added, moved or unlinked afterwards is
  outside what any single run can hold, which is what the recorded hash is for.
- A field that carries content is not thereby correct. Every check of this kind establishes that
  something was written where the protocol requires a value, and nothing about whether it is true.
- The `FEASIBILITY` arm constrains the structured fields, which is where an outcome value would have
  to go to be usable. It cannot constrain free text. Numeric tokens in probe notes are reported for
  a human to read, not failed on.
- Decision attribution records who chose. It does not establish that the choice was made before the
  outcome was visible. The probe and access date rules make the ordering checkable at the register
  level only.
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

## AI assistance, conflicts and limitations

This work was produced through an AI-assisted workflow directed and reviewed by the author. AI
systems supported tasks such as research, drafting, coding and review. The systems used are
recorded in the repository's commit metadata. They are tools, not authors.

An assisting system may be supplied by an organisation discussed in the work, and model review may
cover material produced elsewhere in the same workflow. Model review is therefore supporting
evidence, not independent assurance unless the release record explicitly establishes that
separation.

AI-generated errors may survive human and automated checks. Deterministic gates and cross-provider
review reduce, but do not eliminate, that risk. The author remains responsible for the released
work, and corrections are logged when identified.

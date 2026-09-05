# Empirical bundle programme

**Purpose.** This working specification converts completed Divergence Registry subjects into
short empirical records and coherent publication bundles. It is not a manuscript and is not part
of a deposit.

## Separation of outputs

The research output and the operations case study are companion artefacts. They are not combined
in one deposit.

The research output contains the finding, method, verified sources, claim records, machine-readable
results and reproducer. The operations case study describes the operating model and links to the
research output after publication.

## Candidate intake

`OBJECTIVE_CANDIDATE_REGISTER.csv` is the intake record. A candidate remains `pending` until a
feasibility probe records all of the following:

1. a sample of the historical record rather than current state alone;
2. `reachable_now`, `history_bulk` and `archive_fallback` separately;
3. whether the retrieved artefact carries machine-readable structure or source markup;
4. byte count and SHA-256 for every retrieved sample;
5. an admission decision and reason.

A candidate is admitted only when `history_bulk=yes` or `archive_fallback=yes`, and
`structured_bytes=yes`. A successful route in an earlier trial supports selection for a new probe.
It does not admit the candidate under v0.3 by itself.

## Trial sequence

1. Close the outstanding C3 and C7 feasibility decisions.
2. Freeze the committed v0.3 instrument snapshot for the wave.
3. Probe C11, C12 and C13 in order.
4. Stop after C13 and assess source authenticity, gate behaviour and the value of the findings.
5. Open C14 to C20 only after that assessment.

The runner, scope reviewer and semantic reviewer record distinct runs. A mechanical pass does not
establish that a source supports a claim or that a conclusion is correct.

## First acceptance run

C11 does not open directly from the synthetic controller fixture. First run one scratch known-answer
replay against a real, already verified dataset and compare the generated candidate claims with the
held result. The completed C3 and C7 directories contain final registers and findings but no
executable analysis program, so neither is a genuine replay fixture without reconstructing the
method after seeing its result.

C11 is the first acceptance candidate for the combined lifecycle, which is developed separately and
is not released in this repository. It remains parked until the
exact trial directory, runner, scope reviewer and semantic reviewer are recorded. Reopening Data
without those four entries is not authorised.

The run is useful only if it produces a source-bound research result and reduces the researcher's
checking burden. Record the number of researcher interventions, reviewer-requested substantive
corrections,
unresolved anchor claims and completed output level. A gate pass alone is not acceptance. Compare
those measures with the existing C11 sessions where the records permit a like-for-like count. If the
comparison cannot be reconstructed, record that no baseline was available.

## Publication eligibility

A subject can enter bundle selection only where all conditions below are recorded:

- feasibility decision `admit`;
- complete v0.3 registers through draft;
- `research_gate.py` exit 0 against the frozen instrument snapshot;
- every declared retrieved source holds authentic bytes with a local path and hash;
- every public claim has an atomic claim record and precise source locator;
- every derived ratio records numerator, denominator and N;
- semantic support and atomicity reviewed by a run other than the drafting run;
- negative and inconclusive results retained;
- no unresolved anchor claim;
- a manual decision that the result justifies a permanent public record.

Gate success alone gives the subject `trial_complete`, not `publication_ready`.

## Bundle decision

Bundle membership is a manual editorial decision made after eligible subjects are known. Subjects
share a bundle only where they have a common measurement object, comparable units and a synthesis
that adds information beyond placing unrelated records beside one another.

Two provisional families organise intake but do not predetermine publication:

| Family | Candidates | Possible common object |
|---|---|---|
| Revision history | C11, C12, C13, C18, C19, C20 | Change recorded across versions or events |
| AI record drift | C14, C15, C16, C17 | Change or disagreement in public AI-system records |

If C11 to C13 produce comparable measures, they may form the first revision-history bundle. If
their measures or conclusions do not cohere, each remains a separate short empirical record.

## Bundle contents

Each bundle contains:

- one concise synthesis with the common question and limits;
- one self-contained finding record per subject;
- machine-readable claim, source and result records;
- held public-source bytes where redistribution is permitted, otherwise hashes and retrieval
  instructions;
- one command that reproduces derived results;
- a verification note before the conflict-of-interest note;
- a manifest binding the included files and instrument version.

Working trails, agent handoffs, case-study material and internal friction logs stay outside the
deposit.

## Release boundary

House-style correction begins only after semantic review. Rendering, publication, DOI minting,
remote push and live portfolio changes require their own current-session approval and applicable
gates.

# Divergence Registry

A versioned protocol and deterministic checker suite for recording methodological decisions and
comparing research runs.

*AI disclosure: the research is the author's; this text was drafted with AI assistance and reviewed
by the author. The model, and the conflict it creates, are named in the Conflict of interest and
scope section.*

**v0.3 release candidate: retained as a component on 24 August 2026.** The toolchain passed its
recorded structural and adversarial checks. Trial C11 reached a corrected scope and bound
pre-analysis plan, then stopped before renewed scope approval or Stage 3 outcome collection. No
v0.2 or v0.3 subject has completed end to end, and the method is not presented as validated.
Published v0.2-rc2 remains the historical release. OpenDFM/Xcientist was assessed and rejected for
the current workflow. A combined research lifecycle that uses v0.3 for its decision record is
developed separately and is not released here: it invokes a claim checker that is not distributed
with it, so a copy in this repository could not be run from a clone.

Three contracts are recognised. Contract v0.1 is the original 26-decision protocol and is selected
only by explicit request. Contract v0.2 is the 27-decision protocol with the mandatory `S6` exit and
censoring rule; its instruments are frozen under `_frozen_instruments/v0.2` and projects bound to it
continue to validate unchanged. Contract v0.3 keeps the same 27 decision identifiers and adds
required decision attribution, a bounded pre-scope feasibility route, a scope coherence review
bound to the digests of the decision rows it read, and the researcher's separate hash-bound
approval to open stage 3.

Read [`DIVERGENCE_PROTOCOL.md`](DIVERGENCE_PROTOCOL.md) first. The supported claim is that recorded
divergence is attributable to named methodological decisions. The protocol does not claim that
different researchers will agree or that a completed result is substantively correct.

## Requirements

Python 3, and nothing else. Everything in this repository runs from a clone with no third-party
package, no external tool and no network request.

## Divergence v0.3 enforcement scope

Six stages (question, scope, data, digest, draft, mint), each with named decision points. Every
choice capable of changing a result is logged with the alternatives available at the time. The
resulting decision registers can be compared across research runs.

The claim is divergence is attributable, not that divergence is absent. Two competent people on
the same subject may still reach different conclusions.

## Components

The two checkers in this repository make no network request and run no analysis of their own. They
read a project directory, check it, and report. Sandboxed execution belongs to the separately
developed lifecycle and is not part of this release.

```
python3 research_gate.py --init PROJECT_DIR    scaffold the four registers for v0.2
python3 research_gate.py --init PROJECT_DIR --contract v0.3  scaffold for v0.3
python3 research_gate.py PROJECT_DIR           gate the process
python3 research_gate.py LEGACY_DIR --contract v0.1  explicit legacy evaluation
python3 research_gate.py PROJECT_DIR --scope-digests  v0.3 review digest block
python3 research_gate.py PROJECT_DIR --approval-digests  v0.3 approval digest block
python3 research_gate.py --demo                self-test, seeded faults
python3 tests/test_manifest_fail_closed.py     independent manifest regressions

python3 agp_deterministic.py DRAFT.md --source filing.txt:1 --source deck.txt:5
python3 agp_deterministic.py --demo
```

`research_gate.py` checks 27 required decisions in v0.2 and v0.3 (26 in explicitly selected v0.1),
release and project manifest agreement, current instrument bytes, source custody, claim-to-source
links, controlled vocabulary and required draft sections. Under v0.3 it also requires every decision
to name its decision-maker, a bounded feasibility register completed before stage 3, a scope
coherence review recorded by someone other than the runner and still bound to the rows it read, and
the researcher's recorded approval to proceed, bound by hash to the registers and the review it
approves. Under v0.3 a material claim resting on an interested source names its corroborating source
on the claim row rather than inheriting one from the source register.

Those checks establish that the required rows are present, that the register is internally
consistent, and that each specifically hash-bound record still matches the digest recorded for it at
its own boundary: the scope rows a review was bound to, and the approval together with the files it
binds. That is narrower than one review-time binding over every project file. They do not
authenticate who recorded anything, and they do not establish that a source supports a claim.

`agp_deterministic.py` checks the draft against supplied sources for unsupported numeric tokens,
entity mismatches, internal numeric contradictions, claims supported only by tier 4 or 5 sources,
and names appearing solely inside a correction or negation.

The scripts cover different failure classes. Run both demos before relying on a project result.

## Use

1. `python3 research_gate.py --init subject_dir`
2. Fill `decisions.csv` top down, working the stages in `DIVERGENCE_PROTOCOL.md`. Blanks and
   placeholders are refused, and so is any decision with no alternative recorded.
3. `python3 research_gate.py subject_dir --through scope` as you go, widening the stage as you
   reach it.
4. Draft into a `.md` in the project directory, then run both scripts.

## Limits

The checkers establish process integrity and source grounding within their stated rules. They do
not assess the substantive value of the research question or conclusion. Full limitations are
listed in the protocol.

## Conflict of interest and scope

The research design, method, sourcing decisions and analytical judgements are the author's. Anthropic
Claude Opus 5 assisted with implementation, repair and release preparation for v0.3. OpenAI GPT-5.6
Sol assisted with earlier v0.3 implementation and performed the independent acceptance review of this
release. Google Gemini 3.7 Flash assisted with maintenance and trial orchestration in the v0.2 era.
This text was artificially generated and was reviewed by the author before publication. Models are
not authors.

The assisting model is not always a neutral party to the subject matter. Two conflicts are specific
to this release. The reviewing model had earlier contributed implementation to the same contract, so
part of the acceptance review examined work that reviewer had a hand in. Separately, each release
gate here is a check on output that assisting models helped produce, and no gate authenticates who
recorded anything. Both are reasons the author's own review remains the primary control rather than a
formality.

What the author cannot guarantee: a language model's output can be wrong in ways that survive review.
In prose the error is locally plausible; in code it simply runs, and a wrong constant or a mis-set
filter still returns a clean number. Independent review across labs, adversarial fixtures and
deterministic gates are deployed against this, but the review is not claimed to be exhaustive.
Corrections are logged against the release when surfaced.

No warranty is offered beyond the terms of the licences below. Independent analysis and open-science
documentation only, not investment advice.

## Licence

The protocol and documentation are licensed under CC BY 4.0. Python source code and tests are
licensed under the MIT License. See [`LICENSE.md`](LICENSE.md).

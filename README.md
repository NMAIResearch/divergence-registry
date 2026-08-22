# Divergence Registry

A versioned protocol and deterministic checker suite for recording methodological decisions and
comparing research runs.

**v0.3 release candidate: on trial.** The toolchain has passed structural and adversarial checks.
The research method has not completed an end-to-end v0.2 or v0.3 subject and is not presented as
validated.

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

## Enforcement scope

Six stages (question, scope, data, digest, draft, mint), each with named decision points. Every
choice capable of changing a result is logged with the alternatives available at the time. The
resulting decision registers can be compared across research runs.

The claim is divergence is attributable, not that divergence is absent. Two competent people on
the same subject may still reach different conclusions.

## Components

Standard library only. No dependencies, no network.

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

Those checks establish that the record is complete, internally consistent and unchanged since it was
reviewed. They do not authenticate who recorded anything, and they do not establish that a source
supports a claim.

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

## Licence

The protocol and documentation are licensed under CC BY 4.0. Python source code and tests are
licensed under the MIT License. See [`LICENSE.md`](LICENSE.md).

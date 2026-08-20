# Divergence Registry

A versioned protocol and deterministic checker suite for recording methodological decisions and
comparing research runs.

**v0.2 release candidate: on trial.** The toolchain has passed structural and adversarial checks.
The research method has not completed an end-to-end v0.2 subject and is not presented as validated.

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
python3 research_gate.py PROJECT_DIR           gate the process
python3 research_gate.py LEGACY_DIR --contract v0.1  explicit legacy evaluation
python3 research_gate.py --demo                self-test, seeded faults
python3 tests/test_manifest_fail_closed.py     independent manifest regressions

python3 agp_deterministic.py DRAFT.md --source filing.txt:1 --source deck.txt:5
python3 agp_deterministic.py --demo
```

`research_gate.py` checks 27 required decisions in v0.2 (26 in explicitly selected v0.1), release
and project manifest agreement, current instrument bytes, source custody, claim-to-source links,
controlled vocabulary and required draft sections.

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

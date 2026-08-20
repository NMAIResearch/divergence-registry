# Divergence Registry

A versioned research protocol and deterministic checker suite for making methodological divergence
attributable.

**v0.2 release candidate: on trial.** The toolchain has passed structural and adversarial checks.
The research method has not completed an end-to-end v0.2 subject and is not presented as validated.

Read [`DIVERGENCE_PROTOCOL.md`](DIVERGENCE_PROTOCOL.md) first. Its central claim is deliberately
narrow: the process record can show where two research runs diverged. It cannot guarantee that two
researchers reach the same conclusion or that either conclusion is sound.

## What it enforces

Six stages (question, scope, data, digest, draft, mint), each with named decision points. Every
choice that could send two researchers in different directions is logged with the alternatives that
were available, so two artefacts can be diffed and the diff says where they split.

The claim is **divergence is attributable**, not that divergence is absent. Two competent people on
the same subject may still reach different conclusions.

## The scripts

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

`research_gate.py` gates the **registers and instrument binding**: 27 required decisions in v0.2
(26 in explicitly selected v0.1), exact release and project manifest agreement, current protocol,
gate and prose-checker bytes, source custody and hashes, claims resolving to sources, controlled
vocabulary and draft sections.

`agp_deterministic.py` gates the **prose against the sources**: fabricated numbers, grafted
relations, internal contradictions, claims resting only on self-interested sources, and
misattribution where the named subject appears solely inside a correction.

Neither covers the other. Run both. Run `--demo` on each before trusting a pass.

## Quickstart

1. `python3 research_gate.py --init subject_dir`
2. Fill `decisions.csv` top down, working the stages in `DIVERGENCE_PROTOCOL.md`. Blanks and
   placeholders are refused, and so is any decision with no alternative recorded.
3. `python3 research_gate.py subject_dir --through scope` as you go, widening the stage as you
   reach it.
4. Draft into a `.md` in the project directory, then run both scripts.

## Limits

Stated in full at the end of the protocol. The short version: this checks that the process is intact
and the claims are grounded. It cannot tell you whether the research is any good, and nothing
here defends against a well-formed artefact answering a worthless question.

## Licence

The protocol and documentation are licensed under CC BY 4.0. Python source code and tests are
licensed under the MIT License. See [`LICENSE.md`](LICENSE.md).

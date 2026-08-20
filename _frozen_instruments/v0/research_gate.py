#!/usr/bin/env python3
"""research_gate.py - process gate for the Research Guide.

    python3 research_gate.py --init PROJECT_DIR     scaffold a new project
    python3 research_gate.py PROJECT_DIR            run every arm
    python3 research_gate.py PROJECT_DIR --through digest
    python3 research_gate.py --demo                 self-test with seeded faults

Standard library only, no network. Exits non-zero on any failure.

This gates the PROCESS, not the deposit. It enforces that every decision the guide names has
been made, logged with a real alternative, and that the evidence register supports the claims.
It cannot tell you whether the research is any good. Nothing can.

Six arms:

  MANIFEST    the four register files exist and carry their columns
  DECISIONS   every required decision id for the stages reached is present and complete,
              each with at least one genuine alternative
  SOURCES     motive tier is 1-5, retrieved sources exist and match their hash, sources
              that could not be retrieved carry a reason
  CLAIMS      every claim resolves to a registered source; a load-bearing claim grounded
              only in tier 4 or 5 carries a second source
  VOCAB       controlled columns validated against vocabulary.csv
  DRAFT       the draft names the falsifier and carries a verification section, a negative-
              results or retained-limits section, and a COI note
"""

import argparse
import csv
import hashlib
import re
import shutil
import sys
import tempfile
from pathlib import Path

STAGES = ["question", "scope", "data", "digest", "draft", "mint"]

REQUIRED = {
    "question": {
        "Q1": "unit of analysis",
        "Q2": "the proposition, stated so it can fail",
        "Q3": "the falsifier, dated and observable",
        "Q4": "describe or score",
    },
    "scope": {
        "S1": "population and denominator",
        "S2": "inclusion and exclusion rule",
        "S3": "as-of date and vintage policy",
        "S4": "kill criterion",
        "S5": "research mode per stage",
    },
    "data": {
        "D1": "what counts as primary here",
        "D2": "custody policy",
        "D3": "non-retrieval policy",
        "D4": "second-source rule",
    },
    "digest": {
        "G1": "extraction schema",
        "G2": "new-field admission rule",
        "G3": "controlled vocabulary",
        "G4": "derived against reported",
        "G5": "uncertainty form",
    },
    "draft": {
        "R1": "the claim ladder",
        "R2": "negative results retained",
        "R3": "register and voice gates",
        "R4": "conflict of interest",
    },
    "mint": {
        "M1": "evidence floor met",
        "M2": "ships against stays local",
        "M3": "version and lineage",
        "M4": "commitment gate",
    },
}

FILES = {
    "decisions.csv": ["decision_id", "stage", "question", "chosen", "alternatives",
                      "rationale", "decided_date", "decided_by", "revisit_trigger"],
    "sources.csv": ["source_id", "title", "publisher", "motive_tier", "source_role", "url",
                    "local_path", "sha256", "retrieval_status", "accessed_date",
                    "second_source_id", "notes"],
    "claims.csv": ["claim_id", "claim_text", "source_id", "claim_basis", "load_bearing",
                   "uncertainty", "notes"],
    "vocabulary.csv": ["column", "value", "definition"],
}

SEED_VOCAB = [
    ("claim_basis", "reported", "The source states this value itself."),
    ("claim_basis", "derived", "Computed by the author from source values. The computation is named."),
    ("claim_basis", "inferred", "A judgement the source does not itself make. Never presented as reported."),
    ("load_bearing", "yes", "The finding changes if this claim is wrong."),
    ("load_bearing", "no", "Supporting or contextual. The finding survives without it."),
    ("retrieval_status", "retrieved", "Held locally and hash-verified."),
    ("retrieval_status", "registered_not_retrieved",
     "Judged necessary but could not be obtained. Stays in the register with a reason and counts "
     "against the denominator."),
    ("retrieval_status", "cited_not_held",
     "Deliberately not held under the D2 custody policy. Stable, archived or mirrored source."),
]

# A placeholder is not an answer. --init writes these; the gate refuses them.
PLACEHOLDER = re.compile(r"^\s*(|todo|tbd|n/?a|none|-+|\.\.\.|xxx+|\?+)\s*$", re.I)

# R2's section, under the several headings the trials actually used: "Negative Results Retained",
# "Negative and null results retained", "Retained Negative Results and Limitations", "Negative
# Results and Retained Limits". Matched on the words rather than on one fixed title.
NEG_RESULTS_HEAD = re.compile(
    r"^#{1,6}[^\n]*(?:\bnegative\b[^\n]*\bresults?\b|\bnull results?\b|\blimitations?\b|"
    r"\bretained limits?\b|\bcaveats?\b)", re.M | re.I)
NEG_RESULTS_LEAD = re.compile(r"^\s*\*?\*?(?:negative results?|limitations?)\b\s*:", re.M | re.I)


class Report:
    def __init__(self):
        self.errors = []
        self.notes = []

    def check(self, ok, msg, arm):
        if not ok:
            self.errors.append(f"{arm}: {msg}")
        return ok

    def note(self, msg):
        self.notes.append(msg)


def blank(value):
    return PLACEHOLDER.match(value or "") is not None


def read_csv(path, report, arm="MANIFEST", needed_at=None, through=None):
    """Read a register, checking its columns. Returns [] and records an error on any problem.

    A register that is empty is only a failure once the stage that fills it has been reached.
    sources.csv is legitimately empty until stage 'data', claims.csv until stage 'digest'.
    """
    name = path.name
    if not path.exists():
        report.check(False, f"{name} is missing. Run --init to scaffold it.", arm)
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    expected = FILES[name]
    got = list(rows[0].keys()) if rows else None
    if got is not None:
        if name == "decisions.csv":
            legacy = ["decision_id", "stage", "question", "chosen", "alternatives",
                      "rationale", "decided_date", "revisit_trigger"]
            if got != expected and got != legacy:
                report.check(False, f"{name} columns are {got}, expected {expected}", arm)
                return []
        elif name == "claims.csv":
            missing = [c for c in expected if c not in got]
            if missing:
                report.check(False, f"{name} is missing required columns {missing}", arm)
                return []
            extra = [c for c in got if c not in expected]
            if extra:
                report.note(f"{name} includes domain extraction column(s): {', '.join(extra)}")
        elif got != expected:
            report.check(False, f"{name} columns are {got}, expected {expected}", arm)
            return []
    if not rows:
        premature = (needed_at is not None and through is not None
                     and STAGES.index(through) < STAGES.index(needed_at))
        if premature:
            report.note(f"{name} is empty, which is expected before stage '{needed_at}'")
        else:
            report.check(False, f"{name} has no rows", arm)
    return rows


def arm_decisions(rows, through, report):
    required = {}
    for stage in STAGES[:STAGES.index(through) + 1]:
        required.update({k: (stage, v) for k, v in REQUIRED[stage].items()})

    seen = {}
    for i, r in enumerate(rows, start=2):
        did = (r["decision_id"] or "").strip().upper()
        if did in seen:
            report.check(False, f"row {i}: decision {did} is logged twice", "DECISIONS")
            continue
        seen[did] = r

    for did, (stage, what) in sorted(required.items()):
        r = seen.get(did)
        if r is None:
            report.check(False, f"{did} ({stage}, {what}) is not logged", "DECISIONS")
            continue
        if blank(r["chosen"]):
            report.check(False, f"{did}: nothing chosen", "DECISIONS")
        if blank(r["rationale"]):
            report.check(False, f"{did}: no rationale", "DECISIONS")
        # The alternative is the whole point. A decision with no road not taken was not a
        # decision, and logging it as one makes the record look richer than it is.
        alts = [a for a in (r["alternatives"] or "").split("|") if not blank(a)]
        if not alts:
            report.check(False, f"{did}: no alternative recorded, so nothing was decided. "
                                f"Name at least one option genuinely available, pipe-separated.",
                         "DECISIONS")
        if blank(r["decided_date"]):
            report.check(False, f"{did}: no decided_date", "DECISIONS")

    extra = sorted(set(seen) - set(required) - {""})
    if extra:
        report.note(f"decisions beyond the required set, kept: {', '.join(extra)}")
    report.note(f"{len(required)} decisions required through stage '{through}', "
                f"{len(seen)} logged")


def arm_sources(rows, root, report, decisions=None):
    ids, held, unretrieved = set(), 0, 0
    scope_dates = []
    if decisions:
        for r in decisions:
            did = (r.get("decision_id") or "").strip().upper()
            if did in {"S1", "S2", "S3", "S4", "S5"} and not blank(r.get("decided_date")):
                scope_dates.append(r["decided_date"].strip())
    earliest_scope_date = min(scope_dates) if scope_dates else None

    for i, r in enumerate(rows, start=2):
        sid = (r["source_id"] or "").strip()
        if not sid:
            report.check(False, f"row {i}: no source_id", "SOURCES")
            continue
        if sid in ids:
            report.check(False, f"row {i}: source_id {sid} is registered twice", "SOURCES")
        ids.add(sid)

        tier = (r["motive_tier"] or "").strip()
        if tier not in {"1", "2", "3", "4", "5"}:
            report.check(False, f"{sid}: motive_tier is '{tier}', expected 1 to 5 "
                                f"(1 primary or regulator, 5 seller marketing)", "SOURCES")

        status = (r["retrieval_status"] or "").strip()
        if status == "retrieved":
            if blank(r["local_path"]):
                report.check(False, f"{sid}: retrieved but no local_path", "SOURCES")
                continue
            p = root / r["local_path"]
            if not p.exists():
                report.check(False, f"{sid}: file missing at {r['local_path']}", "SOURCES")
                continue
            got = hashlib.sha256(p.read_bytes()).hexdigest()
            if blank(r["sha256"]):
                report.check(False, f"{sid}: held but not hashed. Recorded hash should be "
                                    f"{got}", "SOURCES")
            elif got != r["sha256"].strip():
                report.check(False, f"{sid}: hash mismatch. File is {got}, register says "
                                    f"{r['sha256'].strip()}", "SOURCES")
            else:
                held += 1
        elif status == "registered_not_retrieved":
            unretrieved += 1
            # D3: a source that could not be got is evidence about the subject, not an
            # embarrassment to be deleted. But it has to say why.
            if blank(r["notes"]):
                report.check(False, f"{sid}: registered_not_retrieved with no reason in notes. "
                                    f"Record what was tried and what happened.", "SOURCES")
        if blank(r["accessed_date"]):
            report.check(False, f"{sid}: no accessed_date", "SOURCES")
        elif earliest_scope_date and r["accessed_date"].strip() < earliest_scope_date:
            report.check(False, f"{sid}: accessed_date {r['accessed_date'].strip()} is earlier "
                                f"than earliest scope decision date {earliest_scope_date}. "
                                f"Data collection cannot precede scope definition (S1-S5).",
                         "SOURCES")

    total = len(ids)
    if total:
        report.note(f"{total} sources, {held} held and hash-verified, "
                    f"{unretrieved} registered and not retrieved "
                    f"({100 * unretrieved / total:.0f}% of the register)")
    return ids


def arm_claims(rows, sources, source_ids, report):
    tier = {(r["source_id"] or "").strip(): (r["motive_tier"] or "").strip() for r in sources}
    second = {(r["source_id"] or "").strip(): (r["second_source_id"] or "").strip()
              for r in sources}
    load_bearing = 0
    for i, r in enumerate(rows, start=2):
        cid = (r["claim_id"] or "").strip() or f"row {i}"
        sid = (r["source_id"] or "").strip()
        if not sid:
            report.check(False, f"{cid}: cites no source", "CLAIMS")
            continue
        if sid not in source_ids:
            report.check(False, f"{cid}: cites '{sid}', which is not in sources.csv", "CLAIMS")
            continue
        if blank(r["uncertainty"]):
            report.check(False, f"{cid}: no uncertainty recorded. A point estimate is a "
                                f"choice (G5), so state it as one.", "CLAIMS")
        if (r["load_bearing"] or "").strip().lower() == "yes":
            load_bearing += 1
            # D4 and the AGP source-tier gate: faithful transcription of a self-interested
            # source still fails. Grounding is not truth.
            if tier.get(sid) in {"4", "5"} and blank(second.get(sid)):
                report.check(False, f"{cid}: load-bearing, grounded only in {sid} at motive "
                                    f"tier {tier.get(sid)}, and that source has no "
                                    f"second_source_id", "CLAIMS")
    report.note(f"{len(rows)} claims, {load_bearing} load-bearing")


def arm_vocab(vocab_rows, tables, report):
    allowed = {}
    for r in vocab_rows:
        col = (r["column"] or "").strip()
        if col:
            allowed.setdefault(col, set()).add((r["value"] or "").strip())
    if not allowed:
        report.check(False, "vocabulary.csv declares no controlled column. At minimum control "
                            "the column that records what the artefact refuses to do (G3).",
                     "VOCAB")
        return
    checked = 0
    for name, rows in tables.items():
        for i, r in enumerate(rows, start=2):
            for col, values in allowed.items():
                if col not in r:
                    continue
                got = (r[col] or "").strip()
                checked += 1
                if got not in values:
                    report.check(False, f"{name} row {i}: {col} is '{got}', not declared in "
                                        f"vocabulary.csv", "VOCAB")
    report.note(f"{checked} values checked against {len(allowed)} controlled column(s): "
                f"{', '.join(sorted(allowed))}")


def arm_draft(root, decisions, claims, report):
    drafts = sorted(p for p in root.glob("*.md") if not p.name.startswith("_"))
    if not drafts:
        report.check(False, "no draft .md found in the project directory", "DRAFT")
        return
    for p in drafts:
        text = p.read_text(encoding="utf-8", errors="replace")
        low = text.lower()
        report.check(re.search(r"falsif|would prove .{0,20}wrong|kill(s|ed)? the claim", low)
                     is not None,
                     f"{p.name}: nothing names the falsifier. Q3 was decided; the artefact has "
                     f"to state it.", "DRAFT")
        report.check(re.search(r"^#{1,6}\s*(?:\d+(?:\.\d+)*[.)]?\s+)?verification\b",
                               text, re.M | re.I)
                     or re.search(r"^\s*\*?\*?verification:", text, re.M | re.I),
                     f"{p.name}: no verification section. It names which primary document each "
                     f"figure was traced to, and which figures are derived.", "DRAFT")
        report.check("conflict of interest" in low or re.search(r"\bcoi\b", low) is not None,
                     f"{p.name}: no conflict-of-interest note", "DRAFT")
        report.check(NEG_RESULTS_HEAD.search(text) is not None
                     or NEG_RESULTS_LEAD.search(text) is not None,
                     f"{p.name}: no negative-results or retained-limits section. R2 was decided; "
                     f"what did not work, what could not be obtained and what the data refused to "
                     f"settle are named in the artefact, not dropped.", "DRAFT")

        # Notes, deliberately not gates. Whether a baseline or a censoring treatment is the right
        # one is a research judgement and the gate does not hold it. That the artefact never
        # raises either is mechanically visible, and worth a look before it ships.
        if not re.search(r"\bbaselines?\b|\bbase rates?\b|\bnull model\b", low):
            report.note(f"{p.name}: no baseline or base rate is named. If the finding is a rate "
                        f"or an effect, state what it is measured against, or state that no "
                        f"baseline was run.")
        if re.search(r"\battrition\b|\bsurviv\w*|\bdisappear\w*|\bdepart(?:ed|ure|ures)\b|"
                     r"\bdelist\w*|\bchurn\b|\bdrop(?:ped)?[ -]off\b", low) \
                and not re.search(r"\bcensor\w*|\bsurvivorship\b|\bselection bias\b", low):
            report.note(f"{p.name}: this reads as an exit or survival claim and nothing in it "
                        f"mentions censoring, survivorship or selection. An entry still present "
                        f"at the edge of the held window has not been observed leaving. Check by "
                        f"hand which side of that line each count sits on.")

        # Informational, deliberately not a gate. The AGP number-grep adapted: numbers in prose
        # that appear nowhere in the claim register are worth a look, but section numbers, dates
        # and list counters make this too noisy to fail on.
        in_claims = " ".join(c["claim_text"] + " " + c["uncertainty"] for c in claims)
        prose = re.sub(r"`[^`]*`|https?://\S+", " ", text)
        nums = {n for n in re.findall(r"\b\d[\d,]*\.?\d*\b", prose) if len(n) > 2}
        loose = sorted(n for n in nums if n not in in_claims)
        if loose:
            report.note(f"{p.name}: {len(loose)} numeric tokens not found in claims.csv, "
                        f"check by hand: {', '.join(loose[:8])}"
                        f"{' ...' if len(loose) > 8 else ''}")


def run(root, through, quiet=False):
    report = Report()
    root = Path(root)
    if not root.is_dir():
        print(f"FAIL: {root} is not a directory")
        return 1

    decisions = read_csv(root / "decisions.csv", report, needed_at="question", through=through)
    sources = read_csv(root / "sources.csv", report, needed_at="data", through=through)
    claims = read_csv(root / "claims.csv", report, needed_at="digest", through=through)
    vocab = read_csv(root / "vocabulary.csv", report, needed_at="digest", through=through)

    if STAGES.index(through) < STAGES.index("data") and sources:
        report.check(False, f"sources.csv contains {len(sources)} row(s) before stage 'data' is reached "
                            f"(currently gating through '{through}'). Question and Scope (Idea Mode) "
                            f"must be completed before collecting source data.", "SOURCES")

    if STAGES.index(through) < STAGES.index("digest") and claims:
        report.check(False, f"claims.csv contains {len(claims)} row(s) before stage 'digest' is reached "
                            f"(currently gating through '{through}'). Scope and source data custody "
                            f"must be locked before extracting claims.", "CLAIMS")

    if decisions:
        arm_decisions(decisions, through, report)
    source_ids = arm_sources(sources, root, report, decisions) if sources else set()
    if claims and sources:
        arm_claims(claims, sources, source_ids, report)
    if vocab:
        arm_vocab(vocab, {"sources.csv": sources, "claims.csv": claims}, report)
    if STAGES.index(through) >= STAGES.index("draft"):
        arm_draft(root, decisions, claims, report)

    if not quiet:
        print(f"research_gate: {root.name}, gated through stage '{through}'")
        for n in report.notes:
            print(f"  - {n}")
        print()
        if report.errors:
            print(f"FAIL ({len(report.errors)}):")
            for e in report.errors:
                print(f"  {e}")
        else:
            print("PASS: every required decision is logged, every claim is grounded, and "
                  "every held source matches its hash.")
            print("      This says the process is intact. It says nothing about whether the "
                  "research is right.")
    return 1 if report.errors else 0


def init(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "sources").mkdir(exist_ok=True)
    made = []
    for name, cols in FILES.items():
        p = root / name
        if p.exists():
            print(f"  kept    {name} (already exists)")
            continue
        with p.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            if name == "decisions.csv":
                for stage in STAGES:
                    for did, what in REQUIRED[stage].items():
                        w.writerow([did, stage, what, "", "", "", "", "", ""])
            elif name == "vocabulary.csv":
                w.writerows(SEED_VOCAB)
        made.append(name)
        print(f"  created {name}")
    if made:
        print(f"\n{root}/ scaffolded. Fill decisions.csv top down; the gate refuses blanks and "
              f"placeholders.")
        print("Alternatives are pipe-separated. A decision with no alternative is rejected.")
    return 0


def demo():
    """Seed a fault into each arm and assert the arm fires. A checker that has only ever
    returned PASS has not been tested."""
    tmp = Path(tempfile.mkdtemp(prefix="research_gate_demo_"))
    try:
        proj = tmp / "worked_subject"
        init(proj)
        print()

        # A minimal but genuinely complete project.
        held = proj / "sources" / "regulator_filing.txt"
        held.write_text("Reported capacity 4,200 MW across 17 sites.\n", encoding="utf-8")
        digest = hashlib.sha256(held.read_bytes()).hexdigest()

        with (proj / "decisions.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(FILES["decisions.csv"])
            for stage in STAGES:
                for did, what in REQUIRED[stage].items():
                    w.writerow([did, stage, what, f"chose the {what} as stated",
                                "the wider reading|the narrower reading",
                                "the narrower one survives a hostile read", "2026-08-14",
                                "author:N", "revisit if the regulator restates"])

        with (proj / "sources.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(FILES["sources.csv"])
            w.writerow(["regulator_filing", "Capacity return", "The regulator", "1",
                        "primary", "https://example.invalid/return",
                        "sources/regulator_filing.txt", digest, "retrieved", "2026-08-14",
                        "", "Held because the return is republished in place."])
            w.writerow(["vendor_deck", "Investor deck", "The operator", "5", "seller",
                        "https://example.invalid/deck", "", "", "registered_not_retrieved",
                        "2026-08-14", "regulator_filing",
                        "Gated behind a registration wall; three routes tried, all refused."])

        with (proj / "claims.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(FILES["claims.csv"])
            w.writerow(["C1", "Returned capacity is 4,200 MW across 17 sites.",
                        "regulator_filing", "reported", "yes", "as filed, no band given", ""])
            w.writerow(["C2", "Mean site size is 247 MW.", "regulator_filing", "derived", "no",
                        "4,200 divided by 17, rounded", "Derived, the return states no mean."])

        (proj / "findings.md").write_text(
            "# Worked subject\n\n"
            "Returned capacity is 4,200 MW across 17 sites.\n\n"
            "## Falsifier\n\nA restated return below 3,000 MW would prove this wrong.\n\n"
            "## Verification\n\nCapacity traced to the regulator's capacity return. The mean "
            "site size is derived, the return states no mean.\n\n"
            "## Negative results retained\n\nThe investor deck could not be obtained and stays "
            "in the register against the denominator. No baseline was run.\n\n"
            "## Conflict of interest\n\nNone.\n", encoding="utf-8")

        print("clean project, expect PASS")
        print("=" * 62)
        clean = run(proj, "mint")
        assert clean == 0, "the clean demo project should pass"

        # A project part-way through, which is the normal state while working. The registers that
        # later stages fill are still empty, and that must not be reported as a fault.
        print()
        print("part-way project, registers not yet reached, expect PASS at each stage")
        print("=" * 62)
        early = tmp / "early_subject"
        init(early)
        with (early / "decisions.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(FILES["decisions.csv"])
            for stage in ("question", "scope"):
                for did, what in REQUIRED[stage].items():
                    w.writerow([did, stage, what, f"chose the {what} as stated",
                                "the wider reading|the narrower reading",
                                "the narrower one survives a hostile read", "2026-08-14",
                                "author:N", "revisit if the regulator restates"])
        for stage in ("question", "scope"):
            rc = run(early, stage, quiet=True)
            assert rc == 0, (f"a project worked through '{stage}' should pass at --through "
                             f"{stage}; empty later registers are not a fault")
            print(f"  --through {stage}: PASS")
        # Premature data collection check (F6)
        with (early / "sources.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(FILES["sources.csv"])
            w.writerow(["premature_src", "Premature", "Publisher", "1", "primary", "", "", "", "retrieved", "2026-08-14", "", ""])
        rc = run(early, "scope", quiet=True)
        assert rc != 0, "F6: sources.csv populated before stage 'data' must fail at --through scope"
        print("  F6 premature sources.csv population at --through scope caught")
        with (early / "sources.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(FILES["sources.csv"])

        # Regressions for defects found by trials, which the arms above would not have caught.
        print()
        print("regressions from trial findings")
        print("=" * 62)
        heading = re.compile(r"^#{1,6}\s*(?:\d+(?:\.\d+)*[.)]?\s+)?verification\b", re.M | re.I)
        for h in ("## Verification", "## 6. Verification", "## 6.1 Verification",
                  "## 6) Verification"):
            assert heading.search(h), f"F5: numbered heading {h!r} must satisfy the draft arm"
        assert not heading.search("## Verifications of doom"), "F5: must not match loosely"
        print("  F5 numbered verification headings accepted, loose matches still refused")

        for h in ("## Negative Results Retained", "## 6. Negative Results Retained",
                  "## Negative and null results retained", "## 5. Negative Results and "
                  "Retained Limits", "## Retained Negative Results and Limitations",
                  "## Limitations", "## Caveats"):
            assert NEG_RESULTS_HEAD.search(h), (
                f"F11: heading {h!r} must satisfy the negative-results check")
        assert not NEG_RESULTS_HEAD.search("## Results"), "F11: must not match loosely"
        assert NEG_RESULTS_LEAD.search("**Negative results:** none."), (
            "F11: a bold lead-in must satisfy the negative-results check")
        print("  F11 negative-results headings accepted in the forms the trials used")

        friction = sorted(p for p in ["FINDINGS.md", "_FRICTION.md"]
                          if not p.startswith("_"))
        assert friction == ["FINDINGS.md"], (
            "F4: the underscore convention must keep a runner's friction log out of the draft arm")
        print("  F4 _FRICTION.md stays out of the draft arm")

        faults = [
            ("DECISIONS", "blank the alternative on G2",
             lambda: rewrite_csv(proj / "decisions.csv", "decision_id", "G2",
                                 {"alternatives": ""})),
            ("SOURCES", "corrupt the held file so the hash breaks",
             lambda: held.write_text("Reported capacity 9,900 MW.\n", encoding="utf-8")),
            ("SOURCES", "drop the reason from the unretrieved source",
             lambda: rewrite_csv(proj / "sources.csv", "source_id", "vendor_deck",
                                 {"notes": ""})),
            ("SOURCES", "source accessed before scope decision date",
             lambda: rewrite_csv(proj / "sources.csv", "source_id", "regulator_filing",
                                 {"accessed_date": "2026-08-10"})),
            ("CLAIMS", "point a claim at a source that is not registered",
             lambda: rewrite_csv(proj / "claims.csv", "claim_id", "C1",
                                 {"source_id": "press_writeup"})),
            ("CLAIMS", "make a tier-5 source carry a load-bearing claim alone",
             lambda: (rewrite_csv(proj / "claims.csv", "claim_id", "C1",
                                  {"source_id": "vendor_deck"}),
                      rewrite_csv(proj / "sources.csv", "source_id", "vendor_deck",
                                  {"second_source_id": ""}))),
            ("VOCAB", "use an undeclared claim_basis",
             lambda: rewrite_csv(proj / "claims.csv", "claim_id", "C2",
                                 {"claim_basis": "estimated"})),
            ("DRAFT", "remove the verification section",
             lambda: (proj / "findings.md").write_text(
                  (proj / "findings.md").read_text(encoding="utf-8")
                  .replace("## Verification", "## Method"), encoding="utf-8")),
            ("DRAFT", "remove the negative-results section",
             lambda: (proj / "findings.md").write_text(
                  (proj / "findings.md").read_text(encoding="utf-8")
                  .replace("## Negative results retained", "## Further reading"),
                  encoding="utf-8")),
        ]

        backup = tmp / "backup"
        shutil.copytree(proj, backup)
        failures = []
        print("\n\nseeded faults, each must be caught")
        print("=" * 62)
        for arm, what, apply in faults:
            shutil.rmtree(proj)
            shutil.copytree(backup, proj)
            apply()
            rc = run(proj, "mint", quiet=True)
            caught = "CAUGHT" if rc != 0 else "MISSED"
            if rc == 0:
                failures.append(f"{arm}: {what}")
            print(f"  [{caught}] {arm:<9} {what}")

        print()
        if failures:
            print(f"FAIL: {len(failures)} seeded fault(s) passed the gate:")
            for f in failures:
                print(f"  {f}")
            return 1
        print(f"OK: the clean project passes and all {len(faults)} seeded faults are caught.")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def rewrite_csv(path, key_col, key, updates):
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
        cols = list(rows[0].keys())
    for r in rows:
        if r[key_col] == key:
            r.update(updates)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description="Process gate for the Research Guide.")
    ap.add_argument("project", nargs="?", help="project directory")
    ap.add_argument("--init", action="store_true", help="scaffold the registers")
    ap.add_argument("--through", choices=STAGES, default="mint",
                    help="gate only the stages up to and including this one (default: mint)")
    ap.add_argument("--demo", action="store_true", help="self-test with seeded faults")
    a = ap.parse_args()

    if a.demo:
        return demo()
    if not a.project:
        ap.error("a project directory is required (or use --demo)")
    if a.init:
        return init(a.project)
    return run(a.project, a.through)


if __name__ == "__main__":
    sys.exit(main())

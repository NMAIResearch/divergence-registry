#!/usr/bin/env python3
"""Independent scratch regressions for Divergence Register manifest and contract controls.

The v0.2 cases cover the manifest binding. The v0.3 cases cover decision attribution, source
independence, the bounded feasibility route and the decision-digest-bound scope coherence review.
Every fixture here is constructed by this file rather than by the gate's own --demo helpers, so a
defect in one builder cannot hide the same defect in the other.

Every invalid fixture names the arm that must reject it, and the verdict checks that arm as well as
the exit code. Without that, a fixture that trips an unrelated manifest or schema fault exits
non-zero and is counted as caught while the control it was written for has never run.
"""

import contextlib
import csv
import hashlib
import importlib.util
import io
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TOOL_FILES = (
    "research_gate.py",
    "DIVERGENCE_PROTOCOL.md",
    "agp_deterministic.py",
    "instrument_manifest.json",
)


def load_gate(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RG = load_gate(REPO / "research_gate.py", "research_gate_audit")


def build_clean(root, contract="v0.2"):
    with contextlib.redirect_stdout(io.StringIO()):
        RG.init(root, contract=contract)
    schema = RG.CONTRACT_V0_2 if contract == "v0.2" else RG.CONTRACT_V0_1
    held = root / "sources" / "official.txt"
    held.write_text("Reported population 17.\n", encoding="utf-8")
    digest = hashlib.sha256(held.read_bytes()).hexdigest()

    with (root / "decisions.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(RG.FILES["decisions.csv"])
        for stage in RG.STAGES:
            for decision_id, question in schema[stage].items():
                writer.writerow([
                    decision_id,
                    stage,
                    question,
                    f"chosen {question}",
                    "wider rule|narrower rule",
                    "the stated boundary is reproducible",
                    "2026-08-14",
                    "author:N",
                    "revisit if the source changes",
                ])

    with (root / "sources.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(RG.file_columns("sources.csv", contract))
        writer.writerow([
            "official",
            "Official record",
            "Regulator",
            "1",
            "primary",
            "https://example.invalid/official",
            "sources/official.txt",
            digest,
            "retrieved",
            "2026-08-14",
            "",
            "held locally",
        ])

    with (root / "claims.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(RG.file_columns("claims.csv", contract))
        writer.writerow([
            "C1",
            "Reported population is 17.",
            "official",
            "reported",
            "yes",
            "as recorded",
            "",
        ])

    (root / "findings.md").write_text(
        "# Scratch finding\n\n"
        "Reported population is 17.\n\n"
        "## Falsifier\n\nA revised official record would disconfirm this.\n\n"
        "## Verification\n\nThe value was traced to the held official record.\n\n"
        "## Negative results retained\n\nNone. No baseline was run.\n\n"
        "## Conflict of interest\n\nNone.\n",
        encoding="utf-8",
    )


# An arm-prefixed error line in the printed report. FAIL and PASS are the report's own headers.
ARM_LINE = re.compile(r"^(?!FAIL:|PASS:)[A-Z_]+: ")


def quiet_run(root, contract=None):
    """Gate a project in-process and return (exit code, the arm-prefixed errors it raised).

    The errors come back with the code because an exit code alone cannot say which rule fired. A
    fixture that trips an unrelated manifest or schema fault exits non-zero without testing the
    control it was written for, and would otherwise be counted as caught.
    """
    report, _ = RG.evaluate(root, "mint", contract=contract)
    return (1 if report.errors else 0), list(report.errors)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def copy_tools(root):
    root.mkdir(parents=True)
    for filename in TOOL_FILES:
        shutil.copy2(REPO / filename, root / filename)
    shutil.copytree(REPO / "_frozen_instruments", root / "_frozen_instruments")


def cli_run(tool_dir, project, contract=None):
    """Gate a project through a separate toolchain copy, returning (exit code, arm-prefixed errors).

    A mutated toolchain has to run out of process, so the arms are recovered from the printed
    report rather than from a Report object.
    """
    command = ["python3", str(tool_dir / "research_gate.py"), str(project)]
    if contract:
        command.extend(["--contract", contract])
    return cli_result(subprocess.run(command, text=True, capture_output=True, check=False))


def cli_result(proc):
    errors = [line.strip() for line in proc.stdout.splitlines()
              if ARM_LINE.match(line.strip())]
    return proc.returncode, errors


def rows(path):
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_rows(path, fieldnames, data):
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)


AUDIT_RUNNER = "audit-runner:model-q harness:pytest run:audit-1"
AUDIT_REVIEWER = "audit-reviewer:model-r harness:pytest run:audit-2"
SCOPE_CLOSE = "2026-08-14"
PROBE_DATE = "2026-08-11"


def build_v03(root, runner=AUDIT_RUNNER, reviewer=AUDIT_REVIEWER, review_date=SCOPE_CLOSE):
    """A v0.3 fixture built here, not by the gate's demo helpers."""
    with contextlib.redirect_stdout(io.StringIO()):
        RG.init(root, contract="v0.3")

    held = root / "sources" / "record.txt"
    held.write_text("Register lists 31 entities.\n", encoding="utf-8")
    held_digest = hashlib.sha256(held.read_bytes()).hexdigest()

    sample = root / "sources" / "probe_sample.txt"
    sample.write_text("head of the export\n", encoding="utf-8")
    sample_digest = hashlib.sha256(sample.read_bytes()).hexdigest()

    release = root / "sources" / "release.txt"
    release.write_text("The operator states 31 entities were admitted.\n", encoding="utf-8")
    release_digest = hashlib.sha256(release.read_bytes()).hexdigest()

    audit = root / "sources" / "audit.txt"
    audit.write_text("Audit confirms 31 admitted entities.\n", encoding="utf-8")
    audit_digest = hashlib.sha256(audit.read_bytes()).hexdigest()

    with (root / "decisions.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(RG.FILES["decisions.csv"])
        for stage in RG.STAGES:
            for decision_id, question in RG.CONTRACT_V0_3[stage].items():
                writer.writerow([
                    decision_id, stage, question, f"chosen {question}",
                    "wider rule|narrower rule", "the stated boundary is reproducible",
                    SCOPE_CLOSE, runner, "revisit if the source changes",
                ])

    probes = [
        ["P1", "public register", "source_exists", "https://example.invalid/reg", PROBE_DATE,
         "available", "index page", "", "", "", "", "", "", runner, "Reachable."],
        ["P2", "public register", "bytes_retrievable", "https://example.invalid/reg", PROBE_DATE,
         "available", "export endpoint", "sources/probe_sample.txt", sample_digest,
         "", "", "", "", runner, "Sample held."],
        ["P3", "public register", "period_and_retention", "https://example.invalid/reg",
         PROBE_DATE, "available", "retention note", "", "", "2020-01-01 to 2026-07-31",
         "prior editions retained", "", "", runner, "Stated on the page."],
        ["P4", "public register", "derivation_independence", "https://example.invalid/method",
         PROBE_DATE, "available", "methodology note", "", "", "", "", "no", "", runner,
         "Compiled independently of the subject."],
        ["P5", "public register", "population_coverage", "https://example.invalid/scope",
         PROBE_DATE, "available", "scope note", "", "", "", "", "", "yes", runner,
         "Covers the proposed population."],
    ]
    with (root / "feasibility.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(RG.file_columns("feasibility.csv", "v0.3"))
        writer.writerows(probes)

    with (root / "sources.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(RG.file_columns("sources.csv", "v0.3"))
        writer.writerow([
            "record", "Public register", "Regulator", "1",
            "authoritative for what the register records",
            "https://example.invalid/reg", "sources/record.txt", held_digest, "retrieved",
            SCOPE_CLOSE, "", "", "held locally",
        ])
        # An interested source and an unrelated audit of the same fact, so the claim-level
        # corroboration rule is exercised on the passing path as well as by seeded faults.
        writer.writerow([
            "release", "Operator release", "The operator", "5",
            "authoritative only for what the operator asserted",
            "https://example.invalid/release", "sources/release.txt", release_digest, "retrieved",
            SCOPE_CLOSE, "", "", "held locally",
        ])
        writer.writerow([
            "audit", "Independent audit", "An audit body", "2",
            "authoritative for the totals it verified",
            "https://example.invalid/audit", "sources/audit.txt", audit_digest, "retrieved",
            SCOPE_CLOSE, "", "", "held locally",
        ])

    with (root / "claims.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(RG.file_columns("claims.csv", "v0.3"))
        writer.writerow([
            "C1", "The register lists 31 entities.", "record", "reported", "yes",
            "as recorded", "", "",
        ])
        writer.writerow([
            "C2", "The operator states 31 entities were admitted.", "release", "reported", "yes",
            "as stated", "audit", "Tier 5 primary, corroborated on this row.",
        ])

    write_review(root, reviewer=reviewer, review_date=review_date)
    write_approval(root)

    (root / "findings.md").write_text(
        "# Scratch v0.3 finding\n\n"
        "The register lists 31 entities.\n\n"
        "## Falsifier\n\nA revised register would disconfirm this.\n\n"
        "## Verification\n\nThe value was traced to the held register record.\n\n"
        "## Negative results retained\n\nNone. No baseline was run.\n\n"
        "## Conflict of interest\n\nNone.\n",
        encoding="utf-8",
    )


def write_review(root, reviewer, review_date, checks=None, digests=None):
    by_id = {(r.get("decision_id") or "").strip().upper(): r for r in rows(root / "decisions.csv")}
    block = digests or {
        did: RG.decision_row_digest(by_id[did]) for did in RG.SCOPE_REVIEW_DECISIONS
    }
    write_json(root / RG.SCOPE_REVIEW_FILE, {
        "record_type": RG.SCOPE_REVIEW_RECORD_TYPE,
        "schema_version": RG.SCOPE_REVIEW_SCHEMA_VERSION,
        "contract": "v0.3",
        "reviewer": reviewer,
        "review_date": review_date,
        "reviewed_decisions": block,
        "checks": checks or {
            name: {"result": "pass", "note": f"Reviewed: {question}"}
            for name, question in RG.SCOPE_REVIEW_CHECKS.items()
        },
    })


def write_approval(root, approved_by=RG.SCOPE_APPROVAL_AUTHORITY, approval_date=SCOPE_CLOSE,
                   decision=RG.SCOPE_APPROVAL_OPENS, accepted=None,
                   reference=("Scratch fixture, standing for the decision of 2026-08-14 recorded "
                              "in handoffs/audit_approval.md"),
                   bound=None):
    """The retained human approval, built here rather than by the gate's demo helpers."""
    write_json(root / RG.SCOPE_APPROVAL_FILE, {
        "record_type": RG.SCOPE_APPROVAL_RECORD_TYPE,
        "schema_version": RG.SCOPE_APPROVAL_SCHEMA_VERSION,
        "contract": "v0.3",
        "approved_by": approved_by,
        "approval_date": approval_date,
        "decision": decision,
        "accepted_checks": list(accepted or []),
        "approval_reference": reference,
        "bound_files": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in RG.SCOPE_APPROVAL_BOUND_FILES
        } if bound is None else bound,
    })


def review_with(root, check, result, note):
    """Rewrite the review with one check recorded as fail or unresolved."""
    checks = {name: {"result": "pass", "note": f"Reviewed: {question}"}
              for name, question in RG.SCOPE_REVIEW_CHECKS.items()}
    checks[check] = {"result": result, "note": note}
    write_review(root, reviewer=AUDIT_REVIEWER, review_date=SCOPE_CLOSE, checks=checks)


def v03_cases(scratch, results):
    """Each case builds its own fixture, then asserts the exit and the arm that produced it."""
    def case(name, arm, mutate=None):
        root = scratch / f"v03_{len(results):02d}_{name.replace(' ', '_')[:40]}"
        build_v03(root)
        if mutate:
            mutate(root)
        observed, errors = quiet_run(root, "v0.3")
        record(results, f"v0.3: {name}", arm, observed, errors, want_fail=arm is not None)

    case("clean fixture passes", None)

    case("blank decided_by", "DECISIONS", lambda r: set_decision(r, "Q1", {"decided_by": ""}))
    case("whitespace-only decided_by", "DECISIONS",
         lambda r: set_decision(r, "S2", {"decided_by": "   "}))
    case("placeholder decided_by", "DECISIONS",
         lambda r: set_decision(r, "D1", {"decided_by": "n/a"}))

    case("feasibility register deleted", "FEASIBILITY",
         lambda r: (r / "feasibility.csv").unlink())
    case("feasibility register emptied", "FEASIBILITY",
         lambda r: empty_register(r, "feasibility.csv"))
    case("two feasibility questions unprobed", "FEASIBILITY",
         lambda r: drop_probes(r, {"P4", "P5"}))
    case("outcome value in the result field", "FEASIBILITY",
         lambda r: set_probe(r, "P1", {"result": "31 entities counted"}))
    case("outcome column added to the register", "FEASIBILITY",
         lambda r: add_column(r / "feasibility.csv", "entity_count", "31"))
    case("probe dated after scope closed", "FEASIBILITY",
         lambda r: set_probe(r, "P3", {"access_date": "2026-08-15"}))
    case("probe bytes altered after hashing", "FEASIBILITY",
         lambda r: (r / "sources" / "probe_sample.txt").write_text("tampered\n", encoding="utf-8"))
    case("probe claims custody with no bytes", "FEASIBILITY",
         lambda r: set_probe(r, "P2", {"local_path": "", "sha256": ""}))
    case("probe with no attribution", "FEASIBILITY",
         lambda r: set_probe(r, "P5", {"probed_by": ""}))
    case("restricted route with no reason", "FEASIBILITY",
         lambda r: set_probe(r, "P1", {"result": "restricted", "notes": ""}))
    case("circular derivation left unanswered", "FEASIBILITY",
         lambda r: set_probe(r, "P4", {"derives_from_subject": ""}))

    case("scope review absent", "SCOPE_REVIEW", lambda r: (r / RG.SCOPE_REVIEW_FILE).unlink())
    case("scope review unparseable", "SCOPE_REVIEW",
         lambda r: (r / RG.SCOPE_REVIEW_FILE).write_text("not json", encoding="utf-8"))
    case("scope review with no reviewer", "SCOPE_REVIEW",
         lambda r: write_review(r, reviewer="", review_date=SCOPE_CLOSE))
    case("runner reviews its own scope", "SCOPE_REVIEW",
         lambda r: write_review(r, reviewer=AUDIT_RUNNER, review_date=SCOPE_CLOSE))
    case("self-review disguised by case and spacing", "SCOPE_REVIEW",
         lambda r: write_review(r, reviewer="  AUDIT-RUNNER:MODEL-Q   HARNESS:PYTEST run:audit-1 ",
                                review_date=SCOPE_CLOSE))
    case("self-review disguised by respelled punctuation", "SCOPE_REVIEW",
         lambda r: write_review(r, reviewer="Audit Runner: Model Q, harness pytest, run audit 1",
                                review_date=SCOPE_CLOSE))
    case("reviewed decision edited after review", "SCOPE_REVIEW",
         lambda r: set_decision(r, "S3", {"chosen": "a different vintage policy"}))
    case("reviewed decision re-dated after review", "SCOPE_REVIEW",
         lambda r: set_decision(r, "S4", {"decided_date": "2026-08-13"}))
    case("digest replaced with a plausible constant", "SCOPE_REVIEW",
         lambda r: patch_json(r / RG.SCOPE_REVIEW_FILE, ["reviewed_decisions", "S1"], "a" * 64))
    case("reviewed decision id omitted", "SCOPE_REVIEW",
         lambda r: pop_json(r / RG.SCOPE_REVIEW_FILE, ["reviewed_decisions", "Q2"]))
    case("coherence check omitted", "SCOPE_REVIEW",
         lambda r: pop_json(r / RG.SCOPE_REVIEW_FILE, ["checks", "s6_matches_population_window"]))
    case("failed check the approval does not accept", "SCOPE_APPROVAL",
         lambda r: patch_json(r / RG.SCOPE_REVIEW_FILE, ["checks", "s4_tests_sufficiency"],
                              {"result": "fail", "note": "S4 suppresses a falsifying result."}))
    case("unresolved check the approval does not accept", "SCOPE_APPROVAL",
         lambda r: patch_json(r / RG.SCOPE_REVIEW_FILE, ["checks", "q3_disconfirms_q2"],
                              {"result": "unresolved", "note": "Interval left open."}))
    # Acceptance inside the review is refused rather than ignored, because a reviewer wrote its
    # own name there and cleared its own finding.
    case("exception accepted inside the review record", "SCOPE_REVIEW",
         lambda r: patch_json(r / RG.SCOPE_REVIEW_FILE, ["checks", "s4_tests_sufficiency"],
                              {"result": "fail", "note": "S4 suppresses a falsifying result.",
                               "exception_accepted_by": "author:N"}))
    case("review predates the decisions it reviews", "SCOPE_REVIEW",
         lambda r: write_review(r, reviewer=AUDIT_REVIEWER, review_date="2026-08-01"))
    case("reviewer that normalises to nothing", "SCOPE_REVIEW",
         lambda r: write_review(r, reviewer="!!!", review_date=SCOPE_CLOSE))
    case("decided_by that normalises to nothing", "DECISIONS",
         lambda r: set_decision(r, "S1", {"decided_by": "!!!"}))
    case("probed_by that normalises to nothing", "FEASIBILITY",
         lambda r: set_probe(r, "P4", {"probed_by": "***"}))

    case("scope approval absent", "SCOPE_APPROVAL",
         lambda r: (r / RG.SCOPE_APPROVAL_FILE).unlink())
    case("scope approval unparseable", "SCOPE_APPROVAL",
         lambda r: (r / RG.SCOPE_APPROVAL_FILE).write_text("not json", encoding="utf-8"))
    case("approval recorded by the reviewer", "SCOPE_APPROVAL",
         lambda r: write_approval(r, approved_by=AUDIT_REVIEWER))
    case("approval recorded by the runner", "SCOPE_APPROVAL",
         lambda r: write_approval(r, approved_by=AUDIT_RUNNER))
    case("approval decision held", "SCOPE_APPROVAL",
         lambda r: write_approval(r, decision="hold"))
    case("approval decision outside the closed set", "SCOPE_APPROVAL",
         lambda r: write_approval(r, decision="signed off"))
    case("approval with no reference", "SCOPE_APPROVAL",
         lambda r: write_approval(r, reference=""))
    case("approval predating the review", "SCOPE_APPROVAL",
         lambda r: write_approval(r, approval_date="2026-08-01"))
    case("approval binding a digest that is not a digest", "SCOPE_APPROVAL",
         lambda r: patch_json(r / RG.SCOPE_APPROVAL_FILE, ["bound_files", "decisions.csv"],
                              "not-a-digest"))
    case("approval carried past an edit to a bound register", "SCOPE_APPROVAL",
         lambda r: set_probe(r, "P1", {"notes": "Reachable, rechecked after approval."}))
    case("approval accepting a check the review did not fail", "SCOPE_APPROVAL",
         lambda r: write_approval(r, accepted=["q3_disconfirms_q2"]))
    case("approval accepting something that is not a check", "SCOPE_APPROVAL",
         lambda r: write_approval(r, accepted=["looks_fine_to_me"]))
    case("approval omitting the exception the review recorded", "SCOPE_APPROVAL",
         lambda r: (review_with(r, "q3_disconfirms_q2", "unresolved", "Interval left open."),
                    write_approval(r, accepted=[])))
    # The full exception path, end to end: the reviewer records what it found, the researcher
    # accepts exactly that, and the approval still binds to the bytes.
    case("an exception accepted in the approval record passes", None,
         lambda r: (review_with(r, "q3_disconfirms_q2", "unresolved", "Interval left open."),
                    write_approval(r, accepted=["q3_disconfirms_q2"])))

    case("blank source_role", "SOURCES",
         lambda r: set_source(r, "record", {"source_role": ""}))
    case("a mirror offered as an independent second source", "SOURCES", mirror_second_source)
    case("a two-hop ancestor offered as an independent second source", "SOURCES",
         lambda r: chained_second_source(r, "syndication", "record"))
    case("a two-hop derivative offered as an independent second source", "SOURCES",
         lambda r: chained_second_source(r, "record", "syndication"))
    case("two mirrors of one disclosure seconding each other", "SOURCES", shared_origin_pair)
    case("a derivation loop with no origin", "SOURCES", derivation_loop)
    case("accessed_date that is not an ISO date", "SOURCES",
         lambda r: set_source(r, "record", {"accessed_date": "sometime last week"}))
    case("source accessed before the final scope decision", "SOURCES", late_scope_source)
    case("a source with no title", "SOURCES", lambda r: set_source(r, "release", {"title": ""}))
    case("a source with no publisher", "SOURCES",
         lambda r: set_source(r, "release", {"publisher": ""}))
    case("a source with neither url nor local_path", "SOURCES",
         lambda r: set_source(r, "release", {"url": "", "local_path": "", "sha256": "",
                                             "retrieval_status": "cited_not_held"}))

    case("a claim grounded in an unobtained source", "CLAIMS",
         lambda r: (set_source(r, "audit", {"retrieval_status": "registered_not_retrieved",
                                            "local_path": "", "sha256": "",
                                            "notes": "Withdrawn before retrieval."}),
                    set_claim(r, "C1", {"source_id": "audit"})))
    case("a material tier-5 claim with no corroborating source", "CLAIMS",
         lambda r: set_claim(r, "C2", {"corroborating_source_id": ""}))
    case("a source-level second source standing in for the claim", "CLAIMS",
         lambda r: (set_source(r, "release", {"second_source_id": "audit"}),
                    set_claim(r, "C2", {"corroborating_source_id": ""})))
    case("a corroborating source that is not registered", "CLAIMS",
         lambda r: set_claim(r, "C2", {"corroborating_source_id": "nowhere"}))
    case("a claim corroborated by its own source", "CLAIMS",
         lambda r: set_claim(r, "C2", {"corroborating_source_id": "release"}))
    case("a corroborating source at motive tier 5", "CLAIMS", tier_five_corroborator)
    case("a corroborating source nobody obtained", "CLAIMS",
         lambda r: set_source(r, "audit", {"retrieval_status": "registered_not_retrieved",
                                           "local_path": "", "sha256": "",
                                           "notes": "Withdrawn before retrieval."}))
    case("a corroborating source sharing the primary source's origin", "CLAIMS",
         lambda r: (set_source(r, "release", {"derived_from": "record"}),
                    set_source(r, "audit", {"derived_from": "record"})))

    case("a v0.3 claims register with no corroboration column", "MANIFEST",
         lambda r: drop_column(r / "claims.csv", "corroborating_source_id"))
    case("a claim row with no claim_id", "CLAIMS",
         lambda r: set_claim(r, "C1", {"claim_id": ""}))
    case("a placeholder claim_id", "CLAIMS",
         lambda r: set_claim(r, "C1", {"claim_id": "TBD"}))
    case("a claim_id already used by another row", "CLAIMS",
         lambda r: set_claim(r, "C2", {"claim_id": "C1"}))
    case("a claim row with no claim_text", "CLAIMS",
         lambda r: set_claim(r, "C1", {"claim_text": ""}))
    case("a placeholder claim_text", "CLAIMS",
         lambda r: set_claim(r, "C1", {"claim_text": "n/a"}))

    # Punctuation is neither blank nor a placeholder word, so every field required to carry
    # content is tested with a value that passes both of those checks and still says nothing.
    case("a punctuation-only claim_id", "CLAIMS",
         lambda r: set_claim(r, "C1", {"claim_id": "!!!"}))
    case("a punctuation-only claim_text", "CLAIMS",
         lambda r: set_claim(r, "C1", {"claim_text": "***"}))
    case("a punctuation-only source title", "SOURCES",
         lambda r: set_source(r, "release", {"title": "!!!"}))
    case("a punctuation-only source publisher", "SOURCES",
         lambda r: set_source(r, "release", {"publisher": "---"}))
    case("a punctuation-only url as the only locator", "SOURCES", punctuation_locator)
    case("a url with no scheme as the only locator", "SOURCES",
         lambda r: cited_locator(r, "example.invalid/release"))
    case("a url under a disallowed scheme as the only locator", "SOURCES",
         lambda r: cited_locator(r, "file:///etc/passwd"))
    case("a local_path naming a file absent from the project", "SOURCES",
         lambda r: set_source(r, "release", {"retrieval_status": "cited_not_held", "url": "",
                                             "local_path": "sources/never_written.txt",
                                             "sha256": ""}))
    case("an unreachable corroborator seen by the source register", "SOURCES",
         lambda r: cited_locator(r, "!!!", source_id="audit"))
    # Same mutation, different rule. The claim arm establishes that this claim's second source is
    # reachable rather than relying on SOURCES to have noticed on the register's behalf.
    case("a material tier-5 claim leaning on an unreachable corroborator", "CLAIMS",
         lambda r: cited_locator(r, "!!!", source_id="audit"))

    case("a punctuation-only approval reference", "SCOPE_APPROVAL",
         lambda r: write_approval(r, reference="!!!"))
    case("an approval reference with no date", "SCOPE_APPROVAL",
         lambda r: write_approval(r, reference="the decision in handoffs/audit_approval.md"))
    case("an approval reference with no retrievable route", "SCOPE_APPROVAL",
         lambda r: write_approval(r, reference="the user approved this on 2026-08-14"))
    case("an approval reference dated 2026-02-30", "SCOPE_APPROVAL",
         lambda r: write_approval(r, reference="decision of 2026-02-30 in handoffs/a.md"))

    # Every v0.3 field whose arm requires content. Bound records are rewritten after each register
    # edit, so a stale digest cannot stand in for the arm under test.
    case("punctuation-only decision 'chosen'", "DECISIONS",
         lambda r: (set_decision(r, "S2", {"chosen": "!!!"}), rebind(r)))
    case("punctuation-only decision 'rationale'", "DECISIONS",
         lambda r: (set_decision(r, "S3", {"rationale": "***"}), rebind(r)))
    case("every recorded alternative is punctuation", "DECISIONS",
         lambda r: (set_decision(r, "S4", {"alternatives": "!!!|***"}), rebind(r)))
    case("a punctuation-only source_id", "SOURCES", punctuation_source_id)
    case("a punctuation-only source_role", "SOURCES",
         lambda r: set_source(r, "release", {"source_role": "!!!"}))
    case("a punctuation-only reason for an unobtained source", "SOURCES",
         lambda r: set_source(r, "release", {"retrieval_status": "registered_not_retrieved",
                                             "local_path": "", "sha256": "", "notes": "!!!"}))
    case("a punctuation-only claim uncertainty", "CLAIMS",
         lambda r: set_claim(r, "C1", {"uncertainty": "!!!"}))
    case("a punctuation-only probe_id", "FEASIBILITY",
         lambda r: (set_probe(r, "P3", {"probe_id": "!!!"}), write_approval(r)))
    case("a punctuation-only probe source_name", "FEASIBILITY",
         lambda r: (set_probe(r, "P3", {"source_name": "!!!"}), write_approval(r)))
    case("a punctuation-only reason for an unknown probe result", "FEASIBILITY",
         lambda r: (set_probe(r, "P1", {"result": "unknown", "notes": "!!!"}), write_approval(r)))
    case("a punctuation-only stated_period", "FEASIBILITY",
         lambda r: (set_probe(r, "P3", {"stated_period": "!!!"}), write_approval(r)))
    case("a punctuation-only retention_policy", "FEASIBILITY",
         lambda r: (set_probe(r, "P3", {"retention_policy": "***"}), write_approval(r)))
    case("a probe whose only record of where it looked is punctuation", "FEASIBILITY",
         lambda r: (set_probe(r, "P1", {"url": "", "evidence_locator": "!!!"}), write_approval(r)))
    case("a punctuation-only scope review note", "SCOPE_REVIEW",
         lambda r: (review_with(r, "s2_third_party_applicable", "pass", "!!!"), write_approval(r)))

    # netloc is not a hostname: neither of these names a host at all.
    case("a url carrying a port and no host", "SOURCES",
         lambda r: cited_locator(r, "http://:80"))
    case("a url carrying user information and no host", "SOURCES",
         lambda r: cited_locator(r, "http://user@"))

    # Custody means bytes held in the project. The bytes exist in every case below, so only
    # containment can be what rejects them.
    case("a held local_path outside the project", "SOURCES",
         lambda r: set_source(r, "record", {"local_path": str(stray_bytes(r))}))
    case("a held local_path reaching out through a parent traversal", "SOURCES",
         lambda r: (stray_bytes(r),
                    set_source(r, "record", {"local_path": "../outside_the_project.txt"})))
    case("a held local_path behind a symlink resolving outside the project", "SOURCES",
         escaping_symlink)

    case("an approval reference whose route is only separators", "SCOPE_APPROVAL",
         lambda r: write_approval(r, reference="2026-08-21 ///"))
    case("an approval reference carrying a malformed url", "SCOPE_APPROVAL",
         lambda r: write_approval(r, reference="2026-08-21 http://!!!"))

    # Every recorded alternative is read, not only the first usable one. The row keeps one genuine
    # option, so nothing but the unusable token can be what fails it.
    case("a usable alternative recorded beside a punctuation-only one", "DECISIONS",
         lambda r: (set_decision(r, "S5", {"alternatives": "a real alternative|!!!"}), rebind(r)))

    # A probe that reports custody holds the bytes in the project, under the same containment
    # predicate as the source register. The bytes exist and the recorded hash matches them in all
    # three cases, so only containment can be what rejects the row.
    case("probe custody claimed on an absolute path outside the project", "FEASIBILITY",
         lambda r: escaping_probe(r, str(stray_bytes(r))))
    case("probe custody claimed through a parent traversal", "FEASIBILITY",
         lambda r: escaping_probe(r, "../outside_the_project.txt"))
    case("probe custody claimed behind a symlink resolving outside the project", "FEASIBILITY",
         escaping_probe_symlink)

    # One URL predicate governs the source register, the approval reference and the feasibility
    # evidence route, so each syntactic escape is seeded on an arm that reads it through that
    # predicate.
    case("a url containing whitespace as the only locator", "SOURCES",
         lambda r: cited_locator(r, "https://example.invalid/release a"))
    case("a url containing a backslash as the only locator", "SOURCES",
         lambda r: cited_locator(r, "https://example.invalid\\release"))
    case("a url whose port is not a number", "SOURCES",
         lambda r: cited_locator(r, "https://example.invalid:port/release"))
    case("a url whose port is out of range", "SOURCES",
         lambda r: cited_locator(r, "https://example.invalid:99999/release"))
    case("an approval reference whose url carries a malformed port", "SCOPE_APPROVAL",
         lambda r: write_approval(
             r, reference="decision of 2026-08-14 at http://example.invalid:port/approval.md"))
    case("a probe url containing whitespace, with no evidence_locator", "FEASIBILITY",
         lambda r: (set_probe(r, "P1", {"url": "https://example.invalid/reg a",
                                        "evidence_locator": ""}),
                    write_approval(r)))
    case("a source url containing an incomplete percent escape", "SOURCES",
         lambda r: cited_locator(r, "https://%GG/"))
    case("a feasibility url containing an incomplete percent escape", "FEASIBILITY",
         lambda r: (set_probe(r, "P1", {"url": "https://%GG/", "evidence_locator": ""}),
                    write_approval(r)))
    case("an approval reference containing an incomplete percent escape", "SCOPE_APPROVAL",
         lambda r: write_approval(r, reference="decision of 2026-08-14 at https://%GG/"))

    # Fixed v0.3 records and drafts are project bytes. A symlink resolving outside the project is
    # not a self-contained register, even when the external bytes and all recorded hashes agree.
    for filename, arm in (
        ("instrument_manifest.json", "MANIFEST"),
        ("decisions.csv", "DECISIONS"),
        ("sources.csv", "SOURCES"),
        ("claims.csv", "CLAIMS"),
        ("vocabulary.csv", "VOCAB"),
        ("feasibility.csv", "FEASIBILITY"),
        (RG.SCOPE_REVIEW_FILE, "SCOPE_REVIEW"),
        (RG.SCOPE_APPROVAL_FILE, "SCOPE_APPROVAL"),
        ("findings.md", "DRAFT"),
    ):
        case(f"v0.3 {filename} resolves outside the project", arm,
             lambda r, filename=filename: external_project_file(r, filename))

    # The same containment predicate reaches the corroborator, and both arms that read it are
    # asserted. A second source held outside the project is unreachable whichever arm notices.
    case("a corroborator held through a parent traversal", "SOURCES",
         lambda r: escaping_corroborator(r, "../outside_the_project.txt"))
    case("a claim leaning on a corroborator held through a parent traversal", "CLAIMS",
         lambda r: escaping_corroborator(r, "../outside_the_project.txt"))
    case("a corroborator held behind a symlink resolving outside the project", "SOURCES",
         escaping_corroborator_symlink)
    case("a claim leaning on a corroborator behind an escaping symlink", "CLAIMS",
         escaping_corroborator_symlink)


def restatement(source_id, origin, tier="3"):
    return {
        "source_id": source_id, "title": f"Restatement {source_id}", "publisher": "Aggregator",
        "motive_tier": tier, "source_role": "restates its origin",
        "url": f"https://example.invalid/{source_id}", "local_path": "", "sha256": "",
        "retrieval_status": "cited_not_held", "accessed_date": SCOPE_CLOSE,
        "second_source_id": "", "derived_from": origin, "notes": "Byte-for-byte restatement.",
    }


def mirror_second_source(root):
    source_rows = rows(root / "sources.csv") + [restatement("mirror", "record")]
    for row in source_rows:
        if row["source_id"] == "record":
            row["second_source_id"] = "mirror"
    write_rows(root / "sources.csv", RG.file_columns("sources.csv", "v0.3"), source_rows)


def chained_second_source(root, source_id, second_source_id):
    """Build record <- mirror <- syndication, then offer one end of the chain to the other.

    Neither named source derives directly from the other, so only a walk past the first hop
    establishes that they are the same disclosure reaching the register twice.
    """
    source_rows = rows(root / "sources.csv") + [
        restatement("mirror", "record"), restatement("syndication", "mirror", tier="4"),
    ]
    for row in source_rows:
        if row["source_id"] == source_id:
            row["second_source_id"] = second_source_id
    write_rows(root / "sources.csv", RG.file_columns("sources.csv", "v0.3"), source_rows)


def shared_origin_pair(root):
    """Two restatements of one filing, each offered as the other's independent second source.

    Neither derives from the other, so both directional walks pass. Only the inclusive ancestor
    sets show that their agreement is the register's own filing arriving twice.
    """
    source_rows = rows(root / "sources.csv") + [
        restatement("mirror_a", "record"), restatement("mirror_b", "record"),
    ]
    for row in source_rows:
        if row["source_id"] == "mirror_a":
            row["second_source_id"] = "mirror_b"
    write_rows(root / "sources.csv", RG.file_columns("sources.csv", "v0.3"), source_rows)


def rebind(root):
    """Rewrite the review and the approval against the registers as they now stand.

    A fixture that edits a bound register invalidates both by hash, and a stale digest firing is a
    real control answering the wrong question.
    """
    write_review(root, reviewer=AUDIT_REVIEWER, review_date=SCOPE_CLOSE)
    write_approval(root)


def punctuation_source_id(root):
    """Rename a source to punctuation and point its claim at the new value."""
    set_source(root, "record", {"source_id": "!!!"})
    set_claim(root, "C1", {"source_id": "!!!"})


def stray_bytes(root):
    """Write real bytes just outside the project and return the path."""
    outside = Path(root).parent / "outside_the_project.txt"
    outside.write_text("Register lists 31 entities.\n", encoding="utf-8")
    return outside


def external_project_file(root, name):
    """Replace one v0.3 project record with a symlink to identical bytes outside the project."""
    root = Path(root)
    path = root / name
    outside = root.parent / f"outside_{name.replace('/', '_')}"
    outside.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(outside)


def escaping_symlink(root):
    """Hold a source through a symlink inside the project that resolves outside it."""
    outside = stray_bytes(root)
    link = Path(root) / "sources" / "escape.txt"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(outside)
    set_source(root, "record", {"local_path": "sources/escape.txt"})


def escaping_probe(root, local_path):
    """Point the custody probe at real bytes outside the project, hash and all.

    The recorded hash is taken from the file the path reaches, so the row is refused for where the
    bytes live rather than for disagreeing with the register.
    """
    outside = stray_bytes(root)
    set_probe(root, "P2", {"local_path": local_path,
                           "sha256": hashlib.sha256(outside.read_bytes()).hexdigest()})
    write_approval(root)


def escaping_probe_symlink(root):
    """Hold probe bytes through a symlink inside the project that resolves outside it."""
    link = Path(root) / "sources" / "probe_escape.txt"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(stray_bytes(root))
    escaping_probe(root, "sources/probe_escape.txt")


def escaping_corroborator(root, local_path):
    """Hold the corroborating source outside the project, hash and all.

    The url column is cleared, so the escaping path is the only route the row claims and the claim
    that leans on it has nothing reachable to lean on.
    """
    outside = stray_bytes(root)
    set_source(root, "audit", {"url": "", "local_path": local_path,
                               "sha256": hashlib.sha256(outside.read_bytes()).hexdigest()})


def escaping_corroborator_symlink(root):
    """Hold the corroborating source through a symlink that resolves outside the project."""
    link = Path(root) / "sources" / "corroborator_escape.txt"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(stray_bytes(root))
    escaping_corroborator(root, "sources/corroborator_escape.txt")


def cited_locator(root, url, source_id="release"):
    """Cite a source without custody, so the recorded URL is the only route a reader has."""
    set_source(root, source_id, {"retrieval_status": "cited_not_held", "url": url,
                                 "local_path": "", "sha256": ""})


def punctuation_locator(root):
    cited_locator(root, "!!!")


def tier_five_corroborator(root):
    """Corroborate an interested claim with a second interested source, held and unrelated.

    Custody and derivation are both clean here, so only the motive-tier rule can reject the pair.
    """
    set_source(root, "audit", {"motive_tier": "5",
                               "source_role": "authoritative only for what its publisher asserted"})


def derivation_loop(root):
    source_rows = rows(root / "sources.csv") + [restatement("mirror", "record")]
    for row in source_rows:
        if row["source_id"] == "record":
            row["derived_from"] = "mirror"
    write_rows(root / "sources.csv", RG.file_columns("sources.csv", "v0.3"), source_rows)


def late_scope_source(root):
    """Close scope after the source was accessed, rewriting the review so only SOURCES can fire."""
    set_decision(root, "S6", {"decided_date": "2026-08-20"})
    write_review(root, reviewer=AUDIT_REVIEWER, review_date="2026-08-20")


def set_decision(root, decision_id, updates):
    data = rows(root / "decisions.csv")
    for row in data:
        if row["decision_id"] == decision_id:
            row.update(updates)
    write_rows(root / "decisions.csv", RG.FILES["decisions.csv"], data)


def set_source(root, source_id, updates):
    data = rows(root / "sources.csv")
    for row in data:
        if row["source_id"] == source_id:
            row.update(updates)
    write_rows(root / "sources.csv", RG.file_columns("sources.csv", "v0.3"), data)


def set_claim(root, claim_id, updates):
    data = rows(root / "claims.csv")
    for row in data:
        if row["claim_id"] == claim_id:
            row.update(updates)
    write_rows(root / "claims.csv", RG.file_columns("claims.csv", "v0.3"), data)


def set_probe(root, probe_id, updates):
    data = rows(root / "feasibility.csv")
    for row in data:
        if row["probe_id"] == probe_id:
            row.update(updates)
    write_rows(root / "feasibility.csv", RG.file_columns("feasibility.csv", "v0.3"), data)


def drop_probes(root, probe_ids):
    data = [r for r in rows(root / "feasibility.csv") if r["probe_id"] not in probe_ids]
    write_rows(root / "feasibility.csv", RG.file_columns("feasibility.csv", "v0.3"), data)


def empty_register(root, name):
    with (root / name).open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerow(RG.file_columns(name, "v0.3"))


def add_column(path, column, value):
    data = rows(path)
    fieldnames = list(data[0].keys()) + [column]
    for row in data:
        row[column] = value
    write_rows(path, fieldnames, data)


def drop_column(path, column):
    data = rows(path)
    fieldnames = [c for c in data[0].keys() if c != column]
    for row in data:
        row.pop(column, None)
    write_rows(path, fieldnames, data)


def patch_json(path, key_path, value):
    data = read_json(path)
    cursor = data
    for key in key_path[:-1]:
        cursor = cursor[key]
    cursor[key_path[-1]] = value
    write_json(path, data)


def pop_json(path, key_path):
    data = read_json(path)
    cursor = data
    for key in key_path[:-1]:
        cursor = cursor[key]
    cursor.pop(key_path[-1], None)
    write_json(path, data)


def record(results, case, arm, observed, errors, want_fail=True):
    """Bank one fixture with the arm it was written to test, so the verdict can check both."""
    results.append((case, arm, observed, errors, want_fail))


def verdict_for(arm, observed, errors, want_fail):
    """Return (verdict, is_defect). A non-zero exit off the named arm is not a catch."""
    if not want_fail:
        return ("PASSES", False) if observed == 0 else ("REGRESSION", True)
    if observed == 0:
        return "FAIL OPEN", True
    if arm and not any(e.startswith(f"{arm}: ") for e in errors):
        return "WRONG ARM", True
    return "CAUGHT", False


def arms_fired(errors):
    seen = []
    for error in errors:
        arm = error.split(":", 1)[0]
        if arm not in seen:
            seen.append(arm)
    return ", ".join(seen) or "none"


def check_verdict_logic():
    """A harness that cannot return a defect verdict proves nothing about the fixtures it runs."""
    assert verdict_for("SOURCES", 1, ["SOURCES: mirrored"], True) == ("CAUGHT", False)
    assert verdict_for("SOURCES", 1, ["MANIFEST: stale hash"], True) == ("WRONG ARM", True)
    assert verdict_for("SOURCES", 1, [], True) == ("WRONG ARM", True)
    assert verdict_for("SOURCES", 0, [], True) == ("FAIL OPEN", True)
    assert verdict_for(None, 0, [], False) == ("PASSES", False)
    assert verdict_for(None, 1, ["SOURCES: mirrored"], False) == ("REGRESSION", True)
    assert verdict_for("SOURCE", 1, ["SOURCES: mirrored"], True) == ("WRONG ARM", True), (
        "an arm must match in full; a prefix of a longer arm name is a different arm")
    assert ARM_LINE.match("SCOPE_REVIEW: no reviewer recorded")
    assert not ARM_LINE.match("FAIL: release catalogue is not valid:")


def main():
    scratch = Path(tempfile.mkdtemp(prefix="v02_independent_audit_"))
    results = []
    check_verdict_logic()
    try:
        for filename in ("DIVERGENCE_PROTOCOL.md", "research_gate.py", "agp_deterministic.py"):
            tool_dir = scratch / f"mutated_{filename.replace('.', '_')}"
            copy_tools(tool_dir)
            project = scratch / f"project_{filename.replace('.', '_')}"
            build_clean(project)
            target = tool_dir / filename
            target.write_bytes(target.read_bytes() + b"\n# scratch byte mutation\n")
            observed, errors = cli_run(tool_dir, project)
            record(results, f"actual instrument byte mismatch: {filename}", "MANIFEST",
                   observed, errors)

        wrong_file = scratch / "wrong_file_identity"
        build_clean(wrong_file)
        binding = read_json(wrong_file / "instrument_manifest.json")
        binding["instruments"]["protocol"] = dict(binding["instruments"]["prose_checker"])
        write_json(wrong_file / "instrument_manifest.json", binding)
        record(results, "protocol binding points to prose checker", "MANIFEST",
               *quiet_run(wrong_file))

        wrong_version = scratch / "wrong_version"
        build_clean(wrong_version)
        binding = read_json(wrong_version / "instrument_manifest.json")
        binding["instruments"]["protocol"]["version"] = "unrecognised-version"
        write_json(wrong_version / "instrument_manifest.json", binding)
        record(results, "unrecognised instrument version", "MANIFEST", *quiet_run(wrong_version))

        legacy_claim_field = scratch / "legacy_claim_field_under_v02"
        build_clean(legacy_claim_field)
        claims_path = legacy_claim_field / "claims.csv"
        claims_path.write_text(
            claims_path.read_text(encoding="utf-8")
            .replace("material_to_conclusion", "load_bearing", 1),
            encoding="utf-8",
        )
        record(results, "legacy v0.1 claim field under v0.2", "MANIFEST",
               *quiet_run(legacy_claim_field))

        missing_schema = scratch / "missing_schema"
        build_clean(missing_schema)
        binding = read_json(missing_schema / "instrument_manifest.json")
        binding.pop("schema_version", None)
        write_json(missing_schema / "instrument_manifest.json", binding)
        record(results, "missing project schema version", "MANIFEST", *quiet_run(missing_schema))

        malformed_legacy = scratch / "malformed_legacy"
        build_clean(malformed_legacy, contract="v0.1")
        (malformed_legacy / "instrument_manifest.json").write_text("{malformed", encoding="utf-8")
        record(results, "malformed binding under explicit v0.1", "MANIFEST",
               *quiet_run(malformed_legacy, "v0.1"))

        mutable_contract_tools = scratch / "mutable_contract_tools"
        copy_tools(mutable_contract_tools)
        catalogue = read_json(mutable_contract_tools / "instrument_manifest.json")
        catalogue["contracts"]["v0.2"]["stages"]["scope"].pop("S6")
        write_json(mutable_contract_tools / "instrument_manifest.json", catalogue)
        mutable_contract_project = scratch / "mutable_contract_project"
        build_clean(mutable_contract_project)
        decision_rows = [r for r in rows(mutable_contract_project / "decisions.csv")
                         if r["decision_id"] != "S6"]
        write_rows(mutable_contract_project / "decisions.csv", RG.FILES["decisions.csv"], decision_rows)
        record(results, "release catalogue removes mandatory S6", "MANIFEST",
               *cli_run(mutable_contract_tools, mutable_contract_project))

        late_scope = scratch / "late_scope"
        build_clean(late_scope)
        decision_rows = rows(late_scope / "decisions.csv")
        for row in decision_rows:
            if row["decision_id"] == "S6":
                row["decided_date"] = "2026-08-20"
        write_rows(late_scope / "decisions.csv", RG.FILES["decisions.csv"], decision_rows)
        source_rows = rows(late_scope / "sources.csv")
        source_rows[0]["accessed_date"] = "2026-08-19"
        write_rows(late_scope / "sources.csv", RG.FILES["sources.csv"], source_rows)
        record(results, "source predates final scope decision S6", "SOURCES",
               *quiet_run(late_scope))

        non_iso_v02 = scratch / "non_iso_accessed_date_v02"
        build_clean(non_iso_v02)
        source_rows = rows(non_iso_v02 / "sources.csv")
        source_rows[0]["accessed_date"] = "sometime last week"
        write_rows(non_iso_v02 / "sources.csv", RG.FILES["sources.csv"], source_rows)
        record(results, "accessed_date that is not an ISO date under v0.2", "SOURCES",
               *quiet_run(non_iso_v02))

        no_catalogue_tools = scratch / "no_catalogue_tools"
        no_catalogue_tools.mkdir()
        shutil.copy2(REPO / "research_gate.py", no_catalogue_tools / "research_gate.py")
        no_catalogue_project = scratch / "no_catalogue_project"
        proc = subprocess.run(
            ["python3", str(no_catalogue_tools / "research_gate.py"), "--init", str(no_catalogue_project)],
            text=True,
            capture_output=True,
            check=False,
        )
        record(results, "v0.2 init without release catalogue", "MANIFEST", *cli_result(proc))

        # The v0.2-rc1 instruments moved to _frozen_instruments/v0.2 when v0.3 took the working
        # tree. Their custody must still be enforced from the frozen root.
        frozen_v02 = scratch / "mutated_frozen_v02"
        copy_tools(frozen_v02)
        frozen_project = scratch / "project_frozen_v02"
        build_clean(frozen_project)
        target = frozen_v02 / "_frozen_instruments" / "v0.2" / "research_gate.py"
        target.write_bytes(target.read_bytes() + b"\n# scratch byte mutation\n")
        record(results, "frozen v0.2 instrument byte mismatch", "MANIFEST",
               *cli_run(frozen_v02, frozen_project))

        # Compatibility controls. A v0.3 pass that came at the cost of a v0.2 or v0.1 regression
        # is not a pass.
        compat_v02 = scratch / "compat_clean_v02"
        build_clean(compat_v02)
        record(results, "clean v0.2 project under the v0.3 toolchain", None,
               *quiet_run(compat_v02), want_fail=False)

        compat_v01 = scratch / "compat_clean_v01"
        build_clean(compat_v01, contract="v0.1")
        record(results, "clean v0.1 project under explicit legacy invocation", None,
               *quiet_run(compat_v01, "v0.1"), want_fail=False)

        record(results, "v0.2 project refused under --contract v0.3", "MANIFEST",
               *quiet_run(compat_v02, "v0.3"))

        v03_cases(scratch, results)

        print("case | expected arm | observed exit | arms fired | verdict")
        print("=" * 110)
        defects = 0
        for case, arm, observed, errors, want_fail in results:
            verdict, is_defect = verdict_for(arm, observed, errors, want_fail)
            defects += is_defect
            print(f"{case} | {arm or 'none, must pass'} | {observed} | "
                  f"{arms_fired(errors)} | {verdict}")
        invalid = sum(1 for e in results if e[4])
        valid = len(results) - invalid
        print(f"\n{defects} of {len(results)} fixtures disagreed with their expected result "
              f"({invalid} invalid fixtures that must fail on the named arm, "
              f"{valid} valid fixtures that must pass).")
        return 1 if defects else 0
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

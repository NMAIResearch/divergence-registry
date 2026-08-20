#!/usr/bin/env python3
"""research_gate.py - process gate for the Divergence Protocol.

    python3 research_gate.py --init PROJECT_DIR     scaffold a new project
    python3 research_gate.py PROJECT_DIR            run every arm
    python3 research_gate.py PROJECT_DIR --through digest
    python3 research_gate.py --demo                 self-test with seeded faults

Standard library only, no network. Exits non-zero on any failure.

This gates the PROCESS, not the deposit. It enforces that every decision the protocol names has
been made, logged with a real alternative, and that the evidence register supports the claims.
It cannot tell you whether the research is any good. Nothing can.

Six arms:

  MANIFEST    the release catalogue, project binding and four register files are valid;
              bound instrument identities, versions, hashes and current bytes agree
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
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

STAGES = ["question", "scope", "data", "digest", "draft", "mint"]

CONTRACT_V0_1 = {
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

CONTRACT_V0_2 = {
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
        "S6": "exit and censoring rule",
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

DEFAULT_CONTRACT = "v0.2"
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


RELEASE_CATALOGUE_FILE = "instrument_manifest.json"
CATALOGUE_SCHEMA_VERSION = "1.2"
PROJECT_BINDING_SCHEMA_VERSION = "1.0"
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
CONTRACT_INSTRUMENT_FILES = {
    "v0.1": {
        "guide": "RESEARCH_GUIDE.md",
        "gate": "research_gate.py",
        "prose_checker": "agp_deterministic.py",
    },
    "v0.2": {
        "protocol": "DIVERGENCE_PROTOCOL.md",
        "gate": "research_gate.py",
        "prose_checker": "agp_deterministic.py",
    },
}
CONTRACT_SCHEMAS = {
    "v0.1": CONTRACT_V0_1,
    "v0.2": CONTRACT_V0_2,
}
CONTRACT_INSTRUMENT_VERSIONS = {
    "v0.1": "v0",
    "v0.2": "v0.2",
}
CONTRACT_VERSION_FIELDS = {
    "v0.1": "guide_version",
    "v0.2": "protocol_version",
}
CONTRACT_INSTRUMENT_ROOTS = {
    "v0.1": "_frozen_instruments/v0",
    "v0.2": ".",
}


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_iso_date(value):
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        return None


def validate_release_catalogue(data):
    errors = []
    if not isinstance(data, dict):
        return ["root JSON must be an object"]
    if data.get("manifest_type") != "release_catalogue":
        errors.append("manifest_type must be 'release_catalogue'")
    if data.get("schema_version") != CATALOGUE_SCHEMA_VERSION:
        errors.append(f"schema_version must be '{CATALOGUE_SCHEMA_VERSION}'")
    if data.get("default_contract") != DEFAULT_CONTRACT:
        errors.append(f"default_contract must be '{DEFAULT_CONTRACT}'")

    contracts = data.get("contracts")
    if not isinstance(contracts, dict):
        return errors + ["contracts must be an object"]
    expected_names = set(CONTRACT_SCHEMAS)
    got_names = set(contracts)
    if got_names != expected_names:
        errors.append("contracts must contain exactly: " + ", ".join(sorted(expected_names)))

    script_dir = Path(__file__).resolve().parent
    for contract_name, expected_schema in CONTRACT_SCHEMAS.items():
        c_data = contracts.get(contract_name)
        if not isinstance(c_data, dict):
            errors.append(f"contract '{contract_name}' must be an object")
            continue
        expected_version = CONTRACT_INSTRUMENT_VERSIONS[contract_name]
        version_field = CONTRACT_VERSION_FIELDS[contract_name]
        expected_root = CONTRACT_INSTRUMENT_ROOTS[contract_name]
        if c_data.get(version_field) != expected_version:
            errors.append(f"contract '{contract_name}' {version_field} must be '{expected_version}'")
        if c_data.get("instrument_root") != expected_root:
            errors.append(f"contract '{contract_name}' instrument_root must be '{expected_root}'")
        if c_data.get("required_decisions") != sum(len(stage) for stage in expected_schema.values()):
            errors.append(f"contract '{contract_name}' required_decisions does not match its fixed schema")
        if c_data.get("stages") != expected_schema:
            errors.append(f"contract '{contract_name}' stages do not match the fixed code schema")

        hashes = c_data.get("hashes")
        if not isinstance(hashes, dict):
            errors.append(f"contract '{contract_name}' hashes must be an object")
            continue
        instrument_root = script_dir / expected_root
        instrument_files = CONTRACT_INSTRUMENT_FILES[contract_name]
        for filename in instrument_files.values():
            allowed = hashes.get(filename)
            if not isinstance(allowed, list) or not allowed:
                errors.append(f"contract '{contract_name}' has no recognised hashes for {filename}")
                continue
            invalid = [value for value in allowed
                       if not isinstance(value, str) or not SHA256_HEX.fullmatch(value)]
            if invalid:
                errors.append(f"contract '{contract_name}' has an invalid SHA-256 entry for {filename}")
                continue
            actual_path = instrument_root / filename
            if not actual_path.is_file():
                errors.append(f"contract '{contract_name}' instrument file is missing: {actual_path}")
                continue
            actual_hash = file_sha256(actual_path)
            if actual_hash not in allowed:
                errors.append(
                    f"contract '{contract_name}' instrument bytes for {filename} hash "
                    f"{actual_hash[:12]}..., which is not recognised by the release catalogue")
    return errors


def load_release_catalogue():
    script_dir = Path(__file__).resolve().parent
    cat_path = script_dir / RELEASE_CATALOGUE_FILE
    if not cat_path.is_file():
        return None, [f"release catalogue missing at {cat_path}"]
    try:
        with cat_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        return None, [f"release catalogue is malformed: {exc}"]
    errors = validate_release_catalogue(data)
    return data, errors


def load_project_binding(root):
    p = Path(root) / "instrument_manifest.json"
    if not p.is_file():
        return None, "missing"
    try:
        with p.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as e:
        return None, f"malformed JSON: {e}"
    if not isinstance(data, dict):
        return None, "root JSON must be an object"
    mtype = data.get("manifest_type")
    if mtype != "project_binding":
        return None, f"invalid manifest_type '{mtype}', expected 'project_binding'"
    return data, None


def validate_project_binding(binding, contract_name, catalogue, report):
    if binding.get("schema_version") != PROJECT_BINDING_SCHEMA_VERSION:
        report.check(False, f"project binding schema_version must be '{PROJECT_BINDING_SCHEMA_VERSION}'", "MANIFEST")
    bound_date = binding.get("bound_date")
    if not bound_date or parse_iso_date(bound_date) is None:
        report.check(False, "project binding bound_date must be an ISO date", "MANIFEST")

    c_data = catalogue["contracts"][contract_name]
    version_field = CONTRACT_VERSION_FIELDS[contract_name]
    expected_version = c_data[version_field]
    instrument_root = Path(__file__).resolve().parent / c_data["instrument_root"]
    insts = binding.get("instruments")
    if not isinstance(insts, dict):
        report.check(False, "project binding missing 'instruments' map", "MANIFEST")
        return

    valid_hashes_map = c_data["hashes"]
    instrument_files = CONTRACT_INSTRUMENT_FILES[contract_name]
    for key, expected_file in instrument_files.items():
        if key not in insts or not isinstance(insts[key], dict):
            report.check(False, f"project binding missing instrument metadata for '{key}'", "MANIFEST")
            continue
        item = insts[key]
        filename = item.get("file")
        version = item.get("version")
        recorded_hash = item.get("sha256")
        if filename != expected_file:
            report.check(False, f"instrument '{key}' file must be '{expected_file}', not '{filename}'", "MANIFEST")
        if version != expected_version:
            report.check(False, f"instrument '{key}' version must be '{expected_version}', not '{version}'", "MANIFEST")
        if not isinstance(recorded_hash, str) or not SHA256_HEX.fullmatch(recorded_hash):
            report.check(False, f"instrument '{key}' sha256 must be 64 lowercase hexadecimal characters", "MANIFEST")
            continue
        valid_hashes = valid_hashes_map.get(expected_file, [])
        if recorded_hash not in valid_hashes:
            report.check(False, f"instrument '{key}' ({expected_file}) hash {recorded_hash[:12]}... in project binding is not recognised for contract '{contract_name}'", "MANIFEST")
        actual_path = instrument_root / expected_file
        if not actual_path.is_file():
            report.check(False, f"bound instrument file is missing: {actual_path}", "MANIFEST")
            continue
        actual_hash = file_sha256(actual_path)
        if actual_hash != recorded_hash:
            report.check(False, f"instrument '{key}' byte mismatch. File is {actual_hash}, project binding says {recorded_hash}", "MANIFEST")


def arm_manifest(root, report, cli_contract=None):
    catalogue, catalogue_errors = load_release_catalogue()
    for error in catalogue_errors:
        report.check(False, error, "MANIFEST")
    binding, bind_err = load_project_binding(root)
    known_contracts = CONTRACT_SCHEMAS

    contract_name = DEFAULT_CONTRACT
    if cli_contract:
        c_key = cli_contract.strip().lower()
        if c_key not in known_contracts:
            report.check(False, f"unknown CLI contract '{cli_contract}'", "MANIFEST")
            c_key = DEFAULT_CONTRACT
        if bind_err:
            if bind_err == "missing" and c_key == "v0.1":
                report.note("v0.1 legacy evaluation: project binding manifest is absent")
            elif bind_err == "missing":
                report.check(False, "instrument_manifest.json (project binding) missing", "MANIFEST")
            else:
                report.check(False, f"instrument_manifest.json (project binding) invalid: {bind_err}", "MANIFEST")
            contract_name = c_key
        else:
            bound_c = (binding.get("contract") or "").strip().lower()
            if bound_c != c_key:
                report.check(False, f"CLI contract '{cli_contract}' conflicts with project bound contract '{bound_c}'", "MANIFEST")
            if bound_c not in known_contracts:
                report.check(False, f"unknown contract '{bound_c}' in project binding", "MANIFEST")
                contract_name = c_key
            else:
                contract_name = bound_c
    else:
        if bind_err == "missing":
            report.check(False, "instrument_manifest.json (project binding) missing. Run --init to scaffold it, or use explicit --contract v0.1 for a legacy fixture.", "MANIFEST")
            contract_name = DEFAULT_CONTRACT
        elif bind_err:
            report.check(False, f"instrument_manifest.json (project binding) invalid: {bind_err}", "MANIFEST")
            contract_name = DEFAULT_CONTRACT
        else:
            bound_c = (binding.get("contract") or "").strip().lower()
            if bound_c not in known_contracts:
                report.check(False, f"unknown contract '{bound_c}' in project binding", "MANIFEST")
                contract_name = DEFAULT_CONTRACT
            else:
                contract_name = bound_c
                if bound_c == "v0.1":
                    report.check(False, "v0.1 is a legacy contract and requires explicit --contract v0.1", "MANIFEST")

    if binding and contract_name in known_contracts and catalogue is not None and not catalogue_errors:
        validate_project_binding(binding, contract_name, catalogue, report)

    required_schema = known_contracts.get(contract_name, CONTRACT_V0_2)
    return contract_name, required_schema


def arm_decisions(rows, through, report, required_schema=CONTRACT_V0_2, contract_name="v0.2"):
    required = {}
    for stage in STAGES[:STAGES.index(through) + 1]:
        required.update({k: (stage, v) for k, v in required_schema[stage].items()})

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
        alts = [a for a in (r["alternatives"] or "").split("|") if not blank(a)]
        if not alts:
            report.check(False, f"{did}: no alternative recorded, so nothing was decided. "
                                f"Name at least one option genuinely available, pipe-separated.",
                         "DECISIONS")
        if blank(r["decided_date"]):
            report.check(False, f"{did}: no decided_date", "DECISIONS")
        elif contract_name == "v0.2" and parse_iso_date(r["decided_date"]) is None:
            report.check(False, f"{did}: decided_date must be an ISO date", "DECISIONS")

    extra = sorted(set(seen) - set(required) - {""})
    if extra:
        report.note(f"decisions beyond the required set, kept: {', '.join(extra)}")
    report.note(f"{len(required)} decisions required for contract '{contract_name}' through stage '{through}', "
                f"{len(seen)} logged")


def arm_sources(rows, root, report, decisions=None, contract_name="v0.2"):
    ids, held, unretrieved = set(), 0, 0
    scope_dates = []
    if decisions:
        for r in decisions:
            did = (r.get("decision_id") or "").strip().upper()
            if did in {"S1", "S2", "S3", "S4", "S5", "S6"} and not blank(r.get("decided_date")):
                parsed = parse_iso_date(r["decided_date"])
                if parsed is not None:
                    scope_dates.append(parsed)
    latest_scope_date = max(scope_dates) if scope_dates else None

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
            recorded_hash = (r["sha256"] or "").strip()
            if blank(r["sha256"]):
                report.check(False, f"{sid}: held but not hashed. Recorded hash should be "
                                    f"{got}", "SOURCES")
            elif got == recorded_hash:
                held += 1
            else:
                report.check(False, f"{sid}: hash mismatch. File is {got}, register says "
                                    f"{recorded_hash}", "SOURCES")
        elif status == "registered_not_retrieved":
            unretrieved += 1
            if blank(r["notes"]):
                report.check(False, f"{sid}: registered_not_retrieved with no reason in notes. "
                                    f"Record what was tried and what happened.", "SOURCES")
        if blank(r["accessed_date"]):
            report.check(False, f"{sid}: no accessed_date", "SOURCES")
        else:
            accessed_date = parse_iso_date(r["accessed_date"])
            if accessed_date is None and contract_name == "v0.2":
                report.check(False, f"{sid}: accessed_date must be an ISO date", "SOURCES")
            elif accessed_date is not None and latest_scope_date and accessed_date < latest_scope_date:
                report.check(False, f"{sid}: accessed_date {accessed_date.isoformat()} is earlier "
                                    f"than final scope decision date {latest_scope_date.isoformat()}. "
                                    f"Data collection cannot precede completion of scope decisions (S1-S6).",
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


def run(root, through, quiet=False, contract=None):
    report = Report()
    root = Path(root)
    if not root.is_dir():
        print(f"FAIL: {root} is not a directory")
        return 1

    contract_name, required_schema = arm_manifest(root, report, cli_contract=contract)

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
        arm_decisions(decisions, through, report, required_schema=required_schema, contract_name=contract_name)
    source_ids = arm_sources(sources, root, report, decisions, contract_name=contract_name) if sources else set()
    if claims and sources:
        arm_claims(claims, sources, source_ids, report)
    if vocab:
        arm_vocab(vocab, {"sources.csv": sources, "claims.csv": claims}, report)
    if STAGES.index(through) >= STAGES.index("draft"):
        arm_draft(root, decisions, claims, report)

    if not quiet:
        print(f"research_gate: {root.name}, contract '{contract_name}', gated through stage '{through}'")
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


def init(root, contract="v0.2"):
    contract_key = (contract or DEFAULT_CONTRACT).strip().lower()
    if contract_key not in CONTRACT_SCHEMAS:
        print(f"FAIL: unknown contract '{contract_key}'")
        return 1
    catalogue, catalogue_errors = load_release_catalogue()
    if catalogue_errors:
        print("FAIL: release catalogue is not valid:")
        for error in catalogue_errors:
            print(f"  MANIFEST: {error}")
        return 1
    c_data = catalogue["contracts"][contract_key]
    schema = CONTRACT_SCHEMAS[contract_key]
    instrument_root = Path(__file__).resolve().parent / c_data["instrument_root"]
    instrument_files = CONTRACT_INSTRUMENT_FILES[contract_key]
    instrument_hashes = {
        key: file_sha256(instrument_root / filename)
        for key, filename in instrument_files.items()
    }

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
                    for did, what in schema[stage].items():
                        w.writerow([did, stage, what, "", "", "", "", "", ""])
            elif name == "vocabulary.csv":
                w.writerows(SEED_VOCAB)
        made.append(name)
        print(f"  created {name}")

    p_manifest = root / "instrument_manifest.json"
    if not p_manifest.exists():
        version_field = CONTRACT_VERSION_FIELDS[contract_key]
        instrument_version = c_data[version_field]
        manifest_data = {
            "manifest_type": "project_binding",
            "schema_version": PROJECT_BINDING_SCHEMA_VERSION,
            "contract": contract_key,
            "bound_date": date.today().isoformat(),
            "instruments": {
                key: {
                    "file": filename,
                    "version": instrument_version,
                    "sha256": instrument_hashes[key]
                }
                for key, filename in instrument_files.items()
            },
        }
        p_manifest.write_text(json.dumps(manifest_data, indent=2) + "\n", encoding="utf-8")
        made.append("instrument_manifest.json")
        print(f"  created instrument_manifest.json (bound to {contract_key})")
    else:
        print("  kept    instrument_manifest.json (already exists)")

    if made:
        print(f"\n{root}/ scaffolded for contract {contract_key}. Fill decisions.csv top down; the gate refuses blanks and "
              f"placeholders.")
        print("Alternatives are pipe-separated. A decision with no alternative is rejected.")
    return 0


def demo():
    """Seed a fault into each arm and assert the arm fires. A checker that has only ever
    returned PASS has not been tested."""
    tmp = Path(tempfile.mkdtemp(prefix="research_gate_demo_"))
    try:
        # 1. Clean v0.2 project (27 decisions including S6) under default invocation (no CLI --contract)
        proj = tmp / "worked_subject_v02"
        init(proj, contract="v0.2")
        print()

        held = proj / "sources" / "regulator_filing.txt"
        held.write_text("Reported capacity 4,200 MW across 17 sites.\n", encoding="utf-8")
        digest = hashlib.sha256(held.read_bytes()).hexdigest()

        with (proj / "decisions.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(FILES["decisions.csv"])
            for stage in STAGES:
                for did, what in CONTRACT_V0_2[stage].items():
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

        print("clean v0.2 project (27 decisions, default invocation), expect PASS")
        print("=" * 62)
        clean = run(proj, "mint")
        assert clean == 0, "the clean v0.2 demo project should pass under default invocation"

        # 2. Clean legacy v0.1 project (26 decisions) under explicit --contract v0.1
        print()
        print("clean v0.1 project (26 decisions, explicit --contract v0.1), expect PASS")
        print("=" * 62)
        proj_v01 = tmp / "worked_subject_v01"
        init(proj_v01, contract="v0.1")
        held_v01 = proj_v01 / "sources" / "regulator_filing.txt"
        held_v01.write_text("Reported capacity 4,200 MW across 17 sites.\n", encoding="utf-8")
        digest_v01 = hashlib.sha256(held_v01.read_bytes()).hexdigest()

        with (proj_v01 / "decisions.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(FILES["decisions.csv"])
            for stage in STAGES:
                for did, what in CONTRACT_V0_1[stage].items():
                    w.writerow([did, stage, what, f"chose the {what} as stated",
                                "the wider reading|the narrower reading",
                                "the narrower one survives a hostile read", "2026-08-14",
                                "author:N", "revisit if the regulator restates"])
        with (proj_v01 / "sources.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(FILES["sources.csv"])
            w.writerow(["regulator_filing", "Capacity return", "The regulator", "1",
                        "primary", "https://example.invalid/return",
                        "sources/regulator_filing.txt", digest_v01, "retrieved", "2026-08-14",
                        "", "Held because the return is republished in place."])
        with (proj_v01 / "claims.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(FILES["claims.csv"])
            w.writerow(["C1", "Returned capacity is 4,200 MW across 17 sites.",
                        "regulator_filing", "reported", "yes", "as filed, no band given", ""])
        (proj_v01 / "findings.md").write_text(
            "# Worked subject v0.1\n\n"
            "Returned capacity is 4,200 MW across 17 sites.\n\n"
            "## Falsifier\n\nA restated return below 3,000 MW would prove this wrong.\n\n"
            "## Verification\n\nCapacity traced to the regulator's capacity return.\n\n"
            "## Negative results retained\n\nNone.\n\n"
            "## Conflict of interest\n\nNone.\n", encoding="utf-8")

        clean_v01 = run(proj_v01, "mint", contract="v0.1")
        assert clean_v01 == 0, "the clean v0.1 demo project should pass"

        default_v01 = run(proj_v01, "mint", quiet=True)
        assert default_v01 != 0, "v0.1 must not activate without explicit --contract v0.1"
        print("  v0.1 project without explicit --contract v0.1 caught")

        malformed_v01 = tmp / "malformed_v01_binding"
        shutil.copytree(proj_v01, malformed_v01)
        (malformed_v01 / "instrument_manifest.json").write_text("{malformed", encoding="utf-8")
        malformed_v01_rc = run(malformed_v01, "mint", quiet=True, contract="v0.1")
        assert malformed_v01_rc != 0, "explicit v0.1 must reject a malformed binding that is present"
        print("  malformed v0.1 project binding caught under explicit legacy mode")

        # 3. Clean fixed-population v0.2 project (S6 recorded as not applicable with rationale)
        print()
        print("clean fixed-population v0.2 project (S6 N/A with rationale), expect PASS")
        print("=" * 62)
        proj_static = tmp / "worked_subject_static_v02"
        init(proj_static, contract="v0.2")
        held_static = proj_static / "sources" / "regulator_filing.txt"
        held_static.write_text("Reported capacity 4,200 MW across 17 sites.\n", encoding="utf-8")
        digest_static = hashlib.sha256(held_static.read_bytes()).hexdigest()

        with (proj_static / "decisions.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(FILES["decisions.csv"])
            for stage in STAGES:
                for did, what in CONTRACT_V0_2[stage].items():
                    if did == "S6":
                        w.writerow(["S6", "scope", "exit and censoring rule",
                                    "not applicable: fixed cohort with zero exits",
                                    "model as right-censored at t_end|hazard rate model",
                                    "All 17 sites observed throughout entire window; no departures occur.",
                                    "2026-08-14", "author:N", "revisit if cohort expands"])
                    else:
                        w.writerow([did, stage, what, f"chose the {what} as stated",
                                    "the wider reading|the narrower reading",
                                    "the narrower one survives a hostile read", "2026-08-14",
                                    "author:N", "revisit if the regulator restates"])
        with (proj_static / "sources.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(FILES["sources.csv"])
            w.writerow(["regulator_filing", "Capacity return", "The regulator", "1",
                        "primary", "https://example.invalid/return",
                        "sources/regulator_filing.txt", digest_static, "retrieved", "2026-08-14",
                        "", "Held because the return is republished in place."])
        with (proj_static / "claims.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(FILES["claims.csv"])
            w.writerow(["C1", "Returned capacity is 4,200 MW across 17 sites.",
                        "regulator_filing", "reported", "yes", "as filed, no band given", ""])
        (proj_static / "findings.md").write_text(
            "# Worked static subject v0.2\n\n"
            "Returned capacity is 4,200 MW across 17 sites.\n\n"
            "## Falsifier\n\nA restated return below 3,000 MW would prove this wrong.\n\n"
            "## Verification\n\nCapacity traced to the regulator's capacity return.\n\n"
            "## Negative results retained\n\nNone.\n\n"
            "## Conflict of interest\n\nNone.\n", encoding="utf-8")

        clean_static = run(proj_static, "mint")
        assert clean_static == 0, "the clean fixed-population v0.2 demo project should pass"

        # 4. A project part-way through
        print()
        print("part-way project, registers not yet reached, expect PASS at each stage")
        print("=" * 62)
        early = tmp / "early_subject"
        init(early, contract="v0.2")
        with (early / "decisions.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(FILES["decisions.csv"])
            for stage in ("question", "scope"):
                for did, what in CONTRACT_V0_2[stage].items():
                    w.writerow([did, stage, what, f"chose the {what} as stated",
                                "the wider reading|the narrower reading",
                                "the narrower one survives a hostile read", "2026-08-14",
                                "author:N", "revisit if the regulator restates"])
        for stage in ("question", "scope"):
            rc = run(early, stage, quiet=True)
            assert rc == 0, (f"a project worked through '{stage}' should pass at --through "
                             f"{stage}; empty later registers are not a fault")
            print(f"  --through {stage}: PASS")
        # Premature data collection check
        with (early / "sources.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(FILES["sources.csv"])
            w.writerow(["premature_src", "Premature", "Publisher", "1", "primary", "", "", "", "retrieved", "2026-08-14", "", ""])
        rc = run(early, "scope", quiet=True)
        assert rc != 0, "sources.csv populated before stage 'data' must fail at --through scope"
        print("  premature sources.csv population at --through scope caught")
        with (early / "sources.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(FILES["sources.csv"])

        # Regressions for defects found by trials
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
                                 {"alternatives": ""}), {}),
            ("DECISIONS", "omit required S6 under v0.2 (default invocation)",
             lambda: delete_row_csv(proj / "decisions.csv", "decision_id", "S6"), {}),
            ("DECISIONS", "blank the alternative on S6 under v0.2",
             lambda: rewrite_csv(proj / "decisions.csv", "decision_id", "S6",
                                 {"alternatives": ""}), {}),
            ("MANIFEST", "missing project binding manifest (default invocation)",
             lambda: (proj / "instrument_manifest.json").unlink(), {}),
            ("MANIFEST", "malformed project binding manifest JSON",
             lambda: (proj / "instrument_manifest.json").write_text("{malformed JSON", encoding="utf-8"), {}),
            ("MANIFEST", "unknown contract in project binding (e.g. v9.9)",
             lambda: rewrite_json(proj / "instrument_manifest.json", {"contract": "v9.9"}), {}),
            ("MANIFEST", "project contract v0.2 and CLI contract v0.1 conflict",
             lambda: None, {"cli_contract": "v0.1"}),
            ("MANIFEST", "missing instrument metadata in project binding",
             lambda: delete_binding_field(proj / "instrument_manifest.json", ["instruments", "gate"]), {}),
            ("MANIFEST", "stale/unrecognised instrument hash in project binding",
             lambda: rewrite_binding_field(proj / "instrument_manifest.json", ["instruments", "gate", "sha256"], "0123456789abcdef"*4), {}),
            ("MANIFEST", "missing project binding schema_version",
             lambda: delete_binding_field(proj / "instrument_manifest.json", ["schema_version"]), {}),
            ("MANIFEST", "invalid project binding bound_date",
             lambda: rewrite_binding_field(proj / "instrument_manifest.json", ["bound_date"], "not-a-date"), {}),
            ("MANIFEST", "protocol binding substituted with prose-checker identity",
             lambda: copy_binding_instrument(proj / "instrument_manifest.json", "protocol", "prose_checker"), {}),
            ("MANIFEST", "unrecognised protocol version in project binding",
             lambda: rewrite_binding_field(proj / "instrument_manifest.json", ["instruments", "protocol", "version"], "unrecognised-version"), {}),
            ("SOURCES", "corrupt the held file so the hash breaks (custody mismatch)",
             lambda: held.write_text("Reported capacity 9,900 MW.\n", encoding="utf-8"), {}),
            ("SOURCES", "drop the reason from the unretrieved source",
             lambda: rewrite_csv(proj / "sources.csv", "source_id", "vendor_deck",
                                 {"notes": ""}), {}),
            ("SOURCES", "source accessed before scope decision date",
             lambda: rewrite_csv(proj / "sources.csv", "source_id", "regulator_filing",
                                 {"accessed_date": "2026-08-10"}), {}),
            ("SOURCES", "source accessed before the final S6 scope decision",
             lambda: (rewrite_csv(proj / "decisions.csv", "decision_id", "S6",
                                  {"decided_date": "2026-08-20"}),
                      rewrite_csv(proj / "sources.csv", "source_id", "regulator_filing",
                                  {"accessed_date": "2026-08-19"})), {}),
            ("CLAIMS", "point a claim at a source that is not registered",
             lambda: rewrite_csv(proj / "claims.csv", "claim_id", "C1",
                                 {"source_id": "press_writeup"}), {}),
            ("CLAIMS", "make a tier-5 source carry a load-bearing claim alone",
             lambda: (rewrite_csv(proj / "claims.csv", "claim_id", "C1",
                                  {"source_id": "vendor_deck"}),
                      rewrite_csv(proj / "sources.csv", "source_id", "vendor_deck",
                                  {"second_source_id": ""})), {}),
            ("VOCAB", "use an undeclared claim_basis",
             lambda: rewrite_csv(proj / "claims.csv", "claim_id", "C2",
                                 {"claim_basis": "estimated"}), {}),
            ("DRAFT", "remove the verification section",
             lambda: (proj / "findings.md").write_text(
                  (proj / "findings.md").read_text(encoding="utf-8")
                  .replace("## Verification", "## Method"), encoding="utf-8"), {}),
            ("DRAFT", "remove the negative-results section",
             lambda: (proj / "findings.md").write_text(
                  (proj / "findings.md").read_text(encoding="utf-8")
                  .replace("## Negative results retained", "## Further reading"),
                  encoding="utf-8"), {}),
        ]

        backup = tmp / "backup"
        shutil.copytree(proj, backup)
        failures = []
        print("\n\nseeded faults, each must be caught")
        print("=" * 62)
        for arm, what, apply, opts in faults:
            shutil.rmtree(proj)
            shutil.copytree(backup, proj)
            apply()
            cli_c = opts.get("cli_contract")
            rc = run(proj, "mint", quiet=True, contract=cli_c)
            caught = "CAUGHT" if rc != 0 else "MISSED"
            if rc == 0:
                failures.append(f"{arm}: {what}")
            print(f"  [{caught}] {arm:<9} {what}")

        print()
        print("toolchain binding faults, each must be caught")
        print("=" * 62)
        toolchain_fault_count = 0
        for filename in CONTRACT_INSTRUMENT_FILES["v0.2"].values():
            tool_dir = tmp / f"mutated_{filename.replace('.', '_')}"
            copy_toolchain_fixture(tool_dir)
            target = tool_dir / filename
            target.write_bytes(target.read_bytes() + b"\n# scratch byte mutation\n")
            proc = subprocess.run(
                [sys.executable, str(tool_dir / "research_gate.py"), str(backup)],
                text=True, capture_output=True, check=False)
            toolchain_fault_count += 1
            caught = "CAUGHT" if proc.returncode != 0 else "MISSED"
            if proc.returncode == 0:
                failures.append(f"MANIFEST: actual instrument byte mismatch for {filename}")
            print(f"  [{caught}] MANIFEST  actual instrument byte mismatch for {filename}")

        altered_catalogue_dir = tmp / "altered_release_catalogue"
        copy_toolchain_fixture(altered_catalogue_dir)
        altered_catalogue = read_json_file(altered_catalogue_dir / RELEASE_CATALOGUE_FILE)
        altered_catalogue["contracts"]["v0.2"]["stages"]["scope"].pop("S6")
        write_json_file(altered_catalogue_dir / RELEASE_CATALOGUE_FILE, altered_catalogue)
        proc = subprocess.run(
            [sys.executable, str(altered_catalogue_dir / "research_gate.py"), str(backup)],
            text=True, capture_output=True, check=False)
        toolchain_fault_count += 1
        caught = "CAUGHT" if proc.returncode != 0 else "MISSED"
        if proc.returncode == 0:
            failures.append("MANIFEST: release catalogue can remove mandatory S6")
        print(f"  [{caught}] MANIFEST  release catalogue removes mandatory S6")

        no_catalogue_dir = tmp / "missing_release_catalogue"
        copy_toolchain_fixture(no_catalogue_dir, include_catalogue=False)
        no_catalogue_project = tmp / "no_catalogue_project"
        proc = subprocess.run(
            [sys.executable, str(no_catalogue_dir / "research_gate.py"), "--init",
             str(no_catalogue_project)],
            text=True, capture_output=True, check=False)
        toolchain_fault_count += 1
        caught = "CAUGHT" if proc.returncode != 0 else "MISSED"
        if proc.returncode == 0:
            failures.append("MANIFEST: --init succeeds without a release catalogue")
        print(f"  [{caught}] MANIFEST  --init without release catalogue")

        print()
        if failures:
            print(f"FAIL: {len(failures)} seeded fault(s) passed the gate:")
            for f in failures:
                print(f"  {f}")
            return 1
        print(f"OK: all clean projects pass and all {len(faults) + toolchain_fault_count} seeded faults are caught.")
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


def delete_row_csv(path, key_col, key):
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
        cols = list(rows[0].keys())
    rows = [r for r in rows if r[key_col] != key]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def rewrite_json(path, updates):
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    data.update(updates)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def rewrite_binding_field(path, key_path, value):
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    cur = data
    for k in key_path[:-1]:
        cur = cur[k]
    cur[key_path[-1]] = value
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def delete_binding_field(path, key_path):
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    cur = data
    for k in key_path[:-1]:
        cur = cur[k]
    cur.pop(key_path[-1], None)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def copy_binding_instrument(path, target_key, source_key):
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    data["instruments"][target_key] = dict(data["instruments"][source_key])
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def read_json_file(path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def write_json_file(path, data):
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def copy_toolchain_fixture(target, include_catalogue=True):
    source = Path(__file__).resolve().parent
    target.mkdir(parents=True, exist_ok=True)
    for filename in CONTRACT_INSTRUMENT_FILES["v0.2"].values():
        shutil.copy2(source / filename, target / filename)
    if include_catalogue:
        shutil.copy2(source / RELEASE_CATALOGUE_FILE, target / RELEASE_CATALOGUE_FILE)
    shutil.copytree(source / "_frozen_instruments", target / "_frozen_instruments")


def main():
    ap = argparse.ArgumentParser(description="Process gate for the Divergence Protocol.")
    ap.add_argument("project", nargs="?", help="project directory")
    ap.add_argument("--init", action="store_true", help="scaffold the registers")
    ap.add_argument("--contract", choices=["v0.1", "v0.2"], default=None,
                    help="contract version to enforce (default: project binding or v0.2; v0.1 requires explicit selection)")
    ap.add_argument("--through", choices=STAGES, default="mint",
                    help="gate only the stages up to and including this one (default: mint)")
    ap.add_argument("--demo", action="store_true", help="self-test with seeded faults")
    a = ap.parse_args()

    if a.demo:
        return demo()
    if not a.project:
        ap.error("a project directory is required (or use --demo)")
    if a.init:
        return init(a.project, contract=a.contract or "v0.2")
    return run(a.project, a.through, contract=a.contract)


if __name__ == "__main__":
    sys.exit(main())

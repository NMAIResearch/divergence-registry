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

Six arms on every contract:

  MANIFEST    the release catalogue, project binding and four register files are valid;
              bound instrument identities, versions, hashes and current bytes agree
  DECISIONS   every required decision id for the stages reached is present and complete,
              each with at least one genuine alternative
  SOURCES     motive tier is 1-5, retrieved sources exist and match their hash, sources
              that could not be retrieved carry a reason
  CLAIMS      every claim resolves to a registered source; a claim material to the conclusion
              carries a second source when grounded only in tier 4 or 5
  VOCAB       controlled columns validated against vocabulary.csv
  DRAFT       the draft names the falsifier and carries a verification section, a negative-
              results or retained-limits section, and a COI note

Three further arms on contract v0.3:

  FEASIBILITY   the bounded pre-scope route: every probe asks one of five permitted questions,
                returns one of four permitted outcome-free results, is attributed, is dated no
                later than the last scope decision, and hashes any bytes it claims to hold
  SCOPE_REVIEW  a scope coherence review exists, names a reviewer who is not a decision-maker
                on the reviewed rows, and carries a current digest of every reviewed decision
                row
  SCOPE_APPROVAL  the researcher's recorded decision to open stage 3 exists, names the recorded
                authority, accepts exactly the checks the review left failed or unresolved, and
                still matches the digests of the files it binds
"""

import argparse
import contextlib
import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
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
        "S4": "stop criterion",
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

CONTRACT_V0_3 = {
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
        "S4": "stop criterion",
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
    "claims.csv": ["claim_id", "claim_text", "source_id", "claim_basis", "material_to_conclusion",
                   "uncertainty", "notes"],
    "vocabulary.csv": ["column", "value", "definition"],
}

LEGACY_V0_1_CLAIMS_COLUMNS = [
    "claim_id", "claim_text", "source_id", "claim_basis", "load_bearing", "uncertainty", "notes"
]
LEGACY_DECISIONS_COLUMNS = [
    "decision_id", "stage", "question", "chosen", "alternatives", "rationale", "decided_date",
    "revisit_trigger"
]
# v0.3 records what a source is authoritative for beside what it is derived from, so a mirror of
# a subject's own disclosure cannot be entered as an independent second source.
V0_3_SOURCES_COLUMNS = [
    "source_id", "title", "publisher", "motive_tier", "source_role", "url", "local_path",
    "sha256", "retrieval_status", "accessed_date", "second_source_id", "derived_from", "notes"
]
# v0.3 carries corroboration on the claim rather than on the source. A source can contain several
# unrelated statements, so one source-level second_source_id cannot establish confirmation of every
# claim extracted from that source.
V0_3_CLAIMS_COLUMNS = [
    "claim_id", "claim_text", "source_id", "claim_basis", "material_to_conclusion", "uncertainty",
    "corroborating_source_id", "notes"
]
FEASIBILITY_COLUMNS = [
    "probe_id", "source_name", "question", "url", "access_date", "result", "evidence_locator",
    "local_path", "sha256", "stated_period", "retention_policy", "derives_from_subject",
    "covers_population", "probed_by", "notes"
]
CLAIM_MATERIAL_FIELDS = {
    "v0.1": "load_bearing",
    "v0.2": "material_to_conclusion",
    "v0.3": "material_to_conclusion",
}
# The registers a contract adds beyond the four scaffolded for every contract.
CONTRACT_EXTRA_REGISTERS = {
    "v0.1": [],
    "v0.2": [],
    "v0.3": ["feasibility.csv"],
}


def file_columns(name, contract_name=DEFAULT_CONTRACT):
    if name == "claims.csv" and contract_name == "v0.1":
        return LEGACY_V0_1_CLAIMS_COLUMNS
    if name == "claims.csv" and contract_name == "v0.3":
        return V0_3_CLAIMS_COLUMNS
    if name == "sources.csv" and contract_name == "v0.3":
        return V0_3_SOURCES_COLUMNS
    if name == "feasibility.csv":
        return FEASIBILITY_COLUMNS
    return FILES[name]


def seed_vocab(contract_name=DEFAULT_CONTRACT):
    material_field = CLAIM_MATERIAL_FIELDS[contract_name]
    return [
        ("claim_basis", "reported", "The source states this value itself."),
        ("claim_basis", "derived", "Computed by the author from source values. The computation is named."),
        ("claim_basis", "inferred", "A judgement the source does not itself make. Never presented as reported."),
        (material_field, "yes", "The finding changes if this claim is wrong."),
        (material_field, "no", "Supporting or contextual. The finding survives without it."),
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


def read_csv(path, report, arm="MANIFEST", needed_at=None, through=None,
             contract_name=DEFAULT_CONTRACT, allow_empty=False, project_root=None,
             containment_arm=None):
    """Read a register, checking its columns. Returns [] and records an error on any problem.

    A register that is empty is only a failure once the stage that fills it has been reached.
    sources.csv is legitimately empty until stage 'data', claims.csv until stage 'digest'.
    """
    name = path.name
    read_path = path
    if contract_name == "v0.3" and project_root is not None:
        read_path = contained_path(project_root, name)
        if read_path is None:
            report.check(False, f"{name} does not resolve to a file inside the project. The v0.3 "
                         f"register bytes must travel with the project.",
                         containment_arm or arm)
            return []
    if not read_path.exists():
        report.check(False, f"{name} is missing. Run --init to scaffold it.", arm)
        return []
    with read_path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    expected = file_columns(name, contract_name)
    got = list(rows[0].keys()) if rows else None
    if got is not None:
        if name == "decisions.csv":
            # The eight-column register predates decided_by. v0.3 requires attribution, so the
            # column that carries it cannot be absent.
            accepted = [expected] if contract_name == "v0.3" else [expected, LEGACY_DECISIONS_COLUMNS]
            if got not in accepted:
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
        elif not allow_empty:
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
    "v0.3": {
        "protocol": "DIVERGENCE_PROTOCOL.md",
        "gate": "research_gate.py",
        "prose_checker": "agp_deterministic.py",
    },
}
CONTRACT_SCHEMAS = {
    "v0.1": CONTRACT_V0_1,
    "v0.2": CONTRACT_V0_2,
    "v0.3": CONTRACT_V0_3,
}
CONTRACT_INSTRUMENT_VERSIONS = {
    "v0.1": "v0",
    "v0.2": "v0.2",
    "v0.3": "v0.3",
}
CONTRACT_VERSION_FIELDS = {
    "v0.1": "guide_version",
    "v0.2": "protocol_version",
    "v0.3": "protocol_version",
}
# v0.2-rc1 was frozen byte for byte when v0.3 took the working tree. Its recognised hashes are
# unchanged; only the directory they are read from moved.
CONTRACT_INSTRUMENT_ROOTS = {
    "v0.1": "_frozen_instruments/v0",
    "v0.2": "_frozen_instruments/v0.2",
    "v0.3": ".",
}
LEGACY_CONTRACTS = {"v0.1"}

# The bounded feasibility route. These five questions are the whole permitted surface: a probe
# establishes whether the evidence route can be walked, never what it would show. A question or a
# result outside these sets is refused, so a count, an effect size or any other outcome value has
# no structured field to arrive in.
FEASIBILITY_QUESTIONS = {
    "source_exists": "is the named source published and reachable",
    "bytes_retrievable": "can the bytes be held locally and hashed",
    "period_and_retention": "what period does the source state and how long does it retain it",
    "derivation_independence": "does the source derive from the subject's own disclosure",
    "population_coverage": "does the source cover the proposed population",
}
FEASIBILITY_RESULTS = {"available", "unavailable", "restricted", "unknown"}
FEASIBILITY_TERNARY = {"yes", "no", "unknown"}

SCOPE_REVIEW_FILE = "scope_review.json"
SCOPE_REVIEW_TEMPLATE_FILE = "_scope_review_template.json"
SCOPE_REVIEW_SCHEMA_VERSION = "1.0"
SCOPE_REVIEW_RECORD_TYPE = "scope_coherence_review"
SCOPE_REVIEW_DECISIONS = ["Q2", "Q3", "S1", "S2", "S3", "S4", "S6"]
SCOPE_REVIEW_CHECKS = {
    "q3_disconfirms_q2": "Q3 exactly disconfirms Q2 with no unresolved interval",
    "s1_observable_denominator": "S1 names an observable denominator rather than an unknowable total",
    "s2_third_party_applicable": "S2 can be applied by a third party and yield the same set",
    "s3_vintage_reconstructable": "S3 can be reconstructed from held or retrievable vintages",
    "s4_tests_sufficiency": "S4 tests evidential sufficiency rather than suppressing a falsifying result",
    "s6_matches_population_window": "S6 matches the population and the time boundary",
}
SCOPE_REVIEW_RESULTS = {"pass", "fail", "unresolved"}

# Retained human authority, recorded separately from the review that raised the exception.
# Free text inside the review cannot carry it: a reviewer writing its own name into
# exception_accepted_by accepted its own unresolved finding, which is the control inverted. The
# approval is its own record, bound by hash to the three files it approves, so editing any of them
# invalidates it.
SCOPE_APPROVAL_FILE = "scope_approval.json"
SCOPE_APPROVAL_TEMPLATE_FILE = "_scope_approval_template.json"
SCOPE_APPROVAL_SCHEMA_VERSION = "1.0"
SCOPE_APPROVAL_RECORD_TYPE = "scope_exception_approval"
# The one recorded authority the gate accepts. Compared with normalise_actor, so 'N' and 'N.' are
# the same authority and 'the reviewer' is not.
SCOPE_APPROVAL_AUTHORITY = "N."
SCOPE_APPROVAL_DECISIONS = {"proceed", "hold", "revise"}
SCOPE_APPROVAL_OPENS = "proceed"
SCOPE_APPROVAL_SCOPE_BINDING = "decisions.csv#question_scope"
SCOPE_APPROVAL_DECISION_IDS = (
    list(CONTRACT_V0_3["question"]) + list(CONTRACT_V0_3["scope"])
)
SCOPE_APPROVAL_BOUND_FILES = [
    SCOPE_APPROVAL_SCOPE_BINDING, "feasibility.csv", SCOPE_REVIEW_FILE
]

DECISION_DIGEST_FIELDS = [
    "decision_id", "stage", "question", "chosen", "alternatives", "rationale", "decided_date",
    "decided_by", "revisit_trigger"
]


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalise_actor(value):
    """Collapse an attribution string so 'Model:X  run 1', 'model-x run 1' and 'Model X, run 1'
    all compare equal.

    Case, spacing and punctuation are each cheap to vary and none of them changes who acted. Every
    non-alphanumeric character becomes a space and runs of whitespace collapse, so a reviewer
    cannot separate itself from the decision maker it is reviewing by respelling the same
    identifier. Two genuinely different actors collide here only if they differ by punctuation
    alone, and that collision fails the gate closed, which is the safe direction for a control on
    who reviewed whom.
    """
    folded = "".join(ch if ch.isalnum() else " " for ch in (value or "").lower())
    return " ".join(folded.split())


def punctuation_only(value):
    """True when a value carries no alphanumeric character anywhere.

    str.isalnum() is Unicode-aware, so a non-Latin identifier counts as content and '!!!', '***'
    and '---' do not.
    """
    return not any(ch.isalnum() for ch in (value or ""))


def unusable_value(value):
    """True when a required field is blank, a placeholder, or punctuation only.

    blank() refuses an empty field and a closed list of placeholder words. It does not refuse
    '!!!', which is neither empty nor a placeholder word and which a reader can do nothing with.
    Every field the gate requires to carry content is tested with both halves, because a field
    that reaches the gate as punctuation is as absent as one left empty, and reads as filled in.
    """
    return blank(value) or punctuation_only(value)


ACTOR_REQUIRED_FIELDS = ("model", "harness", "run")
ACTOR_OPTIONAL_FIELDS = ("role",)


def actor_identity(value):
    """Return the comparable model, harness and run tuple from a structured attribution.

    The accepted form is `model=...; harness=...; run=...`, with an optional `role=...` field.
    Role is deliberately excluded from the comparison: changing runner to reviewer does not create
    a second run. The gate reads a recorded identity and does not authenticate it.
    """
    if not isinstance(value, str) or unusable_value(value):
        return None
    parts = {}
    allowed = set(ACTOR_REQUIRED_FIELDS + ACTOR_OPTIONAL_FIELDS)
    for segment in value.split(";"):
        key, separator, raw = segment.partition("=")
        key = key.strip().lower()
        raw = raw.strip()
        if not separator or key not in allowed or key in parts or unusable_value(raw):
            return None
        parts[key] = raw
    if any(key not in parts for key in ACTOR_REQUIRED_FIELDS):
        return None
    return tuple(normalise_actor(parts[key]) for key in ACTOR_REQUIRED_FIELDS)


def unidentifiable_actor(value):
    """True when model, harness and run cannot be compared mechanically."""
    return actor_identity(value) is None


ALLOWED_URL_SCHEMES = {"http", "https"}
URI_ASCII_ALLOWED = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    "-._~:/?#[]@!$&'()*+,;=%"
)
HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


def usable_url(value):
    """True when a value parses as an absolute http or https URL naming a host.

    The host is read from parsed.hostname, not from netloc. netloc also carries user information
    and a port, so 'http://:80' and 'http://user@' are non-empty netlocs naming no host at all and
    passed while the check read netloc.

    RFC 3986 URI characters are enforced before parsing. Raw non-ASCII characters, characters
    outside the generic URI grammar and incomplete percent encodings are refused. The port is read
    inside the guarded parse rather than left unread. urlparse accepts malformed percent escapes
    and several characters outside the URI grammar without complaint. Every column that records a
    route reaches this one predicate, so what it accepts here is what the source register, the
    approval reference and the feasibility evidence route all accept.

    Surrounding whitespace is stripped before the test, because that is an artefact of the CSV
    cell rather than part of the address.

    Syntax only, and deliberately so: nothing here opens a connection, and a well-formed URL that
    resolves to nothing still passes. What it refuses is a locator column holding a string that
    could never be followed by anyone, which is what '!!!' is.
    """
    text = (value or "").strip()
    if not text:
        return False
    if any(ch.isspace() or ord(ch) < 0x20 or 0x7f <= ord(ch) <= 0x9f for ch in text):
        return False
    if any(ord(ch) > 0x7f or ch not in URI_ASCII_ALLOWED for ch in text):
        return False
    for index, char in enumerate(text):
        if char == "%":
            if (index + 2 >= len(text)
                    or text[index + 1] not in HEX_DIGITS
                    or text[index + 2] not in HEX_DIGITS):
                return False
    if "\\" in text:
        return False
        return False
    try:
        parsed = urllib.parse.urlparse(text)
        host, port = parsed.hostname, parsed.port
    except ValueError:
        return False
    return (parsed.scheme.lower() in ALLOWED_URL_SCHEMES
            and bool(host) and not punctuation_only(host)
            and (port is None or 0 < port <= 65535))


def contained_file(root, candidate):
    """True when candidate resolves to a file inside root.

    Custody means bytes held in the project, so the path is resolved before it is tested and the
    result must still sit under the resolved project root. Resolving first is what closes all three
    escapes at once: an absolute path elsewhere, a parent traversal, and a symlink inside the
    project pointing outside it. is_file() alone answered none of them.
    """
    return contained_path(root, candidate) is not None


def contained_path(root, candidate):
    """Return the resolved contained file for candidate, or None when it escapes root."""
    text = (candidate or "").strip()
    if not text:
        return None
    try:
        base = Path(root).resolve()
        target = (base / text).resolve()
    except (OSError, ValueError, RuntimeError):
        return None
    if target == base or base not in target.parents:
        return None
    try:
        return target if target.is_file() else None
    except OSError:
        return None


ISO_DATE_IN_TEXT = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
# The document forms a reference may name. A route that names no document names a directory, which
# does not identify a decision.
DOCUMENT_FORM = re.compile(r"\.(?:md|json|csv|txt|pdf|py)$", re.I)


def usable_route(token):
    """True when one whitespace-separated token of a reference is a route somebody could follow.

    A URL is parsed by the same predicate that governs the source register, so a malformed address
    fails here exactly as it fails there. Anything else must name a document and carry at least one
    component that is not punctuation: matching any token containing a slash accepted '///', which
    is a route to nowhere.
    """
    cleaned = token.strip().rstrip(".,;:)]}")
    if not cleaned:
        return False
    if cleaned.lower().startswith(("http://", "https://")):
        return usable_url(cleaned)
    if not DOCUMENT_FORM.search(cleaned):
        return False
    return any(not punctuation_only(part) for part in cleaned.split("/") if part)


def reference_defect(value):
    """Why an approval reference cannot be traced back to anything, or None.

    The minimum enforceable shape for 'the dated decision or handoff this record stands for' is
    content, a date, and something to retrieve it by. Each part is mechanically checkable and each
    is useless without the others: a date alone does not say where to look, and a filename alone
    does not say which version of it.

    What this establishes: the reference has the shape of a dated, retrievable record. What it does
    not establish: that the record exists, that it is reachable, or that it says what the approval
    implies it says. Nothing here opens the reference.
    """
    if unusable_value(value):
        return ("no reference. Name the dated decision or handoff this approval records, so it "
                "can be traced to something outside this file")
    text = value.strip()
    dates = [d for d in ISO_DATE_IN_TEXT.findall(text) if parse_iso_date(d) is not None]
    if not dates:
        return (f"reference '{text}' carries no ISO date. An undated decision cannot be matched to "
                "the decision it stands for")
    if not any(usable_route(token) for token in text.split()):
        return (f"reference '{text}' names no retrievable route. Give the path, filename or URL of "
                "the record, not only a description of it. A path names a document and an address "
                "parses as one")
    return None


def decision_row_digest(row):
    """SHA-256 over the nine decision fields, unit-separated so no two field splits collide.

    A scope review carries these digests. Editing any reviewed field after the review changes the
    digest, and the review no longer binds.
    """
    payload = "\x1f".join((row.get(field) or "").strip() for field in DECISION_DIGEST_FIELDS)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def scope_decisions_digest(root):
    """Digest only the closed question and scope rows in decisions.csv.

    Data, digest, draft and mint decisions are recorded after scope approval. They must not stale
    that approval. Any change to Q1-Q4 or S1-S6 still changes this projection and requires fresh
    review and approval.
    """
    path = contained_path(root, "decisions.csv")
    if path is None:
        return None
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    by_id = {}
    for row in rows:
        decision_id = (row.get("decision_id") or "").strip().upper()
        if decision_id in by_id:
            return None
        by_id[decision_id] = row
    if any(decision_id not in by_id for decision_id in SCOPE_APPROVAL_DECISION_IDS):
        return None
    payload = "\n".join(
        f"{decision_id}:{decision_row_digest(by_id[decision_id])}"
        for decision_id in SCOPE_APPROVAL_DECISION_IDS
    ) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def approval_binding_digest(root, name):
    """Return a digest for one scope-approval binding item, or None when unavailable."""
    if name == SCOPE_APPROVAL_SCOPE_BINDING:
        return scope_decisions_digest(root)
    path = contained_path(root, name)
    return file_sha256(path) if path is not None else None


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
            if bind_err == "missing" and c_key in LEGACY_CONTRACTS:
                report.note(f"{c_key} legacy evaluation: project binding manifest is absent")
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
                if bound_c in LEGACY_CONTRACTS:
                    report.check(False, f"{bound_c} is a legacy contract and requires explicit --contract {bound_c}", "MANIFEST")

    if contract_name == "v0.3" and contained_path(root, "instrument_manifest.json") is None:
        report.check(False, "instrument_manifest.json does not resolve to a file inside the project. "
                     "The v0.3 project binding bytes must travel with the project.", "MANIFEST")

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
        # v0.3 refuses punctuation as well as blanks and placeholders. v0.1 and v0.2 keep the
        # weaker test, because changing what they accept is outside this repair.
        empty = unusable_value if contract_name == "v0.3" else blank
        if empty(r["chosen"]):
            report.check(False, f"{did}: nothing chosen", "DECISIONS")
        if empty(r["rationale"]):
            report.check(False, f"{did}: no rationale", "DECISIONS")
        # Every recorded alternative is validated under v0.3, not only the first usable one.
        # Discarding an unusable token while another survived left 'a real alternative|!!!'
        # passing, and the pipe-separated list is the record of what was on the table: a token
        # nobody can read is a recorded option that says nothing, exactly as a punctuation-only
        # 'chosen' does. A token that is genuinely empty records nothing at all and is skipped,
        # which is the same empty-field rule the columns use.
        tokens = [a for a in (r["alternatives"] or "").split("|") if a.strip()]
        if not tokens:
            report.check(False, f"{did}: no alternative recorded, so nothing was decided. "
                                f"Name at least one option genuinely available, pipe-separated.",
                         "DECISIONS")
        elif contract_name == "v0.3":
            for token in tokens:
                if empty(token):
                    report.check(False, f"{did}: alternative '{token.strip()}' carries no content. "
                                        f"Every option recorded in the pipe-separated list is one "
                                        f"that was genuinely available, so each has to name "
                                        f"something a reader can weigh against what was chosen. "
                                        f"Remove the token or record the option it stands for.",
                                 "DECISIONS")
        elif all(empty(a) for a in tokens):
            # v0.1 and v0.2 keep the weaker test: at least one token that is not blank or a
            # placeholder. Changing what they accept is outside this repair.
            report.check(False, f"{did}: no alternative recorded, so nothing was decided. "
                                f"Name at least one option genuinely available, pipe-separated.",
                         "DECISIONS")
        if blank(r["decided_date"]):
            report.check(False, f"{did}: no decided_date", "DECISIONS")
        elif contract_name in {"v0.2", "v0.3"} and parse_iso_date(r["decided_date"]) is None:
            report.check(False, f"{did}: decided_date must be an ISO date", "DECISIONS")
        if contract_name == "v0.3" and unidentifiable_actor(r.get("decided_by")):
            report.check(False, f"{did}: no comparable decided_by. Use "
                                f"'model=...; harness=...; run=...' with an optional "
                                f"'role=...'. v0.3 compares the recorded run identity and ignores "
                                f"role labels, so changing runner to reviewer cannot manufacture "
                                f"a second run.", "DECISIONS")

    extra = sorted(set(seen) - set(required) - {""})
    if extra:
        report.note(f"decisions beyond the required set, kept: {', '.join(extra)}")
    report.note(f"{len(required)} decisions required for contract '{contract_name}' through stage '{through}', "
                f"{len(seen)} logged")


def latest_scope_decision_date(decisions):
    """The last date across S1 to S6. Scope is closed when the last of them is decided, not the
    first, so this is the boundary that outcome-data collection must sit after."""
    scope_dates = []
    for r in decisions or []:
        did = (r.get("decision_id") or "").strip().upper()
        if did in {"S1", "S2", "S3", "S4", "S5", "S6"} and not blank(r.get("decided_date")):
            parsed = parse_iso_date(r["decided_date"])
            if parsed is not None:
                scope_dates.append(parsed)
    return max(scope_dates) if scope_dates else None


def derivation_chain(source_id, parents):
    """Every source that source_id derives from, at any depth, nearest origin first.

    parents maps each source_id to the source_id named in its derived_from column. The walk stops
    as soon as a source repeats, so a loop in the register terminates here rather than hanging the
    gate. A source is never reported as its own ancestor by this walk; the loop check in
    arm_sources owns that case and names the whole cycle.
    """
    chain, seen = [], {source_id}
    cursor = parents.get(source_id, "")
    while cursor and cursor not in seen:
        chain.append(cursor)
        seen.add(cursor)
        cursor = parents.get(cursor, "")
    return chain


def derivation_path(start, target, parents):
    """Render the derivation hops from start to target, for an error message that names the route.

    Always takes at least one hop, so a loop back to start renders as the full cycle rather than
    the bare source_id.
    """
    hops, seen = [start], {start}
    cursor = parents.get(start, "")
    while cursor:
        hops.append(cursor)
        if cursor == target or cursor in seen:
            break
        seen.add(cursor)
        cursor = parents.get(cursor, "")
    return " derives from ".join(hops)


def inclusive_ancestors(source_id, parents):
    """The source itself plus every origin it records, to any depth, nearest first."""
    return [source_id] + derivation_chain(source_id, parents)


def independence_defect(sid, other, parents):
    """Why sid and other cannot corroborate each other, or None when the register records nothing
    that makes them one disclosure.

    The test is intersection of the two inclusive ancestor sets. Ancestry and descent are named
    separately because the route matters to whoever has to correct the register, but both are the
    same failure as a shared third origin: two rows that agree because one copied what the other
    copied are one disclosure arriving twice, not motive-independent confirmation of it.
    """
    if other in derivation_chain(sid, parents):
        return (f"'{other}' is an origin of '{sid}', "
                f"{derivation_path(sid, other, parents)}")
    if sid in derivation_chain(other, parents):
        return (f"'{other}' is a derivative of '{sid}', "
                f"{derivation_path(other, sid, parents)}")
    theirs = set(inclusive_ancestors(other, parents))
    shared = next((s for s in inclusive_ancestors(sid, parents) if s in theirs), None)
    if shared is not None:
        return (f"'{other}' and '{sid}' share the recorded origin '{shared}': "
                f"{derivation_path(sid, shared, parents)}, and "
                f"{derivation_path(other, shared, parents)}")
    return None


MIRROR_LIMIT = "A mirror of a disclosure is not motive-independent confirmation of it."


def arm_sources(rows, root, report, decisions=None, contract_name="v0.2"):
    ids, held, unretrieved = set(), 0, 0
    latest_scope_date = latest_scope_decision_date(decisions)

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

        if contract_name == "v0.3" and unusable_value(sid):
            report.check(False, f"row {i}: source_id '{sid}' carries no content. Every claim and "
                                f"every derivation reference addresses a source by this value.",
                         "SOURCES")

        if contract_name == "v0.3" and unusable_value(r.get("source_role")):
            report.check(False, f"{sid}: no source_role. Record what this source is authoritative "
                                f"for separately from the incentive its motive tier records. A "
                                f"status page is authoritative for what the provider disclosed, "
                                f"not for what occurred.", "SOURCES")

        status = (r["retrieval_status"] or "").strip()

        if contract_name == "v0.3":
            # A row that names nothing and points nowhere cannot be checked by anyone else, so it
            # cannot support a claim or count in the retrieval denominator as a real route.
            if unusable_value(r.get("title")):
                report.check(False, f"{sid}: no usable title. A source nobody else can identify "
                                    f"cannot be looked up, and cannot be shown to say what the "
                                    f"register claims it says.", "SOURCES")
            if unusable_value(r.get("publisher")):
                report.check(False, f"{sid}: no usable publisher. Who published a source is what "
                                    f"its motive tier is a judgement about.", "SOURCES")

            # A locator is usable when it can actually be followed: an absolute http or https URL,
            # or held bytes at a path that exists. A non-blank string in either column is not the
            # same thing, and was the gap: '!!!' satisfied the old check.
            url_value = (r.get("url") or "").strip()
            path_value = (r.get("local_path") or "").strip()
            url_ok = usable_url(url_value)
            path_held = contained_file(root, path_value)
            if url_value and not url_ok:
                report.check(False, f"{sid}: url '{url_value}' is not a usable locator. Record an "
                                    f"absolute {' or '.join(sorted(ALLOWED_URL_SCHEMES))} URL "
                                    f"naming a host, or leave the column empty and hold the bytes.",
                             "SOURCES")
            # The retrieved branch below owns custody for its own rows and reports the missing file
            # itself. Any other status claiming a path is checked here.
            if path_value and not path_held and status != "retrieved":
                report.check(False, f"{sid}: local_path names '{path_value}', which does not "
                                    f"resolve to a file inside the project. A path recorded as a "
                                    f"locator points at bytes the reader can open, held here "
                                    f"rather than somewhere on the machine that ran the gate.",
                             "SOURCES")
            if not url_ok and not path_held:
                report.check(False, f"{sid}: no usable locator. A source carries an absolute "
                                    f"{' or '.join(sorted(ALLOWED_URL_SCHEMES))} URL, or held "
                                    f"bytes at a local_path that exists, so a reader can reach the "
                                    f"same material or see exactly which route was refused.",
                             "SOURCES")
        if status == "retrieved":
            if blank(r["local_path"]):
                report.check(False, f"{sid}: retrieved but no local_path", "SOURCES")
                continue
            p = root / r["local_path"]
            # v0.3 requires custody to resolve inside the project. v0.1 and v0.2 keep the existing
            # existence test, because changing what they accept is outside this repair.
            if contract_name == "v0.3":
                p = contained_path(root, r["local_path"])
            if contract_name == "v0.3" and p is None:
                report.check(False, f"{sid}: local_path '{(r['local_path'] or '').strip()}' does "
                                    f"not resolve to a file inside the project. Held bytes live in "
                                    f"the project directory, so a third party receives them with "
                                    f"the register.", "SOURCES")
                continue
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
            reason_empty = unusable_value if contract_name == "v0.3" else blank
            if reason_empty(r["notes"]):
                report.check(False, f"{sid}: registered_not_retrieved with no reason in notes. "
                                    f"Record what was tried and what happened.", "SOURCES")
        if blank(r["accessed_date"]):
            report.check(False, f"{sid}: no accessed_date", "SOURCES")
        else:
            accessed_date = parse_iso_date(r["accessed_date"])
            if accessed_date is None and contract_name in {"v0.2", "v0.3"}:
                report.check(False, f"{sid}: accessed_date must be an ISO date", "SOURCES")
            elif accessed_date is not None and latest_scope_date and accessed_date < latest_scope_date:
                report.check(False, f"{sid}: accessed_date {accessed_date.isoformat()} is earlier "
                                    f"than final scope decision date {latest_scope_date.isoformat()}. "
                                    f"Data collection cannot precede completion of scope decisions (S1-S6).",
                             "SOURCES")

    if contract_name == "v0.3":
        derived = {(r["source_id"] or "").strip(): (r.get("derived_from") or "").strip()
                   for r in rows}
        for r in rows:
            sid = (r["source_id"] or "").strip()
            origin = derived.get(sid, "")
            if origin and origin not in ids:
                report.check(False, f"{sid}: derived_from names '{origin}', which is not "
                                    f"registered in sources.csv", "SOURCES")
            if origin and origin == sid:
                report.check(False, f"{sid}: derived_from names itself", "SOURCES")
            elif origin and sid in derivation_chain(origin, derived):
                report.check(False, f"{sid}: derived_from closes a loop, "
                                    f"{derivation_path(sid, sid, derived)}. A set of sources that "
                                    f"all derive from each other has no origin, so no row in the "
                                    f"loop can be traced to what it restates.", "SOURCES")
            second = (r.get("second_source_id") or "").strip()
            if not second:
                continue
            if second not in ids:
                report.check(False, f"{sid}: second_source_id names '{second}', which is not "
                                    f"registered in sources.csv", "SOURCES")
                continue
            if second == sid:
                report.check(False, f"{sid}: is recorded as its own second source", "SOURCES")
            else:
                # Derivation is transitive and it branches. A second source is refused when it is
                # this source's origin, its derivative, or a row reached from the same origin at
                # any depth. Two mirrors of one disclosure confirm each other exactly as little as
                # a mirror confirms the disclosure.
                defect = independence_defect(sid, second, derived)
                if defect:
                    report.check(False, f"{sid}: second_source_id {defect}. {MIRROR_LIMIT}",
                                 "SOURCES")

    total = len(ids)
    if total:
        report.note(f"{total} sources, {held} held and hash-verified, "
                    f"{unretrieved} registered and not retrieved "
                    f"({100 * unretrieved / total:.0f}% of the register)")
    return ids


INTERESTED_TIERS = {"4", "5"}
UNOBTAINED = "registered_not_retrieved"


def arm_claims(rows, sources, source_ids, report, root, contract_name=DEFAULT_CONTRACT):
    """Claim rows against the source register.

    What this arm establishes under v0.3: each row has a unique identifier and text, cites a
    registered source that was actually obtained, and, where the claim is material and its source
    is interested, names a second source that is registered, obtained, not itself interested, and
    not recorded as the same disclosure.

    What it does not establish: that either source supports the claim. Registered eligibility and
    recorded independence are mechanical. Whether the second source says the thing the claim says
    is a reviewer's call and no part of this arm reads for it.
    """
    tier = {(r["source_id"] or "").strip(): (r["motive_tier"] or "").strip() for r in sources}
    second = {(r["source_id"] or "").strip(): (r["second_source_id"] or "").strip()
              for r in sources}
    status = {(r["source_id"] or "").strip(): (r.get("retrieval_status") or "").strip()
              for r in sources}
    derived = {(r["source_id"] or "").strip(): (r.get("derived_from") or "").strip()
               for r in sources}
    # Whether a reader could reach the source at all. The SOURCES arm refuses an unreachable row on
    # its own account; this arm checks it again for the corroborator rather than assuming the other
    # arm fired, because a second source nobody can open confirms nothing whichever arm notices.
    reachable = {
        (r["source_id"] or "").strip(): (usable_url(r.get("url"))
                                         or contained_file(root, r.get("local_path")))
        for r in sources
    }
    material_field = CLAIM_MATERIAL_FIELDS[contract_name]
    material_count = 0
    seen_ids = set()
    for i, r in enumerate(rows, start=2):
        raw_id = (r["claim_id"] or "").strip()
        cid = raw_id or f"row {i}"
        if contract_name == "v0.3":
            # Identity and content, kept separate from support. A duplicate identifier makes every
            # later evidence marker and correction ambiguous, and a blank claim has nothing to
            # verify. Neither is detectable once the register is in use.
            if unusable_value(raw_id):
                report.check(False, f"row {i}: no usable claim_id. Every claim carries a stable "
                                    f"identifier, because later corrections and evidence markers "
                                    f"address it by that identifier. A blank, a placeholder or "
                                    f"punctuation alone addresses nothing.", "CLAIMS")
            elif raw_id.lower() in seen_ids:
                report.check(False, f"row {i}: claim_id '{raw_id}' is already used. Two rows under "
                                    f"one identifier make every reference to it ambiguous.",
                             "CLAIMS")
            else:
                seen_ids.add(raw_id.lower())
            if unusable_value(r.get("claim_text")):
                report.check(False, f"{cid}: no usable claim_text. A blank, a placeholder or "
                                    f"punctuation alone states no proposition, so there is nothing "
                                    f"here to verify.", "CLAIMS")
        sid = (r["source_id"] or "").strip()
        if not sid:
            report.check(False, f"{cid}: cites no source", "CLAIMS")
            continue
        if sid not in source_ids:
            report.check(False, f"{cid}: cites '{sid}', which is not in sources.csv", "CLAIMS")
            continue
        uncertainty_empty = unusable_value if contract_name == "v0.3" else blank
        if uncertainty_empty(r["uncertainty"]):
            report.check(False, f"{cid}: no uncertainty recorded. A point estimate is a "
                                f"choice (G5), so state it as one.", "CLAIMS")
        if contract_name == "v0.3" and status.get(sid) == UNOBTAINED:
            report.check(False, f"{cid}: cites '{sid}', whose retrieval_status is "
                                f"'{UNOBTAINED}'. The source stays in the register and in the "
                                f"retrieval denominator under D3, but text nobody obtained cannot "
                                f"be the ground for extracted text.", "CLAIMS")
        if (r[material_field] or "").strip().lower() == "yes":
            material_count += 1
            # D4 and the AGP source-tier gate: faithful transcription of a self-interested
            # source still fails. Grounding is not truth.
            if contract_name == "v0.3":
                claim_corroboration(cid, sid, r, source_ids, tier, status, derived, reachable,
                                    report)
            elif tier.get(sid) in INTERESTED_TIERS and blank(second.get(sid)):
                report.check(False, f"{cid}: material to the conclusion, grounded only in {sid} at motive "
                                    f"tier {tier.get(sid)}, and that source has no "
                                    f"second_source_id", "CLAIMS")
    report.note(f"{len(rows)} claims, {material_count} material to the conclusion")


def claim_corroboration(cid, sid, row, source_ids, tier, status, derived, reachable, report):
    """The v0.3 second-source rule, held on the claim rather than on the source.

    A source can carry several unrelated statements, so a source-level second_source_id cannot
    establish confirmation of each of them. The corroborating source is named on the claim row that
    relies on it, and the same independence test that governs the source register governs the pair.
    """
    if tier.get(sid) not in INTERESTED_TIERS:
        return
    corroborator = (row.get("corroborating_source_id") or "").strip()
    if blank(corroborator):
        report.check(False, f"{cid}: material to the conclusion, grounded in '{sid}' at motive "
                            f"tier {tier.get(sid)}, and the row names no "
                            f"corroborating_source_id. D4 requires motive-independent "
                            f"confirmation of this claim, named on this claim.", "CLAIMS")
        return
    if corroborator not in source_ids:
        report.check(False, f"{cid}: corroborating_source_id '{corroborator}' is not registered in "
                            f"sources.csv", "CLAIMS")
        return
    if corroborator == sid:
        report.check(False, f"{cid}: names '{sid}' as its own corroborating source", "CLAIMS")
        return
    if status.get(corroborator) == UNOBTAINED:
        report.check(False, f"{cid}: corroborating source '{corroborator}' has retrieval_status "
                            f"'{UNOBTAINED}'. A second source nobody obtained confirms nothing.",
                     "CLAIMS")
    if tier.get(corroborator) in INTERESTED_TIERS:
        report.check(False, f"{cid}: corroborating source '{corroborator}' is itself at motive "
                            f"tier {tier.get(corroborator)}. Two interested sources do not make "
                            f"one motive-independent confirmation.", "CLAIMS")
    if not reachable.get(corroborator, False):
        report.check(False, f"{cid}: corroborating source '{corroborator}' has no usable locator, "
                            f"so nobody can reach the material that is supposed to confirm this "
                            f"claim.", "CLAIMS")
    defect = independence_defect(sid, corroborator, derived)
    if defect:
        report.check(False, f"{cid}: corroborating source {defect}. {MIRROR_LIMIT}", "CLAIMS")


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


BARE_NUMBER = re.compile(r"(?<![\w./-])\d[\d,]*(?:\.\d+)?(?![\w./-])")


def arm_feasibility(rows, root, report, decisions=None, required=True):
    """The bounded pre-scope route.

    What this arm establishes: every probe asks a permitted question, returns a permitted
    outcome-free result, names who ran it, is dated no later than the close of scope, and holds
    and hashes any bytes it claims to hold.

    What it does not establish: that a probe's free-text notes are free of outcome information.
    The structured fields are closed enums and the column set is fixed, so a count has no field to
    arrive in, but prose is prose. Numeric tokens in notes are reported for a human to read.
    """
    if not rows:
        if required:
            report.check(False, "feasibility.csv has no probes. Under v0.3 the evidence route is "
                                "established before outcome data is collected. Record one probe "
                                "per permitted question, using result 'unknown' with a reason "
                                "where the route could not be tested.", "FEASIBILITY")
        return

    latest_scope_date = latest_scope_decision_date(decisions)
    seen_ids, seen_questions, flagged_numbers = set(), set(), []

    for i, r in enumerate(rows, start=2):
        pid = (r["probe_id"] or "").strip() or f"row {i}"
        if unusable_value(r["probe_id"]):
            report.check(False, f"row {i}: no usable probe_id. The register addresses a probe by "
                                f"this value, and punctuation addresses nothing.", "FEASIBILITY")
        elif pid in seen_ids:
            report.check(False, f"row {i}: probe_id {pid} is recorded twice", "FEASIBILITY")
        seen_ids.add(pid)

        if unusable_value(r["source_name"]):
            report.check(False, f"{pid}: no source_name. A probe is about a named source.",
                         "FEASIBILITY")
        if unidentifiable_actor(r["probed_by"]):
            report.check(False, f"{pid}: no comparable probed_by. Use "
                                f"'model=...; harness=...; run=...' with an optional "
                                f"'role=...'.", "FEASIBILITY")

        question = (r["question"] or "").strip()
        if question not in FEASIBILITY_QUESTIONS:
            report.check(False, f"{pid}: question is '{question}'. The feasibility route asks only "
                                f"{', '.join(sorted(FEASIBILITY_QUESTIONS))}.", "FEASIBILITY")
        else:
            seen_questions.add(question)

        result = (r["result"] or "").strip()
        if result not in FEASIBILITY_RESULTS:
            report.check(False, f"{pid}: result is '{result}'. A feasibility probe returns one of "
                                f"{', '.join(sorted(FEASIBILITY_RESULTS))} and never an outcome "
                                f"value. Counting results, estimating the effect or recording a "
                                f"measurement here defeats the route.", "FEASIBILITY")
        elif result != "available" and unusable_value(r["notes"]):
            report.check(False, f"{pid}: result '{result}' with no reason in notes. Record what "
                                f"was tried and what happened.", "FEASIBILITY")

        access_date = None
        if blank(r["access_date"]):
            report.check(False, f"{pid}: no access_date", "FEASIBILITY")
        else:
            access_date = parse_iso_date(r["access_date"])
            if access_date is None:
                report.check(False, f"{pid}: access_date must be an ISO date", "FEASIBILITY")
            elif latest_scope_date and access_date > latest_scope_date:
                report.check(False, f"{pid}: access_date {access_date.isoformat()} is later than "
                                    f"the final scope decision date "
                                    f"{latest_scope_date.isoformat()}. The feasibility route runs "
                                    f"before scope closes. A probe dated after it is data "
                                    f"collection under another name, and it bypasses the SOURCES "
                                    f"scope-date rule.", "FEASIBILITY")

        if question == "bytes_retrievable" and result == "available":
            if blank(r["local_path"]):
                report.check(False, f"{pid}: bytes reported retrievable but no local_path. The "
                                    f"probe claims custody is possible, so it holds the bytes.",
                             "FEASIBILITY")
            else:
                # Custody is the same rule here as in the source register, through the same
                # predicate. exists() answered only whether bytes were somewhere on the machine,
                # so an absolute external path, a parent traversal and a symlink out of the
                # project all passed whenever the external bytes matched the recorded hash. The
                # hash is taken from the resolved file, so what is hashed is what was contained.
                path_value = (r["local_path"] or "").strip()
                held_path = contained_path(root, path_value)
                if held_path is None:
                    report.check(False, f"{pid}: local_path '{path_value}' does not resolve to a "
                                        f"file inside the project. A probe that reports custody "
                                        f"holds the bytes here, so a third party receives them "
                                        f"with the register rather than a path onto the machine "
                                        f"that ran the gate.", "FEASIBILITY")
                else:
                    held_bytes = held_path.read_bytes()
                    got = hashlib.sha256(held_bytes).hexdigest()
                    recorded = (r["sha256"] or "").strip()
                    if blank(r["sha256"]):
                        report.check(False, f"{pid}: held but not hashed. Recorded hash should be "
                                            f"{got}", "FEASIBILITY")
                    elif got != recorded:
                        report.check(False, f"{pid}: hash mismatch. File is {got}, register says "
                                            f"{recorded}", "FEASIBILITY")

        if question == "period_and_retention":
            if unusable_value(r["stated_period"]):
                report.check(False, f"{pid}: no stated_period recorded for a period and retention "
                                    f"probe", "FEASIBILITY")
            if unusable_value(r["retention_policy"]):
                report.check(False, f"{pid}: no retention_policy recorded for a period and "
                                    f"retention probe", "FEASIBILITY")

        if question == "derivation_independence":
            value = (r["derives_from_subject"] or "").strip().lower()
            if value not in FEASIBILITY_TERNARY:
                report.check(False, f"{pid}: derives_from_subject is '{value}', expected one of "
                                    f"{', '.join(sorted(FEASIBILITY_TERNARY))}. A source that "
                                    f"restates the subject's own disclosure is circular and the "
                                    f"register says so.", "FEASIBILITY")

        if question == "population_coverage":
            value = (r["covers_population"] or "").strip().lower()
            if value not in FEASIBILITY_TERNARY:
                report.check(False, f"{pid}: covers_population is '{value}', expected one of "
                                    f"{', '.join(sorted(FEASIBILITY_TERNARY))}", "FEASIBILITY")

        # Either route will do, but the one that is present has to be followable. A probe whose
        # only record of where it looked is punctuation has recorded nothing.
        if unusable_value(r["evidence_locator"]) and not usable_url(r["url"]):
            report.check(False, f"{pid}: no usable record of where the probe looked. Give an "
                                f"absolute {' or '.join(sorted(ALLOWED_URL_SCHEMES))} url, an "
                                f"evidence_locator, or both.", "FEASIBILITY")

        for token in BARE_NUMBER.findall(r["notes"] or ""):
            if len(token.replace(",", "")) >= 2:
                flagged_numbers.append(f"{pid}:{token}")

    if required:
        missing = sorted(set(FEASIBILITY_QUESTIONS) - seen_questions)
        if missing:
            report.check(False, f"no probe recorded for {', '.join(missing)}. Each permitted "
                                f"question is answered before outcome data is collected, using "
                                f"result 'unknown' with a reason where it could not be tested.",
                         "FEASIBILITY")

    report.note(f"{len(rows)} feasibility probe(s) across {len(seen_questions)} of "
                f"{len(FEASIBILITY_QUESTIONS)} permitted questions")
    untested = [r for r in rows if (r["result"] or "").strip() == "unknown"]
    if rows and len(untested) == len(rows):
        # Structurally complete and evidentially empty. The register is not failed for this: an
        # untested route is information and the denominator keeps it. Whether scope may proceed on
        # a route nothing established is the researcher's call, and SCOPE_APPROVAL is where that
        # call is recorded.
        report.note(f"every one of the {len(rows)} probe(s) returned 'unknown', so the register is "
                    f"structurally complete and establishes no evidence route. Stage 'data' opens "
                    f"on the recorded approval in {SCOPE_APPROVAL_FILE}, not on this register.")
    if flagged_numbers:
        report.note(f"feasibility notes carry {len(flagged_numbers)} numeric token(s), check by "
                    f"hand that none is an outcome value: {', '.join(flagged_numbers[:8])}"
                    f"{' ...' if len(flagged_numbers) > 8 else ''}")


def arm_scope_review(root, decisions, report):
    """The scope coherence review record.

    What this arm establishes: the record exists and parses, names a reviewer who is not a
    decision-maker on any reviewed row, is dated no earlier than the decisions it reviews, covers
    every reviewed decision id, carries a digest matching each of those rows as they stand now,
    and records a result and a note against each of the six required checks.

    What it does not establish: that Q3 disconfirms Q2, that S1 is observable, or any other
    substantive coherence call. Those are the reviewer's, recorded here and not verified here.
    """
    path = root / SCOPE_REVIEW_FILE
    safe_path = contained_path(root, SCOPE_REVIEW_FILE)
    if safe_path is None:
        location = "missing" if not path.is_file() else "outside the project"
        report.check(False, f"{SCOPE_REVIEW_FILE} is {location}. Before stage 'data' a reviewer other "
                            f"than the runner records the scope coherence review. Copy "
                            f"{SCOPE_REVIEW_TEMPLATE_FILE} and run --scope-digests for the digest "
                            f"block.", "SCOPE_REVIEW")
        return
    try:
        record = json.loads(safe_path.read_text(encoding="utf-8"))
    except Exception as exc:
        report.check(False, f"{SCOPE_REVIEW_FILE} is malformed: {exc}", "SCOPE_REVIEW")
        return
    if not isinstance(record, dict):
        report.check(False, f"{SCOPE_REVIEW_FILE} root JSON must be an object", "SCOPE_REVIEW")
        return

    if record.get("record_type") != SCOPE_REVIEW_RECORD_TYPE:
        report.check(False, f"record_type must be '{SCOPE_REVIEW_RECORD_TYPE}'", "SCOPE_REVIEW")
    if record.get("schema_version") != SCOPE_REVIEW_SCHEMA_VERSION:
        report.check(False, f"scope review schema_version must be "
                            f"'{SCOPE_REVIEW_SCHEMA_VERSION}'", "SCOPE_REVIEW")
    if (record.get("contract") or "").strip().lower() != "v0.3":
        report.check(False, "scope review contract must be 'v0.3'", "SCOPE_REVIEW")

    reviewer = record.get("reviewer")
    if not isinstance(reviewer, str) or unidentifiable_actor(reviewer):
        report.check(False, "no comparable reviewer recorded. Use "
                            "'model=...; harness=...; run=...' with an optional 'role=...'. "
                            "The run identifier distinguishes sandboxed runs; role labels do not.",
                     "SCOPE_REVIEW")
        reviewer = ""

    review_date = None
    raw_date = record.get("review_date")
    if not isinstance(raw_date, str) or blank(raw_date):
        report.check(False, "no review_date recorded", "SCOPE_REVIEW")
    else:
        review_date = parse_iso_date(raw_date)
        if review_date is None:
            report.check(False, "review_date must be an ISO date", "SCOPE_REVIEW")

    by_id = {}
    for r in decisions or []:
        did = (r.get("decision_id") or "").strip().upper()
        if did and did not in by_id:
            by_id[did] = r

    reviewed = record.get("reviewed_decisions")
    if not isinstance(reviewed, dict):
        report.check(False, "reviewed_decisions must be an object mapping each reviewed decision "
                            "id to the digest of its row", "SCOPE_REVIEW")
    else:
        got = {str(k).strip().upper() for k in reviewed}
        expected = set(SCOPE_REVIEW_DECISIONS)
        if got != expected:
            report.check(False, f"reviewed_decisions must cover exactly "
                                f"{', '.join(SCOPE_REVIEW_DECISIONS)}; it covers "
                                f"{', '.join(sorted(got)) or 'nothing'}", "SCOPE_REVIEW")
        reviewer_key = actor_identity(reviewer)
        for did in SCOPE_REVIEW_DECISIONS:
            recorded = None
            for k, v in reviewed.items():
                if str(k).strip().upper() == did:
                    recorded = v
                    break
            if recorded is None:
                continue
            row = by_id.get(did)
            if row is None:
                report.check(False, f"{did} is reviewed but is not logged in decisions.csv",
                             "SCOPE_REVIEW")
                continue
            if not isinstance(recorded, str) or not SHA256_HEX.fullmatch(recorded.strip()):
                report.check(False, f"{did}: digest must be 64 lowercase hexadecimal characters",
                             "SCOPE_REVIEW")
                continue
            actual = decision_row_digest(row)
            if recorded.strip() != actual:
                report.check(False, f"{did}: reviewed digest {recorded.strip()[:12]}... does not "
                                    f"match the current row, which digests to {actual[:12]}.... "
                                    f"The row changed after the review, so the review no longer "
                                    f"binds. Re-review and re-record.", "SCOPE_REVIEW")
            if reviewer_key and reviewer_key == actor_identity(row.get("decided_by")):
                report.check(False, f"{did}: the reviewer '{reviewer.strip()}' is the decision "
                                    f"maker on this row. The scope review is performed by someone "
                                    f"other than the runner who made the choice.", "SCOPE_REVIEW")
            if review_date is not None and not blank(row.get("decided_date")):
                decided = parse_iso_date(row["decided_date"])
                if decided is not None and review_date < decided:
                    report.check(False, f"{did}: review_date {review_date.isoformat()} precedes "
                                        f"the decision it reviews, dated {decided.isoformat()}",
                                 "SCOPE_REVIEW")

    checks = record.get("checks")
    if not isinstance(checks, dict):
        report.check(False, f"checks must be an object covering "
                            f"{', '.join(sorted(SCOPE_REVIEW_CHECKS))}", "SCOPE_REVIEW")
        return None
    if set(checks) != set(SCOPE_REVIEW_CHECKS):
        report.check(False, f"checks must cover exactly "
                            f"{', '.join(sorted(SCOPE_REVIEW_CHECKS))}", "SCOPE_REVIEW")
    exceptional = set()
    for name in sorted(SCOPE_REVIEW_CHECKS):
        item = checks.get(name)
        if not isinstance(item, dict):
            report.check(False, f"check '{name}' must be an object with a result and a note",
                         "SCOPE_REVIEW")
            continue
        result = (item.get("result") or "").strip().lower() if isinstance(item.get("result"), str) else ""
        if result not in SCOPE_REVIEW_RESULTS:
            report.check(False, f"check '{name}': result is '{result}', expected one of "
                                f"{', '.join(sorted(SCOPE_REVIEW_RESULTS))}", "SCOPE_REVIEW")
        note = item.get("note")
        if not isinstance(note, str) or unusable_value(note):
            report.check(False, f"check '{name}': no note. Record what was read and why the result "
                                f"follows, in the reviewer's own words.", "SCOPE_REVIEW")
        if result in {"fail", "unresolved"}:
            exceptional.add(name)
        # Acceptance moved out of this record entirely. Any string here cleared a failure, and the
        # reviewer could write its own name, so the exception control accepted the finding it was
        # written to escalate. The review states the result; SCOPE_APPROVAL carries who accepted it.
        if "exception_accepted_by" in item and not blank(item.get("exception_accepted_by")
                                                         if isinstance(item.get("exception_accepted_by"), str)
                                                         else ""):
            report.check(False, f"check '{name}': exception_accepted_by no longer carries "
                                f"acceptance and free text here cannot clear a result. Record the "
                                f"result as the reviewer found it and put the acceptance in "
                                f"{SCOPE_APPROVAL_FILE}, which is bound by hash to the rows and "
                                f"the review it accepts.", "SCOPE_REVIEW")

    report.note(f"scope coherence review by '{(reviewer or '').strip()}' covering "
                f"{len(SCOPE_REVIEW_DECISIONS)} decision rows against "
                f"{len(SCOPE_REVIEW_CHECKS)} recorded checks, "
                f"{len(exceptional)} recorded fail or unresolved; the arm binds the record to the "
                f"rows and does not verify the coherence calls themselves")
    return exceptional


def arm_scope_approval(root, exceptional, report):
    """The retained human decision to open stage 3, recorded apart from the review it reads.

    What this arm establishes: a record exists that names the fixed recorded authority, carries a
    closed decision value, lists exactly the review checks the reviewer left failed or unresolved,
    and still matches the closed question-and-scope decision projection and the two files it was
    written against. Editing any bound scope row or either bound file invalidates it. Later-stage
    decision rows do not.

    What it does not establish: who wrote the record. There is no signature and no external
    witness here, so the gate can say the record says 'N.' and that it matches what was reviewed.
    It cannot say N. created it. That limit is the reason the record is bound to the bytes: a
    changed scope needs a fresh approval rather than a preserved one.
    """
    path = root / SCOPE_APPROVAL_FILE
    safe_path = contained_path(root, SCOPE_APPROVAL_FILE)
    if safe_path is None:
        location = "missing" if not path.is_file() else "outside the project"
        report.check(False, f"{SCOPE_APPROVAL_FILE} is {location}. From stage 'data' the decision to "
                            f"proceed on the reviewed scope is the researcher's and is recorded "
                            f"separately from the review. Copy {SCOPE_APPROVAL_TEMPLATE_FILE}, "
                            f"complete it, and record the digests of the files it approves.",
                            "SCOPE_APPROVAL")
        return
    try:
        record = json.loads(safe_path.read_text(encoding="utf-8"))
    except Exception as exc:
        report.check(False, f"{SCOPE_APPROVAL_FILE} is malformed: {exc}", "SCOPE_APPROVAL")
        return
    if not isinstance(record, dict):
        report.check(False, f"{SCOPE_APPROVAL_FILE} root JSON must be an object", "SCOPE_APPROVAL")
        return

    if record.get("record_type") != SCOPE_APPROVAL_RECORD_TYPE:
        report.check(False, f"record_type must be '{SCOPE_APPROVAL_RECORD_TYPE}'",
                     "SCOPE_APPROVAL")
    if record.get("schema_version") != SCOPE_APPROVAL_SCHEMA_VERSION:
        report.check(False, f"approval schema_version must be "
                            f"'{SCOPE_APPROVAL_SCHEMA_VERSION}'", "SCOPE_APPROVAL")
    if (record.get("contract") or "").strip().lower() != "v0.3":
        report.check(False, "approval contract must be 'v0.3'", "SCOPE_APPROVAL")

    approved_by = record.get("approved_by")
    approved_by = approved_by if isinstance(approved_by, str) else ""
    if normalise_actor(approved_by) != normalise_actor(SCOPE_APPROVAL_AUTHORITY):
        report.check(False, f"approved_by is '{approved_by.strip()}'. Acceptance of an unresolved "
                            f"scope finding is reserved to {SCOPE_APPROVAL_AUTHORITY} and no "
                            f"reviewer, runner or model substitutes for that authority.",
                     "SCOPE_APPROVAL")

    approval_date = None
    raw_date = record.get("approval_date")
    if not isinstance(raw_date, str) or blank(raw_date):
        report.check(False, "no approval_date recorded", "SCOPE_APPROVAL")
    else:
        approval_date = parse_iso_date(raw_date)
        if approval_date is None:
            report.check(False, "approval_date must be an ISO date", "SCOPE_APPROVAL")

    decision = record.get("decision")
    decision = (decision or "").strip().lower() if isinstance(decision, str) else ""
    if decision not in SCOPE_APPROVAL_DECISIONS:
        report.check(False, f"decision is '{decision}', expected one of "
                            f"{', '.join(sorted(SCOPE_APPROVAL_DECISIONS))}", "SCOPE_APPROVAL")
    elif decision != SCOPE_APPROVAL_OPENS:
        report.check(False, f"decision is '{decision}'. Stage 'data' opens on "
                            f"'{SCOPE_APPROVAL_OPENS}' and on nothing else. A scope recorded as "
                            f"held or under revision has not been approved for data collection.",
                     "SCOPE_APPROVAL")

    reference = record.get("approval_reference")
    if not isinstance(reference, str):
        report.check(False, "approval_reference must be a string naming the dated decision or "
                            "handoff this approval records", "SCOPE_APPROVAL")
    else:
        defect = reference_defect(reference)
        if defect:
            report.check(False, f"approval_reference: {defect}.", "SCOPE_APPROVAL")

    bound = record.get("bound_files")
    if not isinstance(bound, dict):
        report.check(False, f"bound_files must be an object mapping each of "
                            f"{', '.join(SCOPE_APPROVAL_BOUND_FILES)} to its SHA-256 digest",
                     "SCOPE_APPROVAL")
    elif set(bound) != set(SCOPE_APPROVAL_BOUND_FILES):
        report.check(False, f"bound_files must cover exactly "
                            f"{', '.join(SCOPE_APPROVAL_BOUND_FILES)}; it covers "
                            f"{', '.join(sorted(bound)) or 'nothing'}", "SCOPE_APPROVAL")
    else:
        for name in SCOPE_APPROVAL_BOUND_FILES:
            recorded = bound.get(name)
            if not isinstance(recorded, str) or not SHA256_HEX.fullmatch(recorded.strip()):
                report.check(False, f"bound_files['{name}']: digest must be 64 lowercase "
                                    f"hexadecimal characters", "SCOPE_APPROVAL")
                continue
            actual = approval_binding_digest(root, name)
            if actual is None:
                report.check(False, f"bound_files names '{name}', which cannot be resolved from "
                                    f"the project", "SCOPE_APPROVAL")
                continue
            if recorded.strip() != actual:
                report.check(False, f"{name} has changed since the approval: approved "
                                    f"{recorded.strip()[:12]}..., current {actual[:12]}.... The "
                                    f"approval covered the scope as it stood, so it no longer "
                                    f"binds. Re-approve the current record.", "SCOPE_APPROVAL")

    accepted = record.get("accepted_checks")
    if not isinstance(accepted, list) or not all(isinstance(x, str) for x in accepted):
        report.check(False, "accepted_checks must be a list of scope review check identifiers, "
                            "empty where the review left nothing failed or unresolved",
                     "SCOPE_APPROVAL")
    else:
        named = [x.strip() for x in accepted]
        unknown = sorted(set(named) - set(SCOPE_REVIEW_CHECKS))
        if unknown:
            report.check(False, f"accepted_checks names {', '.join(unknown)}, which "
                                f"{'are' if len(unknown) > 1 else 'is'} not a scope review check",
                         "SCOPE_APPROVAL")
        if len(set(named)) != len(named):
            report.check(False, "accepted_checks lists the same check more than once",
                         "SCOPE_APPROVAL")
        if exceptional is not None and set(named) != set(exceptional):
            report.check(False, f"accepted_checks is "
                                f"{'{' + ', '.join(sorted(named)) + '}' if named else 'empty'} but "
                                f"the review records "
                                f"{'{' + ', '.join(sorted(exceptional)) + '}' if exceptional else 'no'} "
                                f"failed or unresolved check(s). The approval names the exact set "
                                f"it accepts, so an exception cannot be added to the review or "
                                f"dropped from it after the fact.", "SCOPE_APPROVAL")

    if approval_date is not None:
        review_path = contained_path(root, SCOPE_REVIEW_FILE)
        if review_path is not None:
            try:
                reviewed_on = parse_iso_date(
                    json.loads(review_path.read_text(encoding="utf-8")).get("review_date"))
            except Exception:
                reviewed_on = None
            if reviewed_on is not None and approval_date < reviewed_on:
                report.check(False, f"approval_date {approval_date.isoformat()} precedes the "
                                    f"review it accepts, dated {reviewed_on.isoformat()}",
                             "SCOPE_APPROVAL")

    report.note(f"scope approval recorded by '{approved_by.strip()}' as '{decision}', accepting "
                f"{len(accepted) if isinstance(accepted, list) else 0} exceptional check(s) and "
                f"bound to {len(SCOPE_APPROVAL_BOUND_FILES)} files; the arm reads the record, and "
                f"nothing here authenticates who created it")


def arm_draft(root, decisions, claims, report):
    drafts = sorted(p for p in root.glob("*.md") if not p.name.startswith("_"))
    if not drafts:
        report.check(False, "no draft .md found in the project directory", "DRAFT")
        return
    for p in drafts:
        safe_path = contained_path(root, p.name)
        if safe_path is None:
            report.check(False, f"{p.name} does not resolve to a file inside the project. The v0.3 "
                         f"draft bytes must travel with the project.", "DRAFT")
            continue
        text = safe_path.read_text(encoding="utf-8", errors="replace")
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


def evaluate(root, through, contract=None):
    """Run every applicable arm and return the report. run() is the printing wrapper."""
    report = Report()
    root = Path(root)

    contract_name, required_schema = arm_manifest(root, report, cli_contract=contract)

    decisions = read_csv(root / "decisions.csv", report, needed_at="question", through=through,
                         contract_name=contract_name, project_root=root,
                         containment_arm="DECISIONS")
    sources = read_csv(root / "sources.csv", report, needed_at="data", through=through,
                       contract_name=contract_name, project_root=root,
                       containment_arm="SOURCES")
    claims = read_csv(root / "claims.csv", report, needed_at="digest", through=through,
                      contract_name=contract_name, project_root=root,
                      containment_arm="CLAIMS")
    vocab = read_csv(root / "vocabulary.csv", report, needed_at="digest", through=through,
                     contract_name=contract_name, project_root=root,
                     containment_arm="VOCAB")

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
        arm_claims(claims, sources, source_ids, report, root, contract_name=contract_name)
    if vocab:
        arm_vocab(vocab, {"sources.csv": sources, "claims.csv": claims}, report)

    if contract_name == "v0.3":
        at_data = STAGES.index(through) >= STAGES.index("data")
        # arm_feasibility owns the emptiness rule, because the register legitimately fills during
        # stages 1 and 2 and must be complete by stage 3.
        feasibility = read_csv(root / "feasibility.csv", report, arm="FEASIBILITY",
                               contract_name=contract_name, allow_empty=True,
                               project_root=root)
        arm_feasibility(feasibility, root, report, decisions, required=at_data)
        if at_data:
            # The review states what it found; the approval states what the researcher accepted.
            # The second reads the first, so it runs after it and fails closed when it is absent.
            exceptional = arm_scope_review(root, decisions, report)
            arm_scope_approval(root, exceptional, report)

    if STAGES.index(through) >= STAGES.index("draft"):
        arm_draft(root, decisions, claims, report)

    return report, contract_name


def run(root, through, quiet=False, contract=None):
    root = Path(root)
    if not root.is_dir():
        print(f"FAIL: {root} is not a directory")
        return 1
    report, contract_name = evaluate(root, through, contract=contract)

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
    for name in FILES:
        cols = file_columns(name, contract_key)
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
                w.writerows(seed_vocab(contract_key))
        made.append(name)
        print(f"  created {name}")

    for name in CONTRACT_EXTRA_REGISTERS[contract_key]:
        p = root / name
        if p.exists():
            print(f"  kept    {name} (already exists)")
            continue
        with p.open("w", encoding="utf-8", newline="") as fh:
            csv.writer(fh).writerow(file_columns(name, contract_key))
        made.append(name)
        print(f"  created {name}")

    if contract_key == "v0.3":
        # Templates only. --init never writes scope_review.json or scope_approval.json: scaffolding
        # an approved record would mean the tool approving the work on the researcher's behalf.
        for template_name, builder in ((SCOPE_REVIEW_TEMPLATE_FILE, scope_review_template),
                                       (SCOPE_APPROVAL_TEMPLATE_FILE, scope_approval_template)):
            p_template = root / template_name
            if p_template.exists():
                print(f"  kept    {template_name} (already exists)")
                continue
            p_template.write_text(json.dumps(builder(), indent=2) + "\n", encoding="utf-8")
            made.append(template_name)
            print(f"  created {template_name}")

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
        if contract_key == "v0.3":
            print(f"v0.3 also requires decided_by on every required row, a complete "
                  f"feasibility.csv before stage 'data', and a {SCOPE_REVIEW_FILE} written by a "
                  f"reviewer other than the runner.")
            print(f"Run --scope-digests for the digest block that binds that review to the "
                  f"decision rows.")
            print(f"Stage 'data' then opens on {SCOPE_APPROVAL_FILE}, the researcher's recorded "
                  f"decision to proceed. Run --approval-digests for the block that binds it.")
    return 0


def scope_review_template():
    return {
        "record_type": SCOPE_REVIEW_RECORD_TYPE,
        "schema_version": SCOPE_REVIEW_SCHEMA_VERSION,
        "contract": "v0.3",
        "reviewer": "",
        "review_date": "",
        "reviewed_decisions": {did: "" for did in SCOPE_REVIEW_DECISIONS},
        # No exception_accepted_by field. The reviewer records what it found; acceptance of a fail
        # or unresolved result is the researcher's and lives in scope_approval.json.
        "checks": {name: {"result": "", "note": ""} for name in SCOPE_REVIEW_CHECKS},
        "_check_questions": dict(SCOPE_REVIEW_CHECKS),
    }


def scope_approval_template():
    """The approval scaffold. Every gate-opening field is left empty on purpose.

    --init writes this and never writes scope_approval.json itself. A tool that scaffolds a
    completed approval has approved the work, which is the decision the record exists to reserve.
    """
    return {
        "record_type": SCOPE_APPROVAL_RECORD_TYPE,
        "schema_version": SCOPE_APPROVAL_SCHEMA_VERSION,
        "contract": "v0.3",
        "approved_by": "",
        "approval_date": "",
        "decision": "",
        "accepted_checks": [],
        "approval_reference": "",
        "bound_files": {name: "" for name in SCOPE_APPROVAL_BOUND_FILES},
        "_fields": {
            "approved_by": f"The recorded authority is {SCOPE_APPROVAL_AUTHORITY} No reviewer, "
                           f"runner or model substitutes for it.",
            "decision": f"One of {', '.join(sorted(SCOPE_APPROVAL_DECISIONS))}. Stage 'data' "
                        f"opens on '{SCOPE_APPROVAL_OPENS}' alone.",
            "accepted_checks": "Exactly the scope review checks recorded as fail or unresolved. "
                               "Empty where the review recorded neither.",
            "approval_reference": "The dated decision or handoff this record stands for. Carry an "
                                  "ISO date and the path, filename or URL of that record.",
            "bound_files": "Run --approval-digests. Editing any question or scope decision row, "
                           "feasibility.csv or scope_review.json invalidates the approval. Later "
                           "decision stages do not.",
        },
    }


def approval_digests(root):
    """Print the stable scope-bound digest block for scope_approval.json."""
    root = Path(root)
    digests = {name: approval_binding_digest(root, name)
               for name in SCOPE_APPROVAL_BOUND_FILES}
    missing = [name for name, digest in digests.items() if digest is None]
    if missing:
        print(f"FAIL: {', '.join(missing)} missing, ambiguous or outside the project in {root}")
        return 1
    print(json.dumps({"bound_files": digests}, indent=2))
    return 0


def scope_digests(root):
    """Print the digest block a scope reviewer pastes into scope_review.json."""
    root = Path(root)
    path = contained_path(root, "decisions.csv")
    if path is None:
        print(f"FAIL: decisions.csv is missing or outside the project in {root}")
        return 1
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    by_id = {}
    for r in rows:
        did = (r.get("decision_id") or "").strip().upper()
        if did and did not in by_id:
            by_id[did] = r
    missing = [did for did in SCOPE_REVIEW_DECISIONS if did not in by_id]
    if missing:
        print(f"FAIL: decisions.csv does not log {', '.join(missing)}")
        return 1
    block = {did: decision_row_digest(by_id[did]) for did in SCOPE_REVIEW_DECISIONS}
    print(json.dumps({"reviewed_decisions": block}, indent=2))
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
            w.writerow(file_columns("claims.csv", "v0.2"))
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
            w.writerow(file_columns("claims.csv", "v0.1"))
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
            w.writerow(file_columns("claims.csv", "v0.2"))
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

        # 4. Clean v0.3 project: attributed decisions, bounded feasibility route, scope review
        print()
        print("clean v0.3 project (attribution, feasibility, scope review), expect PASS")
        print("=" * 62)
        proj_v03 = tmp / "worked_subject_v03"
        build_v03_project(proj_v03)
        clean_v03 = run(proj_v03, "mint", contract="v0.3")
        assert clean_v03 == 0, "the clean v0.3 demo project should pass"

        # A v0.3 project worked only as far as scope: no sources, no claims, feasibility still
        # filling and no review yet. That must pass below stage 'data' and fail from it.
        early_v03 = tmp / "early_subject_v03"
        build_v03_project(early_v03)
        (early_v03 / SCOPE_REVIEW_FILE).unlink()
        (early_v03 / SCOPE_APPROVAL_FILE).unlink()
        (early_v03 / "findings.md").unlink()
        for register in ("sources.csv", "claims.csv", "feasibility.csv"):
            with (early_v03 / register).open("w", encoding="utf-8", newline="") as fh:
                csv.writer(fh).writerow(file_columns(register, "v0.3"))
        for stage in ("question", "scope"):
            rc = run(early_v03, stage, quiet=True, contract="v0.3")
            assert rc == 0, (f"a v0.3 project worked through '{stage}' should pass at --through "
                             f"{stage}; the feasibility register and the scope review are not "
                             f"required before stage 'data'")
            print(f"  --through {stage}: PASS")
        assert run(early_v03, "data", quiet=True, contract="v0.3") != 0, (
            "an empty feasibility register, an absent scope review and an absent scope approval "
            "must fail from stage 'data'")
        print("  feasibility, scope review and scope approval required from stage 'data', "
              "not before")

        # 5. A project part-way through
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
            ("CLAIMS", "make a tier-5 source carry a conclusion-material claim alone",
             lambda: (rewrite_csv(proj / "claims.csv", "claim_id", "C1",
                                  {"source_id": "vendor_deck"}),
                      rewrite_csv(proj / "sources.csv", "source_id", "vendor_deck",
                                  {"second_source_id": ""})), {}),
            ("CLAIMS", "substitute the legacy v0.1 materiality column under v0.2",
             lambda: (proj / "claims.csv").write_text(
                 (proj / "claims.csv").read_text(encoding="utf-8")
                 .replace("material_to_conclusion", "load_bearing", 1),
                 encoding="utf-8"), {}),
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

        v03_faults = [
            ("DECISIONS", "blank decided_by on a required v0.3 row",
             lambda p: rewrite_csv(p / "decisions.csv", "decision_id", "Q1", {"decided_by": ""})),
            ("DECISIONS", "placeholder decided_by on a required v0.3 row",
             lambda p: rewrite_csv(p / "decisions.csv", "decision_id", "S4", {"decided_by": "TBD"})),
            ("DECISIONS", "role-only decided_by on a required v0.3 row",
             lambda p: rewrite_csv(p / "decisions.csv", "decision_id", "Q1",
                                   {"decided_by": "Google Gemini 3.7 Flash runner"})),
            # The register columns are a MANIFEST concern, which is where read_csv reports them.
            ("MANIFEST", "pre-attribution eight-column decisions.csv under v0.3",
             lambda p: drop_csv_column(p / "decisions.csv", "decided_by")),
            ("SOURCES", "blank source_role under v0.3",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "regulator_filing",
                                   {"source_role": ""})),
            ("SOURCES", "a mirror of a source offered as its own second source",
             lambda p: (rewrite_csv(p / "sources.csv", "source_id", "vendor_deck",
                                    {"derived_from": "regulator_filing"}),
                        rewrite_csv(p / "sources.csv", "source_id", "regulator_filing",
                                    {"second_source_id": "vendor_deck"}))),
            ("SOURCES", "second_source_id naming an unregistered source",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "regulator_filing",
                                   {"second_source_id": "press_writeup"})),
            # Derivation is transitive, so the independence rule is tested past one hop in both
            # directions. A two-hop mirror is the same disclosure arriving twice.
            ("SOURCES", "a two-hop ancestor offered as an independent second source",
             lambda p: (add_restatement_chain(p),
                        rewrite_csv(p / "sources.csv", "source_id", "syndication",
                                    {"second_source_id": "regulator_filing"}))),
            ("SOURCES", "a two-hop derivative offered as an independent second source",
             lambda p: (add_restatement_chain(p),
                        rewrite_csv(p / "sources.csv", "source_id", "regulator_filing",
                                    {"second_source_id": "syndication"}))),
            ("SOURCES", "a derivation loop with no origin",
             lambda p: (rewrite_csv(p / "sources.csv", "source_id", "vendor_deck",
                                    {"derived_from": "regulator_filing", "second_source_id": ""}),
                        rewrite_csv(p / "sources.csv", "source_id", "regulator_filing",
                                    {"derived_from": "vendor_deck"}))),
            ("SOURCES", "accessed_date that is not an ISO date under v0.3",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "regulator_filing",
                                   {"accessed_date": "sometime last week"})),
            # The ordering check sits behind the ISO parse, so it is exercised on its own under
            # v0.3. The review is rewritten after the re-dating so only the SOURCES arm can fire.
            ("SOURCES", "source accessed before the final S6 scope decision under v0.3",
             lambda p: (rewrite_csv(p / "decisions.csv", "decision_id", "S6",
                                    {"decided_date": "2026-08-20"}),
                        rewrite_csv(p / "sources.csv", "source_id", "regulator_filing",
                                    {"accessed_date": "2026-08-19"}),
                        write_scope_review(p, reviewer=V03_REVIEWER, review_date="2026-08-20"))),
            ("FEASIBILITY", "empty feasibility register at stage 'data' and beyond",
             lambda p: p.joinpath("feasibility.csv").write_text(
                 ",".join(file_columns("feasibility.csv", "v0.3")) + "\n", encoding="utf-8")),
            ("FEASIBILITY", "no probe for derivation independence (circularity untested)",
             lambda p: delete_row_csv(p / "feasibility.csv", "probe_id", "F4")),
            ("FEASIBILITY", "no probe for population coverage",
             lambda p: delete_row_csv(p / "feasibility.csv", "probe_id", "F5")),
            ("FEASIBILITY", "an outcome value recorded in the result field",
             lambda p: rewrite_csv(p / "feasibility.csv", "probe_id", "F1",
                                   {"result": "37 outages found in the window"})),
            ("FEASIBILITY", "an outcome column smuggled into the register",
             lambda p: add_csv_column(p / "feasibility.csv", "outage_count", "37")),
            ("FEASIBILITY", "a question outside the five permitted",
             lambda p: rewrite_csv(p / "feasibility.csv", "probe_id", "F1",
                                   {"question": "effect_size"})),
            ("FEASIBILITY", "a probe dated after scope closed",
             lambda p: rewrite_csv(p / "feasibility.csv", "probe_id", "F1",
                                   {"access_date": "2026-08-16"})),
            ("FEASIBILITY", "held feasibility bytes corrupted after hashing",
             lambda p: p.joinpath("sources", "feasibility_sample.txt").write_text(
                 "different bytes\n", encoding="utf-8")),
            ("FEASIBILITY", "bytes reported retrievable with nothing held",
             lambda p: rewrite_csv(p / "feasibility.csv", "probe_id", "F2",
                                   {"local_path": "", "sha256": ""})),
            ("FEASIBILITY", "unattributed probe",
             lambda p: rewrite_csv(p / "feasibility.csv", "probe_id", "F3", {"probed_by": ""})),
            ("FEASIBILITY", "probe attribution missing its run identifier",
             lambda p: rewrite_csv(
                 p / "feasibility.csv", "probe_id", "F3",
                 {"probed_by": "model=model-a; harness=cli; role=runner"})),
            ("FEASIBILITY", "unavailable route with no reason recorded",
             lambda p: rewrite_csv(p / "feasibility.csv", "probe_id", "F1",
                                   {"result": "unavailable", "notes": ""})),
            ("FEASIBILITY", "derivation independence left unanswered",
             lambda p: rewrite_csv(p / "feasibility.csv", "probe_id", "F4",
                                   {"derives_from_subject": ""})),
            ("FEASIBILITY", "retention probe with no stated period",
             lambda p: rewrite_csv(p / "feasibility.csv", "probe_id", "F3",
                                   {"stated_period": ""})),
            ("SCOPE_REVIEW", "no scope coherence review",
             lambda p: p.joinpath(SCOPE_REVIEW_FILE).unlink()),
            ("SCOPE_REVIEW", "malformed scope review JSON",
             lambda p: p.joinpath(SCOPE_REVIEW_FILE).write_text("{malformed", encoding="utf-8")),
            ("SCOPE_REVIEW", "no reviewer named",
             lambda p: write_scope_review(p, reviewer="", review_date="2026-08-14")),
            ("SCOPE_REVIEW", "the runner reviewing its own scope",
             lambda p: write_scope_review(p, reviewer=V03_RUNNER, review_date="2026-08-14")),
            ("SCOPE_REVIEW", "the runner reviewing its own scope under different casing",
             lambda p: write_scope_review(
                 p, reviewer=" MODEL=MODEL-A; HARNESS=CLI; RUN=C3-B-001; ROLE=REVIEWER ",
                                          review_date="2026-08-14")),
            ("SCOPE_REVIEW", "the runner reviewing its own scope behind respelled punctuation",
             lambda p: write_scope_review(
                 p, reviewer="model=model a; harness=cli; run=c3 b 001; role=reviewer",
                                          review_date="2026-08-14")),
            ("SCOPE_REVIEW", "a role label offered without model, harness and run identity",
             lambda p: write_scope_review(
                 p, reviewer="Google Gemini 3.7 Flash reviewer", review_date="2026-08-14")),
            ("SCOPE_REVIEW", "the same run relabelled from runner to reviewer",
             lambda p: write_scope_review(
                 p, reviewer="model=model-a; harness=cli; run=c3-b-001; role=reviewer",
                 review_date="2026-08-14")),
            ("SCOPE_REVIEW", "a reviewed decision row edited after the review",
             lambda p: rewrite_csv(p / "decisions.csv", "decision_id", "S1",
                                   {"chosen": "a different population after the review"})),
            ("SCOPE_REVIEW", "a stale digest carried forward",
             lambda p: rewrite_binding_field(p / SCOPE_REVIEW_FILE,
                                             ["reviewed_decisions", "Q3"], "0" * 64)),
            ("SCOPE_REVIEW", "a reviewed decision id dropped from the record",
             lambda p: delete_binding_field(p / SCOPE_REVIEW_FILE,
                                            ["reviewed_decisions", "S6"])),
            ("SCOPE_REVIEW", "a required coherence check dropped from the record",
             lambda p: delete_binding_field(p / SCOPE_REVIEW_FILE,
                                            ["checks", "s4_tests_sufficiency"])),
            ("SCOPE_APPROVAL", "a failed check the approval record does not accept",
             lambda p: rewrite_binding_field(p / SCOPE_REVIEW_FILE,
                                             ["checks", "q3_disconfirms_q2"],
                                             {"result": "fail", "note": "Q3 leaves an interval."})),
            ("SCOPE_APPROVAL", "an unresolved check the approval record does not accept",
             lambda p: rewrite_binding_field(p / SCOPE_REVIEW_FILE,
                                             ["checks", "s1_observable_denominator"],
                                             {"result": "unresolved", "note": "Could not settle."})),
            # The reviewer accepting its own finding was the control inverted, so the field that
            # allowed it is refused outright rather than quietly ignored.
            ("SCOPE_REVIEW", "a reviewer accepting its own unresolved finding in the review",
             lambda p: rewrite_binding_field(
                 p / SCOPE_REVIEW_FILE, ["checks", "q3_disconfirms_q2"],
                 {"result": "unresolved", "note": "Interval left open.",
                  "exception_accepted_by": V03_REVIEWER})),
            ("SCOPE_REVIEW", "an arbitrary string accepting a failed check in the review",
             lambda p: rewrite_binding_field(
                 p / SCOPE_REVIEW_FILE, ["checks", "s4_tests_sufficiency"],
                 {"result": "fail", "note": "S4 suppresses a falsifying result.",
                  "exception_accepted_by": "anybody at all"})),
            ("SCOPE_REVIEW", "a check with a result but no note",
             lambda p: rewrite_binding_field(p / SCOPE_REVIEW_FILE,
                                             ["checks", "s2_third_party_applicable"],
                                             {"result": "pass", "note": ""})),
            ("SCOPE_REVIEW", "a review dated before the decisions it reviews",
             lambda p: write_scope_review(p, reviewer=V03_REVIEWER, review_date="2026-08-10")),
            ("SCOPE_REVIEW", "a review claiming the wrong contract",
             lambda p: rewrite_binding_field(p / SCOPE_REVIEW_FILE, ["contract"], "v0.2")),
            ("SCOPE_REVIEW", "a review with an unrecognised schema version",
             lambda p: rewrite_binding_field(p / SCOPE_REVIEW_FILE, ["schema_version"], "9.9")),

            # P5-F1. An identity that normalises to nothing is the same absence as a blank field,
            # and it silently disabled the comparison that reads it.
            ("DECISIONS", "punctuation-only decided_by on a required v0.3 row",
             lambda p: rewrite_csv(p / "decisions.csv", "decision_id", "Q2",
                                   {"decided_by": "!!!"})),
            ("FEASIBILITY", "punctuation-only probed_by",
             lambda p: rewrite_csv(p / "feasibility.csv", "probe_id", "F2",
                                   {"probed_by": "!!!"})),
            ("SCOPE_REVIEW", "punctuation-only reviewer against a punctuation-only decision maker",
             lambda p: (rewrite_all_csv(p / "decisions.csv", {"decided_by": "!!!"}),
                        write_scope_review(p, reviewer="!!!", review_date="2026-08-14"))),

            # P5-F1, retained human authority. The approval is a separate hash-bound record and
            # stage 'data' opens on it.
            ("SCOPE_APPROVAL", "no scope approval record",
             lambda p: p.joinpath(SCOPE_APPROVAL_FILE).unlink()),
            ("SCOPE_APPROVAL", "malformed scope approval JSON",
             lambda p: p.joinpath(SCOPE_APPROVAL_FILE).write_text("{malformed", encoding="utf-8")),
            ("SCOPE_APPROVAL", "an approval recorded by the reviewer rather than the researcher",
             lambda p: write_scope_approval(p, approved_by=V03_REVIEWER)),
            ("SCOPE_APPROVAL", "an approval recorded by an unidentifiable authority",
             lambda p: write_scope_approval(p, approved_by="!!!")),
            ("SCOPE_APPROVAL", "an approval held rather than proceeding",
             lambda p: write_scope_approval(p, decision="hold")),
            ("SCOPE_APPROVAL", "an approval decision outside the closed set",
             lambda p: write_scope_approval(p, decision="approved")),
            ("SCOPE_APPROVAL", "an approval with no traceable reference",
             lambda p: write_scope_approval(p, reference="")),
            ("SCOPE_APPROVAL", "an approval dated before the review it accepts",
             lambda p: write_scope_approval(p, approval_date="2026-08-10")),
            ("SCOPE_APPROVAL", "an approval that covers only some of the files it binds",
             lambda p: write_scope_approval(
                 p, bound={SCOPE_APPROVAL_SCOPE_BINDING: "0" * 64})),
            ("SCOPE_APPROVAL", "a question row edited after approval",
             lambda p: rewrite_csv(p / "decisions.csv", "decision_id", "Q1",
                                   {"chosen": "a different unit after approval"})),
            # A bound file edited after approval, seeded where no other arm reads the change, so
            # the staleness rule is exercised on its own.
            ("SCOPE_APPROVAL", "a bound register edited after the approval was recorded",
             lambda p: rewrite_csv(p / "feasibility.csv", "probe_id", "F1",
                                   {"notes": "Reachable without a login, rechecked later."})),
            # The digests are re-synced, so only the accepted set can fire.
            ("SCOPE_APPROVAL", "an accepted set that omits the exception the review recorded",
             lambda p: (v03_review_with(p, "q3_disconfirms_q2", "unresolved",
                                        "Interval left open."),
                        write_scope_approval(p, accepted=[]))),
            ("SCOPE_APPROVAL", "an accepted set naming an exception the review did not record",
             lambda p: write_scope_approval(p, accepted=["q3_disconfirms_q2"])),
            ("SCOPE_APPROVAL", "an accepted set naming something that is not a review check",
             lambda p: write_scope_approval(p, accepted=["route_looks_fine"])),

            # P5-F2. Source graph and source eligibility.
            ("SOURCES", "two mirrors of one disclosure offered as each other's second source",
             add_shared_origin_pair),
            ("SOURCES", "a source with no title",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "vendor_deck", {"title": ""})),
            ("SOURCES", "a source with no publisher",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "vendor_deck",
                                   {"publisher": ""})),
            ("SOURCES", "a source with neither a url nor a held local path",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "vendor_deck", {"url": ""})),

            # P5-F2. Claim-level eligibility and corroboration.
            ("CLAIMS", "a claim grounded in a source nobody obtained",
             lambda p: rewrite_csv(p / "claims.csv", "claim_id", "C2",
                                   {"source_id": "vendor_deck"})),
            ("CLAIMS", "a material tier-5 claim with no corroborating source on the row",
             lambda p: rewrite_csv(p / "claims.csv", "claim_id", "C3",
                                   {"corroborating_source_id": ""})),
            # The source-level identifier is what the old rule read. It says nothing about this
            # claim, so the claim must still fail.
            ("CLAIMS", "a source-level second source standing in for claim-level corroboration",
             lambda p: (rewrite_csv(p / "sources.csv", "source_id", "operator_release",
                                    {"second_source_id": "independent_audit"}),
                        rewrite_csv(p / "claims.csv", "claim_id", "C3",
                                    {"corroborating_source_id": ""}))),
            ("CLAIMS", "a corroborating source that is not registered",
             lambda p: rewrite_csv(p / "claims.csv", "claim_id", "C3",
                                   {"corroborating_source_id": "press_writeup"})),
            ("CLAIMS", "a claim corroborated by itself",
             lambda p: rewrite_csv(p / "claims.csv", "claim_id", "C3",
                                   {"corroborating_source_id": "operator_release"})),
            ("CLAIMS", "two interested sources corroborating each other",
             lambda p: (rewrite_csv(p / "sources.csv", "source_id", "vendor_deck",
                                    {"retrieval_status": "cited_not_held", "derived_from": ""}),
                        rewrite_csv(p / "claims.csv", "claim_id", "C3",
                                    {"corroborating_source_id": "vendor_deck"}))),
            ("CLAIMS", "a corroborating source nobody obtained",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "independent_audit",
                                   {"retrieval_status": "registered_not_retrieved",
                                    "local_path": "", "sha256": "",
                                    "notes": "Withdrawn from the audit body's site before "
                                             "retrieval."})),
            ("CLAIMS", "a corroborating source that shares the primary source's origin",
             lambda p: (rewrite_csv(p / "sources.csv", "source_id", "operator_release",
                                    {"derived_from": "regulator_filing"}),
                        rewrite_csv(p / "sources.csv", "source_id", "independent_audit",
                                    {"derived_from": "regulator_filing"}))),

            # P5-F3. Claim row identity and content, kept separate from support.
            ("MANIFEST", "a v0.3 claims register with no corroboration column",
             lambda p: drop_csv_column(p / "claims.csv", "corroborating_source_id")),
            ("CLAIMS", "a claim row with no claim_id",
             lambda p: rewrite_csv(p / "claims.csv", "claim_id", "C2", {"claim_id": ""})),
            ("CLAIMS", "a placeholder claim_id",
             lambda p: rewrite_csv(p / "claims.csv", "claim_id", "C2", {"claim_id": "TBD"})),
            ("CLAIMS", "a claim_id already used by another row",
             lambda p: rewrite_csv(p / "claims.csv", "claim_id", "C2", {"claim_id": "C1"})),
            ("CLAIMS", "a claim row with no claim_text",
             lambda p: rewrite_csv(p / "claims.csv", "claim_id", "C2", {"claim_text": ""})),
            ("CLAIMS", "a placeholder claim_text",
             lambda p: rewrite_csv(p / "claims.csv", "claim_id", "C2", {"claim_text": "n/a"})),

            # SOL-R1 to SOL-R3. A placeholder word is refused and punctuation was not, so every
            # field required to carry content is tested with a value that is neither blank nor a
            # placeholder and still says nothing.
            ("CLAIMS", "a punctuation-only claim_id",
             lambda p: rewrite_csv(p / "claims.csv", "claim_id", "C2", {"claim_id": "!!!"})),
            ("CLAIMS", "a punctuation-only claim_text",
             lambda p: rewrite_csv(p / "claims.csv", "claim_id", "C2", {"claim_text": "!!!"})),
            ("SOURCES", "a punctuation-only title",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "vendor_deck",
                                   {"title": "!!!"})),
            ("SOURCES", "a punctuation-only publisher",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "vendor_deck",
                                   {"publisher": "***"})),
            ("SOURCES", "a punctuation-only url as the only locator",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "vendor_deck",
                                   {"url": "!!!"})),
            ("SOURCES", "a url with no scheme as the only locator",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "vendor_deck",
                                   {"url": "example.invalid/deck"})),
            ("SOURCES", "a url under a scheme the register does not allow",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "vendor_deck",
                                   {"url": "javascript:alert(1)"})),
            ("SOURCES", "a local_path naming a file that is not in the project",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "vendor_deck",
                                   {"url": "", "local_path": "sources/never_written.txt"})),
            # The eligibility gap reached the claim arm through the corroborator, so the pair is
            # tested end to end: a material tier-5 claim leaning on a source nobody can reach.
            ("SOURCES", "a cited corroborator whose only locator is punctuation",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "independent_audit",
                                   {"retrieval_status": "cited_not_held", "local_path": "",
                                    "sha256": "", "url": "!!!"})),
            # Same mutation, different rule. The overlap is deliberate: the claim arm establishes
            # that this claim's second source is reachable rather than relying on SOURCES to have
            # noticed on the register's behalf.
            ("CLAIMS", "a material tier-5 claim leaning on an unreachable corroborator",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "independent_audit",
                                   {"retrieval_status": "cited_not_held", "local_path": "",
                                    "sha256": "", "url": "!!!"})),
            ("SCOPE_APPROVAL", "a punctuation-only approval reference",
             lambda p: write_scope_approval(p, reference="!!!")),
            ("SCOPE_APPROVAL", "an approval reference with no date",
             lambda p: write_scope_approval(
                 p, reference="the decision recorded in handoffs/approval.md")),
            ("SCOPE_APPROVAL", "an approval reference with no retrievable route",
             lambda p: write_scope_approval(
                 p, reference="the user approved this on 2026-08-14")),
            ("SCOPE_APPROVAL", "an approval reference carrying a date that is not a date",
             lambda p: write_scope_approval(
                 p, reference="decision of 2026-13-45 in handoffs/approval.md")),

            # FSR-1. Every v0.3 field whose arm requires content, tested with a value that is
            # neither blank nor a placeholder. Bound records are refreshed after each register
            # edit, so a stale digest cannot stand in for the arm under test.
            ("DECISIONS", "punctuation-only 'chosen' on a required v0.3 row",
             lambda p: (rewrite_csv(p / "decisions.csv", "decision_id", "S2", {"chosen": "!!!"}),
                        refresh_v03_bindings(p))),
            ("DECISIONS", "punctuation-only 'rationale' on a required v0.3 row",
             lambda p: (rewrite_csv(p / "decisions.csv", "decision_id", "S3",
                                    {"rationale": "***"}),
                        refresh_v03_bindings(p))),
            ("DECISIONS", "every recorded alternative is punctuation",
             lambda p: (rewrite_csv(p / "decisions.csv", "decision_id", "S4",
                                    {"alternatives": "!!!|***"}),
                        refresh_v03_bindings(p))),
            ("SOURCES", "a punctuation-only source_id",
             lambda p: (rewrite_csv(p / "sources.csv", "source_id", "vendor_deck",
                                    {"source_id": "!!!"}),
                        rewrite_csv(p / "claims.csv", "claim_id", "C2", {"source_id": "!!!"}))),
            ("SOURCES", "a punctuation-only source_role",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "vendor_deck",
                                   {"source_role": "!!!"})),
            ("SOURCES", "a punctuation-only reason for a source nobody obtained",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "vendor_deck",
                                   {"notes": "!!!"})),
            ("CLAIMS", "a punctuation-only uncertainty",
             lambda p: rewrite_csv(p / "claims.csv", "claim_id", "C2", {"uncertainty": "!!!"})),
            ("FEASIBILITY", "a punctuation-only probe_id",
             lambda p: (rewrite_csv(p / "feasibility.csv", "probe_id", "F3", {"probe_id": "!!!"}),
                        write_scope_approval(p))),
            ("FEASIBILITY", "a punctuation-only probe source_name",
             lambda p: (rewrite_csv(p / "feasibility.csv", "probe_id", "F3",
                                    {"source_name": "!!!"}),
                        write_scope_approval(p))),
            ("FEASIBILITY", "a punctuation-only reason for an unknown result",
             lambda p: (rewrite_csv(p / "feasibility.csv", "probe_id", "F1",
                                    {"result": "unknown", "notes": "!!!"}),
                        write_scope_approval(p))),
            ("FEASIBILITY", "a punctuation-only stated_period",
             lambda p: (rewrite_csv(p / "feasibility.csv", "probe_id", "F3",
                                    {"stated_period": "!!!"}),
                        write_scope_approval(p))),
            ("FEASIBILITY", "a punctuation-only retention_policy",
             lambda p: (rewrite_csv(p / "feasibility.csv", "probe_id", "F3",
                                    {"retention_policy": "***"}),
                        write_scope_approval(p))),
            ("FEASIBILITY", "a probe whose only record of where it looked is punctuation",
             lambda p: (rewrite_csv(p / "feasibility.csv", "probe_id", "F1",
                                    {"url": "", "evidence_locator": "!!!"}),
                        write_scope_approval(p))),
            ("SCOPE_REVIEW", "a punctuation-only scope review note",
             lambda p: (v03_review_with(p, "s2_third_party_applicable", "pass", "!!!"),
                        write_scope_approval(p))),

            # FSR-2. netloc is not a hostname: both of these name no host at all.
            ("SOURCES", "a url carrying a port and no host",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "vendor_deck",
                                   {"url": "http://:80"})),
            ("SOURCES", "a url carrying user information and no host",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "vendor_deck",
                                   {"url": "http://user@"})),

            # FSR-3. Custody means bytes held in the project, so the path is resolved first.
            # The bytes exist in both cases, so only containment can be what rejects them.
            ("SOURCES", "a held local_path outside the project",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "regulator_filing",
                                   {"local_path": str(stray_bytes(p))})),
            ("SOURCES", "a held local_path reaching out through a parent traversal",
             lambda p: (stray_bytes(p),
                        rewrite_csv(p / "sources.csv", "source_id", "regulator_filing",
                                    {"local_path": "../outside_the_project.txt"}))),
            ("SOURCES", "a held local_path behind a symlink that resolves outside the project",
             lambda p: escaping_symlink(p)),

            # FSR-4. A route to nowhere and a malformed address are both refused.
            ("SCOPE_APPROVAL", "an approval reference whose route is only separators",
             lambda p: write_scope_approval(p, reference="2026-08-21 ///")),
            ("SCOPE_APPROVAL", "an approval reference carrying a malformed url",
             lambda p: write_scope_approval(p, reference="2026-08-21 http://!!!")),

            # FSR-5. Every recorded alternative is read, not only the first usable one. The row
            # keeps one genuine option, so nothing but the unusable token can be what fails it.
            ("DECISIONS", "a usable alternative recorded beside a punctuation-only one",
             lambda p: (rewrite_csv(p / "decisions.csv", "decision_id", "S5",
                                    {"alternatives": "a real alternative|!!!"}),
                        refresh_v03_bindings(p))),

            # FSR-6. A probe that reports custody holds the bytes in the project, under the same
            # containment predicate as the source register. The bytes exist in all three cases and
            # the recorded hash matches them, so only containment can be what rejects the row.
            ("FEASIBILITY", "probe custody claimed on an absolute path outside the project",
             lambda p: escaping_probe_path(p, str(stray_bytes(p)))),
            ("FEASIBILITY", "probe custody claimed through a parent traversal",
             lambda p: escaping_probe_path(p, "../outside_the_project.txt")),
            ("FEASIBILITY", "probe custody claimed behind a symlink resolving outside the project",
             lambda p: escaping_probe_symlink(p)),

            # FSR-7. One URL predicate governs the source register, the approval reference and the
            # feasibility evidence route, so each syntactic escape is seeded on an arm that reads
            # it through that predicate.
            ("SOURCES", "a url containing whitespace as the only locator",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "vendor_deck",
                                   {"url": "https://example.invalid/deck a"})),
            ("SOURCES", "a url containing a backslash as the only locator",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "vendor_deck",
                                   {"url": "https://example.invalid\\deck"})),
            ("SOURCES", "a url whose port is not a number",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "vendor_deck",
                                   {"url": "https://example.invalid:port/deck"})),
            ("SOURCES", "a url whose port is out of range",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "vendor_deck",
                                   {"url": "https://example.invalid:99999/deck"})),
            ("SCOPE_APPROVAL", "an approval reference whose url carries a malformed port",
             lambda p: write_scope_approval(
                 p, reference=("decision of 2026-08-14 at "
                               "http://example.invalid:port/approval.md"))),
            ("FEASIBILITY", "a probe url containing whitespace, with no evidence_locator",
             lambda p: (rewrite_csv(p / "feasibility.csv", "probe_id", "F1",
                                    {"url": "https://example.invalid/return a",
                                     "evidence_locator": ""}),
                        write_scope_approval(p))),
            ("SOURCES", "a url containing an incomplete percent escape",
             lambda p: rewrite_csv(p / "sources.csv", "source_id", "vendor_deck",
                                   {"url": "https://%GG/"})),
            ("FEASIBILITY", "a probe url containing an incomplete percent escape",
             lambda p: (rewrite_csv(p / "feasibility.csv", "probe_id", "F1",
                                    {"url": "https://%GG/", "evidence_locator": ""}),
                        write_scope_approval(p))),
            ("SCOPE_APPROVAL", "an approval reference containing an incomplete percent escape",
             lambda p: write_scope_approval(p, reference="decision of 2026-08-14 at https://%GG/")),

            # FSR-8. Every fixed v0.3 project record and top-level draft is project custody. A
            # symlink to bytes outside the project is not a self-contained register.
            ("MANIFEST", "a project binding symlink resolving outside the project",
             lambda p: external_project_file(p, "instrument_manifest.json")),
            ("DECISIONS", "a decisions register symlink resolving outside the project",
             lambda p: external_project_file(p, "decisions.csv")),
            ("SOURCES", "a sources register symlink resolving outside the project",
             lambda p: external_project_file(p, "sources.csv")),
            ("CLAIMS", "a claims register symlink resolving outside the project",
             lambda p: external_project_file(p, "claims.csv")),
            ("VOCAB", "a vocabulary register symlink resolving outside the project",
             lambda p: external_project_file(p, "vocabulary.csv")),
            ("FEASIBILITY", "a feasibility register symlink resolving outside the project",
             lambda p: external_project_file(p, "feasibility.csv")),
            ("SCOPE_REVIEW", "a scope review symlink resolving outside the project",
             lambda p: external_project_file(p, "scope_review.json")),
            ("SCOPE_APPROVAL", "a scope approval symlink resolving outside the project",
             lambda p: external_project_file(p, "scope_approval.json")),
            ("DRAFT", "a draft symlink resolving outside the project",
             lambda p: external_project_file(p, "findings.md")),

            # The same containment predicate reaches the corroborator, and both arms that read it
            # are asserted. A second source held outside the project is unreachable to the reader
            # whichever arm notices.
            ("SOURCES", "a corroborator held through a parent traversal",
             lambda p: escaping_corroborator(p, "../outside_the_project.txt")),
            ("CLAIMS", "a claim leaning on a corroborator held through a parent traversal",
             lambda p: escaping_corroborator(p, "../outside_the_project.txt")),
            ("SOURCES", "a corroborator held behind a symlink resolving outside the project",
             lambda p: escaping_corroborator_symlink(p)),
            ("CLAIMS", "a claim leaning on a corroborator behind an escaping symlink",
             lambda p: escaping_corroborator_symlink(p)),
        ]

        v03_backup = tmp / "backup_v03"
        shutil.copytree(proj_v03, v03_backup)
        print()
        print("v0.3 seeded faults, each must be caught")
        print("=" * 62)
        for arm, what, apply_fault in v03_faults:
            shutil.rmtree(proj_v03)
            shutil.copytree(v03_backup, proj_v03)
            apply_fault(proj_v03)
            # The arm is asserted as well as the exit code. A fault that fails the gate through
            # some unrelated arm proves nothing about the rule it was written to test.
            fault_report, _ = evaluate(proj_v03, "mint", contract="v0.3")
            on_arm = [e for e in fault_report.errors if e.startswith(f"{arm}:")]
            if not fault_report.errors:
                caught = "MISSED"
                failures.append(f"{arm}: {what}")
            elif not on_arm:
                caught = "WRONG ARM"
                failures.append(f"{arm}: {what} (fired on {fault_report.errors[0].split(':')[0]})")
            else:
                caught = "CAUGHT"
            print(f"  [{caught}] {arm:<13} {what}")

        print()
        print("v0.2 and v0.1 compatibility under the v0.3 toolchain")
        print("=" * 62)
        shutil.rmtree(proj_v03)
        shutil.copytree(v03_backup, proj_v03)
        assert run(v03_backup, "mint", quiet=True, contract="v0.3") == 0, (
            "the v0.3 backup fixture must still pass after the fault sweep")
        assert run(backup, "mint", quiet=True) == 0, (
            "a v0.2 project must still pass under default invocation on the v0.3 toolchain")
        assert run(proj_v01, "mint", quiet=True, contract="v0.1") == 0, (
            "a v0.1 project must still pass under explicit legacy invocation")
        v03_cli_on_v02 = run(backup, "mint", quiet=True, contract="v0.3")
        assert v03_cli_on_v02 != 0, "a v0.2 project must not evaluate under --contract v0.3"
        print("  v0.2 default invocation still passes")
        print("  v0.1 explicit legacy invocation still passes")
        print("  v0.2 project refused under --contract v0.3")

        print()
        print("toolchain binding faults, each must be caught")
        print("=" * 62)
        toolchain_fault_count = 0
        for filename in CONTRACT_INSTRUMENT_FILES["v0.3"].values():
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
        total_faults = len(faults) + len(v03_faults) + toolchain_fault_count
        print(f"OK: all clean projects pass and all {total_faults} seeded faults are caught "
              f"({len(faults)} v0.2, {len(v03_faults)} v0.3, {toolchain_fault_count} toolchain).")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


V03_RUNNER = "model=model-a; harness=cli; run=c3-b-001; role=runner"
V03_REVIEWER = "model=model-b; harness=cli; run=review-014; role=reviewer"


def build_v03_project(root, runner=V03_RUNNER, reviewer=V03_REVIEWER):
    """A complete v0.3 fixture: 27 attributed decisions, 5 of 5 feasibility questions probed,
    and a scope coherence review bound to the digests of the 7 reviewed rows."""
    root = Path(root)
    with contextlib.redirect_stdout(io.StringIO()):
        init(root, contract="v0.3")

    held = root / "sources" / "regulator_filing.txt"
    held.write_text("Reported capacity 4,200 MW across 17 sites.\n", encoding="utf-8")
    digest = hashlib.sha256(held.read_bytes()).hexdigest()

    probe_bytes = root / "sources" / "feasibility_sample.txt"
    probe_bytes.write_text("First 200 bytes of the register export.\n", encoding="utf-8")
    probe_digest = hashlib.sha256(probe_bytes.read_bytes()).hexdigest()

    release = root / "sources" / "operator_release.txt"
    release.write_text("The operator states 17 sites were energised in the window.\n",
                       encoding="utf-8")
    release_digest = hashlib.sha256(release.read_bytes()).hexdigest()

    audit = root / "sources" / "independent_audit.txt"
    audit.write_text("Metering audit confirms 17 energised sites in the window.\n",
                     encoding="utf-8")
    audit_digest = hashlib.sha256(audit.read_bytes()).hexdigest()

    with (root / "decisions.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(FILES["decisions.csv"])
        for stage in STAGES:
            for did, what in CONTRACT_V0_3[stage].items():
                w.writerow([did, stage, what, f"chose the {what} as stated",
                            "the wider reading|the narrower reading",
                            "the narrower one survives a hostile read", "2026-08-14",
                            runner, "revisit if the regulator restates"])

    with (root / "feasibility.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(file_columns("feasibility.csv", "v0.3"))
        w.writerow(["F1", "regulator capacity return", "source_exists",
                    "https://example.invalid/return", "2026-08-12", "available",
                    "index page lists the return", "", "", "", "", "", "", runner,
                    "Reachable without a login."])
        w.writerow(["F2", "regulator capacity return", "bytes_retrievable",
                    "https://example.invalid/return", "2026-08-12", "available",
                    "sample export held", "sources/feasibility_sample.txt", probe_digest,
                    "", "", "", "", runner, "Sample held and hashed."])
        w.writerow(["F3", "regulator capacity return", "period_and_retention",
                    "https://example.invalid/retention", "2026-08-12", "available",
                    "retention statement, clause 4", "", "",
                    "2019-01-01 to 2026-06-30", "superseded returns kept indefinitely",
                    "", "", runner, "Period and retention stated on the page."])
        w.writerow(["F4", "regulator capacity return", "derivation_independence",
                    "https://example.invalid/method", "2026-08-12", "available",
                    "methodology note, section 2", "", "", "", "", "no", "", runner,
                    "Compiled from metered returns, not from the operator's own statements."])
        w.writerow(["F5", "regulator capacity return", "population_coverage",
                    "https://example.invalid/scope", "2026-08-12", "available",
                    "scope note, section 1", "", "", "", "", "", "yes", runner,
                    "Covers every licensed site in the proposed population."])

    with (root / "sources.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(file_columns("sources.csv", "v0.3"))
        w.writerow(["regulator_filing", "Capacity return", "The regulator", "1",
                    "authoritative for metered capacity as returned",
                    "https://example.invalid/return", "sources/regulator_filing.txt", digest,
                    "retrieved", "2026-08-14", "", "",
                    "Held because the return is republished in place."])
        w.writerow(["vendor_deck", "Investor deck", "The operator", "5",
                    "authoritative only for what the operator asserted",
                    "https://example.invalid/deck", "", "", "registered_not_retrieved",
                    "2026-08-14", "regulator_filing", "",
                    "Gated behind a registration wall; three routes tried, all refused."])
        # A held tier-5 source and an independent tier-2 audit, so the fixture exercises the
        # claim-level corroboration rule on a passing arm rather than only on seeded faults.
        w.writerow(["operator_release", "Operator capacity release", "The operator", "5",
                    "authoritative only for what the operator asserted",
                    "https://example.invalid/release", "sources/operator_release.txt",
                    release_digest, "retrieved", "2026-08-14", "", "",
                    "Held because the release is revised in place."])
        w.writerow(["independent_audit", "Independent metering audit", "An audit body", "2",
                    "authoritative for the metered totals it verified",
                    "https://example.invalid/audit", "sources/independent_audit.txt",
                    audit_digest, "retrieved", "2026-08-14", "", "",
                    "Held because the audit is republished in place."])

    with (root / "claims.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(file_columns("claims.csv", "v0.3"))
        w.writerow(["C1", "Returned capacity is 4,200 MW across 17 sites.",
                    "regulator_filing", "reported", "yes", "as filed, no band given", "", ""])
        w.writerow(["C2", "Mean site size is 247 MW.", "regulator_filing", "derived", "no",
                    "4,200 divided by 17, rounded", "", "Derived, the return states no mean."])
        w.writerow(["C3", "The operator states 17 sites were energised in the window.",
                    "operator_release", "reported", "yes", "as stated, no band given",
                    "independent_audit", "Tier 5 primary, corroborated on this row."])

    write_scope_review(root, reviewer=reviewer, review_date="2026-08-14")
    write_scope_approval(root)

    (root / "findings.md").write_text(
        "# Worked subject v0.3\n\n"
        "Returned capacity is 4,200 MW across 17 sites.\n\n"
        "## Falsifier\n\nA restated return below 3,000 MW would prove this wrong.\n\n"
        "## Verification\n\nCapacity traced to the regulator's capacity return. The mean "
        "site size is derived, the return states no mean.\n\n"
        "## Negative results retained\n\nThe investor deck could not be obtained and stays "
        "in the register against the denominator. No baseline was run.\n\n"
        "## Conflict of interest\n\nNone.\n", encoding="utf-8")


def project_decisions(root):
    with (Path(root) / "decisions.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_scope_review(root, reviewer, review_date, checks=None, digests=None):
    root = Path(root)
    by_id = {(r.get("decision_id") or "").strip().upper(): r for r in project_decisions(root)}
    block = digests or {did: decision_row_digest(by_id[did]) for did in SCOPE_REVIEW_DECISIONS}
    record = {
        "record_type": SCOPE_REVIEW_RECORD_TYPE,
        "schema_version": SCOPE_REVIEW_SCHEMA_VERSION,
        "contract": "v0.3",
        "reviewer": reviewer,
        "review_date": review_date,
        "reviewed_decisions": block,
        "checks": checks or {
            name: {"result": "pass", "note": f"Read the row and confirmed: {question}"}
            for name, question in SCOPE_REVIEW_CHECKS.items()
        },
    }
    (root / SCOPE_REVIEW_FILE).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def write_scope_approval(root, approved_by=SCOPE_APPROVAL_AUTHORITY, approval_date="2026-08-14",
                         decision=SCOPE_APPROVAL_OPENS, accepted=None,
                         reference=("Demo fixture, standing for the decision of 2026-08-14 "
                                    "recorded in handoffs/worked_subject_v03_approval.md"),
                         bound=None):
    """Write a scope approval bound to the closed scope records as they stand."""
    root = Path(root)
    record = {
        "record_type": SCOPE_APPROVAL_RECORD_TYPE,
        "schema_version": SCOPE_APPROVAL_SCHEMA_VERSION,
        "contract": "v0.3",
        "approved_by": approved_by,
        "approval_date": approval_date,
        "decision": decision,
        "accepted_checks": list(accepted or []),
        "approval_reference": reference,
        "bound_files": {name: approval_binding_digest(root, name)
                        for name in SCOPE_APPROVAL_BOUND_FILES}
                       if bound is None else bound,
    }
    (root / SCOPE_APPROVAL_FILE).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def add_csv_column(path, column, value):
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
        cols = list(rows[0].keys()) + [column]
    for r in rows:
        r[column] = value
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def drop_csv_column(path, column):
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
        cols = [c for c in rows[0].keys() if c != column]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def add_restatement_chain(root):
    """Add regulator_filing <- press_mirror <- syndication to the demo sources register.

    Neither end of the chain derives directly from the other, so offering one as the other's second
    source is only detectable by a walk that goes past the first hop.
    """
    path = Path(root) / "sources.csv"
    for source_id, title, tier, origin in (
        ("press_mirror", "Trade press restatement of the return", "3", "regulator_filing"),
        ("syndication", "Newsletter restatement of the trade press", "4", "press_mirror"),
    ):
        append_csv_row(path, {
            "source_id": source_id,
            "title": title,
            "publisher": "A trade publisher",
            "motive_tier": tier,
            "source_role": "authoritative only for what it restated",
            "url": f"https://example.invalid/{source_id}",
            "retrieval_status": "registered_not_retrieved",
            "accessed_date": "2026-08-14",
            "derived_from": origin,
            "notes": "Paywalled after the first paragraph; recorded against the denominator.",
        })


def add_shared_origin_pair(root):
    """Add two mirrors of one disclosure and offer each as the other's independent second source.

    Neither mirror derives from the other, so the ancestor and descendant walks both pass. Only the
    inclusive ancestor sets show that the two agree because they copied the same filing.
    """
    path = Path(root) / "sources.csv"
    for source_id in ("mirror_a", "mirror_b"):
        append_csv_row(path, {
            "source_id": source_id,
            "title": f"Trade press restatement {source_id}",
            "publisher": "A trade publisher",
            "motive_tier": "3",
            "source_role": "authoritative only for what it restated",
            "url": f"https://example.invalid/{source_id}",
            "retrieval_status": "cited_not_held",
            "accessed_date": "2026-08-14",
            "derived_from": "regulator_filing",
            "notes": "Restates the capacity return without adding to it.",
        })
    rewrite_csv(path, "source_id", "mirror_a", {"second_source_id": "mirror_b"})


def refresh_v03_bindings(root):
    """Rewrite the review and the approval against the registers as they now stand.

    A fixture that edits a bound register invalidates both records by hash. Without this the fixture
    would fail on a stale digest, which is a real control firing on the wrong question and proves
    nothing about the rule the fixture was written for.
    """
    write_scope_review(root, reviewer=V03_REVIEWER, review_date="2026-08-14")
    write_scope_approval(root)


def stray_bytes(root):
    """Write real bytes just outside the project and return the path.

    The containment fixtures point at a file that exists, so nothing but the containment rule can
    be what rejects them.
    """
    outside = Path(root).parent / "outside_the_project.txt"
    outside.write_text("Reported capacity 4,200 MW across 17 sites.\n", encoding="utf-8")
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
    root = Path(root)
    outside = stray_bytes(root)
    link = root / "sources" / "escape.txt"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(outside)
    rewrite_csv(root / "sources.csv", "source_id", "regulator_filing",
                {"local_path": "sources/escape.txt"})


def escaping_probe_path(root, local_path):
    """Point the custody probe at real bytes outside the project, hash and all.

    The recorded hash is taken from the file the path reaches, so the row is refused for where the
    bytes live rather than for disagreeing with the register.
    """
    root = Path(root)
    outside = stray_bytes(root)
    rewrite_csv(root / "feasibility.csv", "probe_id", "F2",
                {"local_path": local_path,
                 "sha256": hashlib.sha256(outside.read_bytes()).hexdigest()})
    write_scope_approval(root)


def escaping_probe_symlink(root):
    """Hold probe bytes through a symlink inside the project that resolves outside it."""
    root = Path(root)
    link = root / "sources" / "probe_escape.txt"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(stray_bytes(root))
    escaping_probe_path(root, "sources/probe_escape.txt")


def escaping_corroborator(root, local_path):
    """Hold the corroborating source outside the project, hash and all.

    The url column is cleared, so the escaping path is the only route the row claims and the
    claim that leans on it has nothing reachable to lean on.
    """
    root = Path(root)
    outside = stray_bytes(root)
    rewrite_csv(root / "sources.csv", "source_id", "independent_audit",
                {"url": "", "local_path": local_path,
                 "sha256": hashlib.sha256(outside.read_bytes()).hexdigest()})


def escaping_corroborator_symlink(root):
    """Hold the corroborating source through a symlink that resolves outside the project."""
    root = Path(root)
    link = root / "sources" / "corroborator_escape.txt"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(stray_bytes(root))
    escaping_corroborator(root, "sources/corroborator_escape.txt")


def v03_review_with(root, check, result, note, reviewer=V03_REVIEWER, review_date="2026-08-14"):
    """Rewrite the demo scope review with one check set to a fail or unresolved result."""
    checks = {name: {"result": "pass", "note": f"Read the row and confirmed: {question}"}
              for name, question in SCOPE_REVIEW_CHECKS.items()}
    checks[check] = {"result": result, "note": note}
    write_scope_review(root, reviewer=reviewer, review_date=review_date, checks=checks)


def rewrite_all_csv(path, updates):
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
        cols = list(rows[0].keys())
    for r in rows:
        r.update(updates)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def append_csv_row(path, values):
    """Append a row, filling every column the register declares and leaving the rest blank."""
    with path.open(encoding="utf-8", newline="") as fh:
        cols = list(csv.DictReader(fh).fieldnames or [])
    row = {c: "" for c in cols}
    row.update(values)
    with path.open("a", encoding="utf-8", newline="") as fh:
        csv.DictWriter(fh, fieldnames=cols).writerow(row)


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
    for filename in CONTRACT_INSTRUMENT_FILES["v0.3"].values():
        shutil.copy2(source / filename, target / filename)
    if include_catalogue:
        shutil.copy2(source / RELEASE_CATALOGUE_FILE, target / RELEASE_CATALOGUE_FILE)
    shutil.copytree(source / "_frozen_instruments", target / "_frozen_instruments")


def main():
    ap = argparse.ArgumentParser(description="Process gate for the Divergence Protocol.")
    ap.add_argument("project", nargs="?", help="project directory")
    ap.add_argument("--init", action="store_true", help="scaffold the registers")
    ap.add_argument("--contract", choices=["v0.1", "v0.2", "v0.3"], default=None,
                    help="contract version to enforce (default: project binding or v0.2; v0.1 requires explicit selection)")
    ap.add_argument("--through", choices=STAGES, default="mint",
                    help="gate only the stages up to and including this one (default: mint)")
    ap.add_argument("--scope-digests", action="store_true",
                    help="print the decision-row digest block for a v0.3 scope coherence review")
    ap.add_argument("--approval-digests", action="store_true",
                    help="print the bound-file digest block for a v0.3 scope approval")
    ap.add_argument("--demo", action="store_true", help="self-test with seeded faults")
    a = ap.parse_args()

    if a.demo:
        return demo()
    if not a.project:
        ap.error("a project directory is required (or use --demo)")
    if a.scope_digests:
        return scope_digests(a.project)
    if a.approval_digests:
        return approval_digests(a.project)
    if a.init:
        return init(a.project, contract=a.contract or DEFAULT_CONTRACT)
    return run(a.project, a.through, contract=a.contract)


if __name__ == "__main__":
    sys.exit(main())

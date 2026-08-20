#!/usr/bin/env python3
"""Independent scratch regressions for Divergence Register v0.2 manifest controls."""

import contextlib
import csv
import hashlib
import importlib.util
import io
import json
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
        writer.writerow(RG.FILES["sources.csv"])
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


def quiet_run(root, contract=None):
    with contextlib.redirect_stdout(io.StringIO()):
        return RG.run(root, "mint", quiet=True, contract=contract)


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
    command = ["python3", str(tool_dir / "research_gate.py"), str(project)]
    if contract:
        command.extend(["--contract", contract])
    return subprocess.run(command, text=True, capture_output=True, check=False)


def rows(path):
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_rows(path, fieldnames, data):
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)


def main():
    scratch = Path(tempfile.mkdtemp(prefix="v02_independent_audit_"))
    results = []
    try:
        for filename in ("DIVERGENCE_PROTOCOL.md", "research_gate.py", "agp_deterministic.py"):
            tool_dir = scratch / f"mutated_{filename.replace('.', '_')}"
            copy_tools(tool_dir)
            project = scratch / f"project_{filename.replace('.', '_')}"
            build_clean(project)
            target = tool_dir / filename
            target.write_bytes(target.read_bytes() + b"\n# scratch byte mutation\n")
            observed = cli_run(tool_dir, project).returncode
            results.append((f"actual instrument byte mismatch: {filename}", "FAIL", observed))

        wrong_file = scratch / "wrong_file_identity"
        build_clean(wrong_file)
        binding = read_json(wrong_file / "instrument_manifest.json")
        binding["instruments"]["protocol"] = dict(binding["instruments"]["prose_checker"])
        write_json(wrong_file / "instrument_manifest.json", binding)
        results.append(("protocol binding points to prose checker", "FAIL", quiet_run(wrong_file)))

        wrong_version = scratch / "wrong_version"
        build_clean(wrong_version)
        binding = read_json(wrong_version / "instrument_manifest.json")
        binding["instruments"]["protocol"]["version"] = "unrecognised-version"
        write_json(wrong_version / "instrument_manifest.json", binding)
        results.append(("unrecognised instrument version", "FAIL", quiet_run(wrong_version)))

        legacy_claim_field = scratch / "legacy_claim_field_under_v02"
        build_clean(legacy_claim_field)
        claims_path = legacy_claim_field / "claims.csv"
        claims_path.write_text(
            claims_path.read_text(encoding="utf-8")
            .replace("material_to_conclusion", "load_bearing", 1),
            encoding="utf-8",
        )
        results.append(("legacy v0.1 claim field under v0.2", "FAIL",
                        quiet_run(legacy_claim_field)))

        missing_schema = scratch / "missing_schema"
        build_clean(missing_schema)
        binding = read_json(missing_schema / "instrument_manifest.json")
        binding.pop("schema_version", None)
        write_json(missing_schema / "instrument_manifest.json", binding)
        results.append(("missing project schema version", "FAIL", quiet_run(missing_schema)))

        malformed_legacy = scratch / "malformed_legacy"
        build_clean(malformed_legacy, contract="v0.1")
        (malformed_legacy / "instrument_manifest.json").write_text("{malformed", encoding="utf-8")
        results.append(("malformed binding under explicit v0.1", "FAIL", quiet_run(malformed_legacy, "v0.1")))

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
        observed = cli_run(mutable_contract_tools, mutable_contract_project).returncode
        results.append(("release catalogue removes mandatory S6", "FAIL", observed))

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
        results.append(("source predates final scope decision S6", "FAIL", quiet_run(late_scope)))

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
        results.append(("v0.2 init without release catalogue", "FAIL", proc.returncode))

        print("case | expected gate result | observed exit | verdict")
        print("=" * 100)
        defects = 0
        for case, expected, observed in results:
            verdict = "CAUGHT" if observed != 0 else "FAIL OPEN"
            if observed == 0:
                defects += 1
            print(f"{case} | {expected} | {observed} | {verdict}")
        print(f"\n{defects} of {len(results)} independent invalid fixtures returned exit 0.")
        return 1 if defects else 0
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

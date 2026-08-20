#!/usr/bin/env python3
"""agp_deterministic.py — Adversarial Grounding Pipeline, the DETERMINISTIC layer (v1 MVP).

The non-model floor of the pipeline: pure string/number checks, zero model judgment, so
nothing here can hallucinate. It audits a model OUTPUT against its SOURCE texts and flags
claims for human review. Models (cross-audit, edge contradiction) are LATER add-ons.

Lineage: the Deliverable Filter applied to output verification. See
adversarial_grounding_pipeline_v1.md (sections 3 + 7).

Six checks:
  1. NUMBER-GREP        every number in the output must appear in a source
  2. ENTITY STRING-MATCH proper-noun spans in flagged claims must appear in a source
  3. CONTRADICTION SCAN any entity assigned two different numbers across the output
  4. SOURCE-TIER GATE   numbers found ONLY in tier>=4 sources flag (grounding != truth)
  5. ATTRIBUTION-BINDING who-said/did: subject absent, or present ONLY in a negation/
                         correction context, flags (the misattribution check 2 misses)
  6. TRIAGE             which sentences are high-risk (entity-density / hedge / bare assertion)

Usage:
    agp_deterministic.py OUTPUT.md --source primary.txt:1 --source blog.txt:5
    agp_deterministic.py --demo        # run on a built-in sample (shows a planted catch)

Source tiers: 1 = primary/filing/regulator ... 5 = seller marketing. Append :N to each path.
Stdlib only. spaCy used for triage IF installed; otherwise a regex fallback runs.
"""
import sys, re, csv, io, os, argparse

# ---------- shared primitives ----------
# A comma inside a number groups thousands (4,200). A comma between numbers separates fields
# (1175,7,114). The two are not distinguishable by a regex alone, so two rules apply.
# Here: a grouping comma is accepted only in a well-formed group, meaning a lead of 1 to 3
# digits with no leading zero, followed by groups of exactly 3 digits, and not running on into
# a further digit or comma. Below, in normalise_source: a delimited file is field-split by its
# own format before any numeric extraction, which is exact where this rule can only be careful.
NUM = re.compile(r'(?:0|[1-9]\d{0,2})(?:,\d{3})+(?:\.\d+)?(?![\d,])|\d+(?:\.\d+)?')
# Delimiters of formats that are field-split rather than read as prose.
DELIMITED = {".csv": ",", ".tsv": "\t"}
# git object names (40 hex) and sha256 digests (64 hex). Stripped before numeric extraction:
# a digest is an identifier, not a quantity, and its digit runs are otherwise reported as
# ungrounded numbers, because no source file contains its own hash.
HEXHASH = re.compile(r'\b[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?\b')
# capitalized spans (1-4 words): pragmatic proper-noun proxy without spaCy
ENT = re.compile(r'\b([A-Z][a-zA-Z.&/-]+(?:\s+[A-Z][a-zA-Z.&/-]+){0,3})\b')
HEDGES = ("likely", "suggests", "suggest", "potentially", "possibly", "may", "might",
          "could", "appears", "seems", "reportedly", "roughly", "approximately",
          "around", "estimated", "probably", "presumably", "arguably")
SENT_SPLIT = re.compile(r'(?<=[.!?])\s+')

# attribution ("who said / who did") detection — for the binding / misattribution check
ATTRIB_VERBS = (r'(?:said|told|announced|reported|claimed|stated|warned|wrote|noted|'
                r'covered|alleged|confirmed|accused|described|found)')
ATTRIB_PATTERNS = [
    re.compile(r'\b([A-Z][\w.&\'-]+(?:\s+[A-Z][\w.&\'-]+){0,3})\s+' + ATTRIB_VERBS + r'\b'),
    re.compile(r'\b(?:according to|per|by)\s+([A-Z][\w.&\'-]+(?:\s+[A-Z][\w.&\'-]+){0,3})\b'),
    re.compile(r"\b([A-Z][\w.&'-]+(?:\s+[A-Z][\w.&'-]+){0,3})'s\s+"
               r'(?:report|memo|study|claim|account|video|post|survey|paper)\b'),
]
NEG_CUE = re.compile(r"(no evidence|not |n't |denied|never |unrelated|mistak|wrongly|"
                     r"incorrectly|misattribut|no connection|rather than|instead of|"
                     r"wasn't|isn't|no link)", re.I)


def normalise_source(text, name=""):
    """Field-split a delimited source so its delimiters are not read as thousands separators.

    A source cited as .csv or .tsv is parsed by its own format and the fields are re-joined with
    spaces. Commas inside a quoted field survive, so a held "4,200" still grounds a draft's 4,200.
    Any file that will not parse is returned unchanged and read as prose.
    """
    delim = DELIMITED.get(os.path.splitext(name)[1].lower())
    if not delim:
        return text
    try:
        rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    except csv.Error:
        return text
    return "\n".join(" ".join(row) for row in rows)


def num_cores(s):
    out = set()
    s = HEXHASH.sub(" ", s)
    for m in NUM.findall(s):
        core = m.replace(",", "").rstrip(".")
        if core and any(c.isdigit() for c in core):
            out.add(core)
    return out


def sentences(text):
    return [s.strip() for s in SENT_SPLIT.split(text.replace("\n", " ")) if s.strip()]


def entities(s):
    found = []
    for m in ENT.finditer(s):
        span = m.group(1).strip()
        # drop a lone sentence-initial capitalized word (likely just the first word)
        if m.start() == 0 and " " not in span:
            continue
        found.append(span)
    return found


def has_citation(s):
    return bool(re.search(r'https?://', s) or re.search(r'\[[^\]]+\]', s)
                or re.search(r'\((?:[^)]*\b(?:19|20)\d{2}\b|[^)]*[A-Z][a-z]+)[^)]*\)', s))


# ---------- the five checks ----------
def check_numbers(output, sources_text):
    src = num_cores(sources_text)
    missing = sorted([n for n in num_cores(output) if n not in src and len(n) >= 2],
                     key=lambda x: (-len(x), x))
    return missing


def check_entity_strings(output, sources_text, only_sentences):
    src_low = sources_text.lower()
    missing = set()
    for s in only_sentences:
        for e in entities(s):
            if e.lower() not in src_low:
                missing.add(e)
    return sorted(missing)


def check_contradictions(output):
    pairs = {}  # entity -> set(num cores)
    for s in sentences(output):
        ents, nums = entities(s), num_cores(s)
        if not nums:
            continue
        for e in ents:
            pairs.setdefault(e, set()).update(nums)
    return {e: sorted(ns) for e, ns in pairs.items() if len(ns) > 1}


def check_tier_gate(output, sources):
    """Flag output numbers whose ONLY supporting source is tier>=4."""
    flagged = []
    for n in num_cores(output):
        if len(n) < 2:
            continue
        tiers = [tier for txt, tier in sources if n in num_cores(txt)]
        if tiers and min(tiers) >= 4:
            flagged.append((n, min(tiers)))
    return sorted(flagged, key=lambda x: (-len(x[0]), x[0]))


def triage(output):
    """Return (tier1_sentences, reasons) using spaCy if available, else regex."""
    try:
        import spacy  # optional
        nlp = spacy.load("en_core_web_sm")
        use_spacy = True
    except Exception:
        use_spacy = False
    flagged = []
    for s in sentences(output):
        reasons = []
        if use_spacy:
            doc = nlp(s)
            propn = sum(1 for t in doc if t.pos_ == "PROPN")
            has_num = any(t.like_num for t in doc)
            has_date = any(e.label_ == "DATE" for e in doc.ents)
        else:
            propn = len(entities(s))
            has_num = bool(num_cores(s))
            has_date = bool(re.search(r'\b(19|20)\d{2}\b|\b\d{1,2}\s+\w+\s+\d{4}\b', s))
        if propn > 2 or has_num or has_date:
            reasons.append("entity/numeric density")
        hedged = any(re.search(r'\b' + h + r'\b', s, re.I) for h in HEDGES)
        if hedged and (propn > 1 or has_num):
            reasons.append("hedge + density (shaky leap)")
        if not hedged and not has_citation(s) and (propn > 1 or has_num):
            reasons.append("unhedged assertion, no citation (Plausible-Void risk)")
        if reasons:
            flagged.append((s, reasons))
    return flagged, use_spacy


def extract_attributions(output):
    """Pull (subject, sentence) for who-said / who-did / per-X / X's-report claims."""
    out, seen = [], set()
    for s in sentences(output):
        for pat in ATTRIB_PATTERNS:
            for m in pat.finditer(s):
                subj = m.group(1).strip()
                if subj.lower() in ("the", "this", "that", "it", "according", "a", "an"):
                    continue
                if subj.lower() in seen:
                    continue
                seen.add(subj.lower())
                out.append((subj, s))
    return out


def check_attribution_binding(output, sources_text):
    """For each attribution, is the subject the AGENT in a source, absent, or only negated?
       Catches the misattribution that entity-string-match (check 2) passes."""
    src_low = sources_text.lower()
    results = []
    for subj, _sent in extract_attributions(output):
        sl = subj.lower()
        idxs = [m.start() for m in re.finditer(re.escape(sl), src_low)]
        if not idxs:
            results.append((subj, "ABSENT",
                            "subject not in any source; attribution may be fabricated"))
            continue
        clean = sum(1 for i in idxs
                    if not NEG_CUE.search(src_low[max(0, i - 70): i + len(sl) + 70]))
        if clean == 0:
            results.append((subj, "NEGATED",
                            "subject appears ONLY inside a negation/correction context; "
                            "likely misattribution (the Rossmann pattern)"))
        else:
            results.append((subj, "PRESENT",
                            "subject present in a clean context but binding NOT "
                            "deterministically confirmed; route to cross-audit/human"))
    return results


# ---------- runner ----------
def run(output, sources):
    sources_text = "\n".join(t for t, _ in sources)
    tier1, used_spacy = triage(output)
    tier1_sents = [s for s, _ in tier1]
    rep = []
    rep.append("=" * 60)
    rep.append("ADVERSARIAL GROUNDING PIPELINE — deterministic layer")
    rep.append(f"(triage engine: {'spaCy' if used_spacy else 'regex fallback'})")
    rep.append("=" * 60)

    miss = check_numbers(output, sources_text)
    rep.append(f"\n[1] NUMBER-GREP — {len(miss)} figure(s) not found in any source:")
    rep.append("    " + (", ".join(miss) if miss else "✅ all numbers grounded"))

    ents_miss = check_entity_strings(output, sources_text, tier1_sents)
    rep.append(f"\n[2] ENTITY STRING-MATCH — {len(ents_miss)} entity(ies) in flagged claims absent from sources:")
    rep.append("    " + (", ".join(ents_miss) if ents_miss else "✅ none"))

    contra = check_contradictions(output)
    rep.append(f"\n[3] CONTRADICTION SCAN — {len(contra)} entity(ies) with conflicting numbers:")
    if contra:
        for e, ns in contra.items():
            rep.append(f"    ⚠️ {e}: {ns}  (verify which value belongs to it)")
    else:
        rep.append("    ✅ no entity carries two different numbers")

    tier = check_tier_gate(output, sources)
    rep.append(f"\n[4] SOURCE-TIER GATE — {len(tier)} number(s) supported ONLY by tier>=4 sources:")
    if tier:
        for n, t in tier:
            rep.append(f"    ⚠️ {n} (best source tier {t}) — grounded but low-trust")
    else:
        rep.append("    ✅ none low-tier-only")

    attrib = check_attribution_binding(output, sources_text)
    hard_attrib = [t for t in attrib if t[1] in ("ABSENT", "NEGATED")]
    rep.append(f"\n[5] ATTRIBUTION-BINDING — {len(attrib)} who-said/did claim(s), {len(hard_attrib)} hard flag(s):")
    if attrib:
        for a, st, why in attrib:
            mark = "⚠️" if st in ("ABSENT", "NEGATED") else "•"
            rep.append(f"    {mark} {a}: {st} — {why}")
    else:
        rep.append("    ✅ no attribution claims detected")

    rep.append(f"\n[6] TRIAGE — {len(tier1)} sentence(s) routed to cross-audit:")
    for s, reasons in tier1:
        rep.append(f"    • [{'; '.join(reasons)}]")
        rep.append(f"      {s[:140]}")

    rep.append("\n" + "-" * 60)
    flags = len(miss) + len(ents_miss) + len(contra) + len(tier) + len(hard_attrib)
    rep.append(f"VERDICT: {flags} hard flag(s) for the human. "
               + ("CLEAN at the deterministic floor." if flags == 0
                  else "Route flags to the orchestrator with this diff-log."))
    rep.append("(Reminder: this floor catches fabrication, and now flags attributions whose "
               "subject is absent or sits ONLY in a negation/correction context [the Rossmann "
               "pattern]. It still cannot confirm a SUBTLE binding [subject present, clean, but "
               "not truly the agent], nor catch omissions — those escalate to cross-audit + human.)")
    return "\n".join(rep)


DEMO_OUTPUT = (
    "Palantir CEO Alex Karp had a realized CAP of around $16.4B, the highest in the cohort. "
    "Karp's granted pay was $8.6M while his realized CAP was $11.1B. "
    "Tesla's Elon Musk reached roughly $49.7B. "
    "This is standard practice across the S&P 100. "
    "The startup's revenue likely tripled to $500M last year. "
    "The Claude billing change was reported by Louis Rossmann."
)
DEMO_SOURCES = [
    ("Top by 5-yr realized CAP: Tesla $49.7B, Palantir $16.4B. "
     "Karp granted $8.6M to $11.1B CAP. Median latest-year granted $28.4M.", 1),
    ("A promotional blog claims the startup's revenue hit $500M.", 5),
    ("There is no evidence that Louis Rossmann covered the Claude billing change; "
     "the prominent critic was Theo Browne.", 2),
]


# Seeded-fault case for the delimited-source path. Every figure in the draft below is present in
# the source as a field, except 1190, which is fabricated. NUMBER-GREP must report 1190 and only
# 1190: the row's own field commas must not merge its numbers, and the quoted "4,200" must survive
# as one figure.
DEMO_CSV_NAME = "digest.csv"
DEMO_CSV_SOURCE = (
    "model,vendor,first_seen,last_seen,elo,rank,votes\n"
    "alpha-1,acme,2024-07-30,2024-09-04,1175,7,114\n"
    'beta-2,globex,2025-01-11,2026-03-02,1288,3,"4,200"\n'
)
DEMO_CSV_OUTPUT = (
    "The alpha-1 model scored 1175 at rank 7 with 114 votes. "
    "The beta-2 model scored 1288 at rank 3 with 4,200 votes. "
    "A later revision put alpha-1 at 1190."
)


def selftest():
    """Assert each seeded fault still trips. Returns (lines, failures)."""
    lines, fails = [], 0

    def expect(label, ok, got):
        nonlocal fails
        if not ok:
            fails += 1
        lines.append(f"    {'PASS' if ok else 'FAIL'}  {label}" + ("" if ok else f"  got: {got}"))

    src_text = "\n".join(t for t, _ in DEMO_SOURCES)
    tier1 = [s for s, _ in triage(DEMO_OUTPUT)[0]]

    miss = check_numbers(DEMO_OUTPUT, src_text)
    expect("[1] number-grep flags the ungrounded 100", miss == ["100"], miss)

    ents = check_entity_strings(DEMO_OUTPUT, src_text, tier1)
    expect("[2] entity string-match flags Elon Musk", "Elon Musk" in ents, ents)

    contra = check_contradictions(DEMO_OUTPUT)
    expect("[3] contradiction scan flags CAP with three values",
           sorted(contra.get("CAP", [])) == ["11.1", "16.4", "8.6"], contra.get("CAP"))

    tier = check_tier_gate(DEMO_OUTPUT, DEMO_SOURCES)
    expect("[4] tier gate flags 500 as tier-5 only", tier == [("500", 5)], tier)

    attrib = check_attribution_binding(DEMO_OUTPUT, src_text)
    negated = [s for s, st, _ in attrib if st == "NEGATED"]
    expect("[5] attribution binding flags Louis Rossmann as negated",
           negated == ["Louis Rossmann"], negated)

    # F9: delimited source. Field commas must not merge adjacent numbers, a quoted grouping comma
    # must survive, and a fabricated figure must still be caught.
    norm = normalise_source(DEMO_CSV_SOURCE, DEMO_CSV_NAME)
    csv_miss = check_numbers(DEMO_CSV_OUTPUT, norm)
    expect("[1] delimited source grounds every real field, flags only the fabricated 1190",
           csv_miss == ["1190"], csv_miss)
    expect("[1] a quoted 4,200 in a csv field grounds a draft's 4,200",
           "4200" in num_cores(norm), sorted(num_cores(norm)))
    expect("[1] an unparsed csv would still merge its fields (the defect this guards)",
           len(check_numbers(DEMO_CSV_OUTPUT, DEMO_CSV_SOURCE)) > 1,
           check_numbers(DEMO_CSV_OUTPUT, DEMO_CSV_SOURCE))

    return lines, fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("output", nargs="?", help="model output file to audit")
    ap.add_argument("--source", action="append", default=[], help="source.txt:TIER")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()

    if a.demo:
        print(run(DEMO_OUTPUT, DEMO_SOURCES))
        lines, fails = selftest()
        print("\n" + "=" * 60)
        print(f"SELF-TEST — {len(lines)} seeded fault(s), {fails} not caught:")
        print("\n".join(lines))
        print("=" * 60)
        sys.exit(1 if fails else 0)
    if not a.output or not a.source:
        sys.exit("usage: agp_deterministic.py OUTPUT.md --source file.txt:TIER [...]  (or --demo)")

    with open(a.output, encoding="utf-8", errors="replace") as f:
        output = f.read()
    sources = []
    for spec in a.source:
        path, _, tier = spec.rpartition(":")
        path, tier = (path, tier) if path else (spec, "3")
        with open(path, encoding="utf-8", errors="replace") as f:
            text = normalise_source(f.read(), path)
        sources.append((text, int(tier) if tier.isdigit() else 3))
    print(run(output, sources))


if __name__ == "__main__":
    main()

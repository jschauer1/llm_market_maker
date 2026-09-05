"""Study-only packaging and immutable receipts; never opens the ledger."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import sys

STUDY = Path(__file__).resolve().parent
REPO = next(parent for parent in STUDY.parents if (parent / "tools" / "judgments.py").exists())
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(STUDY))
from tools import atomic_write, judgments
from tools.domain import Verdict
from disclosure import classify

ALIASES = {
    "baxdrostat": ["baxdrostat"], "camizestrant": ["camizestrant"],
    "cagrisema": ["CagriSema", "cagrilintide and semaglutide"],
    "cytisinicline": ["cytisinicline"], "gedatolisib": ["gedatolisib"],
    "midomafetamine_mdma_for_ptsd": ["midomafetamine", "MDMA", "MDMA-AT"],
    "comp360_psilocybin": ["COMP360", "COMP360 psilocybin", "COMP 360"],
    "retatrutide": ["retatrutide"],
    "v940_intismeran_autogene": ["V940", "V-940", "mRNA-4157", "intismeran autogene"],
    "lonvoguran_ziclumeran_lonvo_z": ["lonvoguran ziclumeran", "lonvo-z", "NTLA-2002"],
}
LABELS = {"substantive_barrier", "plausible_path", "formalities_only", "insufficient_evidence"}
SOURCE_FIELDS = ("source_id", "title", "url", "published_at", "captured_at", "sha256",
                 "availability_basis", "text", "excerpt_locator")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def immutable_json(path, value):
    path = Path(path)
    if path.exists():
        if read(path) != value:
            raise ValueError(f"Refusing to replace different frozen data: {path}")
    else:
        atomic_write.write_json(path, value, indent=2)


def blind_sources(packet):
    result = {"sources": [], "excluded_sources": []}
    asof = datetime.fromisoformat(packet["as_of"].replace("Z", "+00:00"))
    for source in packet["sources"]:
        published = source.get("published_at") or ""
        reason = None
        try:
            if len(published) == 10:
                if datetime.fromisoformat(published).date() >= asof.date():
                    reason = "date-only publication not demonstrated before decision"
            else:
                instant = datetime.fromisoformat(published.replace("Z", "+00:00"))
                if instant.tzinfo is None or instant >= asof:
                    reason = "publication not demonstrated before decision"
        except (ValueError, TypeError):
            reason = "missing or invalid publication time"
        if reason:
            result["excluded_sources"].append({"source_id": source.get("source_id"), "reason": reason})
        elif source.get("text", "").strip():
            result["sources"].append({key: source[key] for key in SOURCE_FIELDS if key in source})
        else:
            result["excluded_sources"].append({"source_id": source.get("source_id"), "reason": "no source text"})
    return result


def prepare(cohort, packets, rules_path):
    audit = read(STUDY / "data/exposure_audit.json")
    roster = (audit["historical_eligible_subjects"] if cohort == "historical" else
              audit["current_forward_outcome_validation"]["in_window_cases"])
    raw_rules = read(rules_path)
    rules = raw_rules.get("rules", raw_rules)
    if isinstance(rules, list):
        rules = {row["ticker"]: row for row in rules}
    found = {}
    for path in Path(packets).rglob("packet.json"):
        packet = read(path)
        if packet["subject_id"] in found:
            raise ValueError("Duplicate subject packet")
        found[packet["subject_id"]] = (path, packet)
    cases, input_audit = [], []
    for row in roster:
        subject = row["subject_id"]
        path, packet = found[subject]
        asof = row.get("diagnostic_asof_utc", "2026-09-05T18:30:00Z")
        if packet["as_of"] != asof:
            raise ValueError(f"Wrong packet asof: {subject}")
        selected = blind_sources(packet)
        ticker = row.get("selected_ticker", row.get("ticker"))
        rule = rules[ticker]
        case = {"case_id": f"{cohort}/{subject}", "subject_id": subject,
                "aliases": ALIASES[subject], "as_of": asof,
                "deadline_date": row["deadline_date"],
                "contract": {key: rule[key] for key in ("ticker", "title", "rules_primary", "rules_secondary", "rules_vintage") if key in rule},
                "sources": selected["sources"],
                "coverage": {key: packet.get("coverage", {}).get(key, []) for key in ("missing", "limitations")}}
        if not case["contract"].get("rules_primary"):
            raise ValueError(f"Missing exact rules for {ticker}")
        cases.append(case)
        input_audit.append({"case_id": case["case_id"], "packet": str(path.relative_to(STUDY)),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "source_count": len(selected["sources"]),
                            "excluded_sources": selected["excluded_sources"]})
    folder = STUDY / "judgments" / cohort
    folder.mkdir(parents=True, exist_ok=True)
    prompt = (STUDY / "judge-prompt.md").read_text(encoding="utf-8")
    prompt += f"\nInput file: {folder / 'input.json'}\nOutput file: {folder / 'first-output.json'}\n"
    request = judgments.BatchRequest.build(
        run_id=f"fda-diagnostic-2026-09-05-{cohort}", theory_id="study/fda_obstacle_judgment",
        theory_version=1, run_mode="backtest" if cohort == "historical" else "live",
        decision_at=cases[0]["as_of"], requested_model="gpt-5.6-sol",
        requested_effort="high", requested_web_search=False,
        output_path=folder / "first-output.json", stage="FDA source-only categorical diagnostic",
        batch_id=cohort, candidate_keys=[case["case_id"] for case in cases],
        payload={"cases": cases}, rendered_prompt=prompt)
    immutable_json(folder / "receipt.json", judgments.JudgmentBatchReceipt(request).to_dict())
    judgments.write_payload(folder / "input.json", request)
    if not (folder / "rendered-prompt.md").exists():
        (folder / "rendered-prompt.md").write_text(prompt, encoding="utf-8")
    immutable_json(STUDY / "data" / f"{cohort}-input-audit.json", input_audit)
    immutable_json(STUDY / "data" / f"{cohort}-baseline.json", {case["case_id"]: classify(case) for case in cases})
    print(json.dumps({"cohort": cohort, "cases": len(cases), "sources": sum(len(c["sources"]) for c in cases),
                      "input_path": str(folder / "input.json"), "prompt_path": str(folder / "rendered-prompt.md"),
                      "payload_sha256": request.payload_sha256, "receipt_identity": request.identity_sha256}))


def complete(cohort):
    folder = STUDY / "judgments" / cohort
    output = read(folder / "first-output.json")
    receipt = judgments.load_batch(folder / "receipt.json")
    cases = {case["case_id"]: case for case in receipt.request.payload["cases"]}
    rows = output["results"]
    if len(rows) != len(cases) or {row["case_id"] for row in rows} != set(cases):
        raise ValueError("Wrong or duplicate output cases")
    checks, verdicts = [], {}
    for row in rows:
        if row["label"] not in LABELS:
            raise ValueError("Unknown categorical label")
        source_texts = {s["source_id"]: " ".join(s["text"].split()) for s in cases[row["case_id"]]["sources"]}
        for citation in row["citations"]:
            quote = " ".join(citation["quote"].split())
            checks.append({"case_id": row["case_id"], "source_id": citation["source_id"],
                           "exact_quote_found": bool(quote) and quote in source_texts.get(citation["source_id"], "")})
        verdicts[row["case_id"]] = Verdict(bucket=row["label"], rationale=json.dumps(row, ensure_ascii=False))
    completed = datetime.fromtimestamp((folder / "first-output.json").stat().st_mtime, timezone.utc).isoformat()
    judgments.complete_batch(folder / "receipt.json", model="gpt-5.6-sol", effort="high",
                             web_search=False, results=verdicts, completed_at=completed)
    immutable_json(folder / "citation-checks.json", checks)
    print(json.dumps({"cohort": cohort, "completed_at": completed, "cases": len(rows),
                      "citation_failures": sum(not row["exact_quote_found"] for row in checks)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "complete"])
    parser.add_argument("cohort", choices=["historical", "current"])
    parser.add_argument("--packets", type=Path)
    parser.add_argument("--rules", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.cohort, args.packets, args.rules)
    else:
        complete(args.cohort)

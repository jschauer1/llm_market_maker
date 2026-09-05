"""Offline integrity checks for the current FDA source packets."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PACKETS = ROOT / "packets"
AS_OF = datetime.fromisoformat("2026-09-05T18:30:00+00:00")
EXPECTED = {
    "cagrisema", "cytisinicline", "midomafetamine_mdma_for_ptsd",
    "comp360_psilocybin", "retatrutide", "v940_intismeran_autogene",
    "lonvoguran_ziclumeran_lonvo_z",
}
TOP_KEYS = {"subject_id", "as_of", "sources", "coverage"}
SOURCE_KEYS = {"source_id", "title", "url", "published_at", "captured_at", "sha256", "raw_path", "availability_basis", "text", "excerpt_locator"}
REQUIRED_PHRASES = {
    "cmps_sec_2026q2_10q": ["rolling review", "may not experience a faster review or approval", "pilot stage", "preliminary data should be viewed with caution"],
    "cmps_20260805_q2": ["final submission expected to be completed in Q4"],
    "lonvo_sec_2026q2_10q": ["initiation of a rolling biologics license application", "accept our submission in the second half of 2026", "unable to successfully file and obtain approval"],
    "cyt_fda_20260620_crl_nda218995": ["FACILITY INSPECTIONS", "FDA Form 483", "may require re-inspection", "Submit draft labeling"],
    "mdma_fda_20240808_crl_nda215455": ["does not provide substantial evidence of effectiveness", "durable treatment effect", "functional unblinding", "conduct a new clinical trial", "independent third-party data audit"],
}


def published_before_cutoff(value: str) -> bool:
    if len(value) == 10:
        return date.fromisoformat(value) <= AS_OF.date()
    return datetime.fromisoformat(value.replace("Z", "+00:00")) <= AS_OF


def main() -> None:
    failures = []
    files = sorted(PACKETS.glob("*.json"))
    subjects, source_ids, referenced = set(), set(), set()
    summary = {}
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        subject = data.get("subject_id")
        subjects.add(subject)
        if set(data) != TOP_KEYS: failures.append(f"{path.name}: top-level keys differ from schema")
        if data.get("as_of") != AS_OF.isoformat().replace("+00:00", "Z"): failures.append(f"{path.name}: wrong cutoff")
        words = 0
        for source in data.get("sources", []):
            sid = source.get("source_id")
            if set(source) != SOURCE_KEYS: failures.append(f"{path.name}/{sid}: source keys differ from schema")
            if sid in source_ids: failures.append(f"duplicate source_id: {sid}")
            source_ids.add(sid)
            if not published_before_cutoff(source["published_at"]): failures.append(f"{sid}: published after cutoff")
            captured = datetime.fromisoformat(source["captured_at"].replace("Z", "+00:00"))
            if captured <= AS_OF: failures.append(f"{sid}: capture metadata should disclose post-cutoff retrieval")
            raw = (ROOT / source["raw_path"]).resolve()
            try: raw.relative_to(ROOT.resolve())
            except ValueError: failures.append(f"{sid}: raw path escapes source folder")
            if not raw.is_file(): failures.append(f"{sid}: raw file missing")
            else:
                digest = hashlib.sha256(raw.read_bytes()).hexdigest()
                if digest != source["sha256"]: failures.append(f"{sid}: SHA-256 mismatch")
                referenced.add(raw)
            header = ROOT / "headers" / f"{sid}.headers.json"
            if not header.is_file(): failures.append(f"{sid}: response headers missing")
            if not source.get("text", "").strip(): failures.append(f"{sid}: empty excerpt")
            for phrase in REQUIRED_PHRASES.get(sid, []):
                if phrase.lower() not in source.get("text", "").lower(): failures.append(f"{sid}: required substantive phrase missing: {phrase}")
            words += len(source.get("text", "").split())
        sponsor = data.get("coverage", {}).get("categories", {}).get("sponsor_release", [])
        if len(sponsor) != 3: failures.append(f"{subject}: expected three latest qualifying sponsor releases, found {len(sponsor)}")
        if not 1300 <= words <= 4100: failures.append(f"{subject}: excerpt word count {words} outside QA tolerance 1300..4100")
        limitations = " ".join(data.get("coverage", {}).get("limitations", [])).lower()
        if "no untouched-input holdout claim" not in limitations: failures.append(f"{subject}: missing no-holdout limitation")
        summary[subject] = {"sources": len(data.get("sources", [])), "excerpt_words": words}
    if subjects != EXPECTED: failures.append(f"subject roster mismatch: {sorted(subjects ^ EXPECTED)}")
    receipts = json.loads((ROOT / "retrieval_receipts.json").read_text(encoding="utf-8"))
    if any(x.get("status") == "failed" for x in receipts): failures.append("retrieval receipts contain failures")
    raw_files = {x.resolve() for x in (ROOT / "raw").glob("*") if x.is_file()}
    if raw_files != referenced: failures.append("raw archive has unreferenced or missing packet files")
    result = {"validated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "status": "pass" if not failures else "fail", "subjects": summary, "source_count": len(source_ids), "failures": failures}
    (ROOT / "validation_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if failures: raise SystemExit(1)


if __name__ == "__main__":
    main()

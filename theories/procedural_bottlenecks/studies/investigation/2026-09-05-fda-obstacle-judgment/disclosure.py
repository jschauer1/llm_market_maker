"""Study-owned deterministic disclosure extraction (no model or prices)."""
from datetime import date
import calendar
import re


ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4}
MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
MONTH_PATTERN = "|".join(MONTHS)
WINDOW = re.compile(
    rf"\b(?:(?P<prep>in|during|on|for|by|before|after|until)\s+)?(?:the\s+)?"
    rf"(?:Q(?P<q>[1-4])\s+(?P<qy>20\d{{2}})"
    rf"|(?P<ord>first|second|third|fourth)\s+(?P<unit>quarter|half)(?:\s+of)?\s+(?P<oy>20\d{{2}})"
    rf"|(?P<month>{MONTH_PATTERN})(?:\s+(?P<day>\d{{1,2}}),?)?\s+(?P<my>20\d{{2}})"
    rf"|(?P<year>20\d{{2}}))\b", re.I)
FILING = re.compile(r"\b(?:re-?submit|submit|submission|resubmission|filing|file)\b", re.I)
APPLICATION = re.compile(r"\b(?:NDA|BLA|new drug application|biologics license application|application)\b", re.I)
PLAN = re.compile(r"\b(?:expect\w*|plan\w*|intend\w*|anticipat\w*|target\w*|scheduled|will)\b", re.I)
CONDITIONAL = re.compile(r"\b(?:may|might|could|if|no assurance|not expect|not plan|not intend|not anticipate|not target)\b", re.I)
WARNING = re.compile(
    r"(?:\bexpect\w*\b.{0,100}\b(?:complete response letter|CRL)\b"
    r"|\b(?:unresolved|outstanding|current)\b.{0,70}\bmanufacturing (?:deficien\w*|issues?)\b"
    r"|\b(?:manufacturing|facility|inspection)\b.{0,100}\b(?:OAI|official action indicated|deficien\w*)\b)", re.I)
INABILITY = re.compile(
    r"\b(?:cannot|will not|unable to|not expect\w* to)\b.{0,80}\b(?:approval|approved)\b.{0,30}\b(?:before|until|by)\b", re.I)


def window_start(match):
    """A 'by' or 'before' upper bound never establishes a late earliest date."""
    parts = match.groupdict()
    if (parts.get("prep") or "").lower() in {"by", "before"}:
        return None
    if parts["q"]:
        return date(int(parts["qy"]), 3 * (int(parts["q"]) - 1) + 1, 1)
    if parts["ord"]:
        ordinal = ORDINALS[parts["ord"].lower()]
        unit = parts["unit"].lower()
        if unit == "half" and ordinal > 2:
            return None
        return date(int(parts["oy"]), (3 if unit == "quarter" else 6) * (ordinal - 1) + 1, 1)
    if parts["month"]:
        try:
            return date(int(parts["my"]), MONTHS[parts["month"].lower()], int(parts["day"] or 1))
        except ValueError:
            return None
    return date(int(parts["year"]), 1, 1)


def units(text):
    # Retain exact text. Avoid treating initials such as U.S. as sentence ends.
    text = text.replace("U.S.", "U~S~")
    for paragraph in re.split(r"\n\s*\n", text):
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", paragraph):
            yield sentence.replace("U~S~", "U.S.").strip()


def classify(case):
    result = {"primary_signal": False, "warning_signal": False,
              "filing_windows": [], "matches": [], "parsing_failures": []}
    deadline = date.fromisoformat(case["deadline_date"])
    aliases = case.get("aliases", [case["subject_id"].replace("_", " ")])
    anchor = re.compile("|".join(r"(?<!\w)" + re.escape(alias) + r"(?!\w)" for alias in aliases), re.I)
    for source in case["sources"]:
        for text in units(source["text"]):
            if not anchor.search(text):
                continue
            record = {"source_id": source["source_id"], "text": text}
            inability = INABILITY.search(text)
            if inability:
                # Inability before D establishes a lower bound, unlike filing by D.
                tail = text[inability.start():]
                match = WINDOW.search(tail)
                if match:
                    plain = WINDOW.search(re.sub(r"\b(before|by)\b", "in", match.group(), flags=re.I))
                    earliest = window_start(plain)
                    if earliest and earliest >= deadline:
                        result["primary_signal"] = True
                        result["matches"].append({**record, "kind": "explicit_inability", "earliest": earliest.isoformat()})
            if CONDITIONAL.search(text):
                continue
            if WARNING.search(text):
                result["warning_signal"] = True
                result["matches"].append({**record, "kind": "warning"})
            filing = FILING.search(text)
            if not filing or not APPLICATION.search(text) or not PLAN.search(text[:filing.end()]):
                continue
            matches = list(WINDOW.finditer(text[filing.end():]))
            if not matches:
                result["parsing_failures"].append({**record, "reason": "no dated filing window"})
                continue
            match = matches[0]
            earliest = window_start(match)
            if earliest is None:
                result["parsing_failures"].append({**record, "reason": "upper bound or invalid date", "window": match.group()})
                continue
            window = {**record, "window": match.group(), "earliest": earliest.isoformat()}
            result["filing_windows"].append(window)
            if earliest >= deadline:
                result["primary_signal"] = True
                result["matches"].append({**window, "kind": "late_required_filing_plan"})
    return result

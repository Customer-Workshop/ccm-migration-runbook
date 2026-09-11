"""Name normalisation and fuzzy matching shared by G0 and G4. Heuristic evidence only."""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterable

STOPWORDS = {"the", "and", "of", "to", "a", "in", "or", "for", "is", "be", "on", "by", "with", "this", "that"}
TOKEN = re.compile(r"[A-Za-z][A-Za-z']+")
ABBREV = {
    "number": {"no", "num", "nbr", "number"},
    "name": {"nam", "name", "nm"},
    "date": {"dte", "dt", "date"},
    "indicator": {"ind", "indicator", "flag"},
    "amount": {"amt", "amount"},
    "code": {"cde", "code"},
    "text": {"txt", "text"},
    "account": {"acct", "accno", "account", "acc"},
    "telephone": {"tel", "phone", "phoneno", "telnum"},
    "first": {"first", "frst"},
    "middle": {"mid", "middle"},
    "quarterly": {"qutr", "quarterly", "quartely"},
    "annual": {"ann", "annual", "annal"},
    "monthly": {"mnthly", "monthly"},
    "frequency": {"freq", "frequency"},
    "recurring": {"recurring", "rec", "rpymt"},
    "payment": {"pymnt", "pymt", "payment", "pay"},
}
CANONICAL = {variant: canonical for canonical, variants in ABBREV.items() for variant in variants}


def norm(name: str | None) -> str:
    if not name:
        return ""
    text = re.sub(r"_FormControl$|_Table.*$|_RowSet.*$", "", name)
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).lower()
    words = (CANONICAL.get(w, w) for w in text.split())
    return " ".join(w for w in words if w not in STOPWORDS)


def best_match(needle: str, haystack: list[str], cutoff: float = 0.72) -> tuple[str | None, float]:
    if not needle or not haystack:
        return None, 0.0
    scored = []
    for candidate in haystack:
        ratio = difflib.SequenceMatcher(None, needle, candidate).ratio()
        overlap = len(set(needle.split()) & set(candidate.split())) / max(1, len(needle.split()))
        scored.append((max(ratio, 0.5 * ratio + 0.5 * overlap), candidate))
    score, candidate = max(scored)
    return (candidate, round(score, 3)) if score >= cutoff else (None, round(score, 3))


def static_text_coverage(cim: dict, inv: dict) -> tuple[float, list[str]]:
    """Share of target static-text tokens present in the source statics or captions, plus the target-only tokens."""
    source = tokens(s["text"] for s in cim["statics"]) | tokens(f["caption"] for f in cim["fields"])
    target = tokens(inv["static_text"])
    coverage = len(target & source) / len(target) if target else 0.0
    return round(coverage, 4), sorted(target - source)[:50]


def tokens(strings: Iterable[str | None]) -> set[str]:
    out = set()
    for value in strings:
        for match in TOKEN.finditer(value or ""):
            word = match.group(0).lower()
            if word not in STOPWORDS and len(word) > 2:
                out.add(word)
    return out

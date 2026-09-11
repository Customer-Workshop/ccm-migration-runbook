"""Idiom classification of XDP event scripts (VAL-05..VAL-07).

Script bodies are matched as text only and never executed (GOV-04). The first
classifier that matches wins, so the tuple is ordered from the most specific
compose-time idioms to the broadest interactive ones. ``page_number`` and
``prefill`` are single-statement idioms: a body that branches or concatenates
around them is not a static read and stays ``unknown``.
"""

from __future__ import annotations

import re

RULE_TRANSLATABLE = "rule_translatable"
RUNTIME_ONLY = "runtime_only"
MANUAL = "manual"

SCRIPT_CLASSIFIERS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "page_number",
        re.compile(r"xfa\.layout\.(?:page|pageCount|absPage|absPageCount|pageSpan)\s*\(", re.I),
        RULE_TRANSLATABLE,
    ),
    (
        "prefill",
        re.compile(
            r"rawValue\s*=\s*(?:xfa\.(?:data|record|datasets)\.resolveNode\s*\(|xfa\.record\.|\$record\.)",
            re.I,
        ),
        RULE_TRANSLATABLE,
    ),
    ("uppercase", re.compile(r"toUpperCase|\.rawValue\s*=\s*.*upper", re.I), RULE_TRANSLATABLE),
    ("mutual_exclusion", re.compile(r"rawValue\s*=\s*(?:0|\"0\"|'0'|\"off\"|off)(?![\w.])", re.I), RULE_TRANSLATABLE),
    ("conditional_clear", re.compile(r"rawValue\s*=\s*(null|\"\")", re.I), RULE_TRANSLATABLE),
    ("visibility", re.compile(r"presence\s*=|\.access\s*=", re.I), RULE_TRANSLATABLE),
    ("navigation", re.compile(r"xfa\.host\.(gotoURL|pageDown|pageUp)|\.execEvent", re.I), RUNTIME_ONLY),
    ("submit", re.compile(r"HTTPSubmit|\.submit\(|\.submit\.target|xfa\.host\.exportData", re.I), RUNTIME_ONLY),
    ("signature", re.compile(r"signature|eSign", re.I), MANUAL),
    ("external_call", re.compile(r"SOAP|WSDL|xfa\.connectionSet|Net\.HTTP", re.I), MANUAL),
    ("formatting", re.compile(r"formatString|util\.printf|replace\(", re.I), RULE_TRANSLATABLE),
    ("calculation", re.compile(r"[-+*/]\s*\w+\.rawValue|Math\.", re.I), RULE_TRANSLATABLE),
)

SINGLE_STATEMENT = frozenset({"page_number", "prefill"})
CLASSIFICATIONS = tuple(label for label, _, _ in SCRIPT_CLASSIFIERS) + ("unknown",)

COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)
BRANCHING = re.compile(r"\b(?:if|else|for|while|switch|function)\b|[{}]")

SOM_REF = re.compile(
    r"(?:xfa\.(?:data\.|record\.|datasets\.)?resolveNode\(\s*\"([^\"]+)\"|([A-Za-z_][\w.]*)\.rawValue)"
)


def classify_script(body: str) -> tuple[str, str]:
    """Return ``(classification, transferability)`` for a script body; unknown idioms are manual."""
    for label, pattern, transfer in SCRIPT_CLASSIFIERS:
        if pattern.search(body) and (label not in SINGLE_STATEMENT or is_single_statement(body)):
            return label, transfer
    return "unknown", MANUAL


def is_single_statement(body: str) -> bool:
    """True when the body, comments removed, is one straight-line statement."""
    code = COMMENT.sub("", body)
    statements = [s for s in code.split(";") if s.strip()]
    return len(statements) == 1 and not BRANCHING.search(statements[0])


def script_targets(body: str, limit: int = 20) -> list[str]:
    """SOM expressions and data paths a script reads or writes, sorted and de-duplicated."""
    refs = {m.group(1) or m.group(2) for m in SOM_REF.finditer(body)}
    return sorted(refs - {None})[:limit]

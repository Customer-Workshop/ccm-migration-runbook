"""Structured conversion rulebook: YAML rules plus a lint that keeps them honest."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

RULES_DIR = Path(__file__).resolve().parent / "rules"
FAMILIES = ("OBJ", "FLD", "LAY", "BND", "VAL", "STY", "UNS", "GOV")
CLASSES = ("AUTO", "AUTO*", "ASSIST", "MANUAL")
STATUSES = ("draft", "verified", "deprecated")
GATES = ("G0", "G1", "G2", "G3", "G4", "G5", "G6")
ORIGIN_TYPES = ("reference_pair", "designer_error", "coverage_report", "lossless_gate", "analysis", "documentation")
RULE_ID = re.compile(r"^(OBJ|FLD|LAY|BND|VAL|STY|UNS|GOV)-\d{2}$")
REQUIRED = (
    "id",
    "title",
    "class",
    "status",
    "source",
    "target",
    "evidence",
    "origin",
    "fixtures",
    "implemented_in",
    "gates",
    "reviewed_by",
    "reviewed_on",
)


@dataclass
class Rule:
    id: str
    family: str
    title: str
    cls: str
    status: str
    source: str
    target: str
    evidence: str
    origin: dict
    fixtures: list
    implemented_in: list
    gates: list
    reviewed_by: str | None
    reviewed_on: str | None
    parameters: dict = field(default_factory=dict)
    notes: str | None = None

    @property
    def is_verified(self) -> bool:
        return self.status == "verified"


def load_rules(rules_dir: Path = RULES_DIR) -> dict[str, Rule]:
    rules: dict[str, Rule] = {}
    for path in sorted(rules_dir.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        family = doc.get("family")
        for raw in doc.get("rules") or []:
            rule = Rule(
                id=raw.get("id"),
                family=family,
                title=raw.get("title"),
                cls=raw.get("class"),
                status=raw.get("status"),
                source=raw.get("source"),
                target=raw.get("target"),
                evidence=raw.get("evidence"),
                origin=raw.get("origin") or {},
                fixtures=raw.get("fixtures") or [],
                implemented_in=raw.get("implemented_in") or [],
                gates=raw.get("gates") or [],
                reviewed_by=raw.get("reviewed_by"),
                reviewed_on=raw.get("reviewed_on"),
                parameters=raw.get("parameters") or {},
                notes=raw.get("notes"),
            )
            rules[rule.id] = rule
    return rules


def lint(rules_dir: Path = RULES_DIR, known_fixtures: set[str] | None = None) -> list[str]:
    """Return a list of problems. Empty list means the rulebook is consistent."""
    problems: list[str] = []
    seen: set[str] = set()
    for path in sorted(rules_dir.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        family = doc.get("family")
        if family not in FAMILIES:
            problems.append(f"{path.name}: unknown family {family!r}")
            continue
        for raw in doc.get("rules") or []:
            rid = raw.get("id", "<missing id>")
            where = f"{path.name}:{rid}"
            for key in REQUIRED:
                if key not in raw:
                    problems.append(f"{where}: missing key {key!r}")
            if not RULE_ID.match(str(rid)):
                problems.append(f"{where}: id does not match FAMILY-NN")
            elif not rid.startswith(family + "-"):
                problems.append(f"{where}: id family does not match file family {family}")
            if rid in seen:
                problems.append(f"{where}: duplicate id")
            seen.add(rid)
            if raw.get("class") not in CLASSES:
                problems.append(f"{where}: class must be one of {CLASSES}")
            status = raw.get("status")
            if status not in STATUSES:
                problems.append(f"{where}: status must be one of {STATUSES}")
            if status == "verified" and not (raw.get("reviewed_by") and raw.get("reviewed_on")):
                problems.append(f"{where}: verified rules need reviewed_by and reviewed_on")
            if status == "draft" and raw.get("reviewed_by"):
                problems.append(f"{where}: draft rules must not carry reviewed_by")
            origin = raw.get("origin") or {}
            if origin.get("type") not in ORIGIN_TYPES:
                problems.append(f"{where}: origin.type must be one of {ORIGIN_TYPES}")
            if not origin.get("refs"):
                problems.append(f"{where}: origin.refs is empty")
            for gate in raw.get("gates") or []:
                if gate not in GATES:
                    problems.append(f"{where}: unknown gate {gate}")
            if not raw.get("gates"):
                problems.append(f"{where}: no gate enforces this rule")
            if known_fixtures is not None:
                for fx in raw.get("fixtures") or []:
                    if fx not in known_fixtures:
                        problems.append(f"{where}: fixture {fx} is not in src/fixtures/pairs.yaml")
            if raw.get("class") in ("AUTO", "AUTO*") and not raw.get("implemented_in") and status != "deprecated":
                problems.append(f"{where}: AUTO rule has no implemented_in entry (mark ASSIST/MANUAL or implement it)")
    return problems

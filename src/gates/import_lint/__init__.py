"""Offline lint of a Quadient Layout export against the import-error catalogue.

Each catalogue entry names a check function in this module. A check receives the target
inventory (gates.target_inventory.inventory) and returns a list of offending node ids.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from gates.common import GateResult, require

CATALOGUE_PATH = Path(__file__).resolve().parent / "catalogue.yaml"
CATALOGUE_STATUSES = ("observed", "inferred")


def load_catalogue(path: Path = CATALOGUE_PATH) -> list[dict]:
    entries = yaml.safe_load(path.read_text(encoding="utf-8"))
    require(isinstance(entries, list) and bool(entries), f"{path}: catalogue must be a non-empty list")
    for entry in entries:
        require(entry["status"] in CATALOGUE_STATUSES, f"{entry['code']}: bad status {entry['status']!r}")
        require(entry["check"].startswith(__name__ + "."), f"{entry['code']}: check must live in {__name__}")
        require(entry["check"].rsplit(".", 1)[1] in CHECKS, f"{entry['code']}: unknown check {entry['check']}")
    return entries


def declarations_have_bodies(inv: dict) -> list[str]:
    return inv["integrity"]["declarations_without_body"]


def bodies_are_declared(inv: dict) -> list[str]:
    return inv["integrity"]["bodies_without_declaration"]


def no_dangling_references(inv: dict) -> list[str]:
    return [f"{d['body']}#{d['id']}/{d['ref_tag']}={d['value']}" for d in inv["integrity"]["dangling_references"]]


def no_orphan_declarations(inv: dict) -> list[str]:
    return inv["integrity"]["orphan_declarations"]


def has_page_and_flow(inv: dict) -> list[str]:
    missing = []
    if not inv["pages"]:
        missing.append("Def.Pages/Page")
    if not inv["counts"]["by_type"].get("Flow"):
        missing.append("Flow")
    return missing


def export_declares_version(inv: dict) -> list[str]:
    return inv["integrity"]["missing_attributes"]


CHECKS = {
    "export_declares_version": export_declares_version,
    "declarations_have_bodies": declarations_have_bodies,
    "bodies_are_declared": bodies_are_declared,
    "no_dangling_references": no_dangling_references,
    "no_orphan_declarations": no_orphan_declarations,
    "has_page_and_flow": has_page_and_flow,
}


def lint(inv: dict, catalogue: list[dict]) -> GateResult:
    result = GateResult(gate="G5", verdict="pass")
    for entry in catalogue:
        offenders = CHECKS[entry["check"].rsplit(".", 1)[1]](inv)
        for node in offenders[:50]:
            result.add(entry["code"], "major", entry["title"], node=node, rule_id=entry["rule_id"])
        result.metrics[entry["code"]] = len(offenders)
    return result

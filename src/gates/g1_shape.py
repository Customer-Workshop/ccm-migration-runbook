"""G1: CIM shape. JSON Schema validation plus referential integrity (GOV-02, FLD-01)."""

from __future__ import annotations

import json
import re

from jsonschema import Draft202012Validator

from cim import SCHEMA_PATH
from gates.common import GateResult

SHA256 = re.compile(r"[a-f0-9]{64}")


def run(cim: dict) -> GateResult:
    result = GateResult(gate="G1", verdict="pass")
    validator = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    for error in sorted(validator.iter_errors(cim), key=lambda e: list(e.absolute_path)):
        path = "/".join(str(p) for p in error.absolute_path) or "<root>"
        result.add("G1-SCHEMA", "blocker", error.message, node=path, rule_id="GOV-02")
    if result.findings:
        return result.finalize()

    if not SHA256.fullmatch(cim["form"]["source_sha256"]):
        result.add("G1-NOHASH", "major", "form.source_sha256 malformed: output is not auditable", rule_id="GOV-02")
    ids = [c["id"] for c in cim["containers"]] + [f["id"] for f in cim["fields"]] + [s["id"] for s in cim["statics"]]
    if len(ids) != len(set(ids)):
        result.add("G1-DUPID", "blocker", "duplicate node ids in CIM", rule_id="FLD-01")
    container_ids = {c["id"] for c in cim["containers"]}
    for container in cim["containers"]:
        if container["parent_id"] and container["parent_id"] not in container_ids:
            result.add(
                "G1-ORPHAN", "blocker", "container references unknown parent", node=container["som"], rule_id="FLD-01"
            )
    for node in cim["fields"] + cim["statics"]:
        if node["container_id"] not in container_ids:
            result.add(
                "G1-NODEORPHAN", "blocker", "node is not attached to a container", node=node["som"], rule_id="FLD-01"
            )
    style_ids = {s["id"] for s in cim["styles"]}
    for node in cim["fields"] + cim["statics"]:
        if node.get("style_ref") and node["style_ref"] not in style_ids:
            result.add(
                "G1-STYLEREF", "major", "style_ref points to an unknown style", node=node["som"], rule_id="STY-03"
            )
    result.metrics = {
        "containers": len(cim["containers"]),
        "fields": len(cim["fields"]),
        "statics": len(cim["statics"]),
    }
    return result.finalize()

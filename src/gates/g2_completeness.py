"""G2: extraction completeness and losslessness.

Every field, draw and container node in the XFA template must appear in the CIM or in
diagnostics.unsupported. The v1.0 extractor silently dropped master-page content; this gate
exists so that class of loss fails CI instead of being discovered in Designer.
"""

from __future__ import annotations

from gates.common import GateResult

CONTAINER_TAGS = ("subform", "area", "pageArea")


def run(cim: dict) -> GateResult:
    result = GateResult(gate="G2", verdict="pass")
    census = cim["diagnostics"]["counts"]["source_nodes"]
    accounted = {"field": len(cim["fields"]), "draw": len(cim["statics"]), "container": len(cim["containers"])}
    expected = {
        "field": census.get("field", 0),
        "draw": census.get("draw", 0),
        "container": sum(census.get(tag, 0) for tag in CONTAINER_TAGS),
    }
    result.metrics = {"source": expected, "accounted": accounted}
    for kind in expected:
        if accounted[kind] != expected[kind]:
            result.add(
                "G2-LOSSLESS",
                "blocker",
                f"source has {expected[kind]} {kind} node(s), CIM has {accounted[kind]}",
                rule_id="OBJ-12",
            )

    if not cim["pages"]:
        result.add("G2-NOPAGE", "blocker", "no page geometry extracted", rule_id="LAY-01")
    for page in cim["pages"]:
        medium = page["medium"]
        if not medium.get("width_mm") or not medium.get("height_mm"):
            result.add("G2-NOMEDIUM", "blocker", "page has no medium size", node=page["name"], rule_id="LAY-01")
        if not page["content_areas"]:
            result.add("G2-NOCONTENT", "major", "page has no content area", node=page["name"], rule_id="LAY-02")
    if not cim["fields"]:
        result.add("G2-NOFIELDS", "blocker", "no fields extracted from the template", rule_id="FLD-01")
    for field in cim["fields"]:
        if field["control"]["kind"] == "unknown":
            result.add(
                "G2-UNKNOWNCTRL", "major", "control kind could not be classified", node=field["som"], rule_id="FLD-02"
            )
        if field["geometry"].get("w_mm") in (None, 0) and field["control"]["kind"] != "action":
            result.add(
                "G2-NOGEOM",
                "minor",
                "field has no width; target sizing needs a designer",
                node=field["som"],
                rule_id="LAY-06",
            )
    for static in cim["statics"]:
        if static["kind"] == "unknown":
            result.add(
                "G2-UNKNOWNSTATIC",
                "minor",
                "static content could not be classified",
                node=static["som"],
                rule_id="OBJ-05",
            )
    if not cim["styles"]:
        result.add("G2-NOSTYLES", "major", "no styles captured", rule_id="STY-03")
    return result.finalize()

"""CIM -> Inspire build plan.

The build plan is the last Python artifact before Quadient tooling takes over.
It is a flat, deterministic JSON document that says *what* migration-model
objects to create (variables, styles, blocks, pages, template) and which
source nodes are skipped or need a human decision.  The Groovy script in
``groovy/CimBuildPlanImport.groovy`` reads it and calls migration-stack
builders; this module never writes target XML itself (GOV-03).
"""

import json
from pathlib import Path

from dictionary import CrosswalkRow

PLAN_VERSION = "1.1"
ROW_SUFFIX = "_R{index}"

DATA_TYPES = {
    "string": "String",
    "boolean": "Boolean",
    "date": "DateTime",
    "decimal": "Double",
    "currency": "Currency",
    "integer": "Integer",
}

ALIGNMENTS = {
    None: "Left",
    "left": "Left",
    "center": "Center",
    "right": "Right",
    "justify": "JustifyLeft",
}

SKIPPED_CONTROLS = {
    "barcode": "OBJ-08",
    "image": "UNS-09",
    "signature": "UNS-07",
    "action": "VAL-09",
}


class BuildPlanError(ValueError):
    """The CIM cannot be expressed as a build plan; the message names the offending node."""


def build_plan(cim: dict, crosswalk: dict[tuple[str, str], CrosswalkRow]) -> dict:
    form_code = cim["form"]["form_code"]
    variables, decisions, skipped = _variables(cim, form_code, crosswalk)
    blocks = _blocks(cim, variables, skipped)
    pages = _pages(cim, blocks)
    return {
        "plan_version": PLAN_VERSION,
        "form_code": form_code,
        "source_sha256": cim["form"]["source_sha256"],
        "variables": sorted(variables.values(), key=lambda v: v["id"]),
        "text_styles": [_text_style(s) for s in cim["styles"]],
        "paragraph_styles": [_paragraph_style(s) for s in cim["styles"]],
        "blocks": blocks,
        "pages": pages,
        "template": {"id": f"{form_code}_Template", "page_ids": [p["id"] for p in pages]},
        "skipped": skipped,
        "decisions_required": decisions,
        "designer_import": "not_run",
    }


def _variables(
    cim: dict, form_code: str, crosswalk: dict[tuple[str, str], CrosswalkRow]
) -> tuple[dict[str, dict], list[dict], list[dict]]:
    variables: dict[str, dict] = {}
    decisions: list[dict] = []
    skipped: list[dict] = []
    for f in cim["fields"]:
        kind = f["control"]["kind"]
        if kind in SKIPPED_CONTROLS:
            skipped.append(
                {
                    "node": f["som"],
                    "reason": f"{kind} control has no build-plan representation",
                    "rule_id": SKIPPED_CONTROLS[kind],
                }
            )
            continue
        row = crosswalk.get((form_code, f["som"]))
        if row is not None and row.status != "rejected":
            name, resolution = row.target_variable, f"dictionary:{row.status}"
        elif f["binding"]["target_variable_hint"]:
            name, resolution = f["binding"]["target_variable_hint"], "binding"
        else:
            name, resolution = f"UNRESOLVED_{f['id']}_{f['name']}", "unresolved"
            decisions.append(
                {
                    "node": f["som"],
                    "decision": "target variable name and data path",
                    "owner": "data_steward",
                    "rule_id": "BND-04",
                }
            )
        if f["datatype"] not in DATA_TYPES:
            raise BuildPlanError(f"{f['som']}: datatype '{f['datatype']}' has no migration-stack DataType")
        data_path = f["binding"]["source_path"]
        group = [v for v in variables.values() if v["name"] == name or v.get("disambiguated_from") == name]
        existing = next((v for v in group if v["data_path"] == data_path), None)
        if existing is not None:
            existing["source_soms"].append(f["som"])
        else:
            variable = {
                "id": f"{form_code}_{name}",
                "name": name,
                "data_type": DATA_TYPES[f["datatype"]],
                "data_path": data_path,
                "resolution": resolution,
                "source_soms": [f["som"]],
            }
            if group:
                row_index = len(group) + 1
                variable["name"] = name + ROW_SUFFIX.format(index=row_index)
                variable["id"] = f"{form_code}_{variable['name']}"
                variable["disambiguated_from"] = name
                variable["row_index"] = row_index
                decisions.append(
                    {
                        "node": f["som"],
                        "decision": f"'{name}' is shared by fields with different data paths; confirm the "
                        f"row-suffix variable '{variable['name']}' or supply the repeat representation",
                        "owner": "data_steward",
                        "rule_id": "BND-10",
                    }
                )
            variables[variable["id"]] = variable
        if kind in ("checkbox", "radio"):
            decisions.append(
                {
                    "node": f["som"],
                    "decision": "checkbox/radio rendering (glyph, radio grouping)",
                    "owner": "designer",
                    "rule_id": "OBJ-06",
                }
            )
    return variables, decisions, skipped


def _text_style(style: dict) -> dict:
    return {
        "id": style["id"],
        "font_family": style["typeface"],
        "size_pt": style["size_pt"],
        "bold": style["bold"],
        "italic": style["italic"],
        "underline": style["underline"],
    }


def _paragraph_style(style: dict) -> dict:
    return {"id": f"{style['id']}_para", "alignment": ALIGNMENTS[style["align"]]}


def _order_key(node: dict) -> tuple[int, float, int, float]:
    g = node["geometry"]
    y = (1, 0.0) if g["y_mm"] is None else (0, g["y_mm"])
    x = (1, 0.0) if g["x_mm"] is None else (0, g["x_mm"])
    return y + x


def _blocks(cim: dict, variables: dict[str, dict], skipped: list[dict]) -> list[dict]:
    skipped_nodes = {s["node"] for s in skipped}
    by_container: dict[str, list[dict]] = {c["id"]: [] for c in cim["containers"]}
    for s in cim["statics"]:
        if s["kind"] in ("text", "rich_text"):
            by_container[s["container_id"]].append(
                {"kind": "text", "text": s["text"], "style_id": s["style_ref"], "node": s}
            )
    var_by_som = {som: v["id"] for v in variables.values() for som in v["source_soms"]}
    for f in cim["fields"]:
        if f["som"] in skipped_nodes:
            continue
        by_container[f["container_id"]].append(
            {
                "kind": "variable",
                "caption": f["caption"],
                "variable_id": var_by_som[f["som"]],
                "style_id": f["style_ref"],
                "node": f,
            }
        )

    blocks = []
    for c in cim["containers"]:
        items = sorted(by_container[c["id"]], key=lambda i: _order_key(i["node"]))
        paragraphs = [{k: v for k, v in item.items() if k != "node"} for item in items]
        children = [k["id"] for k in cim["containers"] if k["parent_id"] == c["id"]]
        if not paragraphs and not children:
            continue
        blocks.append(
            {
                "id": f"{cim['form']['form_code']}_{c['id']}",
                "name": c["section_heading"] or c["name"],
                "role": c["role"],
                "container_id": c["id"],
                "paragraphs": paragraphs,
                "child_block_ids": [f"{cim['form']['form_code']}_{k}" for k in children],
            }
        )
    return blocks


def _pages(cim: dict, blocks: list[dict]) -> list[dict]:
    body = next((b for b in blocks if b["role"] == "page_body"), None)
    if body is None:
        raise BuildPlanError(f"{cim['form']['form_code']}: no page_body block; the root subform emitted no content")
    pages = []
    for p in cim["pages"]:
        areas = [
            {
                "left_mm": a["x_mm"],
                "top_mm": a["y_mm"],
                "width_mm": a["w_mm"],
                "height_mm": a["h_mm"],
                "flow_to_next_page": True,
                "block_id": body["id"],
            }
            for a in p["content_areas"]
        ]
        pages.append(
            {
                "id": f"{cim['form']['form_code']}_{p['name']}",
                "width_mm": p["medium"]["width_mm"],
                "height_mm": p["medium"]["height_mm"],
                "areas": areas,
            }
        )
    return pages


def write_plan(plan: dict, out: Path) -> None:
    out.write_text(json.dumps(plan, indent=2, sort_keys=False) + "\n", encoding="utf-8")

"""Inventory of a Quadient Inspire Layout export (the *.xml next to a WFD).

Observed grammar (two reference exports, Designer 17.0.436.3): the root <Layout> holds a flat
list of records. A record with <ParentId> is a declaration (type, Name, ParentId, IndexInParent,
Forward). A record without <ParentId> is the body of a declared object, keyed by <Id>. Group
declarations never have a body and Def.* roots never have a declaration.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

from gates.common import load_xml

ID_REF_TAGS = re.compile(r"(Id|Ref|Style|Font|Color|Parent|Variable|Page|Table|Flow)$")
STYLE_KINDS = ("TextStyle", "ParaStyle", "BorderStyle", "FillStyle", "Color", "Font", "FormStyleSkin")


def _text(el: ET.Element, tag: str) -> str:
    return (el.findtext(tag) or "").strip()


def inventory(path: Path) -> dict:
    root = load_xml(path)
    declarations: dict[str, dict] = {}
    bodies: dict[str, list] = defaultdict(list)
    for child in root:
        ident = _text(child, "Id")
        if child.find("ParentId") is None:
            bodies[child.tag].append(child)
            continue
        declarations[ident] = {
            "type": child.tag,
            "name": _text(child, "Name"),
            "parent": _text(child, "ParentId"),
            "index_in_parent": _text(child, "IndexInParent"),
            "forward": _text(child, "Forward"),
        }

    body_ids = {_text(b, "Id") for tag in bodies for b in bodies[tag]}
    declared_ids = set(declarations)

    dangling = []
    for tag, elements in bodies.items():
        for element in elements:
            for node in element.iter():
                if node is element or not ID_REF_TAGS.search(node.tag):
                    continue
                value = (node.text or "").strip()
                if value.isdigit() and value not in declared_ids:
                    dangling.append({"body": tag, "id": _text(element, "Id"), "ref_tag": node.tag, "value": value})

    def named(kind: str) -> list[str]:
        return sorted(d["name"] for d in declarations.values() if d["type"] == kind and d["name"])

    system_variables = {i for i, d in declarations.items() if d["parent"] == "Def.SystemVariables"}
    data_variables = sorted(
        d["name"]
        for i, d in declarations.items()
        if d["type"] == "Variable" and i not in system_variables and d["name"]
    )

    static_runs, inline_objects = [], []
    for flow in bodies.get("Flow", []):
        for content in flow.iter("FlowContent"):
            static_runs.extend((run.text or "").strip() for run in content.iter("T") if (run.text or "").strip())
            inline_objects.extend(ref.get("Id") for ref in content.iter("O") if ref.get("Id"))

    missing_body = sorted(i for i in declared_ids - body_ids if declarations[i]["type"] != "Group")
    undeclared_body = sorted(b for b in body_ids if b and b not in declared_ids and not b.startswith("Def."))
    orphans = sorted(
        i
        for i, d in declarations.items()
        if d["parent"] and not d["parent"].startswith("Def.") and d["parent"] not in declared_ids
    )

    return {
        "source_file": path.name,
        "root": root.tag,
        "counts": {
            "records_total": len(declarations) + sum(len(v) for v in bodies.values()),
            "declarations": len(declarations),
            "bodies": sum(len(v) for v in bodies.values()),
            "by_type": dict(Counter(d["type"] for d in declarations.values())),
            "system_variables": len(system_variables),
            "data_variables": len(data_variables),
            "static_text_runs": len(static_runs),
            "inline_object_placeholders": len(inline_objects),
        },
        "pages": named("Page"),
        "tables": named("Table"),
        "rowsets": named("RowSet"),
        "form_controls": named("FormControl"),
        "data_variables": data_variables,
        "styles": {kind: named(kind) for kind in STYLE_KINDS},
        "static_text": static_runs,
        "inline_object_ids": inline_objects,
        "integrity": {
            "orphan_declarations": orphans,
            "declarations_without_body": missing_body,
            "bodies_without_declaration": undeclared_body,
            "dangling_references": dangling[:200],
            "dangling_reference_count": len(dangling),
        },
    }

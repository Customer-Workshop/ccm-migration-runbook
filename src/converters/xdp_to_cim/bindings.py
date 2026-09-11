"""Binding normalisation and datatype derivation (BND-01, BND-03, FLD-03)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

KIND_TO_DATATYPE = {
    "text": "string",
    "multiline_text": "string",
    "checkbox": "boolean",
    "radio": "boolean",
    "dropdown": "string",
    "date": "date",
    "number": "decimal",
    "currency": "currency",
    "barcode": "barcode",
    "image": "image",
    "signature": "string",
    "action": "void",
    "computed": "string",
    "unknown": "string",
}

CURRENCY_PICTURE = re.compile(r"\$|zzz9\.99|num\{")
DATE_PICTURE = re.compile(r"date\{|YYYY|MM/DD")
PREFIXES = ("$record.", "$data.", "$.")


def empty_binding() -> dict:
    return {
        "mode": "none",
        "match": None,
        "source_path": None,
        "xsd_type": None,
        "target_variable_hint": None,
        "nullable": None,
    }


def normalise_ref(ref: str) -> str:
    """BND-01: strip XFA data-model prefixes and predicates into a dotted canonical path."""
    source = ref
    for prefix in PREFIXES:
        source = source.replace(prefix, "")
    source = source.replace("!", "").replace("[*]", "[]").lstrip(".")
    return re.sub(r"\s+", "", source)


def binding_of(bind: ET.Element | None) -> dict:
    if bind is None:
        return empty_binding()
    match = bind.get("match")
    ref = bind.get("ref")
    if match == "none" or (match is None and ref is None):
        mode = "none"
    elif match == "global":
        mode = "global"
    elif ref:
        mode = "dataRef"
    else:
        mode = "unresolved"
    source = normalise_ref(ref) if ref else None
    return {
        "mode": mode,
        "match": match,
        "source_path": source,
        "xsd_type": None,
        "target_variable_hint": source.split(".")[-1] if source else None,
        "nullable": None,
    }


def datatype_for(kind: str, fmt: dict, binding: dict) -> str:
    """FLD-03: control kind gives the base type; pictures and the embedded XSD refine it."""
    base = KIND_TO_DATATYPE.get(kind, "string")
    picture = (fmt.get("display_picture") or "") + (fmt.get("data_picture") or "")
    if base in ("decimal", "string") and CURRENCY_PICTURE.search(picture):
        return "currency"
    if base == "string" and DATE_PICTURE.search(picture):
        return "date"
    xsd = (binding.get("xsd_type") or "").lower()
    if "boolean" in xsd:
        return "boolean"
    if "date" in xsd:
        return "date"
    if any(t in xsd for t in ("double", "decimal", "float")):
        return "decimal"
    if any(t in xsd for t in ("int", "long", "short")):
        return "integer"
    return base


def leaf_types(dictionary: dict) -> dict[str, set[str | None]]:
    """Leaf element name -> set of XSD types declared for it across all complexTypes."""
    out: dict[str, set[str | None]] = {}
    for entry in dictionary["types"]:
        for element in entry["elements"]:
            if element["name"]:
                out.setdefault(element["name"], set()).add(element["type"])
    return out

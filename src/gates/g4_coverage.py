"""G4: source-to-target coverage against an accepted reference Layout export.

Reports evidence (matched objects, sections, static text) and never asserts semantic
correctness. Field matching below the floor is a major finding: it usually means the
target grammar or naming convention has not been captured in the rulebook yet.
"""

from __future__ import annotations

from gates.common import GateResult
from gates.matching import best_match, norm, tokens

FIELD_MATCH_MIN = 0.70
SECTION_ROLES = ("section", "header", "footer", "signature")


def run(cim: dict, inv: dict) -> GateResult:
    result = GateResult(gate="G4", verdict="pass")
    controls = {norm(n): n for n in inv["form_controls"]}
    radio_variables = {norm(n)[: -len(" radio")]: n for n in inv["data_variables"] if norm(n).endswith(" radio")}
    value_variables = {norm(n): n for n in inv["data_variables"] if not norm(n).endswith(" radio")}
    containers = {norm(n): n for n in inv["tables"] + inv["rowsets"]}

    field_rows = [
        _match_field(f, controls, radio_variables, value_variables)
        for f in cim["fields"]
        if f["control"]["kind"] != "action"
    ]
    section_rows = [_match_section(c, containers) for c in cim["containers"] if c["role"] in SECTION_ROLES]

    source_tokens = tokens(s["text"] for s in cim["statics"]) | tokens(f["caption"] for f in cim["fields"])
    target_tokens = tokens(inv["static_text"])
    matched = [r for r in field_rows if r["matched_target"]]
    field_pct = len(matched) / len(field_rows) if field_rows else 0.0

    result.metrics = {
        "target_file": inv["source_file"],
        "cim_fields_in_scope": len(field_rows),
        "target_form_controls": len(inv["form_controls"]),
        "target_data_variables": len(inv["data_variables"]),
        "field_match_pct": round(field_pct, 4),
        "exact_name_pct": round(sum(1 for r in matched if r["exact"]) / len(field_rows), 4) if field_rows else 0.0,
        "sections_matched": sum(1 for r in section_rows if r["matched_target"]),
        "sections_total": len(section_rows),
        "static_text_coverage": round(len(target_tokens & source_tokens) / len(target_tokens), 4)
        if target_tokens
        else 0.0,
        "target_only_tokens": sorted(target_tokens - source_tokens)[:50],
        "unmatched_target_controls": sorted(set(inv["form_controls"]) - {r["matched_target"] for r in matched})[:50],
        "fields": field_rows,
        "sections": section_rows,
    }
    if field_pct < FIELD_MATCH_MIN:
        result.add(
            "G4-FIELD-COVERAGE",
            "major",
            f"{field_pct:.1%} of source fields match a target object (< {FIELD_MATCH_MIN:.0%})",
            rule_id="BND-05",
        )
    for row in field_rows:
        if not row["matched_target"]:
            result.add(
                "G4-UNMATCHED", "minor", "no target object found for source field", node=row["som"], rule_id="BND-05"
            )
    if inv["integrity"]["dangling_reference_count"]:
        result.add(
            "G4-DANGLING",
            "major",
            f"{inv['integrity']['dangling_reference_count']} dangling id references in target",
            rule_id="GOV-02",
        )
    return result.finalize()


def _match_field(field: dict, controls: dict, radio_variables: dict, value_variables: dict) -> dict:
    keys = [field["semantic"]["target_name_hint"], field["caption"], field["name"], field["binding"]["source_path"]]
    kind = field["control"]["kind"]
    indexes = (
        (("form_control", controls), ("variable", radio_variables))
        if kind in ("checkbox", "radio")
        else (("form_control", controls), ("variable", value_variables))
    )
    best = (None, 0.0, None, None)
    for key in keys:
        for label, index in indexes:
            candidate, score = best_match(norm(key), list(index))
            if candidate and score > best[1]:
                best = (index[candidate], score, label, candidate)
    if kind in ("checkbox", "radio") and best[0] is None:
        for key in keys:
            candidate, score = best_match(norm(key), list(value_variables))
            if candidate and score > best[1]:
                best = (value_variables[candidate], score, "variable", candidate)
    return {
        "som": field["som"],
        "kind": kind,
        "binding_mode": field["binding"]["mode"],
        "proposed_name": field["semantic"]["target_name_hint"],
        "matched_target": best[0],
        "matched_kind": best[2],
        "score": best[1],
        "exact": bool(best[0] and norm(field["semantic"]["target_name_hint"]) == best[3]),
    }


def _match_section(container: dict, index: dict) -> dict:
    candidate, score = best_match(norm(container["target_name_hint"] or container["name"]), list(index))
    return {
        "som": container["som"],
        "role": container["role"],
        "heading": container["section_heading"],
        "proposed_name": container["target_name_hint"],
        "matched_target": index[candidate] if candidate else None,
        "score": score,
    }

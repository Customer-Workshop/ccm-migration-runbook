"""G4: source-to-target coverage against an accepted reference Layout export.

Reports evidence (matched objects, sections, static text) and never asserts semantic
correctness. Field matching below the floor is a major finding: it usually means the
target grammar or naming convention has not been captured in the rulebook yet.
Proposed crosswalk rows are reported but do not count toward field coverage until verified.
"""

from __future__ import annotations

from dictionary import CrosswalkRow
from gates.common import GateResult
from gates.matching import best_match, norm, static_text_coverage

FIELD_MATCH_MIN = 0.70
SECTION_ROLES = ("section", "header", "footer", "signature")
PENDING_STATUSES = ("auto", "proposed")
BOOLEAN_KINDS = ("checkbox", "radio")


def run(cim: dict, inv: dict, crosswalk: dict[tuple[str, str], CrosswalkRow] | None = None) -> GateResult:
    crosswalk = {} if crosswalk is None else crosswalk
    result = GateResult(gate="G4", verdict="pass")
    controls = {norm(n): n for n in inv["form_controls"]}
    radio_variables = {norm(n)[: -len(" radio")]: n for n in inv["data_variables"] if norm(n).endswith(" radio")}
    value_variables = {norm(n): n for n in inv["data_variables"] if not norm(n).endswith(" radio")}
    containers = {norm(n): n for n in inv["tables"] + inv["rowsets"]}
    form_code = cim["form"]["form_code"]

    field_rows = [
        _match_field(
            f,
            controls,
            radio_variables,
            value_variables,
            crosswalk.get((form_code, f["som"])),
            inv,
        )
        for f in cim["fields"]
        if f["control"]["kind"] != "action"
    ]
    section_rows = [_match_section(c, containers) for c in cim["containers"] if c["role"] in SECTION_ROLES]

    text_coverage, target_only = static_text_coverage(cim, inv)
    matched = [r for r in field_rows if r["matched_target"]]
    field_pct = len(matched) / len(field_rows) if field_rows else 0.0
    pending = [r for r in field_rows if r["crosswalk_status"] in PENDING_STATUSES]
    projected_matches = len(matched) + sum(
        1 for r in pending if not r["matched_target"] and not r["crosswalk_target_missing"]
    )

    result.metrics = {
        "target_file": inv["source_file"],
        "cim_fields_in_scope": len(field_rows),
        "target_form_controls": len(inv["form_controls"]),
        "target_data_variables": len(inv["data_variables"]),
        "field_match_pct": round(field_pct, 4),
        "crosswalk_rows_pending": len(pending),
        "field_match_pct_if_proposed_verified": round(projected_matches / len(field_rows), 4) if field_rows else 0.0,
        "exact_name_pct": round(sum(1 for r in matched if r["exact"]) / len(field_rows), 4) if field_rows else 0.0,
        "sections_matched": sum(1 for r in section_rows if r["matched_target"]),
        "sections_total": len(section_rows),
        "static_text_coverage": text_coverage,
        "target_only_tokens": target_only,
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
        if row["crosswalk_target_missing"]:
            result.add(
                "G4-CROSSWALK-MISSING",
                "major",
                f"crosswalk row names {row['crosswalk_target']}, which is not in the target export",
                node=row["som"],
                rule_id="BND-05",
            )
            continue
        if not row["matched_target"]:
            if row["crosswalk_status"] in PENDING_STATUSES:
                result.add(
                    "G4-CROSSWALK-PROPOSED",
                    "minor",
                    f"target named by proposed crosswalk row <{row['crosswalk_target']}>; "
                    "counts toward field match once verified",
                    node=row["som"],
                    rule_id="BND-05",
                )
            else:
                result.add(
                    "G4-UNMATCHED",
                    "minor",
                    "no target object found for source field",
                    node=row["som"],
                    rule_id="BND-05",
                )
    if inv["integrity"]["dangling_reference_count"]:
        result.add(
            "G4-DANGLING",
            "major",
            f"{inv['integrity']['dangling_reference_count']} dangling id references in target",
            rule_id="GOV-02",
        )
    return result.finalize()


def _match_field(
    field: dict,
    controls: dict,
    radio_variables: dict,
    value_variables: dict,
    row: CrosswalkRow | None,
    inv: dict,
) -> dict:
    keys = [field["semantic"]["target_name_hint"], field["caption"], field["name"], field["binding"]["source_path"]]
    kind = field["control"]["kind"]
    boolean = kind in BOOLEAN_KINDS
    # BND-09: boolean controls match *Radio variables first and fall back to value variables;
    # value controls never match a *Radio variable.
    indexes = [("form_control", controls), ("variable", radio_variables if boolean else value_variables)]
    best = _best_over(keys, indexes)
    if boolean and best[0] is None:
        best = _best_over(keys, [("variable", value_variables)])
    target_present = row is not None and (
        row.target_variable in inv["form_controls"] or row.target_variable in inv["data_variables"]
    )
    crosswalk_status = row.status if row is not None else None
    crosswalk_target = row.target_variable if row is not None else None
    crosswalk_target_missing = row is not None and row.status != "rejected" and not target_present
    exact = bool(best[0] and norm(field["semantic"]["target_name_hint"]) == best[3])
    if row is not None and row.status == "verified" and target_present:
        best = (row.target_variable, 1.0, "crosswalk:verified", norm(row.target_variable))
        exact = True
    return {
        "som": field["som"],
        "kind": kind,
        "binding_mode": field["binding"]["mode"],
        "proposed_name": field["semantic"]["target_name_hint"],
        "matched_target": best[0],
        "matched_kind": best[2],
        "score": best[1],
        "exact": exact,
        "crosswalk_status": crosswalk_status,
        "crosswalk_target": crosswalk_target,
        "crosswalk_target_missing": crosswalk_target_missing,
    }


def _best_over(keys: list[str | None], indexes: list[tuple[str, dict]]) -> tuple:
    best: tuple = (None, 0.0, None, None)
    for key in keys:
        for label, index in indexes:
            candidate, score = best_match(norm(key), list(index))
            if candidate and score > best[1]:
                best = (index[candidate], score, label, candidate)
    return best


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

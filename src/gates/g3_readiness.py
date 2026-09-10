"""G3: migration readiness. Semantic findings that need a human before the form can be built,
plus the GOV-06 check that every rule the form depends on has a named verifier and the GOV-07
reconciliation of findings against the form's decision record.
"""

from __future__ import annotations

from collections.abc import Iterator

from decisions import Decision, DecisionRecord
from gates.common import Finding, GateResult
from rulebook import Rule

ROUTABLE = ("blocker", "major")
STATUS_KEYS = ("proposed", "accepted", "rejected")


def run(cim: dict, rules: dict[str, Rule], record: DecisionRecord | None = None) -> GateResult:
    result = GateResult(gate="G3", verdict="pass")
    fields = [f for f in cim["fields"] if f["control"]["kind"] != "action"]

    for field in fields:
        binding = field["binding"]
        if binding["mode"] == "dataRef" and not binding["source_path"]:
            result.add(
                "G3-UNRESOLVED-BIND",
                "major",
                "bound field has no resolvable data path",
                node=field["som"],
                rule_id="BND-01",
            )
        if binding["mode"] == "none":
            result.add(
                "G3-UNBOUND",
                "major",
                "unbound field: target data path needs a data steward",
                node=field["som"],
                rule_id="BND-04",
            )
        if not field["semantic"]["target_name_hint"]:
            result.add(
                "G3-NONAME",
                "major",
                "no target-name evidence (no binding, caption or label)",
                node=field["som"],
                rule_id="BND-05",
            )
        if field["control"]["kind"] in ("choice", "radio") and not field["control"]["items"]:
            result.add("G3-NOITEMS", "major", "choice control without items", node=field["som"], rule_id="FLD-07")
        for script in field["scripts"]:
            if script["transferability"] == "interactive_only":
                result.add(
                    "G3-INTERACTIVE",
                    "minor",
                    f"{script['classification']} script belongs to the capture channel",
                    node=field["som"],
                    rule_id="VAL-07",
                )
        for validation in field["validations"]:
            if validation["transferability"] == "manual":
                result.add(
                    "G3-VALIDATION",
                    "major",
                    f"validation '{validation['kind']}' cannot be transferred mechanically",
                    node=field["som"],
                    rule_id="VAL-06",
                )

    for finding in cim["diagnostics"]["unsupported"]:
        result.add(
            finding["code"], finding["severity"], finding["message"], node=finding["node"], rule_id=finding["rule_id"]
        )

    duplicates: dict[str, list[str]] = {}
    for field in fields:
        if field["name"]:
            duplicates.setdefault(field["name"].lower(), []).append(field["som"])
    for leaf, soms in duplicates.items():
        if len(soms) > 1:
            result.add(
                "G3-DUPNAME",
                "minor",
                f"leaf name '{leaf}' occurs {len(soms)} times; disambiguate by section",
                node=";".join(soms[:6]),
                rule_id="FLD-04",
            )
    if not cim["form"]["revision_hint"]:
        result.add("G3-NOREVISION", "minor", "no revision marker: drift cannot be detected", rule_id="GOV-01")

    depended = sorted({r for r in _rule_ids(cim) if r in rules})
    draft = [r for r in depended if rules[r].status == "draft"]
    for rule_id in draft:
        result.add(
            "G3-DRAFT-RULE", "major", f"form depends on rule {rule_id} which has no named verifier", rule_id="GOV-06"
        )

    routing = _apply_decisions(result, record)

    touched = {f.node for f in result.findings if f.severity in ROUTABLE and f.node}
    bound = sum(1 for f in fields if f["binding"]["mode"] == "dataRef")
    scripts = [s for f in fields for s in f["scripts"]]
    result.metrics = {
        **routing,
        "fields_in_scope": len(fields),
        "bound_pct": _pct(bound, len(fields)),
        "name_evidence_pct": _pct(sum(1 for f in fields if f["semantic"]["target_name_hint"]), len(fields)),
        "scripts_total": len(scripts),
        "scripts_mechanically_transferable_pct": _pct(
            sum(1 for s in scripts if s["transferability"] in ("declarative", "rule_translatable")), len(scripts)
        ),
        "nodes_requiring_human_touch": len(touched),
        "rules_depended_on": depended,
        "draft_rules": draft,
    }
    return result.finalize()


def _apply_decisions(result: GateResult, record: DecisionRecord | None) -> dict:
    routable = [f for f in result.findings if f.severity in ROUTABLE and f.node]
    if record is None:
        if routable:
            result.add(
                "G3-NO-DECISIONS",
                "minor",
                f"{len(routable)} findings need routing and src/decisions/<form_id>.yaml is absent",
                rule_id="GOV-07",
            )
        return {
            "findings_routable": len(routable),
            "findings_unrouted": len(routable),
            "decisions_proposed": 0,
            "decisions_accepted": 0,
            "decisions_rejected": 0,
            "decision_session": None,
        }

    matched: set[tuple[str, str]] = set()
    unrouted = 0
    for finding in routable:
        decision = _lookup(record, finding)
        if decision is None:
            unrouted += 1
            continue
        matched.add((decision.node, decision.finding))
        if decision.status == "accepted":
            finding.severity = "info"
            finding.message += f" [accepted {decision.id} by {decision.decided_by}: {decision.action}]"
        elif decision.status == "rejected":
            finding.message += f" [rejected {decision.id} by {decision.decided_by}; needs a new proposal]"
        else:
            finding.message += f" [proposed {decision.id}: {decision.action}; awaiting reviewer]"

    for key, decision in record.decisions.items():
        if key not in matched:
            result.findings.append(
                Finding(
                    "G3-STALE-DECISION",
                    "minor",
                    f"decision {decision.id} refers to {key[1]} on a node the extractor no longer reports",
                    node=key[0],
                    rule_id="GOV-07",
                )
            )
    by_status = {s: sum(1 for d in record.decisions.values() if d.status == s) for s in STATUS_KEYS}
    return {
        "findings_routable": len(routable),
        "findings_unrouted": unrouted,
        "decisions_proposed": by_status["proposed"],
        "decisions_accepted": by_status["accepted"],
        "decisions_rejected": by_status["rejected"],
        "decision_session": record.session,
    }


def _lookup(record: DecisionRecord, finding: Finding) -> Decision | None:
    for node in (finding.node or "").split(";"):
        decision = record.decisions.get((node, finding.code))
        if decision is not None:
            return decision
    return None


def _rule_ids(cim: dict) -> Iterator[str | None]:
    for node in cim["containers"] + cim["fields"] + cim["statics"]:
        yield node["provenance"]["rule_id"]
    for finding in cim["diagnostics"]["unsupported"] + cim["diagnostics"]["review_queue"]:
        yield finding["rule_id"]


def _pct(part: int, whole: int) -> float | None:
    return round(100.0 * part / whole, 1) if whole else None

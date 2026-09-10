from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from decisions import DecisionError, load_for, load_record
from gates import g3_readiness
from rulebook import load_rules
from tests.test_gates import _verified
from tools import corpus

DATA = Path(__file__).resolve().parent / "data"
UNBOUND_NODE = ".EFormData.MainSubform.Information.Notes"

BASE = {
    "id": "D-001",
    "node": UNBOUND_NODE,
    "finding": "G3-UNBOUND",
    "action": "bind_to_element",
    "proposal": "element notes_free_text -> EFormsData.Notes",
    "rationale": "caption 'Notes' and free-text control",
    "status": "proposed",
    "decided_by": None,
    "decided_on": None,
}


def _write(tmp_path: Path, *decisions: dict, form_id: str = "99-0001", session: str = "https://x/sessions/1") -> Path:
    path = tmp_path / f"{form_id}.yaml"
    doc = {"decisions_version": 1, "form_id": form_id, "session": session, "decisions": list(decisions)}
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return path


def test_load_for_returns_none_when_no_record(tmp_path: Path) -> None:
    assert load_for("99-0001", tmp_path) is None


def test_load_record_keys_decisions_by_node_and_finding(tmp_path: Path) -> None:
    record = load_record(_write(tmp_path, BASE), "99-0001")
    assert record.session == "https://x/sessions/1"
    assert list(record.decisions) == [(UNBOUND_NODE, "G3-UNBOUND")]


@pytest.mark.parametrize(
    "mutation, message",
    [
        ({"status": "accepted"}, "need decided_by and decided_on"),
        ({"decided_by": "reviewer"}, "must not carry decided_by"),
        ({"action": "wing_it"}, "action must be one of"),
        ({"status": "done", "decided_by": "r", "decided_on": "2026-09-10"}, "status must be one of"),
        ({"node": ""}, "node and finding are required"),
    ],
)
def test_load_record_rejects_inconsistent_decisions(tmp_path: Path, mutation: dict, message: str) -> None:
    with pytest.raises(DecisionError, match=message):
        load_record(_write(tmp_path, {**BASE, **mutation}), "99-0001")


def test_load_record_rejects_duplicate_and_mismatched_records(tmp_path: Path) -> None:
    with pytest.raises(DecisionError, match="duplicate id"):
        load_record(_write(tmp_path, BASE, BASE), "99-0001")
    with pytest.raises(DecisionError, match="does not match"):
        load_record(_write(tmp_path, BASE), "99-0002")
    with pytest.raises(DecisionError, match="session must be"):
        load_record(_write(tmp_path, BASE, session="devin"), "99-0001")


def test_g3_without_record_counts_every_routable_finding_as_unrouted(synthetic_cim: dict) -> None:
    result = g3_readiness.run(synthetic_cim, _verified(load_rules()))
    assert result.metrics["findings_routable"] == result.metrics["findings_unrouted"] == 2
    assert "G3-NO-DECISIONS" in [f.code for f in result.findings]


def test_g3_proposed_decision_is_visible_but_still_needs_a_human(synthetic_cim: dict, tmp_path: Path) -> None:
    record = load_record(_write(tmp_path, BASE), "99-0001")
    result = g3_readiness.run(synthetic_cim, _verified(load_rules()), record)
    unbound = next(f for f in result.findings if f.code == "G3-UNBOUND")
    assert unbound.severity == "major"
    assert "proposed D-001" in unbound.message
    assert result.metrics["findings_unrouted"] == 1
    assert result.metrics["decisions_proposed"] == 1
    assert result.metrics["nodes_requiring_human_touch"] == 2


def test_g3_accepted_decision_removes_the_node_from_human_touch(synthetic_cim: dict, tmp_path: Path) -> None:
    accepted = {**BASE, "status": "accepted", "decided_by": "Q. Designer", "decided_on": "2026-09-10"}
    record = load_record(_write(tmp_path, accepted), "99-0001")
    result = g3_readiness.run(synthetic_cim, _verified(load_rules()), record)
    unbound = next(f for f in result.findings if f.code == "G3-UNBOUND")
    assert unbound.severity == "info"
    assert result.metrics["nodes_requiring_human_touch"] == 1
    assert result.metrics["decision_session"] == "https://x/sessions/1"


def test_g3_flags_decisions_for_nodes_the_extractor_no_longer_reports(synthetic_cim: dict, tmp_path: Path) -> None:
    stale = {**BASE, "id": "D-002", "node": ".EFormData.Gone"}
    record = load_record(_write(tmp_path, BASE, stale), "99-0001")
    result = g3_readiness.run(synthetic_cim, _verified(load_rules()), record)
    stale_findings = [f for f in result.findings if f.code == "G3-STALE-DECISION"]
    assert [f.node for f in stale_findings] == [".EFormData.Gone"]


def test_g3_verified_rules_and_accepted_decisions_do_not_alone_make_the_form_pass(
    synthetic_cim: dict, tmp_path: Path
) -> None:
    accepted = {**BASE, "status": "accepted", "decided_by": "Q. Designer", "decided_on": "2026-09-10"}
    record = load_record(_write(tmp_path, accepted), "99-0001")
    result = g3_readiness.run(synthetic_cim, _verified(load_rules()), record)
    assert result.verdict == "fail"
    assert result.metrics["findings_unrouted"] == 1


def test_corpus_tiers_and_orders_forms(tmp_path: Path) -> None:
    report = corpus.assess(DATA, load_rules())
    assert [p["form_code"] for p in report["forms"]] == ["99-0001"]
    assert report["forms"][0]["tier"] == "simple"
    assert report["suggested_order"] == ["99-0001"]
    assert corpus.tier_for({"fields": 10, "scripts": 0, "unsupported": 0, "pages": 4}) == "complex"
    assert corpus.tier_for({"fields": 60, "scripts": 0, "unsupported": 0, "pages": 1}) == "medium"


def test_corpus_refuses_an_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        corpus.assess(tmp_path, load_rules())

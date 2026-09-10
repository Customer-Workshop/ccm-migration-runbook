from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from gates import g0_pairing, g1_shape, g2_completeness, g3_readiness, g4_coverage, g5_target, g6_pdf
from gates.common import sha256_of
from gates.target_inventory import inventory
from rulebook import Rule, load_rules
from tests.conftest import SYNTHETIC_XDP, SYNTHETIC_XML


def _pair(raw: Path, with_target: bool) -> dict:
    pair = {
        "form_id": "99-0001",
        "status": "reference_pair" if with_target else "source_only",
        "source": {"file": "990001.xdp", "sha256": sha256_of(raw / "990001.xdp")},
        "target": None,
    }
    if with_target:
        pair["target"] = {
            "layout_xml": {"file": "99-0001.xml", "sha256": sha256_of(raw / "99-0001.xml")},
            "composed_pdf": {"file": "99-0001.pdf", "sha256": sha256_of(raw / "99-0001.pdf")},
        }
    return pair


@pytest.fixture
def raw(tmp_path: Path) -> Path:
    shutil.copy(SYNTHETIC_XDP, tmp_path / "990001.xdp")
    shutil.copy(SYNTHETIC_XML, tmp_path / "99-0001.xml")
    (tmp_path / "99-0001.pdf").write_bytes(
        b"%PDF-1.7\n1 0 obj << /Type /Page >> endobj\n/Creator (Quadient~Inspire)\n%%EOF\n"
    )
    return tmp_path


# G0


def test_g0_passes_when_pair_hashes_match_and_static_text_is_covered(raw: Path, synthetic_cim: dict) -> None:
    result = g0_pairing.run(_pair(raw, True), raw, synthetic_cim)
    assert result.verdict == "pass"
    assert result.metrics["static_text_coverage"] == 1.0


def test_g0_hash_mismatch_is_a_blocker(raw: Path, synthetic_cim: dict) -> None:
    pair = _pair(raw, True)
    pair["source"]["sha256"] = "0" * 64
    result = g0_pairing.run(pair, raw, synthetic_cim)
    assert result.verdict == "fail"
    assert [f.code for f in result.findings] == ["G0-HASH"]


def test_g0_missing_target_file_is_a_blocker_and_skips_coverage(raw: Path, synthetic_cim: dict) -> None:
    pair = _pair(raw, True)
    (raw / "99-0001.xml").unlink()
    result = g0_pairing.run(pair, raw, synthetic_cim)
    assert result.verdict == "fail"
    assert [f.code for f in result.findings] == ["G0-MISSING"]
    assert "static_text_coverage" not in result.metrics


def test_g0_source_only_form_passes_with_info(raw: Path, synthetic_cim: dict) -> None:
    result = g0_pairing.run(_pair(raw, False), raw, synthetic_cim)
    assert result.verdict == "pass"
    assert result.metrics["paired"] is False


def test_g0_flags_revision_drift_when_target_text_is_not_in_source(raw: Path, synthetic_cim: dict) -> None:
    synthetic_cim["statics"] = []
    for field in synthetic_cim["fields"]:
        field["caption"] = None
    result = g0_pairing.run(_pair(raw, True), raw, synthetic_cim)
    assert result.verdict == "fail"
    assert "G0-REVISION-DRIFT" in [f.code for f in result.findings]


# G1


def test_g1_passes_for_extracted_cim(synthetic_cim: dict) -> None:
    assert g1_shape.run(synthetic_cim).verdict == "pass"


def test_g1_rejects_schema_violation(synthetic_cim: dict) -> None:
    synthetic_cim["cim_version"] = "0.9"
    result = g1_shape.run(synthetic_cim)
    assert result.verdict == "fail"
    assert "G1-SCHEMA" in [f.code for f in result.findings]


def test_g1_rejects_field_pointing_at_unknown_container(synthetic_cim: dict) -> None:
    synthetic_cim["fields"][0]["container_id"] = "CT9999"
    result = g1_shape.run(synthetic_cim)
    assert result.verdict == "fail"
    assert [(f.code, f.node) for f in result.findings] == [("G1-NODEORPHAN", synthetic_cim["fields"][0]["som"])]


def test_g1_rejects_duplicate_ids(synthetic_cim: dict) -> None:
    synthetic_cim["fields"][1]["id"] = synthetic_cim["fields"][0]["id"]
    assert g1_shape.run(synthetic_cim).verdict == "fail"


# G2


def test_g2_passes_when_census_matches(synthetic_cim: dict) -> None:
    assert g2_completeness.run(synthetic_cim).verdict == "pass"


def test_g2_detects_dropped_field(synthetic_cim: dict) -> None:
    synthetic_cim["fields"].pop()
    result = g2_completeness.run(synthetic_cim)
    assert result.verdict == "fail"
    assert [f.code for f in result.findings] == ["G2-LOSSLESS"]


def test_g2_detects_dropped_master_page_static(synthetic_cim: dict) -> None:
    synthetic_cim["statics"] = [s for s in synthetic_cim["statics"] if s["text"] != "99-0001 (0126)"]
    assert g2_completeness.run(synthetic_cim).verdict == "fail"


def test_g2_requires_page_geometry(synthetic_cim: dict) -> None:
    synthetic_cim["pages"] = []
    assert "G2-NOPAGE" in [f.code for f in g2_completeness.run(synthetic_cim).findings]


# G3


def _verified(rules: dict[str, Rule]) -> dict[str, Rule]:
    out = {}
    for rid, rule in rules.items():
        clone = copy.copy(rule)
        clone.status = "verified"
        out[rid] = clone
    return out


def _clean(cim: dict) -> dict:
    cim["fields"] = [f for f in cim["fields"] if f["binding"]["mode"] == "dataRef" and not f["scripts"]]
    cim["diagnostics"]["unsupported"] = []
    return cim


def test_g3_fails_on_draft_rules_even_when_bindings_resolve(synthetic_cim: dict) -> None:
    result = g3_readiness.run(_clean(synthetic_cim), load_rules())
    assert result.verdict == "fail"
    assert {f.code for f in result.findings} == {"G3-DRAFT-RULE"}
    assert result.metrics["draft_rules"] == result.metrics["rules_depended_on"]


def test_g3_passes_when_rules_verified_and_no_human_items(synthetic_cim: dict) -> None:
    result = g3_readiness.run(_clean(synthetic_cim), _verified(load_rules()))
    assert result.verdict == "pass"
    assert result.metrics["draft_rules"] == []


def test_g3_reports_unbound_field_and_manual_script(synthetic_cim: dict) -> None:
    result = g3_readiness.run(synthetic_cim, _verified(load_rules()))
    codes = [f.code for f in result.findings]
    assert result.verdict == "fail"
    assert "G3-UNBOUND" in codes
    assert "VAL-SCRIPT-MANUAL" in codes
    assert result.metrics["nodes_requiring_human_touch"] == 2


def test_g3_unresolved_binding_is_major(synthetic_cim: dict) -> None:
    synthetic_cim["fields"][0]["binding"]["source_path"] = None
    result = g3_readiness.run(synthetic_cim, _verified(load_rules()))
    assert "G3-UNRESOLVED-BIND" in [f.code for f in result.findings]


# G4


def test_g4_matches_fields_and_sections_against_target(synthetic_cim: dict, synthetic_inventory: dict) -> None:
    result = g4_coverage.run(synthetic_cim, synthetic_inventory)
    m = result.metrics
    assert m["sections_matched"] == 1
    assert m["static_text_coverage"] == 1.0
    unmatched = [r["som"] for r in m["fields"] if not r["matched_target"]]
    assert unmatched == [".EFormData.MainSubform.Information.Notes"]


def test_g4_fails_below_field_floor(synthetic_cim: dict, synthetic_inventory: dict) -> None:
    result = g4_coverage.run(synthetic_cim, synthetic_inventory)
    assert result.verdict == "fail"
    assert "G4-FIELD-COVERAGE" in [f.code for f in result.findings]


def test_g4_passes_when_every_field_has_a_target(synthetic_cim: dict, synthetic_inventory: dict) -> None:
    synthetic_cim["fields"] = [f for f in synthetic_cim["fields"] if f["name"] != "Notes"]
    result = g4_coverage.run(synthetic_cim, synthetic_inventory)
    assert result.verdict == "pass"
    assert result.metrics["field_match_pct"] == 1.0


def test_g4_dangling_target_reference_is_major(synthetic_cim: dict, synthetic_inventory: dict) -> None:
    inv = copy.deepcopy(synthetic_inventory)
    inv["integrity"]["dangling_reference_count"] = 3
    assert "G4-DANGLING" in [f.code for f in g4_coverage.run(synthetic_cim, inv).findings]


# target inventory


def test_inventory_separates_declarations_from_bodies(synthetic_inventory: dict) -> None:
    counts = synthetic_inventory["counts"]
    assert counts["declarations"] == 9
    assert counts["bodies"] == 8
    assert synthetic_inventory["data_variables"] == ["AviationInd", "State"]
    assert synthetic_inventory["integrity"]["dangling_reference_count"] == 0


def test_inventory_reports_dangling_reference(tmp_path: Path) -> None:
    text = SYNTHETIC_XML.read_text(encoding="utf-8")
    broken = text.replace("<VariableId>11</VariableId>", "<VariableId>999</VariableId>")
    path = tmp_path / "broken.xml"
    path.write_text(broken, encoding="utf-8")
    integrity = inventory(path)["integrity"]
    assert integrity["dangling_reference_count"] == 1
    assert integrity["dangling_references"][0]["value"] == "999"


# G5


def test_g5_is_external_without_import_log(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(g5_target, "IMPORT_LOG_DIR", tmp_path)
    result = g5_target.run(SYNTHETIC_XML)
    assert result.verdict == "external"
    assert result.metrics["IMP-001"] == 0


def test_g5_fails_offline_on_missing_body(tmp_path: Path) -> None:
    text = SYNTHETIC_XML.read_text(encoding="utf-8")
    path = tmp_path / "nobody.xml"
    path.write_text(
        text.replace("<Table>\n    <Id>23</Id>\n    <Columns>1</Columns>\n  </Table>\n", ""), encoding="utf-8"
    )
    result = g5_target.run(path)
    assert result.verdict == "fail"
    assert [f.code for f in result.findings] == ["IMP-001"]


def test_g5_adopts_designer_verdict_from_import_log(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(g5_target, "IMPORT_LOG_DIR", tmp_path)
    record = {
        "verdict": "fail",
        "designer_version": "17.0",
        "imported_by": "qa",
        "imported_on": "2026-09-10",
        "errors": ["Unknown element Foo"],
    }
    (tmp_path / f"{sha256_of(SYNTHETIC_XML)}.json").write_text(json.dumps(record), encoding="utf-8")
    result = g5_target.run(SYNTHETIC_XML)
    assert result.verdict == "fail"
    assert [f.code for f in result.findings] == ["G5-DESIGNER"]


def test_g5_rejects_import_log_with_bad_verdict(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(g5_target, "IMPORT_LOG_DIR", tmp_path)
    (tmp_path / f"{sha256_of(SYNTHETIC_XML)}.json").write_text(json.dumps({"verdict": "maybe"}), encoding="utf-8")
    with pytest.raises(AssertionError):
        g5_target.run(SYNTHETIC_XML)


# G6


def test_g6_is_external_after_inspection(monkeypatch: pytest.MonkeyPatch, raw: Path, tmp_path: Path) -> None:
    monkeypatch.setattr(g6_pdf, "COMPOSITION_LOG_DIR", tmp_path / "logs")
    result = g6_pdf.run(raw / "99-0001.pdf")
    assert result.verdict == "external"
    assert result.metrics["reference_pdf"]["creator"] == "Quadient Inspire"
    assert result.metrics["reference_pdf"]["pages_estimated"] == 1


def test_g6_fails_on_pdf_without_pages(tmp_path: Path) -> None:
    pdf = tmp_path / "empty.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    result = g6_pdf.run(pdf)
    assert result.verdict == "fail"
    assert "G6-NOPAGES" in [f.code for f in result.findings]


def test_g6_rejects_non_pdf(tmp_path: Path) -> None:
    fake = tmp_path / "x.pdf"
    fake.write_bytes(b"hello")
    with pytest.raises(AssertionError):
        g6_pdf.run(fake)


def test_g6_adopts_composition_verdict(monkeypatch: pytest.MonkeyPatch, raw: Path, tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setattr(g6_pdf, "COMPOSITION_LOG_DIR", logs)
    pdf = raw / "99-0001.pdf"
    record = {
        "verdict": "pass",
        "composed_by": "qa",
        "composed_on": "2026-09-10",
        "input_data_sha256": "a" * 64,
        "differences": [],
    }
    (logs / f"{sha256_of(pdf)}.json").write_text(json.dumps(record), encoding="utf-8")
    result = g6_pdf.run(pdf)
    assert result.verdict == "pass"
    assert result.reason.startswith("composed by qa")

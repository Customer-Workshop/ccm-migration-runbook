from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from converters.cim_to_inspire.build_plan import BuildPlanError, build_plan, write_plan
from converters.xdp_to_cim.extractor import XdpExtractor
from converters.xpr_to_cim import XpressionFormatUnknown, extract
from dictionary import CrosswalkRow
from fixtures import load_pairs
from gates.common import sha256_of
from tests.conftest import SYNTHETIC_XDP, SYNTHETIC_XML
from tools import convert, pipeline

SOM_STATE = ".EFormData.MainSubform.Information.State"
SOM_NOTES = ".EFormData.MainSubform.Information.Notes"


def _by_resolution(plan: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for v in plan["variables"]:
        out.setdefault(v["resolution"], []).append(v["name"])
    return out


def test_build_plan_prefers_dictionary_then_binding_then_unresolved(synthetic_cim: dict) -> None:
    row = CrosswalkRow(
        form_code="99-0001",
        som=SOM_STATE,
        element="insured.address.state",
        target_variable="InsuredState",
        data_path="Insured.Address.State",
        status="proposed",
        evidence="test",
        reviewed_by=None,
    )
    plan = build_plan(synthetic_cim, {("99-0001", SOM_STATE): row})
    resolutions = _by_resolution(plan)
    assert resolutions["dictionary:proposed"] == ["InsuredState"]
    assert resolutions["binding"] == ["AviationInd"]
    assert resolutions["unresolved"] and resolutions["unresolved"][0].startswith("UNRESOLVED_")
    assert [d["node"] for d in plan["decisions_required"] if d["rule_id"] == "BND-04"] == [SOM_NOTES]


def test_build_plan_ignores_rejected_dictionary_rows(synthetic_cim: dict) -> None:
    row = CrosswalkRow(
        form_code="99-0001",
        som=SOM_STATE,
        element="insured.address.state",
        target_variable="Wrong",
        data_path="x",
        status="rejected",
        evidence="test",
        reviewed_by="qa",
    )
    plan = build_plan(synthetic_cim, {("99-0001", SOM_STATE): row})
    assert "Wrong" not in [v["name"] for v in plan["variables"]]
    assert "State" in _by_resolution(plan)["binding"]


def test_build_plan_never_claims_designer_import(synthetic_cim: dict) -> None:
    plan = build_plan(synthetic_cim, {})
    assert plan["designer_import"] == "not_run"
    assert plan["source_sha256"] == synthetic_cim["form"]["source_sha256"]


def test_build_plan_skips_controls_without_representation(synthetic_cim: dict) -> None:
    synthetic_cim["fields"][0]["control"]["kind"] = "signature"
    plan = build_plan(synthetic_cim, {})
    assert [(s["node"], s["rule_id"]) for s in plan["skipped"]] == [(synthetic_cim["fields"][0]["som"], "UNS-07")]
    assert synthetic_cim["fields"][0]["som"] not in [s for v in plan["variables"] for s in v["source_soms"]]


def test_build_plan_rejects_unknown_datatype(synthetic_cim: dict) -> None:
    synthetic_cim["fields"][0]["datatype"] = "blob"
    with pytest.raises(BuildPlanError, match="blob"):
        build_plan(synthetic_cim, {})


def test_build_plan_is_deterministic(synthetic_cim: dict, tmp_path: Path) -> None:
    write_plan(build_plan(synthetic_cim, {}), tmp_path / "a.json")
    write_plan(build_plan(synthetic_cim, {}), tmp_path / "b.json")
    assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()


def test_blocks_reference_only_planned_variables(synthetic_cim: dict) -> None:
    plan = build_plan(synthetic_cim, {})
    ids = {v["id"] for v in plan["variables"]}
    block_ids = {b["id"] for b in plan["blocks"]}
    referenced = [p["variable_id"] for b in plan["blocks"] for p in b["paragraphs"] if p["kind"] == "variable"]
    assert referenced and set(referenced) <= ids
    assert all(child in block_ids for b in plan["blocks"] for child in b["child_block_ids"])
    assert all(a["block_id"] in block_ids for p in plan["pages"] for a in p["areas"])


def test_xpression_extraction_fails_explicitly(tmp_path: Path) -> None:
    with pytest.raises(XpressionFormatUnknown, match="format is undefined"):
        extract(tmp_path / "anything.xpr")


# CLI + pipeline


def test_convert_cli_writes_cim_and_plan(tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert convert.main([str(SYNTHETIC_XDP), "-o", str(out)]) == 0
    cim = json.loads((out / "99-0001.cim.json").read_text(encoding="utf-8"))
    plan = json.loads((out / "99-0001.plan.json").read_text(encoding="utf-8"))
    assert cim["form"]["form_code"] == plan["form_code"] == "99-0001"


def test_convert_cli_raises_on_unparseable_input(tmp_path: Path) -> None:
    bad = tmp_path / "990002.xdp"
    bad.write_text("<xdp:xdp xmlns:xdp='http://ns.adobe.com/xdp/'><nothing/></xdp:xdp>", encoding="utf-8")
    with pytest.raises(ValueError, match="no XFA template"):
        convert.main([str(bad), "-o", str(tmp_path / "out")])


def _manifest(
    raw: Path, tmp_path: Path, *, with_target: bool, corrupt_hash: bool = False, layout_only: bool = False
) -> Path:
    source_sha = "0" * 64 if corrupt_hash else sha256_of(raw / "990001.xdp")
    form = {
        "form_id": "99-0001",
        "status": "reference_pair" if with_target else "source_only",
        "source": {"file": "990001.xdp", "sha256": source_sha},
        "target": None,
    }
    if with_target:
        form["target"] = {
            "layout_xml": {"file": "99-0001.xml", "sha256": sha256_of(raw / "99-0001.xml")},
            "composed_pdf": None if layout_only else {"file": "99-0001.pdf", "sha256": sha256_of(raw / "99-0001.pdf")},
        }
    path = tmp_path / "pairs.yaml"
    path.write_text(yaml.safe_dump({"manifest_version": 1, "forms": [form]}), encoding="utf-8")
    return path


@pytest.fixture
def raw(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    shutil.copy(SYNTHETIC_XDP, raw / "990001.xdp")
    shutil.copy(SYNTHETIC_XML, raw / "99-0001.xml")
    (raw / "99-0001.pdf").write_bytes(b"%PDF-1.7\n1 0 obj << /Type /Page >> endobj\n%%EOF\n")
    return raw


def _run(monkeypatch: pytest.MonkeyPatch, raw: Path, manifest: Path, out: Path, *argv: str) -> tuple[int, dict]:
    monkeypatch.setenv("CCM_FIXTURE_ROOT", str(raw))
    monkeypatch.setattr(pipeline, "load_pairs", lambda: load_pairs(manifest))
    code = pipeline.main(["-o", str(out), *argv])
    return code, json.loads((out / "readiness.json").read_text(encoding="utf-8"))


def _verdicts(report: dict) -> dict[str, str]:
    return {g["gate"]: g["verdict"] for g in report["forms"][0]["gates"]}


def test_pipeline_reference_pair_reports_all_gates(monkeypatch: pytest.MonkeyPatch, raw: Path, tmp_path: Path) -> None:
    code, report = _run(monkeypatch, raw, _manifest(raw, tmp_path, with_target=True), tmp_path / "out")
    assert code == 0
    assert _verdicts(report) == {
        "G0": "pass",
        "G1": "pass",
        "G2": "pass",
        "G3": "fail",
        "G4": "fail",
        "G5": "external",
        "G6": "external",
    }
    assert (tmp_path / "out" / "99-0001.plan.json").exists()
    assert (tmp_path / "out" / "readiness.md").exists()


def test_pipeline_source_only_skips_target_gates(monkeypatch: pytest.MonkeyPatch, raw: Path, tmp_path: Path) -> None:
    code, report = _run(monkeypatch, raw, _manifest(raw, tmp_path, with_target=False), tmp_path / "out")
    assert code == 0
    assert {k: v for k, v in _verdicts(report).items() if k in ("G4", "G5", "G6")} == {
        "G4": "skipped",
        "G5": "skipped",
        "G6": "skipped",
    }


def test_pipeline_layout_only_pair_skips_g6(monkeypatch: pytest.MonkeyPatch, raw: Path, tmp_path: Path) -> None:
    manifest = _manifest(raw, tmp_path, with_target=True, layout_only=True)
    code, report = _run(monkeypatch, raw, manifest, tmp_path / "out")

    assert code == 0
    assert {k: v for k, v in _verdicts(report).items() if k in ("G0", "G1", "G2", "G3", "G4", "G5")} == {
        "G0": "pass",
        "G1": "pass",
        "G2": "pass",
        "G3": "fail",
        "G4": "fail",
        "G5": "external",
    }
    assert report["forms"][0]["gates"][-1] == {
        "gate": "G6",
        "verdict": "skipped",
        "reason": "no composed PDF supplied for this form",
        "metrics": {},
        "findings": [],
    }


def test_pipeline_strict_exits_1_on_readiness_failure(
    monkeypatch: pytest.MonkeyPatch, raw: Path, tmp_path: Path
) -> None:
    code, _ = _run(monkeypatch, raw, _manifest(raw, tmp_path, with_target=True), tmp_path / "out", "--strict")
    assert code == 1


def test_pipeline_hash_mismatch_fails_g0_but_is_not_integrity(
    monkeypatch: pytest.MonkeyPatch, raw: Path, tmp_path: Path
) -> None:
    manifest = _manifest(raw, tmp_path, with_target=True, corrupt_hash=True)
    code, report = _run(monkeypatch, raw, manifest, tmp_path / "out")
    assert code == 0
    assert _verdicts(report)["G0"] == "fail"


def test_pipeline_missing_source_skips_every_gate(monkeypatch: pytest.MonkeyPatch, raw: Path, tmp_path: Path) -> None:
    manifest = _manifest(raw, tmp_path, with_target=False)
    (raw / "990001.xdp").unlink()
    code, report = _run(monkeypatch, raw, manifest, tmp_path / "out")
    assert code == 0
    assert set(_verdicts(report).values()) == {"skipped"}


def test_pipeline_output_is_deterministic(monkeypatch: pytest.MonkeyPatch, raw: Path, tmp_path: Path) -> None:
    manifest = _manifest(raw, tmp_path, with_target=True)
    _run(monkeypatch, raw, manifest, tmp_path / "a")
    _run(monkeypatch, raw, manifest, tmp_path / "b")
    for name in ("99-0001.cim.json", "99-0001.plan.json", "readiness.json", "readiness.md"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes(), name


# BND-10: same-named fields


def _clone_field(cim: dict, som: str, *, new_som: str, data_path: str | None) -> dict:
    twin = json.loads(json.dumps(next(f for f in cim["fields"] if f["som"] == som)))
    twin["id"] = f"FD9{len(cim['fields']):03d}"
    twin["som"] = new_som
    twin["binding"]["source_path"] = data_path
    cim["fields"].append(twin)
    return twin


def test_build_plan_shares_a_variable_for_same_name_and_same_data_path(synthetic_cim: dict) -> None:
    state = next(f for f in synthetic_cim["fields"] if f["som"] == SOM_STATE)
    _clone_field(synthetic_cim, SOM_STATE, new_som=SOM_STATE + "[1]", data_path=state["binding"]["source_path"])
    plan = build_plan(synthetic_cim, {})
    matching = [v for v in plan["variables"] if v["name"] == state["binding"]["target_variable_hint"]]
    assert len(matching) == 1
    assert matching[0]["source_soms"] == [SOM_STATE, SOM_STATE + "[1]"]
    assert "disambiguated_from" not in matching[0]
    assert not [d for d in plan["decisions_required"] if d["rule_id"] == "BND-10"]


def test_build_plan_suffixes_same_name_with_different_data_paths_and_routes_bnd10(synthetic_cim: dict) -> None:
    state = next(f for f in synthetic_cim["fields"] if f["som"] == SOM_STATE)
    name = state["binding"]["target_variable_hint"]
    _clone_field(synthetic_cim, SOM_STATE, new_som=SOM_STATE + "[1]", data_path="Row2.State")
    _clone_field(synthetic_cim, SOM_STATE, new_som=SOM_STATE + "[2]", data_path="Row3.State")
    _clone_field(synthetic_cim, SOM_STATE, new_som=SOM_STATE + "[3]", data_path="Row2.State")
    plan = build_plan(synthetic_cim, {})
    group = [v for v in plan["variables"] if v["name"] == name or v.get("disambiguated_from") == name]
    assert [v["name"] for v in group] == [name, f"{name}_R2", f"{name}_R3"]
    assert [v["id"] for v in group] == [f"99-0001_{name}", f"99-0001_{name}_R2", f"99-0001_{name}_R3"]
    assert [v.get("row_index") for v in group] == [None, 2, 3]
    assert group[1]["source_soms"] == [SOM_STATE + "[1]", SOM_STATE + "[3]"]
    assert group[2]["source_soms"] == [SOM_STATE + "[2]"]
    bnd10 = [d for d in plan["decisions_required"] if d["rule_id"] == "BND-10"]
    assert [d["node"] for d in bnd10] == [SOM_STATE + "[1]", SOM_STATE + "[2]"]
    assert all(d["owner"] == "data_steward" and f"'{name}_R" in d["decision"] for d in bnd10)
    var_ids = {v["id"] for v in plan["variables"]}
    referenced = [p["variable_id"] for b in plan["blocks"] for p in b["paragraphs"] if p["kind"] == "variable"]
    assert set(referenced) <= var_ids


def test_build_plan_requires_a_page_body_block(synthetic_cim: dict) -> None:
    for container in synthetic_cim["containers"]:
        if container["role"] == "page_body":
            container["role"] = "group"
    with pytest.raises(BuildPlanError, match="no page_body block"):
        build_plan(synthetic_cim, {})


def test_build_plan_maps_alignment_and_marks_checkbox_rendering(synthetic_cim: dict) -> None:
    synthetic_cim["styles"][0]["align"] = "justify"
    synthetic_cim["fields"][0]["control"]["kind"] = "checkbox"
    synthetic_cim["fields"][0]["datatype"] = "boolean"
    plan = build_plan(synthetic_cim, {})
    assert plan["paragraph_styles"][0]["alignment"] == "JustifyLeft"
    expected = [f["som"] for f in synthetic_cim["fields"] if f["control"]["kind"] in ("checkbox", "radio")]
    assert synthetic_cim["fields"][0]["som"] in expected
    assert [d["node"] for d in plan["decisions_required"] if d["rule_id"] == "OBJ-06"] == expected


# pipeline: integrity short-circuit


def test_pipeline_g1_failure_short_circuits_and_exits_2(
    monkeypatch: pytest.MonkeyPatch, raw: Path, tmp_path: Path
) -> None:
    real_build = XdpExtractor.build

    def broken_build(self: XdpExtractor) -> dict:
        cim = real_build(self)
        cim["fields"][0]["container_id"] = "CT9999"
        return cim

    monkeypatch.setattr(pipeline.XdpExtractor, "build", broken_build)
    code, report = _run(monkeypatch, raw, _manifest(raw, tmp_path, with_target=True), tmp_path / "out")
    assert code == 2
    verdicts = _verdicts(report)
    assert verdicts["G1"] == "fail"
    assert {verdicts[g] for g in ("G2", "G3", "G4", "G5", "G6")} == {"skipped"}
    assert all(
        g["reason"] == "G1 failed" for g in report["forms"][0]["gates"] if g["gate"] in ("G2", "G3", "G4", "G5", "G6")
    )
    assert not (tmp_path / "out" / "99-0001.plan.json").exists()


def test_pipeline_reports_missing_target_files_as_skipped(
    monkeypatch: pytest.MonkeyPatch, raw: Path, tmp_path: Path
) -> None:
    manifest = _manifest(raw, tmp_path, with_target=True)
    (raw / "99-0001.xml").unlink()
    (raw / "99-0001.pdf").unlink()
    code, report = _run(monkeypatch, raw, manifest, tmp_path / "out")
    assert code == 0
    verdicts = _verdicts(report)
    assert (verdicts["G4"], verdicts["G5"], verdicts["G6"]) == ("skipped", "skipped", "skipped")
    reasons = {g["gate"]: g["reason"] for g in report["forms"][0]["gates"]}
    assert reasons["G4"] == "99-0001.xml missing" and reasons["G6"] == "99-0001.pdf missing"


def test_pipeline_markdown_lists_every_gate_and_form(
    monkeypatch: pytest.MonkeyPatch, raw: Path, tmp_path: Path
) -> None:
    _run(monkeypatch, raw, _manifest(raw, tmp_path, with_target=True), tmp_path / "out")
    md = (tmp_path / "out" / "readiness.md").read_text(encoding="utf-8")
    assert "99-0001" in md
    assert all(gate in md for gate in ("G0", "G1", "G2", "G3", "G4", "G5", "G6"))

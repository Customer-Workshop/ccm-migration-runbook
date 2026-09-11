from __future__ import annotations

import importlib
from pathlib import Path

import pytest
import yaml

from dictionary import CrosswalkRow, load_crosswalk, load_elements
from fixtures import load_pairs
from gates.common import ArtifactError
from gates.import_lint import CHECKS, load_catalogue
from rulebook import lint, load_rules
from tools import report

GOOD_RULE = {
    "id": "OBJ-01",
    "title": "t",
    "class": "AUTO",
    "status": "draft",
    "source": "s",
    "target": "t",
    "evidence": "e",
    "origin": {"type": "analysis", "refs": ["x"]},
    "fixtures": [],
    "implemented_in": ["m.f"],
    "gates": ["G1"],
    "reviewed_by": None,
    "reviewed_on": None,
}


def _write_rules(tmp_path: Path, *rules: dict) -> Path:
    (tmp_path / "object.yaml").write_text(yaml.safe_dump({"family": "OBJ", "rules": list(rules)}), encoding="utf-8")
    return tmp_path


def test_repository_rulebook_lints_clean_against_manifest() -> None:
    known = {p["form_id"] for p in load_pairs()}
    assert lint(known_fixtures=known) == []


def _resolve(ref: str) -> object:
    parts = ref.split(".")
    for cut in range(1, len(parts) + 1):
        module_name = ".".join(parts[:cut])
        module = importlib.import_module(module_name)
        if hasattr(module, "__path__"):
            continue
        obj: object = module
        for attr in parts[cut:]:
            obj = getattr(obj, attr)
        return obj
    return importlib.import_module(ref)


def test_every_implemented_in_reference_resolves() -> None:
    for rule in load_rules().values():
        for ref in rule.implemented_in:
            _resolve(ref)


def test_lint_rejects_verified_rule_without_reviewer(tmp_path: Path) -> None:
    rules_dir = _write_rules(tmp_path, {**GOOD_RULE, "status": "verified"})
    assert any("reviewed_by" in p for p in lint(rules_dir))


def test_lint_rejects_draft_rule_carrying_reviewer(tmp_path: Path) -> None:
    rules_dir = _write_rules(tmp_path, {**GOOD_RULE, "reviewed_by": "someone"})
    assert any("draft rules must not carry reviewed_by" in p for p in lint(rules_dir))


def test_lint_rejects_auto_rule_without_implementation(tmp_path: Path) -> None:
    rules_dir = _write_rules(tmp_path, {**GOOD_RULE, "implemented_in": []})
    assert any("AUTO rule has no implemented_in" in p for p in lint(rules_dir))


def test_lint_rejects_duplicate_and_misfiled_ids(tmp_path: Path) -> None:
    rules_dir = _write_rules(tmp_path, GOOD_RULE, GOOD_RULE, {**GOOD_RULE, "id": "FLD-01"})
    problems = lint(rules_dir)
    assert any("duplicate id" in p for p in problems)
    assert any("id family does not match" in p for p in problems)


def test_lint_rejects_unknown_fixture_and_gate(tmp_path: Path) -> None:
    rules_dir = _write_rules(tmp_path, {**GOOD_RULE, "fixtures": ["00-0000"], "gates": ["G9"]})
    problems = lint(rules_dir, known_fixtures={"17-0574"})
    assert any("fixture 00-0000" in p for p in problems)
    assert any("unknown gate G9" in p for p in problems)


def test_lint_accepts_well_formed_rule(tmp_path: Path) -> None:
    assert lint(_write_rules(tmp_path, GOOD_RULE)) == []


# dictionary


def test_repository_dictionary_loads() -> None:
    rows = load_crosswalk()
    assert all(isinstance(r, CrosswalkRow) for r in rows.values())


def test_crosswalk_rejects_unknown_element(tmp_path: Path) -> None:
    path = tmp_path / "crosswalk.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "dictionary_version": 1,
                "rows": [
                    {
                        "form_code": "99-0001",
                        "som": ".a",
                        "element": "missing.element",
                        "target_variable": "X",
                        "data_path": "A.X",
                        "status": "proposed",
                        "evidence": "e",
                        "reviewed_by": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ArtifactError, match="unknown element"):
        load_crosswalk(path, elements={})


def test_crosswalk_verified_row_requires_reviewer(tmp_path: Path) -> None:
    path = tmp_path / "crosswalk.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "dictionary_version": 1,
                "rows": [
                    {
                        "form_code": "99-0001",
                        "som": ".a",
                        "element": "e1",
                        "target_variable": "X",
                        "data_path": "A.X",
                        "status": "verified",
                        "evidence": "e",
                        "reviewed_by": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ArtifactError, match="reviewed_by"):
        load_crosswalk(path, elements={"e1": {}})


def test_elements_reject_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "elements.yaml"
    row = {
        "id": "e1",
        "label": "l",
        "data_type": "string",
        "target_path": None,
        "status": "proposed",
        "evidence": "e",
        "reviewed_by": None,
    }
    path.write_text(yaml.safe_dump({"dictionary_version": 1, "elements": [row, row]}), encoding="utf-8")
    with pytest.raises(ArtifactError, match="duplicate element"):
        load_elements(path)


def test_dictionary_version_is_enforced(tmp_path: Path) -> None:
    path = tmp_path / "elements.yaml"
    path.write_text(yaml.safe_dump({"dictionary_version": 2, "elements": []}), encoding="utf-8")
    with pytest.raises(ArtifactError, match="dictionary_version"):
        load_elements(path)


# import-lint catalogue


def test_catalogue_entries_point_at_existing_checks() -> None:
    for entry in load_catalogue():
        assert entry["check"].rsplit(".", 1)[1] in CHECKS


def test_catalogue_rejects_unknown_check(tmp_path: Path) -> None:
    path = tmp_path / "catalogue.yaml"
    path.write_text(
        yaml.safe_dump(
            [
                {
                    "code": "IMP-999",
                    "status": "inferred",
                    "severity": "major",
                    "check": "gates.import_lint.nope",
                    "message": "m",
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ArtifactError, match="unknown check"):
        load_catalogue(path)


# pairs manifest


def test_pairs_manifest_rejects_status_target_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "pairs.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "manifest_version": 1,
                "forms": [
                    {
                        "form_id": "99-0001",
                        "status": "source_only",
                        "source": {"file": "990001.xdp", "sha256": "0" * 64},
                        "target": {
                            "layout_xml": {"file": "x", "sha256": "0" * 64},
                            "composed_pdf": {"file": "y", "sha256": "0" * 64},
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ArtifactError, match="status/target mismatch"):
        load_pairs(path)


def test_pairs_manifest_rejects_reference_pair_without_layout_xml(tmp_path: Path) -> None:
    path = tmp_path / "pairs.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "manifest_version": 1,
                "forms": [
                    {
                        "form_id": "99-0001",
                        "status": "reference_pair",
                        "source": {"file": "990001.xdp", "sha256": "0" * 64},
                        "target": {"layout_xml": None, "composed_pdf": None},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ArtifactError, match="99-0001: reference_pair needs layout_xml"):
        load_pairs(path)


def test_pairs_manifest_accepts_reference_pair_without_composed_pdf(tmp_path: Path) -> None:
    path = tmp_path / "pairs.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "manifest_version": 1,
                "forms": [
                    {
                        "form_id": "99-0001",
                        "status": "reference_pair",
                        "source": {"file": "990001.xdp", "sha256": "0" * 64},
                        "target": {"layout_xml": {"file": "x", "sha256": "0" * 64}, "composed_pdf": None},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assert load_pairs(path)[0]["target"]["composed_pdf"] is None


def test_pairs_manifest_rejects_source_file_not_carrying_form_number(tmp_path: Path) -> None:
    path = tmp_path / "pairs.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "manifest_version": 1,
                "forms": [
                    {
                        "form_id": "99-0001",
                        "status": "source_only",
                        "source": {"file": "other.xdp", "sha256": "0" * 64},
                        "target": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ArtifactError, match="form number"):
        load_pairs(path)


def test_report_renders_every_rule_once() -> None:
    rules = load_rules()
    text = report.render(rules)
    for rule_id in rules:
        assert text.count(f"### {rule_id} ") == 1
    assert f"{len(rules)} rules, 0 verified" in text


def test_report_exits_nonzero_but_still_writes_when_lint_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bad = dict(GOOD_RULE, status="verified")
    rules_dir = _write_rules(tmp_path, bad)
    monkeypatch.setattr(report, "lint", lambda known_fixtures: lint(rules_dir, known_fixtures))
    monkeypatch.setattr(report, "load_rules", lambda: load_rules(rules_dir))
    out = tmp_path / "rulebook.md"
    assert report.main(["-o", str(out)]) == 1
    assert "### OBJ-01 t" in out.read_text(encoding="utf-8")

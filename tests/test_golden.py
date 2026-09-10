"""Pin the readiness metrics of the supplied reference forms.

Raw artifacts are not committed (see src/fixtures/raw/README.md); these tests skip unless every file in
src/fixtures/pairs.yaml is present. When they run, any movement in a pinned number is either a real
extractor/gate change that must be explained in the PR, or a regression.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fixtures import load_pairs, raw_dir
from tools import pipeline

GOLDEN = {
    "17-0574": {
        "verdicts": {
            "G0": "fail",
            "G1": "pass",
            "G2": "pass",
            "G3": "fail",
            "G4": "fail",
            "G5": "external",
            "G6": "external",
        },
        "G1": {"containers": 41, "fields": 123, "statics": 71},
        "G3": {
            "bound_pct": 97.6,
            "name_evidence_pct": 100.0,
            "scripts_total": 48,
            "scripts_mechanically_transferable_pct": 100.0,
            "nodes_requiring_human_touch": 3,
            "findings_routable": 3,
            "findings_unrouted": 0,
            "decisions_proposed": 3,
        },
        "G4": {
            "field_match_pct": 0.5041,
            "exact_name_pct": 0.122,
            "static_text_coverage": 0.7707,
            "sections_matched": 0,
            "sections_total": 13,
            "target_form_controls": 271,
            "target_data_variables": 314,
        },
    },
    "18-1026": {
        "verdicts": {
            "G0": "pass",
            "G1": "pass",
            "G2": "pass",
            "G3": "fail",
            "G4": "fail",
            "G5": "external",
            "G6": "external",
        },
        "G1": {"containers": 23, "fields": 39, "statics": 39},
        "G3": {
            "bound_pct": 18.4,
            "name_evidence_pct": 100.0,
            "scripts_total": 20,
            "scripts_mechanically_transferable_pct": 75.0,
            "nodes_requiring_human_touch": 32,
            "findings_routable": 38,
            "findings_unrouted": 0,
            "decisions_proposed": 37,
        },
        "G4": {
            "field_match_pct": 0.6842,
            "exact_name_pct": 0.0,
            "static_text_coverage": 0.9921,
            "sections_matched": 6,
            "sections_total": 8,
            "target_form_controls": 30,
            "target_data_variables": 58,
        },
    },
    "18-1721": {
        "verdicts": {
            "G0": "pass",
            "G1": "pass",
            "G2": "pass",
            "G3": "fail",
            "G4": "skipped",
            "G5": "skipped",
            "G6": "skipped",
        },
        "G1": {"containers": 20, "fields": 79, "statics": 17},
        "G3": {"bound_pct": 0.0, "scripts_total": 4, "nodes_requiring_human_touch": 79},
    },
}


def _all_artifacts_present() -> bool:
    raw = raw_dir()
    for pair in load_pairs():
        files = [pair["source"]["file"]]
        if pair["target"]:
            files.append(pair["target"]["layout_xml"]["file"])
            if pair["target"]["composed_pdf"] is not None:
                files.append(pair["target"]["composed_pdf"]["file"])
        if not all((raw / f).exists() for f in files):
            return False
    return True


pytestmark = pytest.mark.skipif(not _all_artifacts_present(), reason="reference artifacts not present locally")


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict[str, dict]]:
    out = tmp_path_factory.mktemp("golden")
    assert pipeline.main(["-o", str(out)]) == 0
    forms = {}
    for form in json.loads((out / "readiness.json").read_text(encoding="utf-8"))["forms"]:
        forms[form["form_id"]] = {g["gate"]: g for g in form["gates"]}
    return forms


@pytest.mark.parametrize("form_id", sorted(GOLDEN))
def test_verdicts_are_pinned(report: dict, form_id: str) -> None:
    assert {g: r["verdict"] for g, r in report[form_id].items()} == GOLDEN[form_id]["verdicts"]


@pytest.mark.parametrize("form_id", sorted(GOLDEN))
def test_metrics_are_pinned(report: dict, form_id: str) -> None:
    for gate, expected in GOLDEN[form_id].items():
        if gate == "verdicts":
            continue
        actual = report[form_id][gate]["metrics"]
        assert {k: actual[k] for k in expected} == expected, f"{form_id} {gate}"


def test_strict_mode_fails_on_current_forms(tmp_path: Path) -> None:
    assert pipeline.main(["-o", str(tmp_path), "--strict"]) == 1

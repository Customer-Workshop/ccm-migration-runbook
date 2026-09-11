"""Pin the readiness metrics of the supplied reference forms.

Raw artifacts are not committed (see src/fixtures/raw/README.md); these tests skip unless every file in
src/fixtures/pairs.yaml is present. When they run, any movement in a pinned number is either a real
extractor/gate change that must be explained in the PR, or a regression.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from fixtures import load_pairs, raw_dir
from tools import pipeline

GOLDEN = {
    "17-0574": {
        "verdicts": {
            "G0": "pass",
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
            "field_match_pct": 0.6341,
            "exact_name_pct": 0.0894,
            "crosswalk_rows_pending": 24,
            "field_match_pct_if_proposed_verified": 0.813,
            "static_text_coverage": 0.9608,
            "sections_matched": 0,
            "sections_total": 13,
            "target_form_controls": 74,
            "target_data_variables": 2494,
        },
        "cim": {
            "title": "REQUEST FOR RECONSIDERATION",
            "controls": {"barcode": 3, "checkbox": 40, "image": 1, "multiline_text": 16, "text": 63},
            "scripts": {"conditional_clear": 10, "mutual_exclusion": 19, "uppercase": 3, "visibility": 16},
            "statics": {"image": 1, "rich_text": 23, "text": 46, "unknown": 1},
            "bindings": {"dataRef": 120, "none": 3},
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
            "scripts_mechanically_transferable_pct": 85.0,
            "nodes_requiring_human_touch": 31,
            "findings_routable": 35,
            "findings_unrouted": 0,
            "decisions_proposed": 34,
        },
        "G4": {
            "field_match_pct": 0.6842,
            "exact_name_pct": 0.0,
            "crosswalk_rows_pending": 27,
            "field_match_pct_if_proposed_verified": 0.7895,
            "static_text_coverage": 0.9921,
            "sections_matched": 6,
            "sections_total": 8,
            "target_form_controls": 30,
            "target_data_variables": 58,
        },
        "cim": {
            "title": "EFT AUTHORIZATION",
            "controls": {"action": 1, "barcode": 1, "checkbox": 14, "date": 2, "number": 2, "text": 19},
            "scripts": {"mutual_exclusion": 14, "page_number": 2, "submit": 1, "unknown": 3, "visibility": 1},
            "statics": {"image": 2, "rich_text": 14, "text": 22, "unknown": 1},
            "bindings": {"dataRef": 7, "none": 32},
        },
    },
    "18-1721": {
        "verdicts": {
            "G0": "fail",
            "G1": "pass",
            "G2": "pass",
            "G3": "fail",
            "G4": "pass",
            "G5": "external",
            "G6": "skipped",
        },
        "G0": {"static_text_coverage": 0.8776},
        "G1": {"containers": 20, "fields": 79, "statics": 17},
        "G3": {
            "bound_pct": 0.0,
            "name_evidence_pct": 89.9,
            "scripts_total": 4,
            "scripts_mechanically_transferable_pct": 100.0,
            "nodes_requiring_human_touch": 79,
            "findings_routable": 87,
            "findings_unrouted": 0,
            "decisions_proposed": 87,
        },
        "G4": {
            "field_match_pct": 0.8734,
            "exact_name_pct": 0.038,
            "crosswalk_rows_pending": 67,
            "field_match_pct_if_proposed_verified": 0.8987,
            "static_text_coverage": 0.8776,
            "sections_matched": 0,
            "sections_total": 5,
            "target_form_controls": 73,
            "target_data_variables": 449,
        },
        "cim": {
            "title": "CORPORATE MARKET TRANSMITTAL LETTER",
            "controls": {"checkbox": 32, "image": 2, "multiline_text": 5, "number": 10, "text": 30},
            "scripts": {"conditional_clear": 2, "page_number": 2},
            "statics": {"image": 1, "rectangle": 5, "rich_text": 5, "text": 6},
            "bindings": {"none": 79},
        },
    },
}

GATE_KEYS = ("verdicts", "cim")


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
def out_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("golden")
    assert pipeline.main(["-o", str(out)]) == 0
    return out


@pytest.fixture(scope="module")
def report(out_dir: Path) -> dict[str, dict[str, dict]]:
    forms = {}
    for form in json.loads((out_dir / "readiness.json").read_text(encoding="utf-8"))["forms"]:
        forms[form["form_id"]] = {g["gate"]: g for g in form["gates"]}
    return forms


def _distributions(cim: dict) -> dict[str, object]:
    return {
        "title": cim["form"]["title"],
        "controls": dict(sorted(Counter(f["control"]["kind"] for f in cim["fields"]).items())),
        "scripts": dict(sorted(Counter(s["classification"] for f in cim["fields"] for s in f["scripts"]).items())),
        "statics": dict(sorted(Counter(s["kind"] for s in cim["statics"]).items())),
        "bindings": dict(sorted(Counter(f["binding"]["mode"] for f in cim["fields"]).items())),
    }


@pytest.mark.parametrize("form_id", sorted(GOLDEN))
def test_verdicts_are_pinned(report: dict, form_id: str) -> None:
    assert {g: r["verdict"] for g, r in report[form_id].items()} == GOLDEN[form_id]["verdicts"]


@pytest.mark.parametrize("form_id", sorted(GOLDEN))
def test_metrics_are_pinned(report: dict, form_id: str) -> None:
    for gate, expected in GOLDEN[form_id].items():
        if gate in GATE_KEYS:
            continue
        actual = report[form_id][gate]["metrics"]
        assert {k: actual[k] for k in expected} == expected, f"{form_id} {gate}"


@pytest.mark.parametrize("form_id", sorted(GOLDEN))
def test_cim_distributions_are_pinned(out_dir: Path, form_id: str) -> None:
    cim = json.loads((out_dir / f"{form_id}.cim.json").read_text(encoding="utf-8"))
    assert _distributions(cim) == GOLDEN[form_id]["cim"]


def test_pipeline_output_is_deterministic(out_dir: Path, tmp_path: Path) -> None:
    assert pipeline.main(["-o", str(tmp_path)]) == 0
    for name in sorted(p.name for p in out_dir.glob("*.json")):
        assert (tmp_path / name).read_bytes() == (out_dir / name).read_bytes(), name


def test_strict_mode_fails_on_current_forms(tmp_path: Path) -> None:
    assert pipeline.main(["-o", str(tmp_path), "--strict"]) == 1

"""Fixture manifest access."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from gates.common import require

STATUSES = ("reference_pair", "source_only")
FIXTURES_DIR = Path(__file__).resolve().parent
PAIRS_PATH = FIXTURES_DIR / "pairs.yaml"


def raw_dir() -> Path:
    return Path(os.environ.get("CCM_FIXTURE_ROOT", FIXTURES_DIR / "raw"))


def load_pairs(path: Path = PAIRS_PATH) -> list[dict]:
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    require(manifest["manifest_version"] == 1, "unsupported pairs.yaml manifest_version")
    forms = manifest["forms"]
    ids = [f["form_id"] for f in forms]
    require(len(ids) == len(set(ids)), "duplicate form_id in pairs.yaml")
    for form in forms:
        require(form["status"] in STATUSES, f"{form['form_id']}: bad status")
        require(
            (form["target"] is None) == (form["status"] == "source_only"), f"{form['form_id']}: status/target mismatch"
        )
        if form["target"] is not None:
            require(form["target"]["layout_xml"] is not None, f"{form['form_id']}: reference_pair needs layout_xml")
        require(
            form["source"]["file"].replace("-", "")[:6] == form["form_id"].replace("-", ""),
            f"{form['form_id']}: source file name does not carry the form number",
        )
    return forms

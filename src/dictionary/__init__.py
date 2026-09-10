"""Data dictionary: canonical business elements and the per-form SOM -> element crosswalk.

elements.yaml   one row per canonical element (policy number, insured name, ...)
crosswalk.yaml  one row per (form_code, som) resolving a source field to an element
                and to the target variable name Quadient will use.

Row status is the tiering from file 8: ``auto`` (deterministic evidence),
``proposed`` (machine guess awaiting a steward), ``verified`` (steward signed),
``rejected``.  Only humans set ``verified``; the loader rejects a verified row
without a reviewer.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

DICT_DIR = Path(__file__).resolve().parent
ELEMENTS_PATH = DICT_DIR / "elements.yaml"
CROSSWALK_PATH = DICT_DIR / "crosswalk.yaml"
STATUSES = ("auto", "proposed", "verified", "rejected")


@dataclass(frozen=True)
class CrosswalkRow:
    form_code: str
    som: str
    element: str
    target_variable: str
    data_path: str
    status: str
    evidence: str
    reviewed_by: str | None


def _rows(path: Path, key: str) -> list[dict]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert doc["dictionary_version"] == 1, f"{path.name}: unsupported dictionary_version"
    return doc[key]


def load_elements(path: Path = ELEMENTS_PATH) -> dict[str, dict]:
    elements = {}
    for row in _rows(path, "elements"):
        assert row["id"] not in elements, f"duplicate element {row['id']}"
        assert row["status"] in STATUSES, f"{row['id']}: bad status {row['status']}"
        elements[row["id"]] = row
    return elements


def load_crosswalk(
    path: Path = CROSSWALK_PATH,
    elements: dict[str, dict] | None = None,
) -> dict[tuple[str, str], CrosswalkRow]:
    known = load_elements() if elements is None else elements
    rows: dict[tuple[str, str], CrosswalkRow] = {}
    for raw in _rows(path, "rows"):
        row = CrosswalkRow(**raw)
        key = (row.form_code, row.som)
        assert key not in rows, f"duplicate crosswalk row {key}"
        assert row.status in STATUSES, f"{key}: bad status {row.status}"
        assert row.element in known, f"{key}: unknown element {row.element}"
        if row.status == "verified":
            assert row.reviewed_by, f"{key}: verified rows need reviewed_by"
        rows[key] = row
    return rows

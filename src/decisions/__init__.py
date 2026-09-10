"""Per-form decision records: how each readiness finding was routed, by whom, and in which session.

src/decisions/<form_id>.yaml is written by the Devin session that converts the form (one record per
blocker/major G3 finding) and later amended by the human reviewer who accepts or rejects each
proposal. G3 reads the file so that accepted decisions stop counting as human-touch items, proposed
ones stay visible, and stale ones (node or finding no longer produced) are reported.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DECISIONS_DIR = Path(__file__).resolve().parent
STATUSES = ("proposed", "accepted", "rejected")
ACTIONS = (
    "bind_to_element",
    "keep_unbound",
    "translate_script",
    "drop_script",
    "manual_design",
    "accept_loss",
    "add_rule",
    "defer",
)
REQUIRED = ("id", "node", "finding", "action", "proposal", "rationale", "status", "decided_by", "decided_on")


@dataclass(frozen=True)
class Decision:
    id: str
    node: str
    finding: str
    action: str
    proposal: str
    rationale: str
    status: str
    decided_by: str | None
    decided_on: str | None


@dataclass(frozen=True)
class DecisionRecord:
    form_id: str
    session: str
    decisions: dict[tuple[str, str], Decision]


class DecisionError(ValueError):
    pass


def path_for(form_id: str, decisions_dir: Path = DECISIONS_DIR) -> Path:
    return decisions_dir / f"{form_id}.yaml"


def load_record(path: Path, form_id: str) -> DecisionRecord:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("decisions_version") != 1:
        raise DecisionError(f"{path.name}: decisions_version must be 1")
    if doc.get("form_id") != form_id:
        raise DecisionError(f"{path.name}: form_id {doc.get('form_id')!r} does not match {form_id!r}")
    session = doc.get("session")
    if not isinstance(session, str) or not session.startswith("https://"):
        raise DecisionError(f"{path.name}: session must be the https URL of the authoring Devin session")

    decisions: dict[tuple[str, str], Decision] = {}
    ids: set[str] = set()
    for raw in doc.get("decisions") or []:
        missing = [k for k in REQUIRED if k not in raw]
        if missing:
            raise DecisionError(f"{path.name}: decision {raw.get('id', '?')} missing keys {missing}")
        decision = Decision(**{k: raw[k] for k in REQUIRED})
        where = f"{path.name}:{decision.id}"
        if decision.id in ids:
            raise DecisionError(f"{where}: duplicate id")
        ids.add(decision.id)
        if not decision.node or not decision.finding:
            raise DecisionError(f"{where}: node and finding are required")
        if decision.action not in ACTIONS:
            raise DecisionError(f"{where}: action must be one of {ACTIONS}")
        if decision.status not in STATUSES:
            raise DecisionError(f"{where}: status must be one of {STATUSES}")
        if decision.status == "proposed" and (decision.decided_by or decision.decided_on):
            raise DecisionError(f"{where}: proposed decisions must not carry decided_by/decided_on")
        if decision.status != "proposed" and not (decision.decided_by and decision.decided_on):
            raise DecisionError(f"{where}: {decision.status} decisions need decided_by and decided_on")
        key = (decision.node, decision.finding)
        if key in decisions:
            raise DecisionError(f"{where}: second decision for {key}")
        decisions[key] = decision
    return DecisionRecord(form_id=form_id, session=session, decisions=decisions)


def load_for(form_id: str, decisions_dir: Path = DECISIONS_DIR) -> DecisionRecord | None:
    path = path_for(form_id, decisions_dir)
    return load_record(path, form_id) if path.exists() else None

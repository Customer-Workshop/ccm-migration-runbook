"""Shared gate plumbing: findings, verdicts, safe loaders."""

from __future__ import annotations

import hashlib
import json
import os
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path

SEVERITY_ORDER = {"info": 0, "minor": 1, "major": 2, "blocker": 3}
MAX_INPUT_BYTES = 256 * 1024 * 1024

# A gate reports one of these. "external" means the gate needs evidence (Designer import,
# composed PDF) that offline tooling cannot produce; it is neither pass nor fail.
VERDICTS = ("pass", "fail", "skipped", "external")


class ArtifactError(ValueError):
    """A repository artifact (manifest, dictionary, catalogue, log, PDF) is malformed; the message names it."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ArtifactError(message)


@dataclass
class Finding:
    code: str
    severity: str
    message: str
    node: str | None = None
    rule_id: str | None = None

    def as_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class GateResult:
    gate: str
    verdict: str
    findings: list[Finding] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    reason: str | None = None

    def add(self, code: str, severity: str, message: str, node: str | None = None, rule_id: str | None = None) -> None:
        if severity not in SEVERITY_ORDER:
            raise ValueError(f"unknown severity {severity!r}")
        self.findings.append(Finding(code, severity, message, node, rule_id))

    def worst(self) -> str:
        if not self.findings:
            return "info"
        return max((f.severity for f in self.findings), key=SEVERITY_ORDER.__getitem__)

    def finalize(self, fail_on: str = "major") -> GateResult:
        if self.verdict in ("skipped", "external"):
            return self
        self.verdict = "fail" if SEVERITY_ORDER[self.worst()] >= SEVERITY_ORDER[fail_on] else "pass"
        return self

    def as_dict(self) -> dict:
        return {
            "gate": self.gate,
            "verdict": self.verdict,
            "reason": self.reason,
            "metrics": self.metrics,
            "findings": [f.as_dict() for f in self.findings],
        }


def skipped(gate: str, reason: str) -> GateResult:
    return GateResult(gate=gate, verdict="skipped", reason=reason)


def external(gate: str, reason: str, metrics: dict | None = None) -> GateResult:
    return GateResult(gate=gate, verdict="external", reason=reason, metrics=metrics or {})


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def guard_size(path: Path) -> None:
    size = os.path.getsize(path)
    if size > MAX_INPUT_BYTES:
        raise ArtifactError(f"{path}: {size} bytes exceeds the {MAX_INPUT_BYTES} byte limit")


def load_xml(path: Path) -> ET.Element:
    """ElementTree never expands external entities, so this is safe for untrusted input."""
    guard_size(path)
    with open(path, "rb") as fh:
        return ET.fromstring(fh.read())


def load_json(path: Path) -> dict:
    guard_size(path)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]

"""G0: pairing and revision gate (GOV-01, UNS-10).

Checks that the source and target files named in src/fixtures/pairs.yaml exist, hash as declared,
and describe the same business-form revision (static-text coverage of the target by the source).
"""

from __future__ import annotations

from pathlib import Path

from gates.common import GateResult, sha256_of, skipped
from gates.matching import tokens
from gates.target_inventory import inventory

STATIC_TEXT_COVERAGE_MIN = 0.95


def run(pair: dict, raw_dir: Path, cim: dict | None) -> GateResult:
    result = GateResult(gate="G0", verdict="pass")
    _check_file(result, raw_dir / pair["source"]["file"], pair["source"]["sha256"], "source")
    if pair["target"] is None:
        result.metrics["paired"] = False
        result.add("G0-UNPAIRED", "info", "no target layout XML or composed PDF supplied", rule_id="GOV-01")
        return result.finalize()

    result.metrics["paired"] = True
    layout = raw_dir / pair["target"]["layout_xml"]["file"]
    _check_file(result, layout, pair["target"]["layout_xml"]["sha256"], "target layout")
    composed_pdf = pair["target"]["composed_pdf"]
    if composed_pdf is None:
        result.metrics["composed_pdf_supplied"] = False
        result.add(
            "G0-NO-PDF",
            "info",
            "no composed PDF supplied; G6 stays external until one arrives",
            rule_id="GOV-02",
        )
    else:
        result.metrics["composed_pdf_supplied"] = True
        pdf = raw_dir / composed_pdf["file"]
        _check_file(result, pdf, composed_pdf["sha256"], "target pdf")
    if not layout.exists() or cim is None:
        return result.finalize()

    inv = inventory(layout)
    source_tokens = tokens(s["text"] for s in cim["statics"]) | tokens(f["caption"] for f in cim["fields"])
    target_tokens = tokens(inv["static_text"])
    coverage = len(target_tokens & source_tokens) / len(target_tokens) if target_tokens else 0.0
    result.metrics.update(
        {
            "static_text_coverage": round(coverage, 4),
            "target_only_tokens": sorted(target_tokens - source_tokens)[:50],
            "threshold": STATIC_TEXT_COVERAGE_MIN,
        }
    )
    if coverage < STATIC_TEXT_COVERAGE_MIN:
        result.add(
            "G0-REVISION-DRIFT",
            "major",
            f"target static text covered by source at {coverage:.1%} (< {STATIC_TEXT_COVERAGE_MIN:.0%}): "
            "the reference layout was likely authored from a different form revision",
            rule_id="GOV-01",
        )
    return result.finalize()


def _check_file(result: GateResult, path: Path, expected_sha: str, label: str) -> None:
    if not path.exists():
        result.add(
            "G0-MISSING", "blocker", f"{label} file {path.name} is not present in {path.parent}", rule_id="GOV-02"
        )
        return
    actual = sha256_of(path)
    if actual != expected_sha:
        result.add(
            "G0-HASH",
            "blocker",
            f"{label} file {path.name} hash {actual[:12]} != manifest {expected_sha[:12]}",
            rule_id="GOV-02",
        )


def skip(reason: str) -> GateResult:
    return skipped("G0", reason)

"""G5: target structural validity.

Offline part: lint a Layout export against the import-error catalogue. External part: the
Designer import itself. Until an import log for the exact artifact hash is recorded in
src/fixtures/import_logs/, the gate verdict is "external", never "pass".
"""

from __future__ import annotations

from pathlib import Path

from gates.common import GateResult, external, load_json, require, sha256_of
from gates.import_lint import lint, load_catalogue
from gates.target_inventory import inventory

IMPORT_LOG_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "import_logs"


def run(layout_xml: Path) -> GateResult:
    inv = inventory(layout_xml)
    result = lint(inv, load_catalogue())
    result.metrics["inventory"] = {k: v for k, v in inv["counts"].items()}
    result.finalize()
    if result.verdict == "fail":
        return result

    log = IMPORT_LOG_DIR / f"{sha256_of(layout_xml)}.json"
    if not log.exists():
        outcome = external(
            "G5", "offline lint passed; Designer import log not recorded for this artifact hash", result.metrics
        )
        outcome.findings = result.findings
        return outcome
    record = load_json(log)
    require(record["verdict"] in ("pass", "fail"), f"{log}: verdict must be pass or fail")
    result.verdict = record["verdict"]
    result.reason = (
        f"Designer {record['designer_version']} import by {record['imported_by']} on {record['imported_on']}"
    )
    for error in record["errors"]:
        result.add("G5-DESIGNER", "blocker", error, rule_id="GOV-03")
    return result

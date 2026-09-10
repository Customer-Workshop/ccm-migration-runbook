"""G6: composed output.

Offline part: the reference PDF exists, is a PDF, and its page count and producer can be read.
External part: composing the generated WFD with fixed input data and comparing it with the
reference. No fixed input data has been supplied for any reference PDF, so the verdict is
"external" until a composition record exists in src/fixtures/composition_logs/.
"""

from __future__ import annotations

import re
from pathlib import Path

from gates.common import GateResult, external, guard_size, load_json, sha256_of

COMPOSITION_LOG_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "composition_logs"
PAGE_OBJECT = re.compile(rb"/Type\s*/Page(?![s/])")
CREATOR = re.compile(rb"/Creator\s*\((.*?)\)", re.S)


def inspect_pdf(path: Path) -> dict:
    guard_size(path)
    data = path.read_bytes()
    assert data.startswith(b"%PDF-"), f"{path.name} is not a PDF"
    creator = CREATOR.search(data)
    return {
        "file": path.name,
        "bytes": len(data),
        "pdf_version": data[5:8].decode("ascii", "replace"),
        "pages_estimated": len(PAGE_OBJECT.findall(data)),
        "creator": creator.group(1).decode("latin-1").replace("~", " ") if creator else None,
        "has_eof_marker": b"%%EOF" in data[-1024:],
    }


def run(pdf: Path) -> GateResult:
    result = GateResult(gate="G6", verdict="pass")
    info = inspect_pdf(pdf)
    result.metrics["reference_pdf"] = info
    if info["pages_estimated"] == 0:
        result.add("G6-NOPAGES", "blocker", "no page objects found in reference PDF", rule_id="GOV-02")
    if not info["has_eof_marker"]:
        result.add("G6-TRUNCATED", "major", "reference PDF has no trailing %%EOF marker", rule_id="GOV-02")
    result.finalize()
    if result.verdict == "fail":
        return result

    log = COMPOSITION_LOG_DIR / f"{sha256_of(pdf)}.json"
    if not log.exists():
        outcome = external(
            "G6", "reference PDF inspected; no composition run with fixed input data recorded", result.metrics
        )
        return outcome
    record = load_json(log)
    assert record["verdict"] in ("pass", "fail"), f"{log}: verdict must be pass or fail"
    result.verdict = record["verdict"]
    result.reason = (
        f"composed by {record['composed_by']} on {record['composed_on']} with input {record['input_data_sha256'][:12]}"
    )
    for diff in record["differences"]:
        result.add("G6-VISUAL", "major", diff, rule_id="LAY-06")
    return result

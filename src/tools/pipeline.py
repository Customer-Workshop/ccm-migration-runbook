"""Run every gate for every form in src/fixtures/pairs.yaml and write the readiness report.

Acceptance policy (see AGENTS.md):
  * G1 and G2 are integrity gates: a fail is a pipeline failure (exit 2). The extractor has lost
    or malformed data and nothing downstream can be trusted.
  * G0, G3 and G4 are readiness gates: their fail verdicts are the product of this tool, not a
    tool failure. They are recorded in the report and pinned by tests/test_golden.py so that a
    regression in readiness is visible in CI without blocking every run on the current forms.
  * G5 and G6 return "external" until an authoritative Designer import or composition record
    exists for the artifact hash. They never pass on offline evidence alone.
  * --strict turns any fail verdict into exit 1 (for use once forms are expected to be ready).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from converters.cim_to_inspire.build_plan import build_plan, write_plan
from converters.xdp_to_cim.extractor import XdpExtractor
from decisions import load_for
from dictionary import load_crosswalk
from fixtures import load_pairs, raw_dir
from gates import g0_pairing, g1_shape, g2_completeness, g3_readiness, g4_coverage, g5_target, g6_pdf
from gates.common import GateResult, skipped
from gates.target_inventory import inventory
from rulebook import load_rules

INTEGRITY_GATES = ("G1", "G2")


def run_form(pair: dict, raw: Path, rules: dict, crosswalk: dict, out_dir: Path) -> dict:
    source = raw / pair["source"]["file"]
    if not source.exists():
        return {
            "form_id": pair["form_id"],
            "status": pair["status"],
            "gates": [
                skipped(g, f"{source.name} not present in {raw}").as_dict()
                for g in ("G0", "G1", "G2", "G3", "G4", "G5", "G6")
            ],
        }

    cim = XdpExtractor(str(source)).build()
    (out_dir / f"{pair['form_id']}.cim.json").write_text(json.dumps(cim, indent=2) + "\n", encoding="utf-8")

    gates: list[GateResult] = [g0_pairing.run(pair, raw, cim), g1_shape.run(cim)]
    if gates[-1].verdict == "fail":
        gates += [skipped(g, "G1 failed") for g in ("G2", "G3", "G4", "G5", "G6")]
        return _summary(pair, gates)

    gates += [g2_completeness.run(cim), g3_readiness.run(cim, rules, load_for(pair["form_id"]))]
    write_plan(build_plan(cim, crosswalk), out_dir / f"{pair['form_id']}.plan.json")
    if pair["target"] is None:
        gates += [skipped(g, "no target artifact supplied for this form") for g in ("G4", "G5", "G6")]
        return _summary(pair, gates)

    layout = raw / pair["target"]["layout_xml"]["file"]
    gates.append(
        g4_coverage.run(cim, inventory(layout)) if layout.exists() else skipped("G4", f"{layout.name} missing")
    )
    gates.append(g5_target.run(layout) if layout.exists() else skipped("G5", f"{layout.name} missing"))
    composed_pdf = pair["target"]["composed_pdf"]
    if composed_pdf is None:
        gates.append(skipped("G6", "no composed PDF supplied for this form"))
    else:
        pdf = raw / composed_pdf["file"]
        gates.append(g6_pdf.run(pdf) if pdf.exists() else skipped("G6", f"{pdf.name} missing"))
    return _summary(pair, gates)


def _summary(pair: dict, gates: list[GateResult]) -> dict:
    return {"form_id": pair["form_id"], "status": pair["status"], "gates": [g.as_dict() for g in gates]}


def to_markdown(report: dict) -> str:
    lines = ["# Readiness report", "", "| form | " + " | ".join(f"G{i}" for i in range(7)) + " |", "|---" * 8 + "|"]
    for form in report["forms"]:
        cells = [f"{g['verdict']}" + (f" ({len(g['findings'])})" if g["findings"] else "") for g in form["gates"]]
        lines.append(f"| {form['form_id']} | " + " | ".join(cells) + " |")
    lines.append("")
    for form in report["forms"]:
        lines.append(f"## {form['form_id']}")
        for gate in form["gates"]:
            lines.append(f"- {gate['gate']}: {gate['verdict']}" + (f", {gate['reason']}" if gate["reason"] else ""))
            if gate["gate"] == "G3" and gate["verdict"] != "skipped":
                m = gate["metrics"]
                lines.append(f"  - draft rules depended on: {', '.join(m['draft_rules']) or 'none'}")
                lines.append(
                    f"  - findings routed {m['findings_routable'] - m['findings_unrouted']}/{m['findings_routable']}"
                    f" (proposed {m['decisions_proposed']}, accepted {m['decisions_accepted']},"
                    f" rejected {m['decisions_rejected']}); session {m['decision_session'] or 'none'}"
                )
            if gate["gate"] == "G4" and gate["verdict"] != "skipped":
                m = gate["metrics"]
                lines.append(
                    f"  - field match {m['field_match_pct']:.1%}, exact names {m['exact_name_pct']:.1%}, "
                    f"static text {m['static_text_coverage']:.1%}"
                )
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--out", type=Path, default=Path("out"), help="output directory (default: out/)")
    parser.add_argument("--strict", action="store_true", help="exit 1 if any gate fails")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    rules = load_rules()
    crosswalk = load_crosswalk()
    report = {"forms": [run_form(pair, raw_dir(), rules, crosswalk, args.out) for pair in load_pairs()]}
    (args.out / "readiness.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (args.out / "readiness.md").write_text(to_markdown(report), encoding="utf-8")
    print(to_markdown(report))

    verdicts = {(f["form_id"], g["gate"]): g["verdict"] for f in report["forms"] for g in f["gates"]}
    if any(v == "fail" for (_, gate), v in verdicts.items() if gate in INTEGRITY_GATES):
        print("integrity gate failed", file=sys.stderr)
        return 2
    if args.strict and any(v == "fail" for v in verdicts.values()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

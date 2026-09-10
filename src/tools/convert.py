"""Convert one XDP to a CIM and an Inspire build plan, running the offline gates that need no target.

    python -m tools.convert path/to/form.xdp -o out/

Exit 2 if G1 or G2 fail (the CIM cannot be trusted), otherwise 0. G3 findings are printed, not fatal:
readiness is a property of the form, not of this tool.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from converters.cim_to_inspire.build_plan import build_plan, write_plan
from converters.xdp_to_cim.extractor import XdpExtractor
from decisions import load_for
from dictionary import load_crosswalk
from gates import g1_shape, g2_completeness, g3_readiness
from rulebook import load_rules


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("xdp", type=Path)
    parser.add_argument("-o", "--out", type=Path, default=Path("out"))
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    cim = XdpExtractor(str(args.xdp)).build()
    form_code = cim["form"]["form_code"]
    (args.out / f"{form_code}.cim.json").write_text(json.dumps(cim, indent=2) + "\n", encoding="utf-8")

    gates = [g1_shape.run(cim), g2_completeness.run(cim), g3_readiness.run(cim, load_rules(), load_for(form_code))]
    for gate in gates:
        print(f"{gate.gate}: {gate.verdict} ({len(gate.findings)} findings)")
        for finding in gate.findings:
            print(f"  {finding.severity:8} {finding.code:22} {finding.message}")
    if any(g.verdict == "fail" for g in gates[:2]):
        return 2

    plan = build_plan(cim, load_crosswalk())
    write_plan(plan, args.out / f"{form_code}.plan.json")
    print(
        f"plan: {len(plan['variables'])} variables, {len(plan['blocks'])} blocks, "
        f"{len(plan['skipped'])} skipped, {len(plan['decisions_required'])} decisions required"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

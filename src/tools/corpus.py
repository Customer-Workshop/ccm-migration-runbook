"""Assess a directory of XDPs: size, binding, scripting and unsupported-construct profile per form,
a complexity tier, and a suggested conversion order.

    python -m tools.corpus path/to/xdps -o out/

Writes corpus.json and corpus.md. Extraction only; no target is needed. Tiering is a triage aid for
the Devin session that plans a batch (see .agents/skills/assess-form-corpus), not an acceptance verdict.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from converters.xdp_to_cim.extractor import XdpExtractor
from gates import g3_readiness
from rulebook import load_rules

TIERS = ("simple", "medium", "complex")
TIER_LIMITS = {"fields": (40, 100), "scripts": (5, 25), "unsupported": (5, 20), "pages": (1, 3)}


def tier_for(profile: dict) -> str:
    worst = 0
    for key, (simple_max, medium_max) in TIER_LIMITS.items():
        value = profile[key]
        worst = max(worst, 0 if value <= simple_max else 1 if value <= medium_max else 2)
    return TIERS[worst]


def profile_form(xdp: Path, rules: dict) -> dict:
    cim = XdpExtractor(str(xdp)).build()
    g3 = g3_readiness.run(cim, rules)
    fields = [f for f in cim["fields"] if f["control"]["kind"] != "action"]
    profile = {
        "file": xdp.name,
        "form_code": cim["form"]["form_code"],
        "revision_hint": cim["form"]["revision_hint"],
        "pages": len(cim["pages"]),
        "fields": len(fields),
        "statics": len(cim["statics"]),
        "containers": len(cim["containers"]),
        "bound_pct": g3.metrics["bound_pct"],
        "scripts": g3.metrics["scripts_total"],
        "unsupported": len(cim["diagnostics"]["unsupported"]),
        "human_touch": g3.metrics["nodes_requiring_human_touch"],
        "draft_rules": g3.metrics["draft_rules"],
    }
    profile["tier"] = tier_for(profile)
    return profile


def assess(xdp_dir: Path, rules: dict) -> dict:
    files = sorted(xdp_dir.glob("*.xdp"))
    if not files:
        raise FileNotFoundError(f"no .xdp files in {xdp_dir}")
    forms = [profile_form(f, rules) for f in files]
    order = sorted(forms, key=lambda p: (TIERS.index(p["tier"]), p["human_touch"], p["fields"], p["file"]))
    return {
        "source_dir": str(xdp_dir),
        "forms": forms,
        "tiers": {t: sum(1 for p in forms if p["tier"] == t) for t in TIERS},
        "suggested_order": [p["form_code"] for p in order],
    }


def to_markdown(report: dict) -> str:
    lines = [
        "# Corpus assessment",
        "",
        f"{len(report['forms'])} forms; tiers: "
        + ", ".join(f"{t} {n}" for t, n in report["tiers"].items())
        + ". Tiers are a triage aid, not a readiness verdict.",
        "",
        "| form | tier | pages | fields | bound % | scripts | unsupported | human touch |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for p in report["forms"]:
        lines.append(
            f"| {p['form_code']} | {p['tier']} | {p['pages']} | {p['fields']} | {p['bound_pct']} | "
            f"{p['scripts']} | {p['unsupported']} | {p['human_touch']} |"
        )
    lines += ["", "Suggested order: " + ", ".join(report["suggested_order"]), ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("xdp_dir", type=Path)
    parser.add_argument("-o", "--out", type=Path, default=Path("out"))
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    report = assess(args.xdp_dir, load_rules())
    (args.out / "corpus.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (args.out / "corpus.md").write_text(to_markdown(report), encoding="utf-8")
    print(to_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

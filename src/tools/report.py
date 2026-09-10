"""Render the rulebook as Markdown so nobody maintains a prose copy of the YAML.

    python -m tools.report -o out/rulebook.md

Exit 1 if the rulebook lint reports problems; the report is still written so the problems can be read.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fixtures import load_pairs
from rulebook import FAMILIES, Rule, lint, load_rules

FAMILY_TITLES = {
    "OBJ": "Object mapping",
    "FLD": "Field identity and controls",
    "LAY": "Layout and geometry",
    "BND": "Binding and dictionary",
    "VAL": "Validation and scripts",
    "STY": "Styles",
    "UNS": "Unsupported constructs",
    "GOV": "Governance and security",
}


def _row(rule: Rule) -> str:
    reviewer = rule.reviewed_by or "-"
    fixtures = ", ".join(rule.fixtures) or "-"
    return f"| {rule.id} | {rule.cls} | {rule.status} | {rule.title} | {fixtures} | {reviewer} |"


def render(rules: dict[str, Rule]) -> str:
    by_family: dict[str, list[Rule]] = {family: [] for family in FAMILIES}
    for rule in rules.values():
        by_family[rule.family].append(rule)

    total = len(rules)
    verified = sum(rule.is_verified for rule in rules.values())
    lines = [
        "# Conversion rulebook",
        "",
        (
            f"{total} rules, {verified} verified. Generated from `src/rulebook/rules/*.yaml` "
            "by `tools.report`; edit the YAML."
        ),
        "",
    ]
    for family in FAMILIES:
        family_rules = sorted(by_family[family], key=lambda rule: rule.id)
        lines += [
            f"## {family}: {FAMILY_TITLES[family]}",
            "",
            "| id | class | status | title | fixtures | reviewed by |",
            "|---|---|---|---|---|---|",
            *(_row(rule) for rule in family_rules),
            "",
        ]
        for rule in family_rules:
            lines += [
                f"### {rule.id} {rule.title}",
                "",
                f"- source: {rule.source}",
                f"- target: {rule.target}",
                f"- evidence: {rule.evidence}",
                f"- origin: {rule.origin['type']} {', '.join(rule.origin['refs'])}",
                f"- gates: {', '.join(rule.gates)}",
                f"- implemented in: {', '.join(rule.implemented_in) or '-'}",
            ]
            if rule.notes:
                lines.append(f"- notes: {rule.notes}")
            lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--out", type=Path, default=Path("out") / "rulebook.md")
    args = parser.parse_args(argv)

    known = {pair["form_id"] for pair in load_pairs()}
    problems = lint(known_fixtures=known)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(load_rules()), encoding="utf-8")
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

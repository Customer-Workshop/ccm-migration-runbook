---
name: review-rulebook-change
description: Review a PR that adds or changes rules under src/rulebook/rules, the CIM schema, gates, or the dictionary. Use when asked to review a rulebook PR, to assess whether a rule can move from draft to verified, or to check a Devin-drafted rule before a Quadient designer signs it off.
---

# Review a rulebook / CIM / gate change

Two audiences use this: a Devin session doing a first-pass review (it may only *recommend*), and the named
Quadient/customer reviewer who is the only person allowed to set `status: verified` and `reviewed_by`.

## Checklist

For every rule touched (`src/rulebook/rules/*.yaml`):

1. **Origin is real.** `origin.type` is one of the lint-accepted types and `origin.refs` points at something a
   reviewer can open: a form id in `src/fixtures/pairs.yaml`, an import-log hash, a document. "Devin inferred it"
   is `analysis` and must say what was compared.
2. **The fixture exercises the rule.** Open the CIM (`out/<form>.cim.json`) for each id in `fixtures` and find
   the construct the rule describes. If the rule fires on nothing, reject; if it fires on one form only, ask
   whether it is a rule or a patch (`AGENTS.md` rule 8).
3. **Class matches implementation.** `AUTO`/`AUTO*` rules must list a resolvable `implemented_in` and that code
   must be covered by a test in `tests/`. A rule described as deterministic but implemented nowhere is
   `ASSIST` at best. `MANUAL` rules must say in `target` where the human decision lands (a G3 finding, a
   dictionary row, a CIM `data_dictionary` entry) so it is persisted as data (GOV-05).
4. **Target claim is evidenced from the target.** The `target` and `evidence` fields must come from a Designer
   export, official Quadient documentation, or the migration-stack source, not from the XDP. Two reference
   exports are examples, not a grammar; say so in the review if the rule generalises beyond them.
5. **Unsupported is honest.** If the rule narrows what is converted, the excluded case must appear in
   `src/rulebook/rules/unsupported.yaml` or as a G3 finding, not disappear.
6. **Thresholds unchanged.** Any edit to `GOV-01`, the G4 floor, `INTEGRITY_GATES`, or pipeline exit codes
   needs a written rationale from the customer, not a green CI run.

For CIM schema changes (`src/cim/schema/cim.schema.json`): `CIM_VERSION` bumped, `tests/test_golden.py` counts
re-pinned from a fresh run, and every extractor field that feeds the changed node still has a test.

For gate changes (`src/gates/`): the failure path is tested (a fixture that *should* fail still fails), and the
gate still distinguishes `fail` / `external` / `skipped` as documented in `src/gates/common.py`.

For dictionary changes (`src/dictionary/*.yaml`): `verified` rows carry `reviewed_by`; `evidence` names the
source (Designer export variable, data master, Factory map); `rejected` rows stay in the file so the same
proposal is not re-made.

## Verdicts

- Devin: comment "recommend verify" / "keep draft: <reason>" / "reject: <reason>". Do not edit `status`.
- Human reviewer: to verify, set `status: verified`, `reviewed_by: <name>`, `reviewed_on: <YYYY-MM-DD>` in the
  same PR. `pytest -q` enforces that verified rules carry a reviewer and draft rules do not.

## Run before commenting

```
ruff check . && pytest -q
python -m tools.pipeline -o out/     # confirm the golden metrics moved only where the PR says they should
```

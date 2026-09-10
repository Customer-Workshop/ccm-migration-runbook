---
name: triage-designer-errors
description: Turn a Quadient Inspire Designer import error log into permanent assets - an import-lint check, a rulebook entry, a fixture, and a G5 import record - then open a PR. Use when someone pastes Designer import errors, asks to "triage import errors for <form>", or supplies an import log.
---

# Triage Designer import errors

Input: the raw error output from a Designer import of a generated artifact, plus who imported it, which
Designer version, and on what date. If the raw text is paraphrased ("it complained about tables"), ask
for the verbatim messages before proceeding; the catalogue stores messages, not summaries.

## Procedure

1. Record the import as evidence first. Compute `sha256sum <layout.xml>` for the artifact that was imported
   and write `src/fixtures/import_logs/<sha256>.json` (format in `src/fixtures/import_logs/README.md`) with
   `verdict: fail` and every message in `errors`. This is the only thing that makes G5 say anything other
   than `external`.
2. Classify each message against `src/gates/import_lint/catalogue.yaml`:
   - **Known code** (`IMP-00x`): set that entry's `status: observed`, paste the message into
     `designer_message`, and extend `evidence`. If the offline check did *not* flag the artifact before
     import, the check is wrong or too narrow: fix it in `src/gates/import_lint/__init__.py` with a test in
     `tests/test_gates.py` that fails on the offending XML before the fix.
   - **New class**: add a catalogue entry with the next code, `status: observed`, the verbatim
     `designer_message`, and a `check` function you implement in `src/gates/import_lint/__init__.py`. The check
     receives the target inventory (`gates.target_inventory.inventory`) and returns offending node ids. Add
     it to `CHECKS`. Add a failing-then-passing test using a mutated copy of `tests/data/99-0001.xml`.
   - **Not structural** (licensing, font not installed, version mismatch): do not add a check. Record it in
     the PR and, if it recurs, in `knowledge/quadient-designer.md`.
3. For each new or changed check, find or add the rulebook rule that prevents the error at build-plan time:
   `src/rulebook/rules/<family>.yaml`, `class` `AUTO` if `src/converters/cim_to_inspire/build_plan.py` can enforce
   it (then implement and list it in `implemented_in`), otherwise `ASSIST`/`MANUAL`. `origin` is
   `{type: designer_error, refs: ["<import_log sha256 prefix>"]}`. Status stays `draft`.
4. Re-run `python -m tools.pipeline -o out/`. The catalogue must now flag the imported artifact offline
   (G5 `fail` with the new code) and must still be clean on the two reference exports (they were produced
   by Designer, so any new finding against them is a false positive).
5. `ruff check . && pytest -q`. Open a PR titled `import-lint: <IMP-code> <short title>` listing: the error
   text, the check, the rule, and what a reviewer must confirm in Designer to mark the rule `verified`.

## Never

- Fix the generated XML by hand to make the import pass.
- Mark a catalogue entry `observed` without the verbatim Designer message.
- Add a check that also fires on `17-0574.xml` or `18-1026_Quad_2.xml`.
- Set a rule to `verified`.

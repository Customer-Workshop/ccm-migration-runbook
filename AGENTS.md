# AGENTS.md - ccm-migration

Always-on constraints for any agent (Devin or human) working in this directory. Procedures live in
`.agents/skills/`, one-off jobs in `playbooks/`. Conversion logic lives in code, never in prose.

## What this repo is

A deterministic mechanism to move AEM Forms (XDP) toward Quadient Inspire: extract to a Canonical
Intermediate Model (`src/cim/`), apply a versioned rulebook (`src/rulebook/`), emit a build plan for the
Quadient `migration-stack` (`src/converters/cim_to_inspire/`), and prove readiness through gates G0-G6
(`src/gates/`). It is a proof-of-concept scaffold over three partner test forms. It is **not** a production
migration tool and must not be described as one.

## Operating model: one form, one Devin session

The Python is the instrument; a Devin session is the operator. Every form goes through a session that
follows `.agents/skills/convert-xdp-form/SKILL.md`, and the code enforces the parts of that it can:

- A blocker/major G3 finding without a record in `src/decisions/<form_id>.yaml` counts as unrouted
  (`findings_unrouted` in `readiness.json`, `G3-NO-DECISIONS` when the file is missing). Routing is the
  session's job; the tool cannot do it.
- `src/decisions/<form_id>.yaml` must carry the `https://` URL of the authoring session (GOV-07). The loader
  rejects records without it. This is how every proposal stays traceable to the reasoning that made it.
- Devin writes `proposed` only. `accepted`/`rejected` need `decided_by` and `decided_on` from a named
  human. The same split applies to rules (`draft`/`verified`) and dictionary rows.
- G5 and G6 are closed by people with Designer access; the session prepares the handoff
  (`prepare-designer-handoff`), triages what comes back (`triage-designer-errors`) and runs the output
  comparison (`validate-pdf-output`) so nothing is decided in an inbox.
- Batches start with `assess-form-corpus`, which orders forms so later sessions inherit earlier decisions.

A PR for a form that has unrouted findings, decisions without rationale, or no session link is not
mergeable. Running the pipeline by hand and pasting `readiness.md` into a ticket is not a conversion.

## Hard rules

1. **Never hand-author target XML.** Quadient objects are produced through the migration-stack builder
   API from a build plan (GOV-03). If a construct cannot be expressed through the plan, it becomes a
   `MANUAL` decision, not a string template.
2. **Never execute embedded scripts.** XDP `<script>` bodies are classified by idiom (`rule_translatable`, `runtime_only`,
   `manual`) and recorded; they are not run (GOV-04).
3. **Every input is untrusted.** Use `gates.common.load_xml` / `guard_size`; keep the size caps; no
   external entities; no network access from converters or gates.
4. **Never set a rule or dictionary row to `verified`.** Agents draft. Verification is a PR by the named
   Quadient/customer reviewer recorded in `reviewed_by` (GOV-05, GOV-06). A form that depends on a `draft` rule
   is not migration-ready and G3 says so.
5. **Never claim G5 or G6 passed** without an import log (`src/fixtures/import_logs/<xml_sha256>.json`) or
   composition log (`src/fixtures/composition_logs/<pdf_sha256>.json`) written by a person with Designer
   access. Offline, these gates return `external`.
6. **Do not commit customer artifacts.** `src/fixtures/raw/` is gitignored; `src/fixtures/pairs.yaml` holds
   hashes only. Ask before changing this.
7. **Do not weaken thresholds or acceptance policy** (`GOV-01` 95% static-text coverage, G4 70% field
   floor, `src/tools/pipeline.py` exit codes) to make a run green. Record the failure and route it.
8. **Fix the rule, not the form.** When a form converts badly, add or amend a rule with a fixture and a
   test so the next form benefits. Per-form patches are `MANUAL` decisions persisted as data.
9. **Filenames are evidence.** `18-1026_Quad_2.xml` is the supplied target name; do not "correct" it.
10. **Every routed finding is a decision record.** No G3 blocker/major is resolved in a PR comment, a
    chat, or by editing the CIM. It is a `proposed` record in `src/decisions/<form_id>.yaml` with a rationale
    that cites evidence, and it stays open until a named human accepts or rejects it (GOV-07).

## Commands

```
pip install -e ".[dev]"
ruff check .
pytest -q --cov --cov-fail-under=90
python -m tools.pipeline -o out/          # all forms, readiness.json + readiness.md
python -m tools.pipeline -o out/ --strict # exit 1 on any fail; use once forms are expected ready
python -m tools.convert path/to/form.xdp  # one form: CIM + plan + G1/G2/G3
python -m tools.corpus path/to/xdps       # batch profile: tiers, suggested order (corpus.json/md)
```

Exit codes from `tools.pipeline`: `2` = G1/G2 integrity failure (extractor bug, fix before anything
else); `1` = readiness failure in `--strict`; `0` otherwise. `tests/test_golden.py` pins the current
readiness metrics for the three proof forms so regressions show in CI even when the gates "fail" by
design.

## Where things go

| concern | location | format |
|---|---|---|
| CIM contract | `src/cim/schema/cim.schema.json` | JSON Schema, versioned |
| mapping rules | `src/rulebook/rules/*.yaml` | one file per family, `src/rulebook/__init__.py` lints |
| gate logic | `src/gates/g*_*.py` | one module per gate, pure functions |
| Designer import errors | `src/gates/import_lint/catalogue.yaml` | `status: inferred` until confirmed |
| business elements | `src/dictionary/elements.yaml`, `src/dictionary/crosswalk.yaml` | review-gated |
| artifact pairing | `src/fixtures/pairs.yaml` | hashes only |
| per-form decisions | `src/decisions/<form_id>.yaml` | session URL + proposed/accepted/rejected records |
| target emission | `src/converters/cim_to_inspire/` | JSON plan + Groovy (draft, untested) |
| xPression | `src/converters/xpr_to_cim/` | fails loudly; format unknown |
| agent procedures | `.agents/skills/*/SKILL.md` | one per job |
| launch prompts | `playbooks/*.md` | one page, points at a skill |
| facts that are not code | `knowledge/*.md` | stubs; fill from account owners |

## Code style

Python 3.10+, typed (`list[str]`, `X | None`), ruff clean, imports at top, no silent fallbacks
(`d["key"]` for required keys, no blanket `except Exception`, no `or ""` on required data). Comments are
absent by default. Tests exercise behaviour and failure paths, not YAML contents.

# ccm-migration

Deterministic mechanism for migrating AEM Forms (XDP) toward Quadient Inspire, built for the
customer proof of concept. It implements the design in deliverable
`7-devin-mechanism-rulebook-cim-validators-in-git.md`: the conversion layer is code and data under
test; the agent layer (`.agents/skills`, `playbooks`, `knowledge`) only tells Devin how to work here.

Status: **proof-of-concept scaffold over three partner test forms.** Gates G0-G4 run offline. G5
(Designer import) and G6 (composed PDF comparison) require Quadient access and return `external` until
a person supplies the evidence. See `docs/11-validation-and-gap-report.md` for what is done, what is
not, and every open question.

## Pipeline

```
XDP ──xdp_to_cim──▶ CIM (JSON, schema-validated) ──rulebook──▶ build plan (JSON)
                       │                                           │
                       │ G1 shape, G2 completeness, G3 readiness   │ Groovy ▶ migration-stack ▶ WFD  (G5, external)
                       │                                           │
   reference XML ◀── G0 pairing / G4 coverage ───────────────────  composed PDF (G6, external)
```

| gate | question | runs offline |
|---|---|---|
| G0 | Is this the artifact pair we think it is (hash, revision drift, static-text coverage >= 95%)? | yes |
| G1 | Does the CIM satisfy the schema and reference only ids that exist? | yes |
| G2 | Did extraction account for every source node (field, draw, subform, page)? | yes |
| G3 | Is the form migration-ready: bindings resolved, no draft rules, no manual items outstanding? | yes |
| G4 | Does the reference Quadient XML cover the source fields, sections and static text? | yes |
| G5 | Is the target XML structurally valid and does Designer import it cleanly? | structural only |
| G6 | Does the composed PDF match the reference (structure + visual)? | inspection only |

## How a form gets converted

One form, one Devin session, one PR. The commands below are what the session runs; they are not the
process. The process is `.agents/skills/convert-xdp-form/SKILL.md`, launched from
`playbooks/convert-form.md`, and it ends with a PR that carries the form's decision record
(`src/decisions/<form_id>.yaml`, every blocker/major finding routed with a rationale and the session URL), the
dictionary and rule proposals it produced, the Designer handoff package, and the pinned metrics. G3 counts
unrouted findings (`findings_unrouted`), so a pipeline run without the session's routing is visibly
incomplete. Humans own the acceptance step: decisions (`decided_by`), rules (`reviewed_by`), Designer import
(G5) and composed output (G6). Skills for each stage:

| stage | skill | playbook |
|---|---|---|
| size and order a batch | `assess-form-corpus` | `playbooks/assess-corpus.md` |
| convert one form | `convert-xdp-form` | `playbooks/convert-form.md` |
| hand the plan to Designer, record the result | `prepare-designer-handoff` | (inside convert-form) |
| turn import errors into checks and rules | `triage-designer-errors` | `playbooks/triage-import-errors.md` |
| compare AEM and Quadient PDFs, mutate payload | `validate-pdf-output` | `playbooks/validate-pdf-output.md` |
| move a rule from draft to verified | `review-rulebook-change` | (reviewer PR) |

## Commands the session runs

```
pip install -e ".[dev]"
cp /path/to/artifacts/* src/fixtures/raw/         # not committed; see src/fixtures/raw/README.md
ruff check . && pytest -q
python -m tools.pipeline -o out/              # readiness.json/.md, decisions routed vs routable per form
python -m tools.corpus /path/to/xdps -o out/  # batch tiering and suggested order
cat out/readiness.md
```

Current readiness for the supplied forms (pinned in `tests/test_golden.py`):

| form | G0 | G1 | G2 | G3 | G4 | G5 | G6 |
|---|---|---|---|---|---|---|---|
| 17-0574 | fail (static text 77%) | pass | pass | fail (draft rules, unresolved bindings) | fail (fields 50%) | external | external |
| 18-1026 | pass | pass | pass | fail (draft rules, unresolved bindings) | fail (fields 63%) | external | external |
| 18-1721 | pass (source only) | pass | pass | fail | skipped | skipped | skipped |

Those `fail` verdicts are the point: no rule has a named verifier yet and no target grammar has been
supplied, so no form can honestly be called ready. The pipeline exits 0 unless an integrity gate (G1/G2)
fails; `--strict` makes readiness failures fatal.

## Layout

```
src/cim/                    JSON Schema for the Canonical Intermediate Model
src/converters/xdp_to_cim/  XDP -> CIM extractor (no script execution, size-capped, master pages included)
src/converters/xpr_to_cim/  xPression -> CIM: raises until an export format is supplied
src/converters/cim_to_inspire/  CIM -> build plan (JSON) + draft Groovy for quadient/migration-stack
src/rulebook/               YAML rules by family with class/status/origin/fixtures + linter (README.md: rule shape)
src/gates/                  G0..G6 + target XML inventory + Designer import-error lint catalogue
src/dictionary/             canonical business elements + per-form crosswalk (review-gated)
src/fixtures/               pairs.yaml (hashes only), raw/ (gitignored), import_logs/, composition_logs/
src/decisions/              per-form decision records written by the converting session, accepted by a human
src/tools/                  pipeline.py (all forms), convert.py (one form), corpus.py (batch), report.py (rulebook)
references/             target grammar evidence the rulebook needs; currently a wanted-list only
tests/                  behaviour tests + golden metrics for the three proof forms
.agents/skills/         convert-xdp-form, triage-designer-errors, review-rulebook-change
playbooks/              one-page launch prompts for Devin sessions
knowledge/              account facts that cannot be code (stubs to fill)
docs/                   validation and gap report
```

## Relationship to quadient/migration-stack

The build plan is the hand-off. `src/converters/cim_to_inspire/groovy/CimBuildPlanImport.groovy` reads a
plan and calls `DocumentObjectBuilder`, `VariableBuilder`, `TextStyleBuilder`, `ParagraphStyleBuilder`
and `PageOptions`. **It has not been executed**: Gradle/Maven Central and Inspire Designer were not
reachable where it was written. Treat it as a hypothesis to run with a Quadient practitioner (see the
gap report, section on G5).

---
name: convert-xdp-form
description: Convert one AEM Forms XDP end to end in a Devin session - run the deterministic pipeline, interpret every gate finding, write the form's decision record, propose dictionary rows and rules, prepare the Designer handoff, and open the PR. Use when asked to "convert form <id>", "run the pipeline on <form>", "process <form>", or to add a form to src/fixtures/pairs.yaml.
---

# Convert an XDP form

Every form goes through this procedure in its own Devin session. The Python tools are deterministic
and produce the facts; this skill is the judgment layer that turns each fact into a routed, reviewable
proposal. A form with an unrouted finding, a proposal without rationale, or a PR without a session link
has not been converted.

## Inputs (stop and ask if any is missing)

- the XDP file (`<digits>.xdp`; six digits are the form number, e.g. `181026.xdp` -> `18-1026`)
- if a Quadient reference exists: the exported XML and composed PDF, exact filenames
- the AEM-rendered PDF and one sanitized upstream payload, if available (they unlock G6 later)
- whether the artifacts may be committed (default: no, they stay under gitignored `src/fixtures/raw/`)
- who will import into Designer (name) and who reviews decisions (name)

## Procedure

### 1. Register the form (deterministic)

1. Copy the artifacts into `src/fixtures/raw/` or point `CCM_FIXTURE_ROOT` at them. Do not rename them.
2. Add the form to `src/fixtures/pairs.yaml` with exact filenames and `sha256sum` hashes;
   `python -c "import fixtures; fixtures.load_pairs()"` must pass.
3. Run `python -m tools.pipeline -o out/`.
   - Exit `2`: G1/G2 failed, the extractor lost data. Fix `src/converters/xdp_to_cim/extractor.py` with a test
     in `tests/test_extractor.py` that fails before the fix. Nothing else until this is exit `0`.
   - Exit `0`: open `out/readiness.json` for the form. Every finding below comes from there.

### 2. Read the form before routing anything (judgment)

Write five lines in your notes, you will need them for the PR and the decision rationales:
what the form is for (title, statics), how it is bound (bound %, data schema names), what the scripts do
(classes from `scripts`), what the target reference looks like if there is one (G4 sections, naming prefix),
and whether the revision hint matches the target (G0).

### 3. Route every blocker/major G3 finding into `src/decisions/<form_id>.yaml`

Create the file per `src/decisions/README.md` with `session` set to this session's URL. One record per
(node, finding), `status: proposed`, a one-sentence `rationale` that cites evidence (caption, schema type,
sibling field, reference-target object). Actions by finding:

| finding | usual action | also do |
|---|---|---|
| `G3-UNBOUND`, `G3-NONAME` | `bind_to_element` | add a `proposed` row in `src/dictionary/crosswalk.yaml` (and `elements.yaml` if the element is new) with `evidence`; if no evidence exists, `keep_unbound` and say why |
| `G3-UNRESOLVED-BIND` | `bind_to_element` or `add_rule` | if the binding syntax is one the normaliser (BND-01) misses, draft the rule with `fixtures: [<form_id>]` |
| `G3-VALIDATION`, `VAL-SCRIPT-MANUAL` | `translate_script` or `drop_script` | quote the script's intent (not its code) in `proposal`, name the Quadient construct it maps to; `drop_script` only for capture-channel behaviour that has no print equivalent |
| `UNS-*` unsupported construct | `add_rule` or `manual_design` | draft rule if it will recur; `manual_design` if it is a one-off for the designer |
| `G3-NOITEMS`, `G3-DUPNAME` | `manual_design` or `defer` | say which section disambiguates |
| `G3-DRAFT-RULE` | none (rule-level, not node-level) | list the rule ids in the PR; do not record decisions for them |

Re-run the pipeline. `findings routed` must equal `findings routable` for the form and `G3-STALE-DECISION`
must be absent. Do not set any decision to `accepted`.

### 4. Interpret G4 (reference pairs only)

For each unmatched field: if the target has the object under a name the matcher should have found, fix
`src/gates/matching.py` with a test. If the designer renamed it by convention (prefixes like `EFTAuth`), record the
convention as a `proposed` crosswalk row and note the pattern for OBJ-05/FLD-01 in the PR. If the target lacks
the field, write a `defer` decision against the G3 finding for that node if one exists, otherwise leave it in
the report. If static-text coverage is below GOV-01, stop routing names: the pair is a revision mismatch and
the PR must say so.

### 5. Prepare the Designer handoff

Follow `.agents/skills/prepare-designer-handoff/SKILL.md` for `out/<form_id>.plan.json`. It produces the
import package and the checklist the designer returns. Name the importer in the PR.

### 6. Pin and verify

Add the form's metrics to `tests/test_golden.py` `GOLDEN` from `out/readiness.json` (copy, do not round).
Run `ruff check . && pytest -q`.

### 7. Open the PR

Branch `devin/<timestamp>-convert-<form_id>`. Commit `pairs.yaml`, `src/decisions/<form_id>.yaml`, dictionary
and rulebook changes, golden metrics, tests. Attach or paste `out/readiness.md` and the handoff package; do
not commit `out/`. The PR body reports, from `readiness.json`: every gate verdict; static-text coverage,
field match and exact-name rate; findings routable/routed with the count per action; scripts by class;
draft rules depended on; the decision reviewer and the Designer importer by name; G5/G6 as `external`.
Link this session. Do not describe the form as converted or ready.

## Never

- Hand-write Quadient XML or edit `<form>.plan.json` by hand.
- Change `GOV-01` / G4 thresholds, exit codes, or `decisions` loader checks to make the run green.
- Mark any rule, dictionary row or decision `verified`/`accepted`.
- Write a decision without a rationale, or a rationale that restates the finding.
- Say the form "converted" or "is ready". Say what the gates said and what you proposed.

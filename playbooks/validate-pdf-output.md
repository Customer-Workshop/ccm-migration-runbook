# Playbook: Validate composed output for form `{{form_id}}`

Run when a Quadient-composed PDF exists for a fixed payload. One form per session.

## Inputs

- `form_id`
- `input_payload`: the sanitized XML payload used for the composition
- `quadient_pdf`, `aem_pdf`: both composed/rendered from `input_payload`, exact filenames
- `mutated_payload`, `mutated_quadient_pdf`: second payload with changed values and its composition, or
  `none` (then the session writes the mutated payload and asks `designer_importer` to compose it)
- `composed_by`, `composed_on`, `designer_version`

## Prompt

```
Work in ccm-migration on a new branch devin/<timestamp>-g6-{{form_id}}. Follow
.agents/skills/validate-pdf-output/SKILL.md for form {{form_id}} with the attached payload and PDFs
(composed by {{composed_by}} on {{composed_on}}, Designer {{designer_version}}). Classify every text and
layout difference, run the data-behaviour test on the mutated payload, write
src/fixtures/composition_logs/<sha256>.json with input_data_sha256, and add proposed decisions or draft rule
changes for every failing difference. Re-run the pipeline so G6 reads the record. Open a PR reporting the
G6 verdict, differences per class, mutation results per value class, and the proposals made. Link this
session.
```

## Done when

- Composition record committed with `input_data_sha256` and classified `differences`.
- G6 for the form is `pass` or `fail` from the record, not `external`.
- Every `formatting`, `missing_content`, `extra_content` difference has a proposal or a decision.

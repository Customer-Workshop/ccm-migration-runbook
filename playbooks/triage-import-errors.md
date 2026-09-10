# Playbook: Triage Designer import errors for `{{form_id}}`

Run after a person with Inspire Designer access has imported a generated artifact and has the raw error
output. One import per session.

## Inputs

- `form_id`
- `artifact`: the exact file that was imported (so its sha256 can be computed)
- `errors`: verbatim Designer output (paste or attach; not a summary)
- `imported_by`, `designer_version`, `imported_on`

## Prompt

```
Work in this repo on a new branch. Follow .agents/skills/triage-designer-errors/SKILL.md for form
{{form_id}}. The artifact {{artifact}} was imported by {{imported_by}} in Designer {{designer_version}} on
{{imported_on}} with the errors attached.

Write the import log first, then classify every error against src/gates/import_lint/catalogue.yaml, add or
fix checks so the artifact fails offline before import, add or amend the preventing rule as draft, and
open a PR. In the PR body list each error, whether it was a known or new class, and what the reviewer
must confirm in Designer to verify the rule. Do not edit the generated XML.
```

## Done when

- `src/fixtures/import_logs/<sha256>.json` exists and G5 reports `fail` with the new codes for this artifact.
- The two reference exports still lint clean.
- Each new catalogue entry is `observed` with the verbatim message.
- Metric to record in the PR: number of error classes that were new (target: falls to zero over the pilot).

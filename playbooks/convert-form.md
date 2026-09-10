# Playbook: Convert form `{{form_id}}`

One form, one Devin session, one PR. Paste into a Devin session (or register as an org playbook) with the
inputs filled in. The session is the unit of work; the pipeline is a tool it runs.

## Inputs

- `form_id`: `NN-NNNN` (e.g. `18-1026`)
- `xdp`: path or attachment of `<digits>.xdp`
- `reference_xml`: exported Quadient layout XML, exact filename, or `none`
- `reference_pdf`: composed PDF, exact filename, or `none`
- `aem_pdf`, `input_payload`: AEM-rendered PDF and the sanitized payload it was rendered from, or `none`
- `may_commit_artifacts`: `no` (default) | `yes, approved by <name>`
- `decision_reviewer`: named Quadient/customer person who will accept or reject decisions
- `designer_importer`: named person with Designer access
- `batch_doc`: `docs/batches/<id>.md` if this form is part of an assessed batch, or `none`

## Prompt

```
Work in this repo on a new branch devin/<timestamp>-convert-{{form_id}}. Follow
.agents/skills/convert-xdp-form/SKILL.md for form {{form_id}} using the attached artifacts. Do not rename
the files. Artifacts may be committed: {{may_commit_artifacts}}.

Run the pipeline, then route every blocker/major G3 finding into src/decisions/{{form_id}}.yaml as a proposed
decision with a rationale that cites evidence, with session set to this session's URL. Put dictionary
proposals in src/dictionary/crosswalk.yaml and rule proposals in src/rulebook/rules/ (status draft). Re-run until
findings routed equals findings routable. Prepare the Designer handoff package per
.agents/skills/prepare-designer-handoff/SKILL.md for {{designer_importer}}. Pin the metrics in
tests/test_golden.py. Run ruff and pytest.

Open a PR. In the body report, from out/readiness.json: every gate verdict; static-text coverage, field
match and exact-name rate; findings routable and routed with counts per action; scripts by class; draft
rules depended on; decision reviewer {{decision_reviewer}}; Designer importer {{designer_importer}};
G5 and G6 as external. Attach out/readiness.md and the handoff package. Do not describe the form as
converted or ready, and do not set any decision, rule or dictionary row to accepted or verified.

In the PR body report, from out/readiness.md: the verdict of every gate, static-text coverage, field match
rate, the number of unbound fields, the number of scripts by class, and the list of draft rules the form
depends on. State that G5 and G6 are external and name who will import the artifact in Designer.
Do not describe the form as converted or ready.
```

## Done when

- PR open, CI green (`ruff`, `pytest`, non-strict pipeline).
- `src/decisions/{{form_id}}.yaml` exists with `session`; `findings routed` = `findings routable`; no
  `G3-STALE-DECISION`.
- Every dictionary and rulebook proposal has `evidence`/`origin` and is `proposed`/`draft`.
- Handoff package attached and importer named.
- Raw artifacts not committed unless `may_commit_artifacts` says otherwise.

## What happens next (separate sessions)

- `{{decision_reviewer}}` accepts or rejects decisions in a PR (sets `decided_by`, `decided_on`).
- `{{designer_importer}}` returns the checklist: run `playbooks/triage-import-errors.md`.
- Composed PDF and payload arrive: run `playbooks/validate-pdf-output.md`.

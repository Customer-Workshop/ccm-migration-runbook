# Playbook: Assess a batch of XDPs `{{batch_id}}`

Run once per incoming batch, before any per-form session.

## Inputs

- `batch_id`: short label (e.g. `customer-lob-annuities-01`)
- `xdp_dir`: directory with the XDPs (outside Git unless cleared)
- `may_commit_artifacts`: `no` (default) | `yes, approved by <name>`

## Prompt

```
Work in ccm-migration on a new branch devin/<timestamp>-assess-{{batch_id}}. Follow
.agents/skills/assess-form-corpus/SKILL.md on {{xdp_dir}}. Write docs/batches/{{batch_id}}.md with the
tiering, the shared constructs and recurring elements with form counts, the rulebook and dictionary work
that unlocks the most forms, the proposed conversion order with a reason for every deviation from
tools.corpus's suggested_order, and the forms to hold. Open a PR and link this session. Do not convert any
form and do not commit the XDPs.
```

## Done when

- `docs/batches/{{batch_id}}.md` merged; `out/corpus.md` attached to the PR.
- A `playbooks/convert-form.md` session can be launched for the first form in the order with
  `batch_doc` set.

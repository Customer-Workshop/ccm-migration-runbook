# Decision records

One file per form, `src/decisions/<form_id>.yaml`, written by the Devin session that converts the form and
amended by the human who accepts or rejects each proposal. G3 reads it (GOV-07).

```yaml
decisions_version: 1
form_id: "18-1026"
session: https://<devin-host>/sessions/<id>      # the session that authored the proposals
decisions:
  - id: D-001
    node: ".EFormData.MainSubform.Payer.custFirstNam"   # SOM path from readiness.json
    finding: G3-UNBOUND                                 # finding code from readiness.json
    action: bind_to_element        # bind_to_element | keep_unbound | translate_script | drop_script |
                                   # manual_design | accept_loss | add_rule | defer
    proposal: "element payer_first_name -> EFormsData.PayerData.custFirstNam"
    rationale: "caption 'First name' inside the Payer subform; same element as 17-0574 payer block"
    status: proposed               # proposed (agent) -> accepted | rejected (human)
    decided_by: null               # required once status is accepted/rejected
    decided_on: null
```

Rules:

- Devin writes `proposed` records only. `accepted`/`rejected` need `decided_by` and `decided_on`.
- One record per (node, finding). A finding with an `accepted` record stops counting as human touch;
  `proposed` and `rejected` keep it open; a record whose node or finding the extractor no longer reports is
  flagged `G3-STALE-DECISION` so re-extraction cannot silently orphan a decision.
- `session` is mandatory. It is the audit trail from every routed finding back to the reasoning that produced
  it.
- Proposals that change the dictionary or the rulebook are still made in `src/dictionary/` and `src/rulebook/`; the
  decision record points at them (`action: bind_to_element` / `add_rule`) so the form's status is in one place.
- SOM paths are form metadata. Clearance for committing them is the same question as for `readiness.md`
  (see `knowledge/customer-clearance-boundaries.md`).

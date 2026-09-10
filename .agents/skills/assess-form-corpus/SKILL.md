---
name: assess-form-corpus
description: Profile a batch of XDPs before anyone converts them - tier each form by size, binding, scripting and unsupported constructs, find the constructs and elements shared across the batch, and propose a conversion order and the rulebook or dictionary work that unlocks the most forms. Use when asked to "assess these forms", "size the batch", "which form next", or when a new set of XDPs arrives.
---

# Assess a form corpus

`python -m tools.corpus <dir>` gives the numbers. This skill is the reading of them: which forms share
a problem, which rule or dictionary element would clear the most findings, and in what order the per-form
sessions should run so later forms inherit earlier decisions.

## Procedure

1. Put the XDPs in one directory (outside Git unless cleared). Run
   `python -m tools.corpus <dir> -o out/`. Exit non-zero means an XDP the extractor cannot parse; open an
   issue with the filename and the traceback, do not skip the file silently.
2. Read `out/corpus.json`. For each form note the tier and the dominant finding. Then aggregate across
   forms, by hand or with a short script you attach to the PR:
   - unsupported construct codes (`UNS-*`, `LAY-*`) with the number of forms each appears in
   - unbound-field captions and schema leaf names that recur (candidate canonical elements)
   - script classifications that recur (candidate `VAL-*` translation rules)
   - forms whose `revision_hint` is missing (G0 will not protect them)
3. Propose the batch plan:
   - conversion order: `suggested_order` from the tool, adjusted so that a form introducing a shared
     construct or element is converted before the forms that only reuse it; say why for each move
   - rulebook work: one line per construct that appears in 2+ forms, with the rule family it belongs to and
     the fixture form
   - dictionary work: one line per recurring element with the forms and the evidence (caption, schema type)
   - forms to hold: anything `complex` with `human_touch` above the batch median, until the shared rules exist
4. Write the plan as `docs/batches/<batch_id>.md` (form ids and counts only, no field values), open a PR,
   link this session. Then launch `playbooks/convert-form.md` per form in the proposed order, one session
   each, and reference the batch doc in each.

## Never

- Convert a form as part of the assessment.
- Reorder the batch to make the metrics look better; reorder to maximise reuse and say so.
- Treat tier as readiness. A `simple` form with a draft rule is not ready.

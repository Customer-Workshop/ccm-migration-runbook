---
name: validate-pdf-output
description: Run the G6 output validation for a form in a Devin session - compare the Quadient-composed PDF with the AEM-rendered PDF for the same fixed input, mutate the payload and confirm the changed values land with the right formatting, and write the composition record. Use when asked to "validate the PDF for <form>", "compare AEM and Quadient output", "do the unit test for <form>", or when a designer returns a composed PDF.
---

# Validate composed output (G6)

This replaces the manual Beyond Compare pass plus manual payload edits that the partner does today, with
the same two questions asked in a repeatable order and the answers recorded as data. The composition
itself still happens in Quadient; Devin drives the comparison, decides what each difference means, and
writes the record.

## Inputs (stop and ask if any is missing)

- the fixed input payload used for the composition (XML), its `sha256`
- the Quadient-composed PDF for that payload, and the AEM-rendered PDF for the same payload
- who composed, on what date, with which Designer version
- for the mutation test: a second payload that changes at least one value in each of these classes
  present in the form: currency amount, date, name/address text, a repeating row count, an optional
  section switch. If the designer cannot supply one, ask them to compose with the mutated payload you
  write (change values only, never structure, and keep it sanitized).

## Procedure

### 1. Structural pass (deterministic)

Run `python -m tools.pipeline -o out/` and confirm G6 for the form is `external`, not `fail` (a `fail`
before any record exists means the PDF itself is broken: no pages or truncated; send it back).

### 2. Text and layout comparison (Devin drives, tool extracts)

Extract page text from both PDFs (`pdftotext -layout` if present, otherwise `pypdf`). For every difference,
classify it before deciding anything:

| class | example | decision |
|---|---|---|
| `expected_data` | the payload value renders in both, positions differ within the same block | pass, note the block |
| `formatting` | `1234.5` vs `$1,234.50`, `2026-09-10` vs `09/10/2026` | fail unless a `FLD-*`/`VAL-*` rule says the target format is the agreed one; then `proposed` rule change |
| `missing_content` | text present in AEM, absent in Quadient | fail; map to the source node and check for a `manual_design`/`accept_loss` decision; if none, add a `proposed` decision |
| `extra_content` | Quadient adds text AEM never showed | fail; usually a designer edit, route via `prepare-designer-handoff` inbound step 3 |
| `layout_only` | same text, different page or order | pass if `readiness.json` G4 sections match; else fail with the section named |
| `static_drift` | boilerplate differs | check G0; if the revisions differ this is the revision problem, not a conversion defect |

Record every difference with its class in the `differences` list. Do not drop differences you consider
cosmetic; classify them `layout_only` with a reason.

### 3. Data-behaviour test (the manual "change the premium and see")

For each mutated value in the second payload: find it in the mutated Quadient PDF text, confirm it is
absent from the baseline PDF text, and confirm its rendered format matches the class rule (currency,
date, text). A value that does not appear, appears in the old form, or appears with a different format
than the baseline value of the same field is a `fail` with the source node named. Repeating rows:
row count in the PDF must follow the payload.

### 4. Write the record

`src/fixtures/composition_logs/<sha256 of the quadient pdf>.json` per `src/fixtures/composition_logs/README.md`,
with `input_data_sha256`, the composer, and the classified `differences`. Add `"mutation": {...}` with the
second payload's `sha256` and the per-value results. Re-run the pipeline; G6 must now read the record.

### 5. Report

In the PR: G6 verdict, count of differences per class, mutation results per value class, and every
`proposed` decision or rule change this produced. If the form fails, say which class dominates; that is
the next rulebook or dictionary work item.

## Never

- Compare PDFs composed from different payloads.
- Write a composition record without `input_data_sha256`.
- Call a `formatting` difference acceptable without a rule that says so.
- Edit the PDFs, the payload structure, or the WFD.

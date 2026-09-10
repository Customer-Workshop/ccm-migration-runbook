---
name: prepare-designer-handoff
description: Turn a form's build plan into a Quadient Designer import package and return checklist for the person with Designer access, then record what comes back as the G5 import record. Use when asked to "hand off <form> to the designer", "prepare the import for <form>", or when a designer returns a Designer import result.
---

# Prepare the Designer handoff

Devin has no Designer licence. G5 is decided by a person importing an artifact into Designer and telling
us what happened. This skill makes that round trip unambiguous in both directions so nothing is lost
between the session and the designer's inbox.

## Outbound (after `convert-xdp-form` step 5)

1. Confirm `out/<form_id>.plan.json` exists and `out/readiness.json` shows G1 and G2 `pass`. If not, stop.
2. Build the package directory `handoff/<form_id>/` (gitignored, attach to the PR):
   - `<form_id>.plan.json` and its `sha256`
   - `CimBuildPlanImport.groovy` from `src/converters/cim_to_inspire/groovy/` with the migration-stack version
     pinned in `knowledge/quadient-designer.md` (if the version is `unknown`, say so in the checklist)
   - `src/decisions/<form_id>.yaml` filtered to `manual_design` and `defer` records: these are the things the
     designer must do by hand, in order
   - `CHECKLIST.md` (template below)
3. Read the plan once as the designer would: for every `decisions_required` entry, check a decision record
   exists; for every `skipped` block, check the skip reason is a rule id. Anything else is a bug in
   `build_plan.py`, fix it with a test before sending.
4. Name the importer in the PR and attach the package.

### CHECKLIST.md template

```
Form: <form_id>   plan sha256: <hash>   session: <devin session url>
Migration-stack version used: <x.y.z or unknown>   Designer version: <from knowledge/quadient-designer.md>

1. In migration-examples (migration-config.toml and project-config.toml set, inspireOutput = "Designer"):
     BUILD_PLAN=<path to plan> ../gradlew CimBuildPlanImport
     ../gradlew DeployStyles
     ../gradlew DeployDocumentObjects
   Paste the full console output of all three below, unedited, and attach report/*-deployment-report-*.csv.
   Record defaultTargetFolder and the ICM path of the deployed .wfd.
2. Open the deployed .wfd in Designer and export it as XML (Designer's generic XML export). Record its
   filename and sha256.
3. For each manual_design / defer item listed, say done / not done / not applicable.
4. Compose once with the fixed input data for this form (if you have it). Record the output PDF sha256.

Target: icm://<defaultTargetFolder>/<form>.wfd    Deployment report: <csv filename>

Console output:
<paste>

Manual items:
<list>

Exported XML: <filename> <sha256>      Composed PDF: <filename> <sha256>
```

## Inbound (when the checklist comes back)

1. If the console output has errors: invoke `.agents/skills/triage-designer-errors/SKILL.md`. Every error
   class becomes an import-lint check, a rule and a fixture. Do not fix the form by hand and re-send.
2. Write `src/fixtures/import_logs/<xml_sha256>.json` per `src/fixtures/import_logs/README.md` with the importer's
   name, date, Designer version, verdict and the raw console text. Re-run the pipeline; G5 must now read the
   record instead of `external`.
3. If the designer changed anything by hand that is not a `manual_design` decision, add a `proposed`
   decision for it with `rationale: "designer edit during import, undocumented"` so the gap is visible.
4. If a composed PDF and input data came back, invoke `.agents/skills/validate-pdf-output/SKILL.md`.
5. Update the PR: G5 verdict, new import-lint checks, new rules, and the count of undocumented edits.

## Never

- Send a package whose plan was edited by hand.
- Summarise the designer's console output; store it raw.
- Record an import log without the importer's name and Designer version.

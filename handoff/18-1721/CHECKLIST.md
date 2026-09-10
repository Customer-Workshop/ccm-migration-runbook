Form: 18-1721   plan sha256: 5d9bef27945dad570d043ed54cf64df80c2f0e440467be009bc97b0a7046f21b   session: https://partner-workshops.devinenterprise.com/sessions/060b9626e9ad430186f22f341a34278b
Migration-stack version used: v17.0.30 (commit 5a710c0) is the reference documented in knowledge/quadient-designer.md; the partner's actual release is unknown - record it   Designer version: Quadient Inspire Designer 17.0.436.3

Importer: none named. designer_importer is `none` for this session; G5 stays `external` until a person with
Designer access runs this checklist and the import log is recorded under src/fixtures/import_logs/<sha256>.json.

Package contents:
- 18-1721.plan.json           refreshed build plan emitted by tools.pipeline (G1 pass, G2 pass); do not edit by hand
- CimBuildPlanImport.groovy   migration-stack importer (draft, untested against a live Designer)
- decisions.manual.yaml       manual/defer records filtered from src/decisions/18-1721.yaml
- CHECKLIST.md                this file

Plan facts: 77 variables (65 dictionary:proposed, 12 unresolved),
44 decisions_required (12 target-variable decisions and 32 checkbox/radio rendering decisions), and 2 skipped controls (both DateField1 image controls per UNS-09).
The 67 proposed crosswalk rows resolve their emitted plan variables as dictionary:proposed; the remaining defer records are retained in decisions.manual.yaml.
G0 static-text coverage remains 0.8776 (< GOV-01 0.95). No composed PDF or fixed input data was supplied; the G6 comparison step cannot be performed.

1. In migration-examples (migration-config.toml and project-config.toml set, inspireOutput = "Designer"):
     BUILD_PLAN=<path to plan> ../gradlew CimBuildPlanImport
     ../gradlew DeployStyles
     ../gradlew DeployDocumentObjects
   Paste the full console output of all three below, unedited, and attach report/*-deployment-report-*.csv.
   Record defaultTargetFolder and the ICM path of the deployed .wfd.
2. Open the deployed .wfd in Designer and export it as XML (Designer's generic XML export). Record its
   filename and sha256.
3. For each defer item listed in decisions.manual.yaml, say done / not done / not applicable. Resolve each
   checkbox/radio rendering decision listed by the plan as part of Designer review.
4. A composed PDF and fixed input data were not supplied for this form, so the G6 comparison step cannot be done.

Target: icm://<defaultTargetFolder>/18-1721.wfd    Deployment report: <csv filename>

Console output:
<paste>

Manual items:
- Review every remaining defer record in decisions.manual.yaml in order and record done / not done / not applicable.
- Resolve the plan's checkbox/radio rendering decisions (glyph and radio grouping) in Designer.

Exported XML: <filename> <sha256>      Composed PDF: not supplied; G6 comparison not performed

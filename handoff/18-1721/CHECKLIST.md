Form: 18-1721   plan sha256: 4e852e2b13b2b8828481fafc7f2855d17e477267a338d3866b0e54d93a24f50c   session: https://partner-workshops.devinenterprise.com/sessions/060b9626e9ad430186f22f341a34278b
Migration-stack version used: v17.0.30 (commit 5a710c0) is the reference documented in knowledge/quadient-designer.md; the partner's actual release is unknown - record it   Designer version: Quadient Inspire Designer 17.0.436.3 (WorkFlow export version of Forms_18-1721 (AEM to Quad).xml)

Importer: none named. designer_importer is `none` for this session; G5 stays `external` until a person with
Designer access runs this checklist and the import log is recorded under src/fixtures/import_logs/<sha256>.json.

Package contents:
- 18-1721.plan.json           build plan emitted by tools.pipeline (G1 pass, G2 pass); do not edit by hand
- CimBuildPlanImport.groovy   migration-stack importer (draft, untested against a live Designer)
- decisions.manual.yaml       defer records filtered from src/decisions/18-1721.yaml
- CHECKLIST.md                this file

Plan facts the importer should expect: 77 variables (all unresolved pending pairing confirmation),
109 decisions_required (77 target-variable decisions and 32 checkbox/radio rendering decisions), and 2 skipped controls (both DateField1 image controls per UNS-09).
G0 static-text coverage is 0.8776 (< GOV-01 0.95), so target names remain deferred pending pairing confirmation. No composed PDF or fixed input data was supplied; the G6 comparison step cannot be performed.

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
- Review every defer record in decisions.manual.yaml in order and record done / not done / not applicable.
- Resolve the plan's checkbox/radio rendering decisions (glyph and radio grouping) in Designer.

Exported XML: <filename> <sha256>      Composed PDF: not supplied; G6 comparison not performed

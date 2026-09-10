# Quadient Inspire Designer: environment facts

Scope: when generating or validating Quadient artifacts, or triaging Designer import errors.

## Known (from the supplied reference exports)

- The two reference PDFs were composed by `Quadient Inspire Designer 17.0.436.3` (PDF `/Creator`). Assume this
  version for import until told otherwise; record any other version in the import log.
- The reference layout exports use the declaration + body record structure inventoried by
  `src/gates/target_inventory.py`; `Def.Data`, `Def.Pages`, `Def.Font` and other `Def.*` roots appear as bodies
  without declarations. Two export variants have been observed and both are read by `target_inventory`:
  a bare `<Layout>` root (`18-1026_Quad_2.xml`, the first `17-0574.xml`) and a full workflow export
  `<WorkFlow version="17.0.436.3">` whose single `Layout` module wraps the same record list
  (`Forms_17-0574 (AEM to Quad).xml`; `export_kind: workflow`). ICM packages have not been inspected.
- The first `17-0574.xml` was authored from a different form revision than `170574.xdp` (G0 77%); the
  later `Forms_17-0574 (AEM to Quad).xml` matches at 96%. Ask which export is the reference before pairing.

## Known (from quadient/migration-stack v17.0.30, commit 5a710c0)

- Scripts under `migration-examples/src/main/groovy` with `//! ---` frontmatter are registered as Gradle
  tasks named after the file. `CimBuildPlanImport.groovy` therefore runs as `../gradlew CimBuildPlanImport`
  from `migration-examples/`, with `BUILD_PLAN` in the environment and `-PscriptArgs="..."` for
  `InitMigration` overrides (`--default-target-folder`, `--project-name`, `--inspire-output`).
- The parser only writes the migration model (PostgreSQL, `[dbConfig]` in `migration-config.toml`).
  Deployment is `DeployStyles` then `DeployDocumentObjects`. With `inspireOutput = "Designer"` both build
  WFD XML and call IPS `xml2wfd` (`[inspireConfig.ipsConfig]`, default `localhost:30354`), writing
  `icm://<defaultTargetFolder>/<name>Styles.wfd` and `icm://<defaultTargetFolder>/<object name>.wfd`.
  Designer output deploys Template, Block and Section objects that are not `internal` and not skipped; the
  plan importer marks blocks and pages internal, so one `.wfd` per form is written, named after the form.
- `DeployBaseTemplates` fails by design for Designer output ("Base template deployment is not supported").
  `baseTemplatePath` and `interactiveTenant` are Interactive-only settings.
- `DeployDocumentObjects` writes `report/<project>-deployment-report-<timestamp>.csv` (under `DATA_DIR` if
  set) with per-object status, next action, ICM paths and error text. This CSV plus the console log is the
  G5 evidence.
- IPS also exposes `wfd2xml` and `run`, so export and composition can be scripted once an IPS is reachable.

## TBD (owner: partner Quadient designer)

- Who imports artifacts into Designer for the POC, and the turnaround (currently through an admin; no
  partner engineer has Designer access).
- Whether the partner or customer has official Quadient documentation or the Layout/WFD schema through their licence
  (the team has so far used public docs and a Scribble guide).
- The exact `migration-stack` commit or release the partner runs (v17.0.30 is the reference above), the JDK, and
  the environment values: PostgreSQL host, IPS host and port, `defaultTargetFolder`, project `name`,
  whether IPS is local, remote or containerised, and who holds the credentials.
- Designer quirks that are not yet lint checks (fonts that must be installed, encoding, name-length limits).
  Once observed, each becomes an `observed` entry in `src/gates/import_lint/catalogue.yaml` and is removed here.

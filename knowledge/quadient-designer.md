# Quadient Inspire Designer: environment facts

Scope: when generating or validating Quadient artifacts, or triaging Designer import errors.

## Known (from the supplied reference exports)

- The two reference PDFs were composed by `Quadient Inspire Designer 17.0.436.3` (PDF `/Creator`). Assume this
  version for import until told otherwise; record any other version in the import log.
- The reference layout exports use the declaration + body record structure inventoried by
  `src/gates/target_inventory.py`; `Def.Data`, `Def.Pages`, `Def.Font` and other `Def.*` roots appear as bodies
  without declarations. Only these two exports have been inspected; do not assume other export variants
  (workflow WFD, ICM package) look the same.
- Whether the supplied `.xml` files are full WFD exports or a partial layout export is **not confirmed**.

## TBD (owner: partner Quadient designer)

- Who imports artifacts into Designer for the POC, and the turnaround (currently through an admin; no
  partner engineer has Designer access).
- Whether the partner or customer has official Quadient documentation or the Layout/WFD schema through their licence
  (the team has so far used public docs and a Scribble guide).
- The exact `migration-stack` commit or release used by the partner, and how the Groovy scripts are run (Gradle
  version, JVM, Designer connection).
- Designer quirks that are not yet lint checks (fonts that must be installed, encoding, name-length limits).
  Once observed, each becomes an `observed` entry in `src/gates/import_lint/catalogue.yaml` and is removed here.

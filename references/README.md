# References

Material the rulebook was inferred from, so a reviewer can see what a rule is based on. Nothing here is
customer content; customer artifacts stay in `src/fixtures/raw/` (gitignored).

## Present

Nothing yet. Every rule in `src/rulebook/rules/` with `origin.type: reference_pair` was inferred from the two
supplied Quadient exports (`17-0574.xml`, `18-1026_Quad_2.xml`), which are not committed. Rules with
`origin.type: analysis` referencing `01_Conversion_Rulebook.md` come from the partner/Devin methodology zip,
also not committed.

## Wanted (in priority order)

1. `quadient/` One minimal WFD per construct (table, header, paragraph, radio group, barcode, repeating
   section) exported to XML by a Quadient designer. This is the target grammar the rulebook currently lacks;
   two whole-form exports cannot supply it.
2. `quadient/` The Layout/WFD export schema or DTD and the Designer version it applies to, obtained through
   the partner or customer licence. Public docs and the Scribble guide are not sufficient evidence for `verified`.
3. `quadient/` The `migration-stack` commit or release the partner runs, and the Gradle/JVM setup used to execute
   the Groovy importers.
4. `customer/` The Designer import error list from the leave-request imports (partner email thread), so
   `src/gates/import_lint/catalogue.yaml` entries can move from `inferred` to `observed`.
5. `customer/` The customer data dictionary or data-master naming standard, if one exists (BND-05).
6. `customer/` Fixed input data for each reference PDF (G6 cannot run without it).
7. `xpression/` One xPression export with its schema or vendor documentation, once cleared.

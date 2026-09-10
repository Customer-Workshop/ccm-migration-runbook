# src/fixtures/import_logs

One JSON file per target layout XML, named `<sha256 of the xml>.json`, written by the person who
imported it into Quadient Inspire Designer. Gate G5 stays `external` until this file exists.

```json
{
  "verdict": "pass",
  "designer_version": "17.0.436.3",
  "imported_by": "name@quadient-or-customer",
  "imported_on": "2026-09-10",
  "errors": []
}
```

`errors` is the verbatim Designer error list. Each new error class should also become an entry in
`src/gates/import_lint/catalogue.yaml` (status `observed`) via the `triage-designer-errors` skill.

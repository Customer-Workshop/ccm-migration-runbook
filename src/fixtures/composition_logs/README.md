# src/fixtures/composition_logs

One JSON file per composed PDF, named `<sha256 of the pdf>.json`, written by the person who ran the
composition and the comparison against the reference PDF. Gate G6 stays `external` until it exists.

```json
{
  "verdict": "pass",
  "composed_by": "name@quadient-or-customer",
  "composed_on": "2026-09-10",
  "input_data_sha256": "<sha256 of the fixed input data file>",
  "differences": []
}
```

`input_data_sha256` is mandatory: a PDF comparison without a fixed input data file proves nothing
about the migrated template.

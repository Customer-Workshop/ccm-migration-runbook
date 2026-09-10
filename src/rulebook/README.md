# Rulebook

One YAML file per family under `src/rulebook/rules/`; `src/rulebook/__init__.py` loads and lints them; `python -m tools.report`
renders the Markdown view. The YAML is the only source; do not maintain a prose copy.

## Rule shape

```yaml
family: BND
rules:
  - id: BND-01                     # FAMILY-NN, unique across all files
    title: Normalise bind/@ref into a dotted canonical path
    class: AUTO                    # AUTO | AUTO* | ASSIST | MANUAL
    status: draft                  # draft | verified | deprecated
    source: "bind/@ref with $record., $data., $., ! and [*] stripped"
    target: EFormsData.PayerData.custFirstNam
    evidence: 120/123 fields in 17-0574
    origin: {type: reference_pair, refs: ["17-0574"]}
    fixtures: ["17-0574"]          # form ids from src/fixtures/pairs.yaml
    implemented_in: [converters.xdp_to_cim.extractor.XdpExtractor._binding]
    gates: [G2]                    # which gate fails if the rule is broken
    reviewed_by: null              # set only by the named reviewer, with status: verified
    reviewed_on: null
    parameters: {}                 # optional, rule-specific thresholds
    notes: null                    # optional
```

| field | meaning |
|---|---|
| `class` | `AUTO`: deterministic code. `AUTO*`: deterministic given a maintained dictionary/style library. `ASSIST`: machine proposes, human confirms. `MANUAL`: human decides; the system records the decision as data. |
| `status` | `draft` rules run, but any form that depends on one is not migration-ready (G3, GOV-06). `verified` requires `reviewed_by` and `reviewed_on`. `deprecated` rules are kept for history and never applied. |
| `origin.type` | `reference_pair`, `designer_error`, `coverage_report`, `lossless_gate`, `analysis`, `documentation`. `refs` must point at something a reviewer can open. |
| `implemented_in` | Dotted Python paths; tests import every one. Required for `AUTO`/`AUTO*`. A Groovy script is referenced through the optional `groovy_entrypoint` key instead (see GOV-03). |

## Families

`OBJ` object mapping, `FLD` field identity and controls, `LAY` layout and geometry, `BND` binding and dictionary,
`VAL` validation and scripts, `STY` styles, `UNS` unsupported constructs, `GOV` governance and security.

## Lint

`lint()` rejects: missing keys, ids not matching the file family, duplicates, unknown class/status/gate/origin
type, `verified` without a reviewer, `draft` with a reviewer, `AUTO` without `implemented_in`, fixtures not in
`src/fixtures/pairs.yaml`. `tests/test_rulebook_and_dictionary.py` runs it and also imports every
`implemented_in` reference.

## Changing a rule

Follow `.agents/skills/review-rulebook-change/SKILL.md`. Agents never set `verified`.

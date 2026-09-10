# 11. Validation and gap report: `ccm-migration` against the supplied artifacts

Scope: what was built from deliverable 7 (`7-devin-mechanism-rulebook-cim-validators-in-git.md`), what the
three XDPs and two Quadient pairs actually show when run through it, what is proven versus assumed, and the
status of every open question carried in the earlier deliverables (file 1 section 11, file 9 section 5,
file 10 sections 3 and 4). Every number below is reproducible with `python -m tools.pipeline -o out/` on the
files listed in `src/fixtures/pairs.yaml`; the same numbers are pinned in `tests/test_golden.py`.

Reading guide for each item: **Done** = implemented and tested here. **Evidence-backed** = confirmed from the
supplied artifacts, not from assumption. **Blocked** = needs something only partner, customer or Quadient can
supply. **Ambiguous** = two readings are possible and a decision is needed.

---

## 1. Artifact validation

### 1.1 Pairing (the "compare the numbers in file names" request)

| form | source | target layout XML | composed PDF | verdict |
|---|---|---|---|---|
| 17-0574 | `170574.xdp` (1,111,158 B) | `17-0574.xml` (3,504,237 B) | `17-0574_Quad.pdf` (358,740 B, 9 pages) | pair confirmed by digits; **G0 fails** (see 1.4) |
| 18-1026 | `181026.xdp` (224,864 B) | `18-1026_Quad_2.xml` (453,783 B) | `181026_Quad.pdf` (68,991 B, 1 page) | pair confirmed; G0 pass |
| 18-1721 | `181721.xdp` | none supplied | none supplied | source only; G4-G6 skipped |

- All five XML/XDP files are well-formed XML; all three XDPs contain an XFA `template` packet. Both PDFs have a
  valid header and `%%EOF`, and both report `/Creator` = `Quadient Inspire Designer 17.0.436.3`.
- SHA-256 of every file is recorded in `src/fixtures/pairs.yaml`; G0 fails on any hash mismatch (`G0-HASH`,
  tested). The raw files are gitignored and are not in the PR.
- `18-1026_Quad_2.xml` is kept with that exact name. The `_2` suffix suggests a second export; which version
  the PDF was composed from is not recorded anywhere in the artifacts. **Ambiguous.**

### 1.2 Extraction (G1 shape, G2 losslessness)

| form | fields | statics (draw) | containers (subform) | pages | scripts | unsupported | G1 | G2 |
|---|---|---|---|---|---|---|---|---|
| 17-0574 | 123 | 71 | 41 | 1 | 48 | 0 | pass | pass |
| 18-1026 | 39 | 39 | 23 | 1 | 20 | 7 | pass | pass |
| 18-1721 | 79 | 17 | 20 | 1 | 4 | 2 | pass | pass |

- G2 compares a census of source nodes (`field`, `draw`, `subform`, `pageArea`, `contentArea`) taken directly
  from the XML against what the CIM accounts for. All three forms are 1:1. The earlier partner/Devin
  extractor counted unsupported diagnostics as accounted nodes, which could mask silent drops; that is fixed
  and tested (`test_g2_*`).
- Master-page content (`pageSet/pageArea`) is extracted with `role: master_page` (OBJ-12). The partner
  extractor skipped it, which is where `18-1026`'s barcode zone and page counters live.
- Scripts are classified (`interactive_only`, `calculation`, `validation`), never executed. 17-0574's 48
  scripts are all mechanically transferable classes; 18-1026 has 6 and 18-1721 has 2 that need a person
  (`VAL-SCRIPT-MANUAL`).
- 17-0574 has one `pageArea` in the XDP but its reference PDF has 9 pages and the target XML has 9 `Page`
  objects. The Quadient designer re-authored a flowed layout; the XDP itself does not say how pages break.
  **Ambiguous** whether pagination is a rule (LAY family) or a per-form designer decision.

### 1.3 Readiness (G3)

| form | bound fields | fields needing human touch | draft rules depended on | verdict |
|---|---|---|---|---|
| 17-0574 | 97.6% | 3 | BND-04, FLD-01, OBJ-02, OBJ-05, OBJ-08, OBJ-12 | fail |
| 18-1026 | 18.4% | 32 | + UNS-07, VAL-06 | fail |
| 18-1721 | 0.0% | 79 | BND-04, FLD-01, OBJ-02, OBJ-05, OBJ-12, VAL-06 | fail |

G3 fails for two independent reasons and reports both: (a) every rule is `draft` because no named reviewer
has verified any of the 68 rules (GOV-06), and (b) 18-1026 and 18-1721 are mostly unbound, so target variable
names cannot be derived without a dictionary decision (BND-04, BND-05). Reason (a) will clear the day a
Quadient designer verifies rules in a PR; reason (b) needs the customer's data steward.

### 1.4 Coverage against the Quadient reference (G0, G4)

| form | static text of target covered by source | field match (fuzzy) | exact name match | sections matched | target FormControls | target data Variables |
|---|---|---|---|---|---|---|
| 17-0574 | **77.1%** | 50.4% | 12.2% | 0 / 13 | 271 | 314 |
| 18-1026 | 99.2% | 63.2% | 0.0% | 6 / 9 | 30 | 58 |

- 17-0574: 77.1% static-text coverage is below the GOV-01 threshold (95%). The target-only vocabulary
  (`bariatric`, `covid`, `citizenship`, `bloodwork`, ...) is medical-questionnaire content that does not exist
  in the XDP. The XDP has 123 fields; the target has 271 FormControls and 314 data variables. **The reference
  XML was almost certainly authored from a newer revision of form 17-0574 than the XDP supplied.** Until customer
  confirms which revision each side is, this pair cannot be used as conversion truth; it is still useful as
  target-grammar evidence. Evidence-backed; owner: customer forms team.
- 18-1026: static text matches (99.2%) so the pair is the same revision. Field match is 63.2% and exact-name
  match is 0% because the designer renamed every control (`Billaccno` -> `EFTAuth BillingAcctNum_FormControl`,
  `Freqmnthly` -> `monthlyRadio`) and added a module prefix `EFTAuth` that is not in the XDP (OBJ-04). This is
  the semantic-dictionary problem from file 8 and the 8 Sep session, measured.
- G4 fuzzy matching (`src/gates/matching.py`) is a heuristic to *measure* the naming gap, not to *close* it. It
  must not be used to auto-name variables.

### 1.5 Target structure and Designer import (G5)

- Inventory of both exports: declaration + body record pairs, `Def.*` roots as body-only, zero dangling
  numeric references, zero orphan declarations. The five offline lint checks (IMP-001..005) pass on both.
- Every catalogue entry is `status: inferred`: no real Designer error message has been supplied. The
  partner error email thread from the leave-request imports is still outstanding.
- G5 returns `external` for both pairs. There is no `src/fixtures/import_logs/<sha256>.json` for either artifact,
  so the repo makes no claim that Designer accepted them, even though they came *from* Designer. Blocked;
  owner: whoever has Designer access on the partner side.

### 1.6 Composed output (G6)

- Both PDFs are inspected (header, version 1.7, page count, creator, EOF). Comparison to a composed PDF cannot
  run: no fixed input-data file was supplied for either form, and no headless compose exists on the partner
  side. G6 returns `external`. Blocked; owner: partner (input data) and Quadient/customer (compose).

### 1.7 Pipeline behaviour

- `python -m tools.pipeline -o out/` exits 0 (no integrity failure). `--strict` exits 1 (readiness failures
  are real). Two consecutive runs produce byte-identical output directories (tested).
- `ruff check .` clean; `pytest -q` 82 passed (75 behaviour tests on synthetic fixtures under `tests/data/`,
  7 golden tests that pin the numbers above and skip when the raw files are absent).
- `python -m tools.report` renders the 68 rules to Markdown and exits non-zero on lint problems.

---

## 2. What is done (against deliverable 7)

| deliverable 7 item | status | where |
|---|---|---|
| CIM as JSON Schema, versioned | Done (`cim_version` 1.1) | `src/cim/schema/cim.schema.json`; G1 validates every CIM |
| Rulebook as YAML with status/origin/fixtures, one file per family | Done: 69 rules, 8 families, all `draft`, lint in code | `src/rulebook/rules/*.yaml`, `src/rulebook/__init__.py` |
| Rulebook rendered to prose, not maintained twice | Done | `python -m tools.report` |
| XDP -> CIM converter, lossless by policy | Done, G2 enforces | `src/converters/xdp_to_cim/` |
| xPression -> CIM stub with the questions to answer | Done, raises with the required-inputs list | `src/converters/xpr_to_cim/` |
| CIM -> Inspire through migration-stack, never hand-authored XML | **Partial**: build plan is emitted; Groovy importer is written but has never been executed | `src/converters/cim_to_inspire/` |
| Gates G0-G4 offline in CI | Done | `src/gates/g0..g4`, `.github/workflows/ccm-migration.yml` |
| G5 human import captured as evidence + import-lint catalogue | Done as mechanism; **no real error has been captured yet** | `src/gates/g5_target.py`, `src/gates/import_lint/` |
| G6 oracle (compose + compare) | Done as boundary only; **cannot run** without input data and compose | `src/gates/g6_pdf.py` |
| Fixtures: accepted reference pairs | Done as hashes; raw files gitignored pending clearance | `src/fixtures/pairs.yaml` |
| Dictionary (elements + crosswalk, review-gated) | Done as structure with a handful of `proposed` rows; no `verified` row | `src/dictionary/` |
| AGENTS.md hard rules | Done | `AGENTS.md` |
| Skills: convert, triage, review | Done, plus assess-form-corpus, prepare-designer-handoff, validate-pdf-output | `.agents/skills/` |
| Playbooks | Done as one-page prompts (convert, assess, triage, validate); not yet registered in the partner Devin org | `playbooks/` |
| Per-form decisions persisted as data, tied to the authoring session | Done: `src/decisions/<form_id>.yaml` loader + G3 routing (GOV-07); no record exists yet for the three forms | `src/decisions/`, `src/gates/g3_readiness.py` |
| Knowledge notes (admin, Designer version, clearance) | Done as stubs with `TBD` owners | `knowledge/` |
| Devin Review + required human approval on `src/rulebook/`, `src/cim/`, `src/gates/` | **Not done**: repository settings, needs an admin | GitHub branch protection / CODEOWNERS |
| `references/` (Designer export, schema) | Directory with a wanted-list only | `references/README.md` |

Reused from the partner/Devin methodology zip: the extraction approach (`xdp_to_cim.py`), the coverage idea
(`coverage_report.py`), the target inventory (`quad_inventory.py`), and the rule inventory in
`01_Conversion_Rulebook.md`. Changed: lossless accounting, master pages, no script execution, size caps, hash
pairing, rule status/origin/reviewer, external verdicts for G5/G6, and everything is under test.

---

### 2.1 Operating model: the session is the unit of work

The Python is deterministic on purpose: it makes the session's output checkable. It does not make the
session optional. What the code now enforces per form, and what only a session can do:

| step | who | enforced by |
|---|---|---|
| extract, gate G0-G4, emit plan | tool | `tools.pipeline` exit codes, golden metrics |
| read the form, route every blocker/major finding with a rationale | Devin session | `findings_unrouted` in G3; `G3-NO-DECISIONS`; `G3-STALE-DECISION` on re-extraction |
| propose dictionary rows and rules | Devin session | `proposed`/`draft` status; rulebook lint |
| accept or reject a decision, verify a rule | named human | loader rejects `accepted` without `decided_by`/`decided_on`; GOV-05/06 |
| prepare Designer import package, record what came back | Devin session + importer | `prepare-designer-handoff`; G5 reads `src/fixtures/import_logs/` only |
| turn each Designer error into a check + rule + fixture | Devin session | `triage-designer-errors`; import-lint catalogue `observed` needs verbatim message |
| compare AEM and Quadient PDFs, mutate payload, classify differences | Devin session + composer | `validate-pdf-output`; G6 reads `src/fixtures/composition_logs/` only |
| order a batch so later forms inherit decisions | Devin session | `tools.corpus` + `assess-form-corpus` |

The measurable outputs of a session are therefore: findings routed / routable (per form), proposals per
action, new import-lint classes captured, G6 differences per class, and rules moved toward `verified` by a
reviewer. None of those numbers exist without a session; the pipeline alone produces only the denominators.

On the three proof forms today: `findings_routable` is 3 (17-0574), 38 (18-1026) and 89 (18-1721), all
unrouted, because no decision record has been written yet. The first three conversion sessions are
`playbooks/convert-form.md` for each.

## 3. What needs to be done, mapped to the open questions

### 3.1 File 1 section 11 (Monday 7 Sep questions)

| # | question | status | what the repo does now | next action and owner |
|---|---|---|---|---|
| 1 | Direct Designer access or a daily import window | Blocked | G5 waits for an import log keyed by artifact hash | partner: name the importer; record the first import with `triage-designer-errors` |
| 2 | Headless compose at the customer | Blocked | G6 waits for a composition log keyed by PDF hash | customer/Quadient: confirm Scaler/CLI availability; until then a person composes and records |
| 3 | Exact import format + schema + one exported WFD | Blocked, partly evidenced | Inventory of two exports; grammar inferred, not documented | Quadient designer: one minimal WFD per construct exported to XML, plus the schema through the licence (`references/README.md` items 1-2) |
| 4 | customer data dictionary / enterprise paths | Blocked | `src/dictionary/` structure; 18-1026 and 18-1721 unbound | customer data steward: confirm whether a dictionary exists; review the `proposed` rows |
| 5 | Which form is complex, how many PDF variations | Partly answered | 17-0574 is the complex one (123 fields, 9-page target); variations unknown | partner: supply the input-data files behind each reference PDF |
| 6 | xPression export format and clearance | Blocked | `xpr_to_cim` raises with the required-inputs list | partner lead: format, version, clearance date |
| 7 | Who built the reference pairs, can they review | Blocked | 68 rules await a `reviewed_by` | partner: name the designer; run `review-rulebook-change` on the first family (OBJ) |
| 8 | Phase 1 exit criteria, ACU per form | Proposed | Gates and thresholds are explicit (GOV-01 95%, G4 70%); `--strict` is the exit test | Cognition/partner: agree that "ready" = strict pipeline passes + G5/G6 logs present; start recording ACU per playbook run |
| 9 | Master, styles, data master hand-built by the partner designer | Unknown | Build plan emits style and variable proposals | partner designer: confirm whether they consume the plan or hand-build |
| 10 | Interceptor rule-mapping spike owner | Out of scope for POC forms | No Interceptor/Factory artifacts exist for the three test forms (confirmed 8 Sep) | Defer to Phase 2 inside the customer environment |

### 3.2 File 9 section 5 (8 Sep working-session questions)

| # | question | status | note |
|---|---|---|---|
| 1 | Which Designer format/version are the reference XMLs, how produced | Partly | Designer 17.0.436.3 from PDF metadata; export type (WFD vs layout) unconfirmed |
| 2 | Official Quadient docs and schema access | Blocked | Nothing in `references/`; rules cannot move to `verified` on public docs alone |
| 3 | Designer behind the pairs, construct samples | Blocked | Same as 3.1 #7 |
| 4 | Constructs the three-page form uses that the one-page does not | Answered by data | 17-0574 adds: 13 sections vs 9, 271 FormControls, radio clusters, 9 pages from one XDP pageArea, medical questionnaire tables. `out/17-0574.cim.json` lists them |
| 5 | Where the migration stack is, what it covers, who maintains it | Partly | `github.com/quadient/migration-stack`; builder APIs identified; partner's pinned version unknown |
| 6 | The four PR artifacts, how much of the rulebook is construct-level | Answered | CIM, plan, readiness report, rule/dictionary changes; 68 rules are construct-level, 0 verified |
| 7 | xPression queued behind clearance, export format looked at | Blocked | Nobody has seen an export |
| 8 | ATO legal review triggered, architecture review dated | Blocked | Outside the repo; `knowledge/customer-clearance-boundaries.md` records the 8 Sep state |

### 3.3 File 10 sections 3 and 4 (comparable migrations and coverage caveats)

| item | status | next action |
|---|---|---|
| No completed AEM/xPression -> Quadient migration anywhere in Cognition's record | Confirmed; the repo is written as a first-of-kind POC and says so in `AGENTS.md` and `README.md` | None; do not claim precedent |
| Private channels and DMs were not searched | Open | Run the private/DM search with the account owner's consent if a precedent claim is ever needed |
| Santander UK Quadient team as a source of Quadient practice | Open | Account team introduction; would answer 3.1 #3 faster than waiting on the customer |
| NYL/Capgemini as the second consumer of the CIM and gates | Design accommodated | CIM, gates and inventory are source/target agnostic; `xpr_to_cim` is the template for a third source |
| Consent before naming customers externally | Standing constraint | Nothing in this repo names a customer other than the customer or partner |

### 3.4 Gaps not covered by any earlier question

1. **The Groovy importer has never run.** Gradle/Maven Central and Inspire Designer were unreachable where it
   was written. It compiles in the author's head only. First run needs a Quadient practitioner with the
   migration-stack toolchain. Until then the target-emission boundary is a JSON build plan.
2. **Pagination.** One XDP `pageArea` became 9 Quadient pages. No rule expresses this; the build plan emits
   one page. Decide whether flowed pagination is LAY-family logic or a designer decision (3.1 #9).
3. **Revision drift on 17-0574.** Either obtain the XDP revision that matches the reference, or accept the
   pair as target-grammar evidence only and drop it from G4 scoring.
4. **Module prefix (`EFTAuth`).** OBJ-04 is `ASSIST`; the plan carries it as a decision. Needs a customer naming
   rule or a per-form input in the playbook.
5. **CI cannot run the pipeline.** Raw artifacts are gitignored, so CI runs lint, tests and the rulebook
   report only; the pipeline step runs only when `vars.CCM_FIXTURE_ROOT` is set on a runner that has the files.
6. **Branch protection / CODEOWNERS** for `src/rulebook/`, `src/cim/`, `src/gates/` with the Quadient reviewer as required
   approver is a repository setting, not code, and has not been applied.
7. **`18-1721` has no target.** Either it was never converted, or its pair was not supplied. Ask.

---

## 4. Ambiguities that need a decision

1. **Which file is "file 10".** The numbered deliverables put comparable-account research at 10 and the
   Monday questions at file 1 section 11. This report maps all three question sets (1 s11, 9 s5, 10 s3-4).
2. **Are the supplied `.xml` files full WFD exports or Layout-only exports?** Their record structure is
   consistent with a Layout export; workflow/data-master objects were not found. Affects what the Groovy
   importer must produce.
3. **`18-1026_Quad_2.xml` versus the PDF.** `_2` implies an earlier export existed; the PDF's origin version
   is unknown.
4. **Committing raw artifacts.** Even hashes plus SOM paths in the readiness report reveal field names and
   captions. Clearance for the current gitignored arrangement has been assumed, not confirmed.
5. **Threshold values.** GOV-01 95% and G4 70% are proposals from the analysis, not customer acceptance criteria.
6. **Devin's role in naming.** G4 fuzzy matching and `target_variable_hint` are measurement aids; whether customer
   allows any machine-proposed variable name to reach a data master without review is a governance decision.

---

## 5. Recommended order of work (each item is one Devin session unless noted)

1. Name the Quadient reviewer and verify the OBJ family (12 rules) on 18-1026 using `review-rulebook-change`.
   This is the first time any rule stops being `draft`. Human time: about half a day.
2. Obtain one Designer import of `out/18-1026.plan.json` via the Groovy importer with a Quadient practitioner;
   record the import log; run `triage-designer-errors`. External dependency: toolchain + Designer.
3. Request the construct-level WFD exports and the schema (`references/README.md` items 1-2). External.
4. Resolve the 17-0574 revision question with customer; re-pin golden metrics.
5. Hand the 32 + 79 unbound fields of 18-1026 and 18-1721 to the data steward as `proposed` crosswalk rows.
6. Register the two playbooks and the three knowledge notes in the partner Devin org; apply CODEOWNERS.
7. xPression: as soon as one export is cleared, implement `xpr_to_cim` against the same CIM and re-use every
   gate unchanged.

# the customer: what may leave the network

Scope: when handling customer artifacts, fixtures, or anything that could leave the customer environment.

## Known

- The three proof forms (`17-0574`, `18-1026`, `18-1721`) are **partner-built test forms**, not confirmed customer
  production forms. There is no Interceptor Java or Factory JSON for them.
- Raw artifacts are gitignored in this repo (`src/fixtures/raw/`); `src/fixtures/pairs.yaml` holds hashes only.
  Committing them requires explicit written approval recorded in the PR.
- No xPression export has been supplied. The export format and its clearance status are unknown
  (`src/converters/xpr_to_cim/` fails deliberately until they are).
- Phase 2 (customer production forms, Interceptor, Factory maps, data masters) is expected to run inside the customer environment after
  ATO; ATO architecture review is undated and a legal review step was missed as of 8 Sep 2026.

## TBD (owner: partner lead / customer security)

- Whether the proof-form XDPs, reference XMLs and PDFs are cleared for a Cognition-hosted repo, or only for
  the partner-hosted one.
- Whether hashes and derived metrics (field counts, coverage percentages, SOM paths in readiness reports) are
  cleared. SOM paths and captions can reveal business content.
- xPression export clearance date and format.
- ATO status and the security, legal and architecture-review gates that remain.

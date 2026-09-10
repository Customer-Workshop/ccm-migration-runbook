# src/fixtures/raw

Drop the customer-supplied artifacts here (or point `CCM_FIXTURE_ROOT` at the directory
that holds them). Nothing in this directory is committed; `../pairs.yaml` records the
SHA-256 of every artifact so gate G0 can prove the file on disk is the one the rulebook
and golden metrics were derived from.

Expected files for the current proof forms:

| form | source | target layout XML | composed PDF |
|---|---|---|---|
| 17-0574 | `170574.xdp` | `17-0574.xml` | `17-0574_Quad.pdf` |
| 18-1026 | `181026.xdp` | `18-1026_Quad_2.xml` | `181026_Quad.pdf` |
| 18-1721 | `181721.xdp` | `Forms_18-1721 (AEM to Quad).xml` | not supplied |

The filename `18-1026_Quad_2.xml` is what was actually supplied; earlier documents call
it `18-1026_Quad.xml`. Do not rename it, update `pairs.yaml` if a different file arrives.

`tests/test_golden.py` skips when these files are absent, so CI is green without them.

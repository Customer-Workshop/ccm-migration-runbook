# the customer: naming and revision conventions

Scope: when naming target objects or variables, or reading form revision markers.

## Known (from the three proof forms and two reference exports)

- Form identity is the six-digit file name (`181026.xdp` -> form code `18-1026`). Target filenames are not
  consistent (`17-0574.xml` vs `18-1026_Quad_2.xml`, `17-0574_Quad.pdf` vs `181026_Quad.pdf`); pairing is
  explicit in `src/fixtures/pairs.yaml`, never inferred from names alone.
- Revision markers appear in static text as `(NNNN)` or `REV xxx` (`extractor.REVISION`). `17-0574` static
  text overlaps its reference export at 77% and G0 flags likely revision drift; nobody has confirmed which
  revision the reference XML was authored from.
- Page-level target objects are prefixed with the form code; FormControls carry a module tag (`EFTAuth` in
  `17-0574`) that is not derivable from the XDP (OBJ-04). It is a human decision recorded in the build plan.
- Target variable names in the reference exports follow the XDP binding leaf in most cases
  (`EFormsData.PayerData.custFirstNam`), but BND-05 requires the enterprise dictionary to decide, not the
  leaf.

## TBD (owner: customer forms team / data steward)

- Whether a customer data dictionary or data-master naming standard exists and can be shared.
- The rule for module tags: who assigns them and whether a list exists.
- Whether `18-1721` has a Quadient counterpart that was simply not supplied.
- How revisions are tracked in AEM (form manager metadata vs static text) so G0 can compare authoritatively.

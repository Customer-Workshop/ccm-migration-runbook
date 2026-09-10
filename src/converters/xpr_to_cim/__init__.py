"""xPression -> CIM.  Deliberately not implemented.

No xPression export has been supplied and the export format is not known
(open question 8 in deliverable file 10).  Until an artifact arrives this
package exists so that the pipeline has one obvious place to fail.

To unblock, supply:
  - one exported xPression document/package per proof form (format and version),
  - the schema or vendor documentation for that export,
  - the security-clearance status that allows the artifact to leave the customer environment,
  - the paired Quadient output, if any, so gates G0 and G4 can run.
"""

from pathlib import Path

REQUIRED_INPUTS = (
    "xPression export artifact (format + version)",
    "export schema or vendor documentation",
    "security clearance for the artifact",
    "paired Quadient output for G0/G4",
)


class XpressionFormatUnknown(NotImplementedError):
    pass


def extract(path: str | Path) -> dict:
    raise XpressionFormatUnknown(
        f"cannot extract {path}: xPression export format is undefined; required inputs: {', '.join(REQUIRED_INPUTS)}"
    )

"""Canonical Intermediate Model (CIM).

The CIM is defined once, as JSON Schema, in ``schema/cim.schema.json``. Python code treats a CIM as a
plain ``dict`` validated by gate G1 (``gates.g1_shape``) immediately after extraction; there is no
parallel dataclass model to keep in sync. The Groovy side (``src/converters/cim_to_inspire``) consumes the
build plan derived from the CIM, not the CIM itself, so the schema is the only contract shared across
languages.

Top-level keys: ``cim_version``, ``form``, ``pages``, ``containers``, ``fields``, ``statics``,
``styles``, ``data_dictionary``, ``diagnostics``. Node identity is the XFA SOM path (FLD-01); node ids
(``CT``, ``FD``, ``SX``, ``ST``, ``PG`` prefixes) are stable per extraction and used for cross-references.
"""

from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "cim.schema.json"
CIM_VERSION = "1.1"

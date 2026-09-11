"""Namespace constants and pure text/measurement helpers shared by the XDP extractor modules."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

XFA_TEMPLATE_NS = "http://www.xfa.org/schema/xfa-template/"
XSD_NS = "{http://www.w3.org/2001/XMLSchema}"
XHTML_NS = "{http://www.w3.org/1999/xhtml}"

BASE64_BLOB = re.compile(r"^[A-Za-z0-9+/=\s]{200,}$")
MEASURE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*(mm|cm|in|pt|mp)?\s*$")
MM_PER_UNIT = {"mm": 1.0, "cm": 10.0, "in": 25.4, "pt": 25.4 / 72.0, "mp": 25.4 / 72000.0}


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def to_mm(value: str | None) -> float | None:
    """Convert an XFA measurement to millimetres. Returns None when absent/unparseable."""
    if not value:
        return None
    m = MEASURE.match(value)
    if not m:
        return None
    return round(float(m.group(1)) * MM_PER_UNIT[m.group(2) or "mm"], 4)


def to_pt(value: str | None) -> float | None:
    mm = to_mm(value)
    return None if mm is None else round(mm * 72 / 25.4, 2)


def text_of(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return " ".join("".join(el.itertext()).split())


def is_blob(s: str) -> bool:
    return bool(s) and " " not in s and bool(BASE64_BLOB.match(s))


def pascal(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", text)
    words = [w for w in cleaned.split() if w]
    if not words:
        return None
    return "".join(w[:1].upper() + w[1:] for w in words[:6])

"""Static content classification (OBJ-05, LAY-10) and form-title evidence (GOV-02)."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from converters.xdp_to_cim.xfa import XHTML_NS, is_blob, text_of, to_mm, to_pt

LINE_THICKNESS_MM = 1.5
INLINE_SIZE = re.compile(r"font-size\s*:\s*([\d.]+\s*(?:pt|mm|in|cm)?)", re.I)
INLINE_BOLD = re.compile(r"font-weight\s*:\s*(bold|[6-9]00)", re.I)
TITLE_MAX_LEN = 100
TITLE_MIN_LEN = 9
NOTE_PREFIX = re.compile(r"^(?:note|important|warning|instructions?)\b", re.I)
ITEM_MARKER = re.compile(r"^[A-Za-z][.)]\s")


@dataclass(frozen=True)
class DrawContent:
    kind: str
    text: str | None
    image_ref: str | None


@dataclass(frozen=True)
class TitleRun:
    text: str
    size_pt: float | None
    bold: bool
    order: int


def draw_content(el: ET.Element, tag, som: str) -> DrawContent:
    """Classify a ``<draw>``: text, rich_text, image, line, rectangle, or unknown.

    A draw whose ``<value>`` is absent or empty is a geometric object when its
    border is visible (filled or with drawn edges); thin ones are lines, the
    rest rectangles. Anything else stays ``unknown`` so G2 can report it.
    """
    value = el.find(tag("value"))
    kind, text, image_ref = "unknown", None, None
    if value is not None:
        for child in value:
            name = child.tag.rsplit("}", 1)[-1]
            if name in ("text", "exData"):
                raw = text_of(child)
                if is_blob(raw):
                    kind, image_ref = "image", f"asset:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"
                else:
                    kind, text = ("rich_text" if name == "exData" else "text"), raw
            elif name == "image":
                kind = "image"
                image_ref = f"asset:{hashlib.sha256((child.text or som).encode()).hexdigest()[:16]}"
            elif name == "line":
                kind = "line"
            elif name == "rectangle":
                kind = "rectangle"
    if kind == "unknown":
        kind = _valueless_kind(el, tag)
    return DrawContent(kind, text, image_ref)


def _valueless_kind(el: ET.Element, tag) -> str:
    border = el.find(tag("border"))
    if border is None:
        return "unknown"
    fill = border.find(tag("fill"))
    filled = fill is not None and fill.find(tag("color")) is not None and fill.get("presence") != "hidden"
    edges = [e for e in border.findall(tag("edge")) if e.get("presence") != "hidden"]
    if not filled and not edges:
        return "unknown"
    w, h = to_mm(el.get("w")), to_mm(el.get("h"))
    if w is not None and h is not None and min(w, h) <= LINE_THICKNESS_MM < max(w, h):
        return "line"
    return "rectangle"


def title_runs(el: ET.Element, tag, order: int) -> list[TitleRun]:
    """Title evidence for a draw: one run per rendered paragraph with its effective size and weight.

    Rich text paragraphs carry inline ``font-size``/``font-weight``; plain text
    inherits the draw's ``<font>``. Returns an empty list for draws without text.
    """
    font = el.find(tag("font"))
    base_size = to_pt(font.get("size")) if font is not None else None
    base_bold = font is not None and font.get("weight") == "bold"
    value = el.find(tag("value"))
    if value is None:
        return []
    runs: list[TitleRun] = []
    for child in value:
        name = child.tag.rsplit("}", 1)[-1]
        if name == "text":
            raw = text_of(child)
            if raw and not is_blob(raw):
                runs.append(TitleRun(raw, base_size, base_bold, order))
        elif name == "exData":
            paragraphs = list(child.iter(XHTML_NS + "p"))
            if not paragraphs:
                raw = text_of(child)
                if raw and not is_blob(raw):
                    runs.append(TitleRun(raw, base_size, base_bold, order))
                continue
            for p in paragraphs:
                raw = text_of(p)
                if not raw or is_blob(raw):
                    continue
                style = p.get("style") or ""
                m = INLINE_SIZE.search(style)
                size = to_pt(m.group(1).replace(" ", "")) if m else base_size
                bold = base_bold or bool(INLINE_BOLD.search(style))
                runs.append(TitleRun(raw, size, bold, order))
    return runs


def is_title_candidate(text: str) -> bool:
    """A title is a short upper-case phrase of at least two words that starts with a letter and carries
    no digits, item marker (``B.``) or note prefix."""
    if not (TITLE_MIN_LEN <= len(text) <= TITLE_MAX_LEN) or not text[0].isalpha():
        return False
    if text.upper() != text or re.search(r"\d", text) or NOTE_PREFIX.match(text) or ITEM_MARKER.match(text):
        return False
    return len(re.findall(r"[A-Za-z]{2,}", text)) >= 2


def select_title(runs: list[TitleRun]) -> str | None:
    """GOV-02: the form title is the largest, boldest upper-case run; earliest in document order on ties."""
    candidates = [r for r in runs if is_title_candidate(r.text)]
    if not candidates:
        return None
    best = min(candidates, key=lambda r: (-(r.size_pt or 0.0), not r.bold, r.order))
    return best.text

"""Style extraction (STY-01, STY-02, OBJ-07): font/para/border of a draw or field -> shared style entry."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import OrderedDict

from converters.xdp_to_cim.xfa import to_mm, to_pt


def _colour(parent: ET.Element | None, tag: str) -> str | None:
    if parent is None:
        return None
    fill = parent.find(tag("fill"))
    if fill is None:
        return None
    colour = fill.find(tag("color"))
    return colour.get("value") if colour is not None else None


def style_entry(el: ET.Element, tag) -> dict | None:
    """Return the style attributes of ``el`` or None when it carries no style nodes.

    ``tag`` maps a local XFA name to its namespaced tag (``XdpExtractor.t``).
    """
    font = el.find(tag("font"))
    para = el.find(tag("para"))
    border = el.find(tag("border"))
    if font is None and para is None and border is None:
        return None
    return {
        "typeface": font.get("typeface") if font is not None else None,
        "size_pt": to_pt(font.get("size")) if font is not None else None,
        "bold": (font.get("weight") == "bold") if font is not None else None,
        "italic": (font.get("posture") == "italic") if font is not None else None,
        "underline": bool(font.get("underline")) if font is not None else None,
        "color": _colour(font, tag),
        "align": para.get("hAlign") if para is not None else None,
        "v_align": para.get("vAlign") if para is not None else None,
        "border": {"present": True} if border is not None else None,
        "fill": _colour(border, tag),
        "margins_mm": {
            "top": to_mm(para.get("spaceAbove")),
            "bottom": to_mm(para.get("spaceBelow")),
        }
        if para is not None
        else None,
    }


def style_name(entry: dict) -> str:
    """STY-02: target style names follow <Font>_<Size>pt[_Bold][_Italic]."""
    size = entry.get("size_pt")
    parts = ["Arial"]  # font substitution policy, see rule STY-01
    if size:
        parts.append(f"{round(size, 1):g}pt")
    if entry.get("bold"):
        parts.append("Bold")
    if entry.get("italic"):
        parts.append("Italic")
    return "_".join(parts)


class StyleRegistry:
    """De-duplicates style entries and hands out stable ``STnnn`` ids in first-seen order."""

    def __init__(self) -> None:
        self._entries: OrderedDict[str, dict] = OrderedDict()

    def register(self, entry: dict) -> str:
        key = json.dumps(entry, sort_keys=True)
        if key not in self._entries:
            stored = dict(entry)
            stored["id"] = f"ST{len(self._entries) + 1:03d}"
            stored["usage_count"] = 0
            stored["target_name_hint"] = style_name(stored)
            self._entries[key] = stored
        self._entries[key]["usage_count"] += 1
        return self._entries[key]["id"]

    def __len__(self) -> int:
        return len(self._entries)

    def values(self) -> list[dict]:
        return list(self._entries.values())

#!/usr/bin/env python3
"""Extract an AEM XFA/XDP template into the Canonical Intermediate Model (CIM).

Deterministic, read-only, stdlib-only. The extractor never guesses silently: every
derived value carries a rule id and a confidence classification, and everything it
cannot establish is emitted into ``diagnostics.review_queue``. Embedded scripts are
classified as text and never executed.

The walk over the template lives here; idiom tables and pure helpers live in the
sibling modules ``scripts`` (script classification), ``styles`` (font/para/border),
``bindings`` (bind/@ref and datatypes), ``statics`` (draw content, title evidence)
and ``xfa`` (namespaces, measurements, text).

Usage:
    python3 -m converters.xdp_to_cim FORM.xdp -o out/FORM.cim.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter

from cim import CIM_VERSION
from converters.xdp_to_cim.bindings import binding_of, datatype_for, leaf_types
from converters.xdp_to_cim.scripts import classify_script, script_targets
from converters.xdp_to_cim.statics import TitleRun, draw_content, select_title, title_runs
from converters.xdp_to_cim.styles import StyleRegistry, style_entry
from converters.xdp_to_cim.xfa import XFA_TEMPLATE_NS, XSD_NS, is_blob, local, pascal, text_of, to_mm

EXTRACTOR = "xdp_to_cim/1.2"

# Maximum accepted input size (defensive: XDP files are untrusted input).
MAX_INPUT_BYTES = 256 * 1024 * 1024

UI_TO_KIND = {
    "textEdit": "text",
    "checkButton": "checkbox",
    "dateTimeEdit": "date",
    "numericEdit": "number",
    "choiceList": "dropdown",
    "barcode": "barcode",
    "imageEdit": "image",
    "signature": "signature",
    "button": "action",
    "passwordEdit": "text",
    "picture": "image",
}

HEADING_NUM = re.compile(r"^\s*(\d+)[.)]\s+(.+)$")
REVISION = re.compile(r"\(\s*(\d{3,4})\s*\)|\b(?:REV|Rev\.?)\s*([A-Za-z0-9/\-]+)")
FORM_CODE = re.compile(r"\b(\d{2}-\d{4})\b")
NAME_TOKEN = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")

ROLE_TOKENS = (
    ("footer", {"footer"}),
    ("header", {"header", "brand", "logo"}),
    ("signature", {"signature", "sign", "sig"}),
    ("barcode_zone", {"barcode"}),
)

PASSIVE_TEMPLATE_CHILDREN = frozenset(
    {
        "pageSet",
        "contentArea",
        "medium",
        "occur",
        "desc",
        "extras",
        "proto",
        "variables",
        "bind",
        "event",
        "border",
        "margin",
        "para",
        "font",
        "keep",
        "break",
        "breakBefore",
        "breakAfter",
        "overflow",
        "bookend",
        "traversal",
        "calculate",
        "validate",
        "assist",
        "setProperty",
    }
)


def name_tokens(name: str | None) -> set[str]:
    """Split a template name into lower-case words on case and non-alphanumeric boundaries."""
    return {t.lower() for t in NAME_TOKEN.findall(name or "")}


def is_signature_name(name: str | None) -> bool:
    return (name or "").lower().endswith("sig")


def _heading_key(text: str) -> str:
    """Heading text without its section number, as stored in ``container.section_heading``."""
    m = HEADING_NUM.match(text)
    return (m.group(2) if m else text).strip()


class XdpExtractor:
    def __init__(self, path: str) -> None:
        size = os.path.getsize(path)
        if size > MAX_INPUT_BYTES:
            raise ValueError(f"input too large ({size} bytes); refusing to parse")
        with open(path, "rb") as fh:
            payload = fh.read()
        self.path = path
        self.sha256 = hashlib.sha256(payload).hexdigest()
        # ET does not expand external entities, so parsing is safe for untrusted input.
        self.root = ET.fromstring(payload)
        self.ns = self._template_namespace()
        self.template = self._first_child("template")
        if self.template is None:
            raise ValueError("no XFA template packet found")
        self.containers: list[dict] = []
        self.fields: list[dict] = []
        self.statics: list[dict] = []
        self.pages: list[dict] = []
        self.styles = StyleRegistry()
        self.review: list[dict] = []
        self.unsupported: list[dict] = []
        self._title_runs: list[TitleRun] = []
        self._seq: Counter = Counter()
        self._som_seen: Counter = Counter()

    # ---------------------------------------------------------------- plumbing
    def _template_namespace(self) -> str:
        for el in self.root.iter():
            if el.tag.startswith("{") and XFA_TEMPLATE_NS in el.tag:
                return el.tag[1:].split("}")[0]
        return XFA_TEMPLATE_NS + "3.3/"

    def t(self, name: str) -> str:
        return f"{{{self.ns}}}{name}"

    def _first_child(self, name: str) -> ET.Element | None:
        for child in self.root:
            if local(child.tag) == name:
                return child
        return None

    def _id(self, prefix: str) -> str:
        self._seq[prefix] += 1
        return f"{prefix}{self._seq[prefix]:04d}"

    def _unique_som(self, path: str) -> str:
        """XFA allows sibling nodes to share a name; index them so SOM is a stable key."""
        path = path or "/"
        self._som_seen[path] += 1
        n = self._som_seen[path]
        return path if n == 1 else f"{path}[{n - 1}]"

    def _prov(self, som: str, rule_id: str | None = None) -> dict:
        return {
            "source": "{}#{}".format(os.path.basename(self.path), som or "/"),
            "extractor": EXTRACTOR,
            "rule_id": rule_id,
        }

    def _flag(
        self,
        code: str,
        severity: str,
        message: str,
        node: str | None = None,
        rule_id: str | None = None,
        owner: str = "analyst",
        unsupported: bool = False,
    ) -> None:
        item = {
            "code": code,
            "severity": severity,
            "message": message,
            "node": node,
            "rule_id": rule_id,
            "owner": owner,
        }
        (self.unsupported if unsupported else self.review).append(item)

    def _geometry(self, el: ET.Element, positioned: bool) -> dict:
        return {
            "x_mm": to_mm(el.get("x")),
            "y_mm": to_mm(el.get("y")),
            "w_mm": to_mm(el.get("w")),
            "h_mm": to_mm(el.get("h")),
            "page_index": None,
            "anchor": el.get("anchorType"),
            "positioned": positioned,
        }

    # ------------------------------------------------------------------ pages
    def extract_pages(self) -> None:
        for area in self.template.iter(self.t("pageArea")):
            medium = area.find(self.t("medium"))
            width = to_mm(medium.get("short")) if medium is not None else None
            height = to_mm(medium.get("long")) if medium is not None else None
            orientation = (medium.get("orientation") if medium is not None else None) or "portrait"
            if orientation == "landscape" and width and height:
                width, height = height, width
            content = []
            for ca in area.iter(self.t("contentArea")):
                content.append(
                    {
                        "x_mm": to_mm(ca.get("x")),
                        "y_mm": to_mm(ca.get("y")),
                        "w_mm": to_mm(ca.get("w")),
                        "h_mm": to_mm(ca.get("h")),
                        "page_index": len(self.pages),
                        "anchor": ca.get("name"),
                        "positioned": True,
                    }
                )
            self.pages.append(
                {
                    "id": self._id("PG"),
                    "name": area.get("name"),
                    "medium": {
                        "width_mm": width,
                        "height_mm": height,
                        "stock": medium.get("stock") if medium is not None else None,
                        "orientation": orientation,
                    },
                    "content_areas": content,
                    "occur": self._occur(area),
                }
            )
            if not content:
                self._flag(
                    "LAY-NOCONTENTAREA",
                    "major",
                    "pageArea without contentArea: page geometry cannot be derived",
                    node=area.get("name"),
                    rule_id="LAY-01",
                    owner="designer",
                )

    def _occur(self, el: ET.Element) -> dict | None:
        occ = el.find(self.t("occur"))
        if occ is None:
            return None

        def as_int(v: str | None) -> int | None:
            if v is None:
                return None
            return -1 if v == "-1" else (int(v) if v.isdigit() else None)

        maximum = as_int(occ.get("max"))
        return {
            "min": as_int(occ.get("min")),
            "max": maximum,
            "initial": as_int(occ.get("initial")),
            "repeating": bool(maximum is not None and (maximum == -1 or maximum > 1)),
        }

    # ----------------------------------------------------------------- styles
    def _style_ref(self, el: ET.Element) -> str | None:
        entry = style_entry(el, self.t)
        return None if entry is None else self.styles.register(entry)

    # ------------------------------------------------------------- containers
    def walk(self) -> None:
        body = self.template.find(self.t("subform"))
        if body is None:
            raise ValueError("template has no root subform")
        self._walk_subform(body, parent_id=None, som="", depth=0)
        root_som = ".{}".format(body.get("name")) if body.get("name") else ""
        for page_set in body.iter(self.t("pageSet")):
            for area in page_set.iter(self.t("pageArea")):
                self._walk_subform(
                    area, parent_id=self.containers[0]["id"], som=root_som, depth=1, role_override="master_page"
                )

    def _walk_subform(
        self, el: ET.Element, parent_id: str | None, som: str, depth: int, role_override: str | None = None
    ) -> None:
        name = el.get("name")
        path = f"{som}.{name}" if name else som
        heading, number = self._heading_of(el)
        container = {
            "id": self._id("CT"),
            "parent_id": parent_id,
            "som": self._unique_som(path),
            "name": name,
            "depth": depth,
            "layout": el.get("layout") or ("position" if depth == 0 else None),
            "role": "unknown",
            "section_number": number,
            "section_heading": heading,
            "target_name_hint": pascal(heading) if heading else None,
            "geometry": self._geometry(el, (el.get("layout") or "position") == "position"),
            "occur": self._occur(el),
            "break_before": None,
            "keep_together": None,
            "confidence": {
                "structural": "deterministic",
                "semantic": "heuristic" if heading else "unresolved",
                "score": 0.9 if heading else 0.4,
                "reasons": ["section heading draw found"] if heading else ["no heading draw; container name is opaque"],
            },
            "provenance": self._prov(path, rule_id="OBJ-02"),
        }
        container["role"] = role_override or self._container_role(container, el)
        if role_override:
            container["provenance"]["rule_id"] = "OBJ-12"
        self.containers.append(container)
        if not heading and container["role"] == "section":
            self._flag(
                "OBJ-NONAME",
                "minor",
                "section container has no heading text; target container name must be supplied by an analyst",
                node=path,
                rule_id="OBJ-03",
            )
        for child in el:
            tag = local(child.tag)
            if tag == "subform":
                self._walk_subform(child, container["id"], path, depth + 1)
            elif tag == "subformSet":
                self._flag(
                    "OBJ-SUBFORMSET",
                    "major",
                    "subformSet (choice/alternate content) has no direct Quadient analogue",
                    node=path,
                    rule_id="UNS-05",
                    unsupported=True,
                )
                for inner in child.findall(self.t("subform")):
                    self._walk_subform(inner, container["id"], path, depth + 1)
            elif tag == "field":
                self._field(child, container, path)
            elif tag == "draw":
                self._draw(child, container, path)
            elif tag == "exclGroup":
                self._excl_group(child, container, path)
            elif tag == "area":
                self._walk_subform(child, container["id"], path, depth + 1)
            elif tag in PASSIVE_TEMPLATE_CHILDREN:
                continue
            else:
                self._flag(
                    "OBJ-UNWALKED",
                    "minor",
                    f"template child <{tag}> is not modelled by the extractor",
                    node=path,
                    rule_id="OBJ-01",
                    unsupported=True,
                )
        if container["role"] in ("group", "section") and self._holds_signature(container["id"]):
            container["role"] = "signature"

    def _holds_signature(self, container_id: str) -> bool:
        """LAY-08: a container that directly holds a signature capture field is the signature block."""
        return any(
            f["container_id"] == container_id and (f["control"]["kind"] == "signature" or is_signature_name(f["name"]))
            for f in self.fields
        )

    def _heading_of(self, el: ET.Element) -> tuple[str | None, str | None]:
        """OBJ-03: the first non-blob draw inside a section carries its business name."""
        for child in el:
            if local(child.tag) != "draw":
                continue
            text = text_of(child.find(self.t("value")))
            if not text or is_blob(text):
                continue
            m = HEADING_NUM.match(text)
            if m and self._is_heading_text(m.group(2)):
                return m.group(2).strip(), m.group(1)
            if len(text) <= 60 and text.upper() == text and self._is_heading_text(text):
                return text.strip(), None
            return None, None
        return None, None

    @staticmethod
    def _is_heading_text(text: str | None) -> bool:
        """Reject item markers ('A.', 'OR', 'B.') that are not section headings."""
        words = [w for w in re.findall(r"[A-Za-z]{2,}", text or "")]
        return bool(words) and (len(words) >= 2 or len(words[0]) >= 5)

    @staticmethod
    def _container_role(container: dict, el: ET.Element) -> str:
        """LAY-08: role from whole-word name tokens, then heading, then repetition/layout."""
        if container["depth"] == 0:
            return "page_body"
        tokens = name_tokens(container["name"])
        for role, words in ROLE_TOKENS:
            if tokens & words:
                return role
        if container["section_heading"]:
            return "section"
        if container["occur"] and container["occur"].get("repeating"):
            return "row"
        if (el.get("layout") or "") in ("lr-tb", "row"):
            return "row"
        return "group"

    # ----------------------------------------------------------------- fields
    def _excl_group(self, el: ET.Element, container: dict, som: str) -> None:
        """OBJ-06: exclGroup members become a Quadient radio group."""
        group_som = "{}.{}".format(som, el.get("name")) if el.get("name") else som
        for child in el.findall(self.t("field")):
            self._field(child, container, group_som, radio_group=group_som)

    def _field(self, el: ET.Element, container: dict, som: str, radio_group: str | None = None) -> None:
        name = el.get("name")
        path = f"{som}.{name}" if name else som
        path = self._unique_som(path)
        ui = el.find(self.t("ui"))
        ui_kind = local(list(ui)[0].tag) if ui is not None and len(ui) else None
        kind = "radio" if radio_group else UI_TO_KIND.get(ui_kind or "", "unknown")
        if kind == "text":
            value = el.find(self.t("ui") + "/" + self.t("textEdit"))
            if value is not None and value.get("multiLine") == "1":
                kind = "multiline_text"
        caption = text_of(el.find(self.t("caption")))
        if is_blob(caption):
            caption = ""
        labels = self._labels(el, caption, container)
        binding = binding_of(el.find(self.t("bind")))
        fmt = self._format(el)
        validations = self._validations(el, path, fmt)
        scripts = self._scripts(el, path)
        field = {
            "id": self._id("FD"),
            "som": path,
            "name": name,
            "container_id": container["id"],
            "control": {
                "xfa_ui": ui_kind,
                "kind": kind,
                "radio_group_som": radio_group,
                "items": self._items(el),
                "max_chars": int(el.get("maxChars")) if (el.get("maxChars") or "").isdigit() else None,
                "comb_cells": None,
                "read_only": el.get("access") in ("readOnly", "protected"),
                "access": el.get("access"),
                "presence": el.get("presence"),
            },
            "datatype": datatype_for(kind, fmt, binding),
            "caption": caption or None,
            "label_candidates": labels,
            "semantic": self._semantic(name, caption, labels, container, binding, kind),
            "binding": binding,
            "geometry": self._geometry(el, container["geometry"]["positioned"]),
            "style_ref": self._style_ref(el),
            "format": fmt,
            "validations": validations,
            "scripts": scripts,
            "confidence": {
                "structural": "deterministic",
                "semantic": "bound" if binding["mode"] == "dataRef" else ("heuristic" if labels else "unresolved"),
                "score": 0.95 if binding["mode"] == "dataRef" else (0.6 if labels else 0.2),
                "reasons": [],
            },
            "provenance": self._prov(path, rule_id="FLD-01"),
        }
        if binding["mode"] == "none":
            field["confidence"]["reasons"].append(
                "no XFA binding: target variable must come from the dictionary crosswalk"
            )
            self._flag(
                "BND-MISSING",
                "major",
                "field has no bind/dataRef: target variable name and data path require resolution",
                node=path,
                rule_id="BND-04",
                owner="data_steward",
            )
        if kind == "unknown":
            self._flag(
                "FLD-UNKNOWNUI",
                "major",
                f"unrecognised XFA ui control: {ui_kind}",
                node=path,
                rule_id="FLD-02",
                unsupported=True,
            )
        if kind == "signature" or is_signature_name(name):
            self._flag(
                "UNS-SIGNATURE",
                "major",
                "signature capture semantics do not transfer to a compose-time layout",
                node=path,
                rule_id="UNS-07",
                owner="analyst",
                unsupported=True,
            )
        if kind == "barcode":
            bc = ui.find(self.t("barcode")) if ui is not None else None
            self._flag(
                "LAY-BARCODE",
                "minor",
                f"barcode type={bc.get('type') if bc is not None else '?'} must be re-created with a Quadient "
                "barcode object and verified against the reference PDF",
                node=path,
                rule_id="OBJ-08",
                owner="designer",
            )
        self.fields.append(field)

    def _items(self, el: ET.Element) -> list[dict]:
        out = []
        for items in el.findall(self.t("items")):
            values = [text_of(c) for c in items]
            for value in values:
                if value and not is_blob(value):
                    out.append({"value": value, "label": None})
        return out

    def _labels(self, el: ET.Element, caption: str | None, container: dict) -> list[dict]:
        labels = []
        if caption:
            labels.append({"text": caption, "source": "caption", "distance_mm": 0.0})
        tooltip = el.find(self.t("assist"))
        if tooltip is not None:
            tip = text_of(tooltip)
            if tip and not is_blob(tip):
                labels.append({"text": tip, "source": "tooltip", "distance_mm": None})
        if container.get("section_heading"):
            labels.append({"text": container["section_heading"], "source": "section_heading", "distance_mm": None})
        return labels

    def _format(self, el: ET.Element) -> dict:
        def picture(node: ET.Element | None) -> str | None:
            if node is None:
                return None
            pic = text_of(node.find(self.t("picture")))
            return pic or None

        return {
            "display_picture": picture(el.find(self.t("format"))),
            "edit_picture": picture(el.find(self.t("ui"))),
            "data_picture": picture(el.find(self.t("bind"))),
        }

    def _validations(self, el: ET.Element, path: str, fmt: dict) -> list[dict]:
        out = []
        validate = el.find(self.t("validate"))
        if validate is not None:
            message = text_of(validate.find(self.t("message"))) or None
            if validate.get("nullTest") in ("error", "warning"):
                out.append(
                    {
                        "kind": "mandatory",
                        "expression": None,
                        "picture": None,
                        "message": message,
                        "severity": "error" if validate.get("nullTest") == "error" else "warning",
                        "transferability": "declarative",
                        "provenance": self._prov(path, rule_id="VAL-01"),
                    }
                )
            picture = text_of(validate.find(self.t("picture")))
            if validate.get("formatTest") in ("error", "warning") or picture:
                out.append(
                    {
                        "kind": "picture_format",
                        "expression": None,
                        "picture": picture or None,
                        "message": message,
                        "severity": "error",
                        "transferability": "declarative",
                        "provenance": self._prov(path, rule_id="VAL-02"),
                    }
                )
            script = validate.find(self.t("script"))
            if script is not None and text_of(script):
                body = text_of(script)
                _, transferability = classify_script(body)
                out.append(
                    {
                        "kind": "script",
                        "expression": body[:2000],
                        "picture": None,
                        "message": message,
                        "severity": "error",
                        "transferability": "manual" if transferability == "manual" else "rule_translatable",
                        "provenance": self._prov(path, rule_id="VAL-03"),
                    }
                )
        if fmt.get("display_picture") and not any(v["kind"] == "picture_format" for v in out):
            out.append(
                {
                    "kind": "picture_format",
                    "expression": None,
                    "picture": fmt["display_picture"],
                    "message": None,
                    "severity": "info",
                    "transferability": "declarative",
                    "provenance": self._prov(path, rule_id="VAL-02"),
                }
            )
        if el.get("minLength") or el.get("maxChars"):
            out.append(
                {
                    "kind": "length",
                    "expression": "maxChars={}".format(el.get("maxChars")),
                    "picture": None,
                    "message": None,
                    "severity": "info",
                    "transferability": "declarative",
                    "provenance": self._prov(path, rule_id="VAL-04"),
                }
            )
        return out

    def _scripts(self, el: ET.Element, path: str) -> list[dict]:
        out = []
        for event in el.findall(self.t("event")):
            script = event.find(self.t("script"))
            body = text_of(script)
            if not body:
                continue
            classification, transferability = classify_script(body)
            out.append(
                {
                    "activity": event.get("activity"),
                    "language": script.get("contentType") if script is not None else None,
                    "body": body[:4000],
                    "length": len(body),
                    "classification": classification,
                    "targets": script_targets(body),
                    "transferability": transferability,
                    "provenance": self._prov(path, rule_id="VAL-05"),
                }
            )
            if transferability == "manual":
                self._flag(
                    "VAL-SCRIPT-MANUAL",
                    "major",
                    "script on '{}' ({}) cannot be translated mechanically".format(
                        event.get("activity"), classification
                    ),
                    node=path,
                    rule_id="VAL-06",
                    unsupported=True,
                )
        return out

    def _semantic(
        self, name: str | None, caption: str | None, labels: list[dict], container: dict, binding: dict, kind: str
    ) -> dict:
        """FLD-05: propose a target name from the strongest available evidence.

        Evidence order: explicit binding leaf > caption > section heading + field name.
        A proposal is never treated as authoritative; see the confidence block.
        """
        section = container.get("target_name_hint") or ""
        leaf = None
        if binding["mode"] == "dataRef" and binding["source_path"]:
            leaf = binding["source_path"].split(".")[-1]
        label = caption or (labels[0]["text"] if labels else None)
        token = pascal(label) if label else pascal(name)
        hint = None
        if leaf:
            hint = f"{section}{pascal(leaf)}" if section else pascal(leaf)
        elif token:
            hint = f"{section}{token}" if section else token
        suffix = {
            "checkbox": "Ind",
            "radio": "Radio",
            "date": "Dte",
            "number": "Num",
            "currency": "Amt",
            "multiline_text": "Txt",
        }.get(kind)
        if hint and suffix and not hint.endswith(suffix):
            hint = hint + suffix
        return {
            "role": None,
            "target_name_hint": hint,
            "dictionary_key": binding["source_path"],
            "requires_review": binding["mode"] != "dataRef",
        }

    # ---------------------------------------------------------------- statics
    def _draw(self, el: ET.Element, container: dict, som: str) -> None:
        name = el.get("name")
        path = f"{som}.{name}" if name else som
        path = self._unique_som(path)
        content = draw_content(el, self.t, path)
        text = content.text
        self._title_runs.extend(title_runs(el, self.t, len(self.statics)))
        heading = bool(text) and _heading_key(text) == container.get("section_heading")
        self.statics.append(
            {
                "id": self._id("SX"),
                "som": path,
                "container_id": container["id"],
                "kind": content.kind,
                "text": text,
                "is_heading": heading,
                "is_legal_block": bool(text) and len(text) > 300,
                "geometry": self._geometry(el, container["geometry"]["positioned"]),
                "style_ref": self._style_ref(el),
                "image_ref": content.image_ref,
                "confidence": {
                    "structural": "deterministic",
                    "semantic": "bound" if text else "heuristic",
                    "score": 1.0 if text else 0.5,
                    "reasons": [],
                },
                "provenance": self._prov(path, rule_id="OBJ-05"),
            }
        )

    # -------------------------------------------------------- data dictionary
    def data_dictionary(self) -> dict:
        connections, types = [], []
        for child in self.root:
            tag = local(child.tag)
            if tag == "connectionSet":
                for conn in child:
                    connections.append(
                        {
                            "kind": local(conn.tag),
                            "name": conn.get("name"),
                            "data_description": conn.get("dataDescription"),
                            "uri": text_of(conn.find("{{{}}}uri".format(conn.tag[1:].split("}")[0]))) or None,
                        }
                    )
            elif tag == "schema":
                ns = child.get("targetNamespace")
                for ctype in child.findall(XSD_NS + "complexType"):
                    elements = []
                    for elem in ctype.iter(XSD_NS + "element"):
                        elements.append(
                            {
                                "name": elem.get("name"),
                                "type": elem.get("type"),
                                "min_occurs": elem.get("minOccurs"),
                                "max_occurs": elem.get("maxOccurs"),
                            }
                        )
                    if ctype.get("name"):
                        types.append({"namespace": ns, "type_name": ctype.get("name"), "elements": elements})
        return {"connections": connections, "types": types}

    def source_node_counts(self) -> dict[str, int]:
        """Raw template node census used by the lossless gate (G2): every field, draw,
        subform, exclGroup and subformSet in the source must be accounted for in the CIM
        or in diagnostics.unsupported."""
        census = Counter()
        for el in self.template.iter():
            tag = local(el.tag)
            if tag in ("field", "draw", "subform", "exclGroup", "subformSet", "area", "pageArea", "contentArea"):
                census[tag] += 1
        return dict(sorted(census.items()))

    # ------------------------------------------------------------------ build
    def build(self) -> dict:
        self.extract_pages()
        self.walk()
        dictionary = self.data_dictionary()
        self._resolve_xsd_types(dictionary)
        form_code, title, revision = self._form_identity()
        counts = {
            "pages": len(self.pages),
            "containers": len(self.containers),
            "sections": sum(1 for c in self.containers if c["role"] == "section"),
            "fields": len(self.fields),
            "fields_bound": sum(1 for f in self.fields if f["binding"]["mode"] == "dataRef"),
            "fields_unbound": sum(1 for f in self.fields if f["binding"]["mode"] != "dataRef"),
            "statics": len(self.statics),
            "static_text_runs": sum(1 for s in self.statics if s["kind"] in ("text", "rich_text")),
            "styles": len(self.styles),
            "validations": sum(len(f["validations"]) for f in self.fields),
            "scripts": sum(len(f["scripts"]) for f in self.fields),
            "scripts_manual": sum(1 for f in self.fields for s in f["scripts"] if s["transferability"] == "manual"),
            "dictionary_types": len(dictionary["types"]),
            "by_control_kind": dict(Counter(f["control"]["kind"] for f in self.fields)),
            "source_nodes": self.source_node_counts(),
        }
        if not revision:
            self._flag(
                "GOV-NOREVISION",
                "minor",
                "no revision marker found in static text: the revision-drift gate cannot compare source and target "
                "revisions",
                rule_id="GOV-01",
                owner="analyst",
            )
        return {
            "cim_version": CIM_VERSION,
            "form": {
                "source_file": os.path.basename(self.path),
                "source_sha256": self.sha256,
                "form_code": form_code,
                "title": title,
                "revision_hint": revision,
                "locale": (self._first_child("localeSet") is not None) and "localeSet" or None,
                "packets": [local(c.tag) for c in self.root],
            },
            "pages": self.pages,
            "containers": self.containers,
            "fields": self.fields,
            "statics": self.statics,
            "styles": self.styles.values(),
            "data_dictionary": dictionary,
            "diagnostics": {"counts": counts, "unsupported": self.unsupported, "review_queue": self.review},
        }

    def _resolve_xsd_types(self, dictionary: dict) -> None:
        """BND-03: type a bound field from the embedded XSD when the leaf name is unique."""
        types = leaf_types(dictionary)
        for field in self.fields:
            path = field["binding"].get("source_path")
            if not path:
                continue
            candidates = types.get(path.split(".")[-1].split("[")[0])
            if candidates and len(candidates) == 1:
                field["binding"]["xsd_type"] = next(iter(candidates))
                field["datatype"] = datatype_for(field["control"]["kind"], field["format"], field["binding"])

    def _form_identity(self) -> tuple[str | None, str | None, str | None]:
        """GOV-02: form code from the file stem, revision from static text, title from the title evidence."""
        code: str | None = None
        revision = None
        stem = re.match(r"^(\d{2})(\d{4})", os.path.basename(self.path))
        if stem:
            code = f"{stem.group(1)}-{stem.group(2)}"
        for static in self.statics:
            text = static["text"]
            if not text:
                continue
            if code is None:
                m = FORM_CODE.search(text)
                if m:
                    code = m.group(1)
            if revision is None:
                m = REVISION.search(text)
                if m:
                    revision = next(g for g in m.groups() if g)
        return code, select_title(self._title_runs), revision


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract an XDP template into the CIM.")
    parser.add_argument("xdp")
    parser.add_argument("-o", "--out", help="output CIM JSON path (default: stdout)")
    parser.add_argument("--summary", action="store_true", help="print the diagnostics summary to stderr")
    args = parser.parse_args(argv)

    cim = XdpExtractor(args.xdp).build()
    payload = json.dumps(cim, indent=2, sort_keys=False)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload + "\n")
    else:
        print(payload)
    if args.summary:
        counts = cim["diagnostics"]["counts"]
        print(json.dumps(counts, indent=2), file=sys.stderr)
        review = len(cim["diagnostics"]["review_queue"])
        unsupported = len(cim["diagnostics"]["unsupported"])
        print(f"review_queue={review} unsupported={unsupported}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

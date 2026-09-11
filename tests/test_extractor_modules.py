"""Focused tests for the extractor's collaborator modules and its structural edge cases.

Every XDP here is synthetic: the template body is wrapped in a minimal <xdp:xdp> envelope so a
test can exercise one construct (a subformSet, an exclGroup, a valueless draw) in isolation.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from converters.xdp_to_cim import extractor
from converters.xdp_to_cim.bindings import binding_of, datatype_for, leaf_types, normalise_ref
from converters.xdp_to_cim.extractor import XdpExtractor, name_tokens
from converters.xdp_to_cim.scripts import (
    MANUAL,
    RULE_TRANSLATABLE,
    RUNTIME_ONLY,
    classify_script,
    is_single_statement,
    script_targets,
)
from converters.xdp_to_cim.statics import TitleRun, draw_content, is_title_candidate, select_title, title_runs
from converters.xdp_to_cim.styles import StyleRegistry, style_entry
from converters.xdp_to_cim.xfa import XFA_TEMPLATE_NS, is_blob, pascal, text_of, to_mm, to_pt

NS = XFA_TEMPLATE_NS + "3.3/"
PAGE_SET = """
<pageSet>
  <pageArea name="Page1"><contentArea x="10mm" y="10mm" w="190mm" h="250mm"/>
  <medium stock="letter" short="215.9mm" long="279.4mm"/></pageArea>
</pageSet>"""


def _tag(name: str) -> str:
    return f"{{{NS}}}{name}"


def _xdp(tmp_path: Path, body: str, name: str = "990002.xdp", page_set: str = PAGE_SET) -> Path:
    path = tmp_path / name
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<xdp:xdp xmlns:xdp="http://ns.adobe.com/xdp/">\n'
        f'<template xmlns="{NS}"><subform name="Root" layout="tb">{page_set}{body}</subform></template>\n'
        "</xdp:xdp>",
        encoding="utf-8",
    )
    return path


def _el(xml: str) -> ET.Element:
    return ET.fromstring(f'<wrap xmlns="{NS}">{xml}</wrap>')[0]


def _cim(tmp_path: Path, body: str, **kwargs) -> dict:
    return XdpExtractor(str(_xdp(tmp_path, body, **kwargs))).build()


# xfa helpers


@pytest.mark.parametrize(
    ("value", "mm"),
    [("10mm", 10.0), ("1in", 25.4), ("72pt", 25.4), ("2.5cm", 25.0), ("72000mp", 25.4), (" 3 ", 3.0), (None, None)],
)
def test_to_mm_converts_every_xfa_unit(value: str | None, mm: float | None) -> None:
    assert to_mm(value) == (None if mm is None else pytest.approx(mm))


def test_to_pt_and_bad_measures() -> None:
    assert to_pt("12pt") == pytest.approx(12.0)
    assert to_pt("25.4mm") == pytest.approx(72.0)
    assert to_mm("wide") is None
    assert to_pt(None) is None


def test_text_of_flattens_nested_markup_and_blob_detection() -> None:
    el = _el("<value><exData>Hello <b>bold</b> world</exData></value>")
    assert text_of(el) == "Hello bold world"
    assert text_of(None) == ""
    assert is_blob("QUJD" * 60)
    assert not is_blob("Synthetic Test Form")


def test_pascal_case_from_labels() -> None:
    assert pascal("bill account number") == "BillAccountNumber"
    assert pascal("EFT-Authorization (rev)") == "EFTAuthorizationRev"
    assert pascal("") is None
    assert pascal(None) is None


# scripts


@pytest.mark.parametrize(
    ("body", "label", "transfer"),
    [
        ('this.rawValue = xfa.layout.page(this) + " of " + xfa.layout.pageCount();', "page_number", RULE_TRANSLATABLE),
        ("xfa.layout.absPageCount()", "page_number", RULE_TRANSLATABLE),
        ('this.rawValue = xfa.data.resolveNode("EFormsData.Emp.Number").value;', "prefill", RULE_TRANSLATABLE),
        ("this.rawValue = xfa.record.Payer.Name.value;", "prefill", RULE_TRANSLATABLE),
        ("this.rawValue = this.rawValue.toUpperCase();", "uppercase", RULE_TRANSLATABLE),
        ("Other.rawValue = 0;", "mutual_exclusion", RULE_TRANSLATABLE),
        ('Other.rawValue = "0";', "mutual_exclusion", RULE_TRANSLATABLE),
        ("Other.rawValue = off;", "mutual_exclusion", RULE_TRANSLATABLE),
        ('Note.rawValue = "";', "conditional_clear", RULE_TRANSLATABLE),
        ('Block.presence = "hidden";', "visibility", RULE_TRANSLATABLE),
        ('xfa.host.gotoURL("http://x");', "navigation", RUNTIME_ONLY),
        ("Button.execEvent('click')", "navigation", RUNTIME_ONLY),
        ('event.target.submit.target = "http://x"; HTTPSubmit', "submit", RUNTIME_ONLY),
        ("xfa.host.exportData()", "submit", RUNTIME_ONLY),
        ("signature.validate()", "signature", MANUAL),
        ("SOAP.request(xfa.connectionSet.ws)", "external_call", MANUAL),
        ('util.printf("%,2f", x)', "formatting", RULE_TRANSLATABLE),
        ("Total.rawValue = A.rawValue + B.rawValue;", "calculation", RULE_TRANSLATABLE),
        ('app.alert("clicked");', "unknown", MANUAL),
    ],
)
def test_classify_script_by_idiom(body: str, label: str, transfer: str) -> None:
    assert classify_script(body) == (label, transfer)


@pytest.mark.parametrize("body", ["Amount.rawValue = 0.5;", "Code.rawValue = 01;", "Count.rawValue = 0x;"])
def test_mutual_exclusion_requires_a_bare_zero(body: str) -> None:
    assert classify_script(body)[0] != "mutual_exclusion"


CONCAT_PREFILL = """this.rawValue = xfa.data.resolveNode("D.isaNum").value;
if (xfa.data.resolveNode("D.isaNum2").value != "")
    this.rawValue = this.rawValue + ", " + xfa.data.resolveNode("D.isaNum2").value;"""
FALLBACK_PREFILL = """if (xfa.data.resolveNode("D.ownerPrefill").value != "N") {
    this.rawValue = xfa.data.resolveNode("D.persOwnerNam").value;
}"""


@pytest.mark.parametrize(
    ("body", "label"),
    [
        (CONCAT_PREFILL, "unknown"),
        (FALLBACK_PREFILL, "unknown"),
        ("this.rawValue = xfa.layout.page(this); if (x) { this.presence = 'hidden'; }", "visibility"),
        ('this.rawValue = xfa.data.resolveNode("D.a").value; // trailing note\n/* block\ncomment */', "prefill"),
        (
            'this.rawValue = xfa.data.resolveNode("D.a").value;\n// B.rawValue = xfa.data.resolveNode("D.b").value;',
            "prefill",
        ),
    ],
)
def test_prefill_and_page_number_require_a_single_straight_line_statement(body: str, label: str) -> None:
    assert classify_script(body)[0] == label


def test_is_single_statement_strips_comments_and_rejects_branches() -> None:
    assert is_single_statement("a = 1; /* b = 2; */ // c = 3;")
    assert not is_single_statement("a = 1; b = 2;")
    assert not is_single_statement("if (a) b = 1")
    assert not is_single_statement("")


def test_script_targets_are_sorted_unique_and_bounded() -> None:
    body = "xfa.resolveNode('B.C').rawValue = 1; A.rawValue = 2; A.rawValue = 3;" + " ".join(
        f"F{i}.rawValue = 0;" for i in range(30)
    )
    targets = script_targets(body)
    assert targets == sorted(targets)
    assert len(targets) == len(set(targets)) == 20
    assert script_targets('xfa.resolveNode("Only.One")') == ["Only.One"]
    assert script_targets("xfa.resolveNode('Single.Quoted')") == []


# bindings


def test_normalise_ref_strips_prefixes_and_predicates() -> None:
    assert normalise_ref("$record.Insured.Address[*].State") == "Insured.Address[].State"
    assert normalise_ref("$.Payer.Name") == "Payer.Name"
    assert normalise_ref("!Extra.Value ") == "Extra.Value"


@pytest.mark.parametrize(
    ("xml", "mode", "path"),
    [
        (None, "none", None),
        ('<bind match="none"/>', "none", None),
        ("<bind/>", "none", None),
        ('<bind match="global"/>', "global", None),
        ('<bind match="dataRef" ref="$record.A.B"/>', "dataRef", "A.B"),
        ('<bind match="dataRef"/>', "unresolved", None),
    ],
)
def test_binding_modes(xml: str | None, mode: str, path: str | None) -> None:
    binding = binding_of(_el(xml) if xml else None)
    assert binding["mode"] == mode
    assert binding["source_path"] == path
    assert binding["target_variable_hint"] == (path.split(".")[-1] if path else None)


@pytest.mark.parametrize(
    ("kind", "fmt", "xsd", "expected"),
    [
        ("text", {}, None, "string"),
        ("number", {"display_picture": "$zzz,zz9.99"}, None, "currency"),
        ("text", {"data_picture": "date{YYYY-MM-DD}"}, None, "date"),
        ("text", {}, "xs:boolean", "boolean"),
        ("text", {}, "xs:dateTime", "date"),
        ("text", {}, "xs:decimal", "decimal"),
        ("text", {}, "xs:int", "integer"),
        ("checkbox", {}, None, "boolean"),
        ("never_seen", {}, None, "string"),
    ],
)
def test_datatype_for_refines_base_kind(kind: str, fmt: dict, xsd: str | None, expected: str) -> None:
    assert datatype_for(kind, fmt, {"xsd_type": xsd}) == expected


def test_leaf_types_collects_types_per_leaf() -> None:
    dictionary = {
        "types": [
            {"elements": [{"name": "State", "type": "xs:string"}, {"name": None, "type": "x"}]},
            {"elements": [{"name": "State", "type": "xs:token"}]},
        ]
    }
    assert leaf_types(dictionary) == {"State": {"xs:string", "xs:token"}}


# styles


def test_style_entry_reads_nested_font_and_border_colours() -> None:
    el = _el(
        "<draw>"
        '<font typeface="Arial" size="9pt" weight="bold" posture="italic" underline="1">'
        '<fill><color value="255,0,0"/></fill></font>'
        '<para hAlign="right" vAlign="middle" spaceAbove="1mm" spaceBelow="2mm"/>'
        '<border><edge/><fill><color value="0,0,255"/></fill></border>'
        "</draw>"
    )
    entry = style_entry(el, _tag)
    assert entry is not None
    assert entry["typeface"] == "Arial"
    assert entry["size_pt"] == pytest.approx(9.0)
    assert (entry["bold"], entry["italic"], entry["underline"]) == (True, True, True)
    assert entry["color"] == "255,0,0"
    assert (entry["align"], entry["v_align"]) == ("right", "middle")
    assert entry["border"] == {"present": True}
    assert entry["fill"] == "0,0,255"
    assert entry["margins_mm"] == {"top": pytest.approx(1.0), "bottom": pytest.approx(2.0)}

    bare = style_entry(_el('<draw><font typeface="Arial"/><border><fill/></border></draw>'), _tag)
    assert bare is not None
    assert (bare["color"], bare["fill"], bare["margins_mm"], bare["size_pt"]) == (None, None, None, None)


def test_style_entry_is_none_without_style_children() -> None:
    assert style_entry(_el("<draw><value><text>x</text></value></draw>"), _tag) is None


def test_style_registry_deduplicates_and_numbers_in_first_seen_order() -> None:
    registry = StyleRegistry()
    a = registry.register({"typeface": "Arial", "size_pt": 9.0})
    b = registry.register({"typeface": "Arial", "size_pt": 12.0})
    again = registry.register({"typeface": "Arial", "size_pt": 9.0})
    assert (a, b, again) == ("ST001", "ST002", "ST001")
    assert [(s["id"], s["usage_count"]) for s in registry.values()] == [("ST001", 2), ("ST002", 1)]
    assert [s["target_name_hint"] for s in registry.values()] == ["Arial_9pt", "Arial_12pt"]
    assert registry.register({"typeface": "Verdana", "size_pt": 7.5, "bold": True, "italic": True}) == "ST003"
    assert registry.values()[-1]["target_name_hint"] == "Arial_7.5pt_Bold_Italic"
    assert len(registry) == 3


# statics


@pytest.mark.parametrize(
    ("xml", "kind"),
    [
        ('<draw w="100mm" h="0.5mm"><border><edge/></border></draw>', "line"),
        ('<draw w="1mm" h="80mm"><border><edge/></border></draw>', "line"),
        ('<draw w="50mm" h="20mm"><border><edge/></border></draw>', "rectangle"),
        ('<draw w="50mm" h="20mm"><border><fill><color value="0,0,0"/></fill></border></draw>', "rectangle"),
        ('<draw w="50mm" h="20mm"><border><edge presence="hidden"/></border></draw>', "unknown"),
        (
            '<draw w="50mm" h="20mm"><border><fill presence="hidden"><color value="0,0,0"/></fill></border></draw>',
            "unknown",
        ),
        ('<draw w="50mm" h="20mm"/>', "unknown"),
        ("<draw><border><edge/></border></draw>", "rectangle"),
        ("<draw><value><line/></value></draw>", "line"),
        ("<draw><value><rectangle/></value></draw>", "rectangle"),
    ],
)
def test_valueless_and_shape_draws(xml: str, kind: str) -> None:
    assert draw_content(_el(xml), _tag, ".x").kind == kind


def test_draw_content_text_rich_text_and_images() -> None:
    assert draw_content(_el("<draw><value><text>Hi there</text></value></draw>"), _tag, ".x") == draw_content(
        _el("<draw><value><text>Hi there</text></value></draw>"), _tag, ".x"
    )
    rich = draw_content(_el("<draw><value><exData>Rich <b>text</b></exData></value></draw>"), _tag, ".x")
    assert (rich.kind, rich.text) == ("rich_text", "Rich text")
    blob = draw_content(_el(f"<draw><value><text>{'QUJD' * 60}</text></value></draw>"), _tag, ".x")
    assert blob.kind == "image" and blob.image_ref.startswith("asset:") and blob.text is None
    image = draw_content(_el("<draw><value><image>abc</image></value></draw>"), _tag, ".x")
    assert image.kind == "image" and image.image_ref.startswith("asset:")


@pytest.mark.parametrize(
    ("text", "ok"),
    [
        ("REQUEST FOR RECONSIDERATION", True),
        ("EFT AUTHORIZATION", True),
        ("(MM/YYYY)", False),
        ("B. ACCOUNT TYPE", False),
        ("Request for Reconsideration", False),
        ("NOTE: PLEASE PRINT", False),
        ("SHORT", False),
        ("A " * 60, False),
    ],
)
def test_title_candidates(text: str, ok: bool) -> None:
    assert is_title_candidate(text) is ok


def test_select_title_prefers_size_then_weight_then_document_order() -> None:
    runs = [
        TitleRun("TELEPHONE NUMBER AREA CODE", 8.0, False, 5),
        TitleRun("CORPORATE MARKET TRANSMITTAL LETTER", 14.0, False, 9),
        TitleRun("ANOTHER LARGE HEADING", 14.0, True, 12),
        TitleRun("(MM/YYYY)", 20.0, True, 0),
    ]
    assert select_title(runs) == "ANOTHER LARGE HEADING"
    ties = [TitleRun("FIRST UPPER CASE", None, False, 1), TitleRun("SECOND UPPER CASE", None, False, 0)]
    assert select_title(ties) == "SECOND UPPER CASE"
    assert select_title([TitleRun("lower case", 30.0, True, 0)]) is None


def test_title_runs_use_inline_font_size_and_weight_for_rich_text() -> None:
    el = _el(
        '<draw><font size="8pt"/><value><exData><body xmlns="http://www.w3.org/1999/xhtml">'
        '<p style="font-size:14pt;font-weight:bold">BIG TITLE HERE</p><p>small note</p>'
        "</body></exData></value></draw>"
    )
    runs = title_runs(el, _tag, 3)
    assert [(r.text, r.size_pt, r.bold, r.order) for r in runs] == [
        ("BIG TITLE HERE", 14.0, True, 3),
        ("small note", 8.0, False, 3),
    ]
    plain_el = _el('<draw><font size="10pt" weight="bold"/><value><text>PLAIN RUN</text></value></draw>')
    plain = title_runs(plain_el, _tag, 0)
    assert plain == [TitleRun("PLAIN RUN", 10.0, True, 0)]
    assert title_runs(_el("<draw/>"), _tag, 0) == []
    no_paragraphs = title_runs(_el("<draw><value><exData>FLAT RICH</exData></value></draw>"), _tag, 1)
    assert no_paragraphs == [TitleRun("FLAT RICH", None, False, 1)]


# extractor: structure


def test_title_is_the_largest_upper_case_run_not_the_first(tmp_path: Path) -> None:
    body = """
    <subform name="Main">
      <draw name="Date" w="30mm" h="5mm"><font size="8pt"/><value><text>(MM/YYYY)</text></value></draw>
      <draw name="Sub" w="60mm" h="5mm"><font size="10pt"/><value><text>B. ACCOUNT TYPE</text></value></draw>
      <draw name="Title" w="120mm" h="8mm"><font size="14pt" weight="bold"/>
        <value><text>EFT AUTHORIZATION</text></value></draw>
      <field name="A" w="20mm" h="6mm"><ui><textEdit/></ui><bind match="dataRef" ref="$record.A"/></field>
    </subform>"""
    cim = _cim(tmp_path, body)
    assert cim["form"]["title"] == "EFT AUTHORIZATION"
    assert cim["form"]["form_code"] == "99-0002"


def test_subform_set_is_flagged_unsupported_but_its_children_are_walked(tmp_path: Path) -> None:
    body = """
    <subform name="Main">
      <subformSet name="Choice" relation="choice">
        <subform name="OptionA"><field name="A" w="20mm" h="6mm"><ui><textEdit/></ui>
          <bind match="dataRef" ref="$record.A"/></field></subform>
        <subform name="OptionB"><field name="B" w="20mm" h="6mm"><ui><textEdit/></ui>
          <bind match="dataRef" ref="$record.B"/></field></subform>
      </subformSet>
    </subform>"""
    cim = _cim(tmp_path, body)
    unsupported = [u["code"] for u in cim["diagnostics"]["unsupported"]]
    assert unsupported == ["OBJ-SUBFORMSET"]
    assert [c["name"] for c in cim["containers"]] == ["Root", "Main", "OptionA", "OptionB", "Page1"]
    assert sorted(f["som"] for f in cim["fields"]) == [".Root.Main.OptionA.A", ".Root.Main.OptionB.B"]
    assert cim["diagnostics"]["counts"]["source_nodes"]["subformSet"] == 1


def test_excl_group_members_become_radio_fields_sharing_a_group_som(tmp_path: Path) -> None:
    body = """
    <subform name="Main">
      <exclGroup name="Freq" w="60mm" h="6mm">
        <field name="Monthly" w="20mm" h="6mm"><ui><checkButton/></ui>
          <caption><value><text>Monthly</text></value></caption>
          <items><text>1</text><text>0</text></items></field>
        <field name="Annual" w="20mm" h="6mm"><ui><checkButton/></ui>
          <caption><value><text>Annual</text></value></caption></field>
        <bind match="dataRef" ref="$record.Freq"/>
      </exclGroup>
    </subform>"""
    cim = _cim(tmp_path, body)
    radios = [f for f in cim["fields"] if f["control"]["kind"] == "radio"]
    assert [f["som"] for f in radios] == [".Root.Main.Freq.Monthly", ".Root.Main.Freq.Annual"]
    assert {f["control"]["radio_group_som"] for f in radios} == {".Root.Main.Freq"}
    assert radios[0]["control"]["items"] == [{"value": "1", "label": None}, {"value": "0", "label": None}]
    assert radios[0]["datatype"] == "boolean"
    assert radios[0]["semantic"]["target_name_hint"] == "MonthlyRadio"
    assert cim["diagnostics"]["counts"]["source_nodes"]["exclGroup"] == 1


def test_occurrence_parsing_marks_repeating_rows(tmp_path: Path) -> None:
    body = """
    <subform name="Main">
      <subform name="Travel" layout="tb"><occur min="1" max="-1" initial="1"/>
        <field name="Dest" w="20mm" h="6mm"><ui><textEdit/></ui>
          <bind match="dataRef" ref="$record.Travel.Dest"/></field>
      </subform>
      <subform name="Fixed"><occur min="1" max="1"/>
        <field name="Note" w="20mm" h="6mm"><ui><textEdit/></ui><bind match="dataRef" ref="$record.Note"/></field>
      </subform>
      <subform name="Bad"><occur max="lots"/>
        <field name="X" w="20mm" h="6mm"><ui><textEdit/></ui><bind match="dataRef" ref="$record.X"/></field>
      </subform>
    </subform>"""
    by_name = {c["name"]: c for c in _cim(tmp_path, body)["containers"]}
    assert by_name["Travel"]["occur"] == {"min": 1, "max": -1, "initial": 1, "repeating": True}
    assert by_name["Travel"]["role"] == "row"
    assert by_name["Fixed"]["occur"]["repeating"] is False
    assert by_name["Fixed"]["role"] == "group"
    assert by_name["Bad"]["occur"] == {"min": None, "max": None, "initial": None, "repeating": False}
    assert by_name["Main"]["occur"] is None


@pytest.mark.parametrize(
    ("name", "role"),
    [
        ("PageFooter", "footer"),
        ("BrandHeader", "header"),
        ("SignatureBlock", "signature"),
        ("PayerSign", "signature"),
        ("BarcodeZone", "barcode_zone"),
        ("Assignment", "group"),
        ("Designer", "group"),
        ("Headers", "group"),
    ],
)
def test_container_role_matches_whole_words_only(tmp_path: Path, name: str, role: str) -> None:
    body = f"""
    <subform name="Main"><subform name="{name}">
      <field name="V" w="20mm" h="6mm"><ui><textEdit/></ui><bind match="dataRef" ref="$record.V"/></field>
    </subform></subform>"""
    by_name = {c["name"]: c for c in _cim(tmp_path, body)["containers"]}
    assert by_name[name]["role"] == role


def test_name_tokens_split_on_case_and_separators() -> None:
    assert name_tokens("PayerSign_Block2") == {"payer", "sign", "block", "2"}
    assert name_tokens("EFTHeader") == {"eft", "header"}
    assert name_tokens(None) == set()


def test_container_holding_a_signature_field_becomes_the_signature_block(tmp_path: Path) -> None:
    body = """
    <subform name="Main"><subform name="Approvals">
      <field name="ApproverSig" w="60mm" h="12mm"><ui><signature/></ui></field>
    </subform></subform>"""
    cim = _cim(tmp_path, body)
    by_name = {c["name"]: c for c in cim["containers"]}
    assert by_name["Approvals"]["role"] == "signature"
    assert [u["code"] for u in cim["diagnostics"]["unsupported"]] == ["UNS-SIGNATURE"]
    assert cim["fields"][0]["control"]["kind"] == "signature"


def test_numbered_heading_names_the_section_and_marks_the_heading_draw(tmp_path: Path) -> None:
    body = """
    <subform name="Main"><subform name="Sec">
      <draw name="H" w="100mm" h="5mm"><value><text>2. Payment Details</text></value></draw>
      <draw name="Blob" w="10mm" h="5mm"><value><text>%s</text></value></draw>
      <field name="Amt" w="20mm" h="6mm"><ui><numericEdit/></ui><format><picture>$zz9.99</picture></format>
        <bind match="dataRef" ref="$record.Amt"/></field>
    </subform>
    <subform name="Marker"><draw name="M" w="10mm" h="5mm"><value><text>B.</text></value></draw>
      <field name="Q" w="20mm" h="6mm"><ui><textEdit/></ui><bind match="dataRef" ref="$record.Q"/></field></subform>
    </subform>""" % ("QUJD" * 60)
    cim = _cim(tmp_path, body)
    by_name = {c["name"]: c for c in cim["containers"]}
    assert by_name["Sec"]["section_number"] == "2"
    assert by_name["Sec"]["section_heading"] == "Payment Details"
    assert by_name["Sec"]["target_name_hint"] == "PaymentDetails"
    assert by_name["Sec"]["role"] == "section"
    assert by_name["Marker"]["section_heading"] is None
    heading = [s for s in cim["statics"] if s["is_heading"]]
    assert [s["text"] for s in heading] == ["2. Payment Details"]
    amount = next(f for f in cim["fields"] if f["name"] == "Amt")
    assert amount["datatype"] == "currency"
    assert amount["semantic"]["target_name_hint"] == "PaymentDetailsAmtNum"
    assert [c["source"] for c in amount["label_candidates"]] == ["section_heading"]


def test_unknown_ui_barcode_dropdown_and_unwalked_children_are_reported(tmp_path: Path) -> None:
    body = """
    <subform name="Main">
      <field name="Odd" w="20mm" h="6mm"><ui><futureWidget/></ui><bind match="dataRef" ref="$record.Odd"/></field>
      <field name="Code" w="40mm" h="10mm"><ui><barcode type="pdf417"/></ui><bind match="dataRef" ref="$record.Code"/>
        <assist><toolTip>Scan me</toolTip></assist></field>
      <field name="Pick" w="40mm" h="6mm"><ui><choiceList/></ui><bind match="dataRef" ref="$record.Pick"/>
        <items><text>A</text><text>B</text></items><items save="1"><text>1</text><text>2</text></items></field>
      <field name="Btn" w="20mm" h="6mm"><ui><button/></ui></field>
      <mystery/>
    </subform>"""
    cim = _cim(tmp_path, body)
    by_name = {f["name"]: f for f in cim["fields"]}
    assert by_name["Odd"]["control"]["kind"] == "unknown"
    assert by_name["Code"]["control"]["kind"] == "barcode"
    assert by_name["Code"]["datatype"] == "barcode"
    assert by_name["Code"]["label_candidates"] == [{"text": "Scan me", "source": "tooltip", "distance_mm": None}]
    assert by_name["Pick"]["control"]["kind"] == "dropdown"
    assert [i["value"] for i in by_name["Pick"]["control"]["items"]] == ["A", "B", "1", "2"]
    assert by_name["Btn"]["control"]["kind"] == "action"
    assert by_name["Btn"]["datatype"] == "void"
    codes = sorted(u["code"] for u in cim["diagnostics"]["unsupported"])
    assert codes == ["FLD-UNKNOWNUI", "OBJ-UNWALKED"]
    review = {r["code"] for r in cim["diagnostics"]["review_queue"]}
    assert {"LAY-BARCODE", "BND-MISSING", "GOV-NOREVISION"} <= review


def test_validations_cover_mandatory_picture_script_and_length(tmp_path: Path) -> None:
    body = """
    <subform name="Main">
      <field name="Zip" w="20mm" h="6mm" maxChars="5"><ui><textEdit/></ui><bind match="dataRef" ref="$record.Zip"/>
        <validate nullTest="error" formatTest="warning"><message><text>Required</text></message>
          <picture>99999</picture><script>if (this.rawValue.length != 5) app.alert("bad");</script></validate>
      </field>
      <field name="Amt" w="20mm" h="6mm"><ui><numericEdit/></ui><bind match="dataRef" ref="$record.Amt"/>
        <format><picture>zz9.99</picture></format>
        <validate><script>this.rawValue = this.rawValue.toUpperCase();</script></validate>
      </field>
    </subform>"""
    cim = _cim(tmp_path, body)
    by_name = {f["name"]: f for f in cim["fields"]}
    zip_kinds = [(v["kind"], v["transferability"], v["severity"]) for v in by_name["Zip"]["validations"]]
    assert zip_kinds == [
        ("mandatory", "declarative", "error"),
        ("picture_format", "declarative", "error"),
        ("script", "manual", "error"),
        ("length", "declarative", "info"),
    ]
    assert by_name["Zip"]["validations"][0]["message"] == "Required"
    assert by_name["Zip"]["control"]["max_chars"] == 5
    amt = [(v["kind"], v["transferability"], v["picture"]) for v in by_name["Amt"]["validations"]]
    assert amt == [("script", "rule_translatable", None), ("picture_format", "declarative", "zz9.99")]


def test_scripts_record_events_targets_and_flag_only_manual_ones(tmp_path: Path) -> None:
    body = """
    <subform name="Main">
      <field name="Pg" w="20mm" h="6mm"><ui><textEdit/></ui><bind match="dataRef" ref="$record.Pg"/>
        <event activity="layout:ready"><script contentType="application/x-javascript">
          this.rawValue = xfa.layout.page(this);</script></event>
        <event activity="click"><script>xfa.host.gotoURL("http://example.test");</script></event>
        <event activity="exit"><script>SOAP.request(Other.rawValue);</script></event>
        <event activity="enter"><script>   </script></event>
      </field>
    </subform>"""
    cim = _cim(tmp_path, body)
    scripts = cim["fields"][0]["scripts"]
    assert [(s["activity"], s["classification"], s["transferability"]) for s in scripts] == [
        ("layout:ready", "page_number", "rule_translatable"),
        ("click", "navigation", "runtime_only"),
        ("exit", "external_call", "manual"),
    ]
    assert scripts[0]["language"] == "application/x-javascript"
    assert scripts[2]["targets"] == ["Other"]
    assert [u["code"] for u in cim["diagnostics"]["unsupported"]] == ["VAL-SCRIPT-MANUAL"]
    assert cim["diagnostics"]["counts"]["scripts_manual"] == 1


def test_master_page_content_and_landscape_medium(tmp_path: Path) -> None:
    page_set = """
    <pageSet>
      <pageArea name="Wide"><contentArea x="10mm" y="10mm" w="250mm" h="180mm"/>
        <medium stock="letter" short="215.9mm" long="279.4mm" orientation="landscape"/>
        <draw name="Foot" w="50mm" h="5mm"><value><text>99-0002 REV 03/24</text></value></draw>
      </pageArea>
      <pageArea name="Empty"><medium stock="letter" short="215.9mm" long="279.4mm"/></pageArea>
    </pageSet>"""
    body = """<subform name="Main"><field name="A" w="20mm" h="6mm"><ui><textEdit/></ui>
      <bind match="dataRef" ref="$record.A"/></field></subform>"""
    cim = _cim(tmp_path, body, page_set=page_set)
    wide = cim["pages"][0]
    assert (wide["medium"]["width_mm"], wide["medium"]["height_mm"]) == (pytest.approx(279.4), pytest.approx(215.9))
    assert wide["medium"]["orientation"] == "landscape"
    assert cim["pages"][1]["content_areas"] == []
    assert "LAY-NOCONTENTAREA" in {r["code"] for r in cim["diagnostics"]["review_queue"]}
    masters = [c for c in cim["containers"] if c["role"] == "master_page"]
    assert [c["name"] for c in masters] == ["Wide", "Empty"]
    assert masters[0]["provenance"]["rule_id"] == "OBJ-12"
    assert cim["form"]["revision_hint"] == "03/24"


def test_area_children_and_duplicate_soms_are_kept_distinct(tmp_path: Path) -> None:
    body = """
    <subform name="Main">
      <area name="Grp"><field name="Dup" w="20mm" h="6mm"><ui><textEdit/></ui>
        <bind match="dataRef" ref="$record.D1"/></field></area>
      <area name="Grp"><field name="Dup" w="20mm" h="6mm"><ui><textEdit/></ui>
        <bind match="dataRef" ref="$record.D2"/></field></area>
    </subform>"""
    cim = _cim(tmp_path, body)
    soms = sorted(f["som"] for f in cim["fields"])
    assert len(soms) == len(set(soms)) == 2
    assert soms[0].startswith(".Root.Main.Grp")
    assert cim["diagnostics"]["counts"]["source_nodes"]["area"] == 2


def test_data_dictionary_reads_connection_set_and_xsd_types(tmp_path: Path) -> None:
    path = tmp_path / "990003.xdp"
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<xdp:xdp xmlns:xdp="http://ns.adobe.com/xdp/">\n'
        f'<template xmlns="{NS}"><subform name="Root">{PAGE_SET}<subform name="Main">'
        '<field name="Count" w="20mm" h="6mm"><ui><textEdit/></ui>'
        '<bind match="dataRef" ref="$record.Emp.Count"/></field>'
        '<field name="Flag" w="20mm" h="6mm"><ui><textEdit/></ui><bind match="dataRef" ref="$record.Emp.Flag"/></field>'
        '<field name="Amb" w="20mm" h="6mm"><ui><textEdit/></ui><bind match="dataRef" ref="$record.Emp.Amb"/></field>'
        "</subform></subform></template>\n"
        '<connectionSet xmlns="http://www.xfa.org/schema/xfa-connection-set/2.8/">'
        '<xsdConnection name="DataConnection" dataDescription="EmpDD"><uri>Emp.xsd</uri></xsdConnection>'
        "</connectionSet>\n"
        '<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema" targetNamespace="urn:emp">'
        '<xsd:complexType name="EmpType"><xsd:sequence>'
        '<xsd:element name="Count" type="xsd:int"/><xsd:element name="Flag" type="xsd:boolean"/>'
        '<xsd:element name="Amb" type="xsd:string"/></xsd:sequence></xsd:complexType>'
        '<xsd:complexType name="Other"><xsd:sequence><xsd:element name="Amb" type="xsd:date"/>'
        "</xsd:sequence></xsd:complexType>"
        "</xsd:schema>\n"
        "</xdp:xdp>",
        encoding="utf-8",
    )
    cim = XdpExtractor(str(path)).build()
    dd = cim["data_dictionary"]
    assert dd["connections"] == [
        {"kind": "xsdConnection", "name": "DataConnection", "data_description": "EmpDD", "uri": "Emp.xsd"}
    ]
    assert [t["type_name"] for t in dd["types"]] == ["EmpType", "Other"]
    by_name = {f["name"]: f for f in cim["fields"]}
    assert (by_name["Count"]["binding"]["xsd_type"], by_name["Count"]["datatype"]) == ("xsd:int", "integer")
    assert (by_name["Flag"]["binding"]["xsd_type"], by_name["Flag"]["datatype"]) == ("xsd:boolean", "boolean")
    assert by_name["Amb"]["binding"]["xsd_type"] is None
    assert cim["form"]["packets"] == ["template", "connectionSet", "schema"]


def test_template_without_root_subform_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "990004.xdp"
    path.write_text(
        f'<xdp:xdp xmlns:xdp="http://ns.adobe.com/xdp/"><template xmlns="{NS}"/></xdp:xdp>', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="root subform"):
        XdpExtractor(str(path)).build()


def test_form_code_falls_back_to_static_text_when_filename_is_opaque(tmp_path: Path) -> None:
    body = """<subform name="Main">
      <draw name="F" w="40mm" h="5mm"><value><text>Form 18-1026 (0423)</text></value></draw>
      <field name="A" w="20mm" h="6mm"><ui><textEdit/></ui><bind match="dataRef" ref="$record.A"/></field></subform>"""
    cim = _cim(tmp_path, body, name="leave-request.xdp")
    assert cim["form"]["form_code"] == "18-1026"
    assert cim["form"]["revision_hint"] == "0423"


def test_cli_writes_json_and_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    xdp = _xdp(tmp_path, '<subform name="Main"><field name="A" w="20mm" h="6mm"><ui><textEdit/></ui></field></subform>')
    out = tmp_path / "nested" / "cim.json"
    assert extractor.main([str(xdp), "-o", str(out), "--summary"]) == 0
    captured = capsys.readouterr()
    assert json.loads(out.read_text(encoding="utf-8"))["form"]["form_code"] == "99-0002"
    assert "review_queue=" in captured.err
    assert captured.out == ""

    assert extractor.main([str(xdp)]) == 0
    assert json.loads(capsys.readouterr().out)["form"]["form_code"] == "99-0002"

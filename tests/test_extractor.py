from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from converters.xdp_to_cim import extractor
from converters.xdp_to_cim.extractor import XdpExtractor
from tests.conftest import SYNTHETIC_XDP


def test_form_identity_comes_from_filename_and_revision_from_static_text(synthetic_cim: dict) -> None:
    assert synthetic_cim["form"]["form_code"] == "99-0001"
    assert synthetic_cim["form"]["revision_hint"] == "0126"


def test_master_page_content_is_extracted_under_master_page_container(synthetic_cim: dict) -> None:
    master = [c for c in synthetic_cim["containers"] if c["role"] == "master_page"]
    assert len(master) == 1
    footer = [s for s in synthetic_cim["statics"] if s["container_id"] == master[0]["id"]]
    assert [s["text"] for s in footer] == ["99-0001 (0126)"]


def test_binding_prefix_is_stripped_and_unbound_field_has_no_path(synthetic_cim: dict) -> None:
    by_name = {f["name"]: f["binding"] for f in synthetic_cim["fields"]}
    assert by_name["State"]["source_path"] == "InsuredData.Address.State"
    assert by_name["Notes"]["mode"] == "none"
    assert by_name["Notes"]["source_path"] is None


def test_scripts_are_classified_not_executed(synthetic_cim: dict) -> None:
    scripts = [s for f in synthetic_cim["fields"] for s in f["scripts"]]
    assert len(scripts) == 1
    assert scripts[0]["transferability"] == "manual"
    assert "app.alert" in scripts[0]["body"]


def test_source_node_census_matches_cim_counts(synthetic_cim: dict) -> None:
    census = synthetic_cim["diagnostics"]["counts"]["source_nodes"]
    assert census["field"] == len(synthetic_cim["fields"])
    assert census["draw"] == len(synthetic_cim["statics"])
    assert census["subform"] + census["pageArea"] == len(synthetic_cim["containers"])


def test_extraction_is_deterministic() -> None:
    first = json.dumps(XdpExtractor(str(SYNTHETIC_XDP)).build(), sort_keys=True)
    second = json.dumps(XdpExtractor(str(SYNTHETIC_XDP)).build(), sort_keys=True)
    assert first == second


def test_oversized_input_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(extractor, "MAX_INPUT_BYTES", 10)
    with pytest.raises(ValueError, match="too large"):
        XdpExtractor(str(SYNTHETIC_XDP))


def test_xdp_without_template_packet_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "000000.xdp"
    path.write_text('<xdp:xdp xmlns:xdp="http://ns.adobe.com/xdp/"><config/></xdp:xdp>', encoding="utf-8")
    with pytest.raises(ValueError, match="no XFA template"):
        XdpExtractor(str(path))


def test_malformed_xml_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "000000.xdp"
    path.write_text("<xdp:xdp><template>", encoding="utf-8")
    with pytest.raises(ET.ParseError):
        XdpExtractor(str(path))

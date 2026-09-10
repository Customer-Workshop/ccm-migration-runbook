from __future__ import annotations

import copy
from pathlib import Path

import pytest

from converters.xdp_to_cim.extractor import XdpExtractor
from gates.target_inventory import inventory

DATA = Path(__file__).resolve().parent / "data"
SYNTHETIC_XDP = DATA / "990001.xdp"
SYNTHETIC_XML = DATA / "99-0001.xml"


@pytest.fixture(scope="session")
def synthetic_cim_frozen() -> dict:
    return XdpExtractor(str(SYNTHETIC_XDP)).build()


@pytest.fixture
def synthetic_cim(synthetic_cim_frozen: dict) -> dict:
    return copy.deepcopy(synthetic_cim_frozen)


@pytest.fixture(scope="session")
def synthetic_inventory() -> dict:
    return inventory(SYNTHETIC_XML)

"""Equipment resolution engine tests."""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ai_engine.equipment_engine import EquipmentResolver


def test_resolves_common_equipment_examples():
    resolver = EquipmentResolver()
    examples = [
        ("my phone will not charge", "Electronics", "Phone"),
        ("laptop screen is black", "Electronics", "Laptop"),
        ("vehicle will not start", "Vehicle", "Vehicle"),
        ("onan generator starts then dies", "Power Equipment", "Generator"),
        ("pump keeps running", "Pump", "Pump"),
        ("water pump runs but no water comes out", "Pump", "Water Pump"),
        ("air conditioner is not cooling", "HVAC", "Air Conditioner"),
        ("microwave display is dead", "Appliance", "Microwave"),
        ("roof leaking near chimney", "Building", "Roof"),
        ("router keeps dropping wifi", "Networking Equipment", "Router"),
        ("printer has paper jam", "Office Equipment", "Printer"),
    ]

    for query, expected_category, expected_name in examples:
        result = resolver.resolve(query)
        assert result["equipment_category"] == expected_category
        assert result["equipment_name"] == expected_name
        assert result["confidence"] >= 0.7


def test_resolves_unknown_when_equipment_is_missing():
    result = EquipmentResolver().resolve("it does not work and makes a noise")

    assert result == {
        "equipment_category": "unknown",
        "equipment_name": "unknown",
        "confidence": 0.0,
    }


def test_prefers_specific_equipment_over_generic_match():
    result = EquipmentResolver().resolve("rv water pump has low pressure")

    assert result["equipment_category"] == "Pump"
    assert result["equipment_name"] == "Water Pump"
    assert result["confidence"] > 0.8

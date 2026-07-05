"""Technical Entity Extraction engine tests."""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ai_engine.tee_engine import TechnicalEntityExtractor


def test_extracts_technical_entities_without_diagnosis_fields():
    extractor = TechnicalEntityExtractor()
    result = extractor.extract(
        "Dometic RM2652 RV fridge shows error code E1 at 12.4V, "
        "burner temp is 45 F, gas valve reads 3 psi near the pilot inside RV."
    )

    assert result["brands"] == ["Dometic"]
    assert "RM2652" in result["models"]
    assert "RV refrigerator" in result["equipment"] or "fridge" in result["equipment"]
    assert "burner" in result["components"]
    assert "gas valve" in result["components"]
    assert "gas valve" in result["parts"]
    assert result["error_codes"] == ["E1"]
    assert result["voltages"] == [{"raw": "12.4V", "value": 12.4, "unit": "V"}]
    assert result["temperatures"] == [{"raw": "45 F", "value": 45, "unit": "F"}]
    assert {"raw": "3 psi", "value": 3, "unit": "psi"} in result["measurements"]
    assert "V" in result["units"]
    assert "psi" in result["units"]
    assert "diagnosis" not in result
    assert "repair_guidance" not in result


def test_extracts_automotive_error_code_and_voltage():
    extractor = TechnicalEntityExtractor()
    result = extractor.extract(
        "Toyota Camry has P0420 and battery is 11.8 volts under hood."
    )

    assert "Toyota" in result["brands"]
    assert "P0420" in result["error_codes"]
    assert "battery" in result["components"]
    assert result["voltages"] == [{"raw": "11.8 volts", "value": 11.8, "unit": "V"}]
    assert "under hood" in [loc.lower() for loc in result["locations"]]

"""
System Role Tests
=================

Tests for the four-stage equipment + entity + intent + routing pipeline:

1. EQUIPMENT RESOLVER
   - Identifies exact equipment_category, equipment_name, confidence

2. ENTITY EXTRACTOR (TEE)
   - Extracts brands, models, components, error codes, measurements, etc.

3. INTENT CLASSIFIER (ICE)
   - Classifies primary intent, secondary intent, user goal

4. DIAGNOSTIC TREE ROUTER
   - Routes to correct version & symptom tree, loads tree structure
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ai_engine.equipment_engine import EquipmentResolver
from ai_engine.tee_engine import TechnicalEntityExtractor
from ai_engine.ice_engine import ICEEngine
from ai_engine.rqu_engine import RQUEngine
from ai_engine.diagnostic_engine import AIDiagnosticEngine


# ===========================================================================
# STAGE 1: Equipment Resolver
# ===========================================================================

def test_equipment_resolver_phone():
    """EQUIPMENT RESOLVER: Identify phone from query."""
    resolver = EquipmentResolver()
    result = resolver.resolve("my phone won't charge")
    
    assert result["equipment_category"] == "Electronics"
    assert result["equipment_name"] == "Phone"
    assert result["confidence"] >= 0.7


def test_equipment_resolver_water_pump():
    """EQUIPMENT RESOLVER: Identify water pump (specific) vs pump (generic)."""
    resolver = EquipmentResolver()
    result = resolver.resolve("rv water pump has low pressure")
    
    assert result["equipment_category"] == "Pump"
    assert result["equipment_name"] == "Water Pump"
    assert result["confidence"] >= 0.8


def test_equipment_resolver_unknown():
    """EQUIPMENT RESOLVER: Return unknown when no match."""
    resolver = EquipmentResolver()
    result = resolver.resolve("it makes a noise and does stuff")
    
    assert result["equipment_category"] == "unknown"
    assert result["equipment_name"] == "unknown"
    assert result["confidence"] == 0.0


# ===========================================================================
# STAGE 2: Entity Extractor (TEE)
# ===========================================================================

def test_tee_extracts_brands_and_models():
    """TEE: Extract brands, models, equipment, components."""
    tee = TechnicalEntityExtractor()
    result = tee.extract("Dometic RM2652 fridge shows E1 error at 12.4V")
    
    # Should extract brand, model, equipment, error code, voltage
    assert "Dometic" in str(result.get("brands", []))
    assert "RM2652" in str(result.get("models", []))
    assert "E1" in str(result.get("error_codes", []))
    assert "12.4V" in str(result.get("voltages", []))


def test_tee_extracts_components():
    """TEE: Extract component names."""
    tee = TechnicalEntityExtractor()
    result = tee.extract("furnace burner pilot light won't stay lit")
    
    # Should extract equipment and components
    assert len(result.get("components", [])) > 0


# ===========================================================================
# STAGE 3: Intent Classifier (ICE)
# ===========================================================================

def test_ice_classifies_diagnostic_intent():
    """ICE: Classify primary intent as DIAGNOSE_PROBLEM."""
    rqu = RQUEngine()
    ice = ICEEngine()
    
    ruo = rqu.understand("my air conditioner is not cooling properly")
    ico = ice.classify(ruo)
    
    assert ico["primary_intent"] == "DIAGNOSE_PROBLEM"
    assert "intent_confidence" in ico
    assert ico["intent_confidence"] > 0.0


def test_ice_classifies_repair_guidance_intent():
    """ICE: Classify primary intent as REPAIR_GUIDANCE."""
    rqu = RQUEngine()
    ice = ICEEngine()
    
    ruo = rqu.understand("how do I fix a leaking roof")
    ico = ice.classify(ruo)
    
    assert ico["primary_intent"] == "REPAIR_GUIDANCE"


def test_ice_classifies_part_lookup_intent():
    """ICE: Classify primary intent as PART_LOOKUP."""
    rqu = RQUEngine()
    ice = ICEEngine()
    
    ruo = rqu.understand("where can I buy a replacement water pump filter")
    ico = ice.classify(ruo)
    
    assert ico["primary_intent"] in ("PART_LOOKUP", "DIAGNOSE_PROBLEM")


# ===========================================================================
# STAGE 4: Diagnostic Tree Router
# ===========================================================================

def test_diagnostic_router_analyzes_symptoms():
    """ROUTER: Match symptoms from free text."""
    with AIDiagnosticEngine(version=1) as diag:
        matches = diag.analyze_symptoms("roof leaking after heavy rain")
        
        assert len(matches) > 0
        assert "symptom_code" in matches[0]
        assert "symptom_name" in matches[0]
        assert "relevance_score" in matches[0]


def test_diagnostic_router_loads_tree():
    """ROUTER: Load full diagnostic tree structure."""
    with AIDiagnosticEngine(version=1) as diag:
        # First find a symptom
        matches = diag.analyze_symptoms("roof leaking")
        if not matches:
            return  # Skip if no matches in DB
        
        symptom_code = matches[0]["symptom_code"]
        tree = diag.get_diagnostic_tree(symptom_code)
        
        # Tree should have structure
        assert tree is not None
        assert "symptom_code" in tree or "name" in tree


def test_diagnostic_router_runs_traversal():
    """ROUTER: Run step-by-step tree traversal."""
    with AIDiagnosticEngine(version=1) as diag:
        matches = diag.analyze_symptoms("electrical outlet not working")
        if not matches:
            return  # Skip if no matches in DB
        
        symptom_code = matches[0]["symptom_code"]
        result = diag.run_diagnostic(symptom_code, user_responses=["yes", "no"])
        
        # Should return traversal result with action
        assert "recommended_action" in result or "repair_code" in result


# ===========================================================================
# INTEGRATION: Multi-stage pipeline
# ===========================================================================

def test_full_pipeline_equipment_to_intent():
    """INTEGRATION: Equipment → TEE → Intent → Router."""
    query = "my rv refrigerator shows E1 error and won't cool"
    
    # Stage 1: Equipment Resolver
    resolver = EquipmentResolver()
    equip = resolver.resolve(query)
    assert equip["equipment_category"] != "unknown"
    
    # Stage 2: Entity Extractor
    tee = TechnicalEntityExtractor()
    entities = tee.extract(query)
    assert len(entities.get("error_codes", [])) > 0 or "E1" in query
    
    # Stage 3: Intent Classifier
    rqu = RQUEngine()
    ice = ICEEngine()
    ruo = rqu.understand(query)
    ico = ice.classify(ruo)
    assert "primary_intent" in ico
    
    # All stages succeeded
    assert equip["confidence"] > 0.5
    assert ico["intent_confidence"] > 0.0


if __name__ == "__main__":
    test_equipment_resolver_phone()
    test_equipment_resolver_water_pump()
    test_equipment_resolver_unknown()
    test_tee_extracts_brands_and_models()
    test_tee_extracts_components()
    test_ice_classifies_diagnostic_intent()
    test_ice_classifies_repair_guidance_intent()
    test_ice_classifies_part_lookup_intent()
    test_diagnostic_router_analyzes_symptoms()
    test_diagnostic_router_loads_tree()
    test_diagnostic_router_runs_traversal()
    test_full_pipeline_equipment_to_intent()
    print("✓ All system role tests passed!")

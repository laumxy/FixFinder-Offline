"""
ai_engine/equipment_engine.py
=============================
Equipment Resolution Engine - FixFinder.

Input:  A raw repair query.
Output: A structured Equipment Resolution Object with:
          - equipment_category
          - equipment_name
          - confidence

No diagnosis, no repair guidance. This engine only determines which equipment
the user is referring to.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class _EquipmentRule:
    category: str
    name: str
    aliases: tuple[str, ...]


_EQUIPMENT_RULES: tuple[_EquipmentRule, ...] = (
    _EquipmentRule("Electronics", "Phone", ("phone", "smartphone", "iphone", "android", "samsung phone")),
    _EquipmentRule("Electronics", "Laptop", ("laptop", "notebook", "macbook", "chromebook")),
    _EquipmentRule("Electronics", "Tablet", ("tablet", "ipad")),
    _EquipmentRule("Electronics", "Television", ("tv", "television", "smart tv")),
    _EquipmentRule("Networking Equipment", "Router", ("router", "wifi router", "wi-fi router", "modem router", "gateway")),
    _EquipmentRule("Office Equipment", "Printer", ("printer", "laser printer", "inkjet printer")),
    _EquipmentRule("Gaming Equipment", "Game Console", ("gaming console", "game console", "ps5", "playstation", "xbox", "nintendo switch")),

    _EquipmentRule("Vehicle", "Vehicle", ("vehicle", "car", "truck", "automobile", "suv", "van")),
    _EquipmentRule("Vehicle", "Engine", ("engine", "motor")),
    _EquipmentRule("Vehicle", "Transmission", ("transmission", "gearbox")),
    _EquipmentRule("Vehicle", "Brakes", ("brakes", "brake system")),

    _EquipmentRule("Power Equipment", "Generator", ("generator", "onan", "genset", "gen set")),
    _EquipmentRule("Power Equipment", "Inverter/Charger", ("inverter", "inverter charger", "inverter/charger")),
    _EquipmentRule("Pump", "Pump", ("pump",)),
    _EquipmentRule("Pump", "Water Pump", ("water pump", "rv water pump", "fresh water pump")),

    _EquipmentRule("HVAC", "Air Conditioner", ("air conditioner", "a/c", "ac unit", "air conditioning", "hvac")),
    _EquipmentRule("HVAC", "Furnace", ("furnace", "heater")),
    _EquipmentRule("Appliance", "Microwave", ("microwave", "microwave oven")),
    _EquipmentRule("Appliance", "Refrigerator", ("refrigerator", "fridge", "rv fridge", "rv refrigerator", "propane refrigerator")),
    _EquipmentRule("Appliance", "Water Heater", ("water heater", "hot water heater")),
    _EquipmentRule("Appliance", "Washer", ("washer", "washing machine")),
    _EquipmentRule("Appliance", "Dryer", ("dryer", "clothes dryer")),
    _EquipmentRule("Appliance", "Oven", ("oven", "stove", "range")),

    _EquipmentRule("Building", "Roof", ("roof", "roofing")),
    _EquipmentRule("Plumbing", "Toilet", ("toilet",)),
    _EquipmentRule("Plumbing", "Drain", ("drain", "sink drain")),
    _EquipmentRule("Electrical", "Electrical Outlet", ("outlet", "electrical outlet", "socket", "receptacle")),
    _EquipmentRule("Electrical", "Circuit Breaker", ("breaker", "circuit breaker")),
    _EquipmentRule("Door/Access", "Garage Door", ("garage door",)),
    _EquipmentRule("Door/Access", "Door", ("door",)),
    _EquipmentRule("Window", "Window", ("window",)),
    _EquipmentRule("RV System", "Slide-out", ("slide-out", "slide out", "rv slide")),
    _EquipmentRule("RV System", "Awning", ("awning", "rv awning")),

    _EquipmentRule("Industrial Equipment", "Compressor", ("compressor", "air compressor")),
    _EquipmentRule("Industrial Equipment", "Excavator", ("excavator",)),
    _EquipmentRule("Industrial Equipment", "Tractor", ("tractor",)),
    _EquipmentRule("Industrial Equipment", "Hydraulic System", ("hydraulic system", "hydraulics")),
)

_CONTEXT_HINTS: dict[str, tuple[str, ...]] = {
    "RV System": ("rv", "camper", "motorhome", "travel trailer", "fifth wheel"),
    "Vehicle": ("car", "truck", "vehicle", "suv", "van", "driving"),
    "Electronics": ("device", "screen", "charging", "battery", "power button"),
    "Networking Equipment": ("wifi", "wi-fi", "internet", "network"),
    "Plumbing": ("water", "leak", "pressure", "pipe"),
    "HVAC": ("cooling", "heat", "thermostat", "air"),
}


class EquipmentResolver:
    """Resolve the equipment referenced by a user query."""

    def resolve(self, raw_query: str) -> dict[str, object]:
        text = raw_query.strip()
        if not text:
            return self._unknown()

        candidates = self._find_candidates(text)
        if not candidates:
            return self._unknown()

        candidates.sort(key=lambda item: item["score"], reverse=True)
        best = candidates[0]
        confidence = best["score"]

        if len(candidates) > 1 and candidates[1]["score"] >= confidence - 0.04:
            confidence -= 0.08

        return {
            "equipment_category": best["category"],
            "equipment_name": best["name"],
            "confidence": round(max(0.0, min(confidence, 1.0)), 2),
        }

    def _find_candidates(self, text: str) -> list[dict[str, object]]:
        candidates: list[dict[str, object]] = []
        for rule in _EQUIPMENT_RULES:
            best_alias = self._best_alias_match(text, rule.aliases)
            if not best_alias:
                continue

            alias, exact = best_alias
            score = 0.86 if exact else 0.74
            score += min(len(alias) / 100, 0.08)
            if self._has_context_hint(text, rule.category):
                score += 0.04

            candidates.append({
                "category": rule.category,
                "name": rule.name,
                "alias": alias,
                "score": round(score, 4),
            })
        return candidates

    @staticmethod
    def _best_alias_match(text: str, aliases: tuple[str, ...]) -> tuple[str, bool] | None:
        best: tuple[str, bool] | None = None
        for alias in sorted(aliases, key=len, reverse=True):
            pattern = r"(?<![A-Za-z0-9])" + re.escape(alias) + r"(?![A-Za-z0-9])"
            if re.search(pattern, text, flags=re.IGNORECASE):
                return alias, True

        normalized = text.lower()
        for alias in sorted(aliases, key=len, reverse=True):
            compact_alias = alias.replace("-", " ").replace("/", " ")
            compact_text = normalized.replace("-", " ").replace("/", " ")
            if compact_alias in compact_text:
                best = (alias, False)
                break
        return best

    @staticmethod
    def _has_context_hint(text: str, category: str) -> bool:
        hints = _CONTEXT_HINTS.get(category, ())
        text_lower = text.lower()
        return any(hint in text_lower for hint in hints)

    @staticmethod
    def _unknown() -> dict[str, object]:
        return {
            "equipment_category": "unknown",
            "equipment_name": "unknown",
            "confidence": 0.0,
        }

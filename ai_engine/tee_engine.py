"""
ai_engine/tee_engine.py
=======================
Technical Entity Extraction (TEE) Engine - FixFinder.

Input:  A raw repair query.
Output: A structured Technical Entity Object with:
          - brands
          - models
          - equipment
          - components
          - parts
          - measurements
          - temperatures
          - voltages
          - error_codes
          - locations
          - units

No diagnosis, no repair guidance, no inferred failures. This engine extracts
technical entities only.
"""

from __future__ import annotations

import re
from typing import Any


_BRANDS: tuple[str, ...] = (
    "Dometic", "Norcold", "Onan", "Generac", "Suburban", "Atwood",
    "Coleman", "Carrier", "Trane", "Lennox", "Rheem", "Whirlpool",
    "Samsung", "LG", "Sony", "Apple", "Dell", "HP", "Lenovo", "Asus",
    "Acer", "Bosch", "Toyota", "Honda", "Ford", "Chevrolet", "GM",
    "GMC", "Ram", "Dodge", "Nissan", "Hyundai", "Kia", "BMW",
    "Mercedes", "Volvo", "Caterpillar", "CAT", "John Deere", "Kubota",
)

_EQUIPMENT: tuple[str, ...] = (
    "RV refrigerator", "propane refrigerator", "refrigerator", "fridge",
    "furnace", "air conditioner", "water heater", "water pump",
    "slide-out", "slide out", "awning", "leveling system", "leveling jacks",
    "generator", "inverter", "inverter/charger", "electrical outlet",
    "outlet", "circuit breaker", "breaker", "roof", "toilet", "drain",
    "window", "door", "garage door", "laptop", "smartphone", "phone",
    "iphone", "tablet", "TV", "television", "router", "printer",
    "gaming console", "PS5", "Xbox", "car", "truck", "automobile",
    "vehicle", "engine", "brakes", "transmission", "excavator", "tractor",
    "hydraulic system", "compressor", "industrial motor",
)

_COMPONENTS: tuple[str, ...] = (
    "burner", "flame", "orifice", "jet", "pilot", "thermocouple",
    "safety sensor", "igniter", "ignitor", "electrode", "fan", "blower",
    "pump", "impeller", "battery", "fuse", "breaker", "gfci",
    "thermostat", "t-stat", "valve", "solenoid", "gas valve", "seal",
    "gasket", "o-ring", "screen", "display", "lcd", "oled", "panel",
    "charging port", "usb port", "lightning port", "carburetor", "carb",
    "starter", "starter motor", "alternator", "radiator", "spark plug",
    "ignition coil", "sensor", "compressor", "capacitor", "relay",
)

_PARTS: tuple[str, ...] = (
    "thermocouple", "igniter", "electrode", "orifice", "burner assembly",
    "control board", "circuit board", "fuse", "breaker", "gfci outlet",
    "capacitor", "relay", "battery", "starter motor", "alternator",
    "radiator", "spark plug", "ignition coil", "fuel filter", "oil filter",
    "water pump", "gas valve", "solenoid valve", "thermostat", "fan motor",
    "blower motor", "charging port", "screen assembly", "display panel",
    "o-ring", "gasket", "seal", "hose", "belt", "sensor",
)

_LOCATION_TERMS: tuple[str, ...] = (
    "inside", "outside", "under", "behind", "near", "next to", "beside",
    "above", "below", "left side", "right side", "front", "rear", "back",
    "roof", "basement", "bathroom", "kitchen", "garage", "engine bay",
    "dashboard", "under hood", "shore power", "breaker panel", "fuse box",
    "rv", "camper", "motorhome", "travel trailer", "chimney", "outlet",
)

_UNIT_ALIASES: dict[str, str] = {
    "v": "V",
    "volt": "V",
    "volts": "V",
    "vac": "VAC",
    "vdc": "VDC",
    "a": "A",
    "amp": "A",
    "amps": "A",
    "ma": "mA",
    "ohm": "ohm",
    "ohms": "ohm",
    "psi": "psi",
    "bar": "bar",
    "f": "F",
    "c": "C",
    "degf": "F",
    "degc": "C",
    "degree": "degree",
    "degrees": "degree",
    "inch": "in",
    "inches": "in",
    "in": "in",
    "ft": "ft",
    "feet": "ft",
    "mm": "mm",
    "cm": "cm",
    "rpm": "rpm",
    "w": "W",
    "kw": "kW",
    "btu": "BTU",
    "lb": "lb",
    "lbs": "lb",
}

_MEASUREMENT_RE = re.compile(
    r"(?P<value>-?\d+(?:\.\d+)?)\s*(?P<unit>"
    r"psi|bar|amps?|a|ma|ohms?|rpm|watts?|w|kw|btu|inches|inch|in|ft|feet|"
    r"mm|cm|lbs?|pounds?|%|percent"
    r")\b",
    re.IGNORECASE,
)

_VOLTAGE_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>vdc|vac|volts?|v)\b",
    re.IGNORECASE,
)

_TEMPERATURE_RE = re.compile(
    r"(?P<value>-?\d+(?:\.\d+)?)\s*(?:degrees?|deg\.?)?\s*(?P<unit>[fc])\b",
    re.IGNORECASE,
)

_ERROR_CODE_RE = re.compile(r"\b(?P<code>(?:P|B|C|U)\d{4}|[EFH]\d{1,3})\b", re.IGNORECASE)

_CONTEXT_ERROR_CODE_RE = re.compile(
    r"\b(?:error|fault|code|dtc|obd|obd2|obd-ii)\s*(?:code\s*)?"
    r"(?P<code>[A-Z]{1,4}-?\d{1,5}|\d{1,5})\b",
    re.IGNORECASE,
)

_MODEL_RE = re.compile(
    r"\b(?=[A-Z0-9-]*\d)(?=[A-Z0-9-]*[A-Z])[A-Z]{1,6}[- ]?\d{2,6}[A-Z0-9-]*\b"
)


class TechnicalEntityExtractor:
    """Extract technical entities from a repair query without diagnosing."""

    def extract(self, raw_query: str) -> dict[str, Any]:
        query = raw_query.strip()
        measurements = self._extract_measurements(query)
        temperatures = self._extract_temperatures(query)
        voltages = self._extract_voltages(query)
        return {
            "brands": self._extract_terms(query, _BRANDS),
            "models": self._extract_models(query),
            "equipment": self._extract_terms(query, _EQUIPMENT),
            "components": self._extract_terms(query, _COMPONENTS),
            "parts": self._extract_terms(query, _PARTS),
            "measurements": measurements,
            "temperatures": temperatures,
            "voltages": voltages,
            "error_codes": self._extract_error_codes(query),
            "locations": self._extract_locations(query),
            "units": self._extract_units(query, measurements, temperatures, voltages),
        }

    @staticmethod
    def _extract_terms(text: str, terms: tuple[str, ...]) -> list[str]:
        found: list[str] = []
        seen: set[str] = set()
        for term in sorted(terms, key=len, reverse=True):
            pattern = r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])"
            if re.search(pattern, text, flags=re.IGNORECASE):
                canonical = term
                key = canonical.lower()
                if key not in seen:
                    seen.add(key)
                    found.append(canonical)
        return found

    @staticmethod
    def _structured_matches(text: str, regex: re.Pattern) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for match in regex.finditer(text):
            raw = match.group(0).strip()
            value = match.groupdict().get("value")
            unit = match.groupdict().get("unit")
            if not value or not unit:
                continue
            normalized_unit = _UNIT_ALIASES.get(unit.lower(), unit)
            key = (value, normalized_unit.lower())
            if key in seen:
                continue
            seen.add(key)
            results.append({
                "raw": raw,
                "value": float(value) if "." in value else int(value),
                "unit": normalized_unit,
            })
        return results

    def _extract_measurements(self, text: str) -> list[dict[str, Any]]:
        voltage_spans = {m.span() for m in _VOLTAGE_RE.finditer(text)}
        temperature_spans = {m.span() for m in _TEMPERATURE_RE.finditer(text)}
        blocked_spans = voltage_spans | temperature_spans

        results: list[dict[str, Any]] = []
        for match in _MEASUREMENT_RE.finditer(text):
            if match.span() in blocked_spans:
                continue
            value = match.group("value")
            unit = match.group("unit")
            normalized_unit = _UNIT_ALIASES.get(unit.lower(), unit)
            results.append({
                "raw": match.group(0).strip(),
                "value": float(value) if "." in value else int(value),
                "unit": normalized_unit,
            })
        return self._dedupe_structured(results)

    def _extract_temperatures(self, text: str) -> list[dict[str, Any]]:
        return self._structured_matches(text, _TEMPERATURE_RE)

    def _extract_voltages(self, text: str) -> list[dict[str, Any]]:
        return self._structured_matches(text, _VOLTAGE_RE)

    @staticmethod
    def _extract_error_codes(text: str) -> list[str]:
        codes: list[str] = []
        seen: set[str] = set()
        for regex in (_ERROR_CODE_RE, _CONTEXT_ERROR_CODE_RE):
            for match in regex.finditer(text):
                code = match.group("code").upper().replace(" ", "")
                if code not in seen:
                    seen.add(code)
                    codes.append(code)
        return codes

    @staticmethod
    def _extract_models(text: str) -> list[str]:
        models: list[str] = []
        seen: set[str] = set()
        error_codes = set(TechnicalEntityExtractor._extract_error_codes(text))
        for match in _MODEL_RE.finditer(text):
            model = re.sub(r"\s+", "-", match.group(0).upper())
            if model in error_codes:
                continue
            if model not in seen:
                seen.add(model)
                models.append(model)
        return models

    @staticmethod
    def _extract_locations(text: str) -> list[str]:
        locations = TechnicalEntityExtractor._extract_terms(text, _LOCATION_TERMS)
        phrase_re = re.compile(
            r"\b(?:inside|outside|under|behind|near|next to|beside|above|below|in|on)\s+"
            r"(?:the\s+|my\s+|a\s+|an\s+)?"
            r"([a-z][a-z0-9-]*(?:\s+[a-z][a-z0-9-]*){0,3})",
            re.IGNORECASE,
        )
        seen = {loc.lower() for loc in locations}
        for match in phrase_re.finditer(text):
            phrase = match.group(0).strip(" .,;:")
            key = phrase.lower()
            if key not in seen:
                seen.add(key)
                locations.append(phrase)
        return locations

    @staticmethod
    def _extract_units(
        text: str,
        measurements: list[dict[str, Any]] | None = None,
        temperatures: list[dict[str, Any]] | None = None,
        voltages: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        units: list[str] = []
        seen: set[str] = set()
        unit_re = re.compile(
            r"\b(vdc|vac|volts?|v|amps?|ma|ohms?|psi|bar|degrees?|deg|"
            r"f|c|rpm|watts?|w|kw|btu|inches|inch|in|ft|feet|mm|cm|lbs?|"
            r"pounds?|percent|%)\b",
            re.IGNORECASE,
        )
        for match in unit_re.finditer(text):
            raw_unit = match.group(1)
            normalized = _UNIT_ALIASES.get(raw_unit.lower(), raw_unit)
            if normalized.lower() not in seen:
                seen.add(normalized.lower())
                units.append(normalized)
        for item in (measurements or []) + (temperatures or []) + (voltages or []):
            normalized = str(item.get("unit", ""))
            if normalized and normalized.lower() not in seen:
                seen.add(normalized.lower())
                units.append(normalized)
        return units

    @staticmethod
    def _dedupe_structured(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[tuple[Any, str]] = set()
        for item in items:
            key = (item.get("value"), str(item.get("unit", "")).lower())
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

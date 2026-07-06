"""
ai_engine/cie_engine.py
========================
Component Identification Engine (CIE) — FixFinder.

System Role:
  Identify every component involved in a repair query.

Input:   A raw user repair query string.
Output:  JSON with a structured list of every component identified,
         each annotated with:
           - component_name   (canonical name)
           - component_type   (mechanical / electrical / electronic /
                               gas / fluid / structural / control)
           - likely_role      (what function it serves)
           - suspect          (True if likely the failing component)

No diagnosis. No repair guidance. Components only.

Usage
-----
    from ai_engine.cie_engine import ComponentIdentifier

    ci  = ComponentIdentifier()
    out = ci.identify("My RV fridge won't light on propane — no flame")
    # out["components"] → [
    #   {"component_name": "Burner Orifice", "component_type": "gas", ...},
    #   {"component_name": "Thermocouple",   "component_type": "electrical", ...},
    #   ...
    # ]
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Master component catalogue
# Each entry:  (canonical_name, type, role, trigger_keywords, system_keywords)
#
#  trigger_keywords  — any of these in the query → component is SUSPECT
#  system_keywords   — any of these in the query → component is INVOLVED
#                      (relevant to the equipment even if not failing)
# ---------------------------------------------------------------------------

_CATALOGUE: list[dict[str, Any]] = [

    # ── Gas / Combustion ────────────────────────────────────────────────────
    {
        "component_name": "Burner Orifice",
        "component_type": "gas",
        "role": "Meters propane/gas flow to the burner",
        "trigger_keywords": ["won't light", "wont light", "no flame", "won't ignite",
                              "wont ignite", "no ignition", "orifice", "clogged burner",
                              "pilot won't stay", "pilot wont stay"],
        "system_keywords":  ["propane", "gas", "burner", "furnace",
                              "water heater", "stove", "oven", "heater"],
    },
    {
        "component_name": "Thermocouple",
        "component_type": "electrical",
        "role": "Safety sensor that keeps the gas valve open when flame is present",
        "trigger_keywords": ["thermocouple", "pilot won't stay", "pilot wont stay",
                              "lights then goes out", "no flame after releasing",
                              "safety sensor"],
        "system_keywords":  ["propane", "gas", "burner", "furnace", "water heater",
                              "pilot", "flame"],
    },
    {
        "component_name": "Igniter / Electrode",
        "component_type": "electrical",
        "role": "Creates a spark to ignite the gas/propane mixture",
        "trigger_keywords": ["won't spark", "wont spark", "no spark", "igniter",
                              "electrode", "won't light", "wont light",
                              "no ignition", "clicking but won't", "clicking but wont"],
        "system_keywords":  ["propane", "gas", "burner", "furnace", "water heater",
                              "stove", "pilot"],
    },
    {
        "component_name": "Gas Valve / Solenoid",
        "component_type": "gas",
        "role": "Controls propane/gas flow to the burner",
        "trigger_keywords": ["gas valve", "solenoid", "no gas", "gas not flowing",
                              "valve stuck", "valve failed", "smell gas",
                              "gas smell", "propane smell", "smell propane"],
        "system_keywords":  ["propane", "gas", "burner", "furnace", "water heater"],
    },
    {
        "component_name": "Flue / Chimney Tube",
        "component_type": "structural",
        "role": "Exhausts combustion gases from the burner",
        "trigger_keywords": ["flue", "chimney", "blocked exhaust", "nest in flue",
                              "insect nest", "spider nest", "no draft"],
        "system_keywords":  ["propane", "gas", "furnace", "water heater",
                              "rv fridge", "refrigerator"],
    },
    {
        "component_name": "Pilot Light Assembly",
        "component_type": "gas",
        "role": "Small standing flame that ignites the main burner",
        "trigger_keywords": ["pilot", "pilot light", "pilot won't stay",
                              "pilot keeps going out"],
        "system_keywords":  ["furnace", "water heater", "gas"],
    },

    # ── Refrigeration / Cooling ─────────────────────────────────────────────
    {
        "component_name": "Compressor",
        "component_type": "mechanical",
        "role": "Pumps refrigerant through the cooling cycle",
        "trigger_keywords": ["compressor", "not cooling", "warm fridge",
                              "refrigerant", "clicking compressor",
                              "compressor not running"],
        "system_keywords":  ["refrigerator", "fridge", "air conditioner", "ac",
                              "freezer", "cooling"],
    },
    {
        "component_name": "Capacitor",
        "component_type": "electrical",
        "role": "Provides starting/running power to motors",
        "trigger_keywords": ["capacitor", "won't start", "hums but won't run",
                              "ac not cooling", "single click then nothing"],
        "system_keywords":  ["air conditioner", "hvac", "compressor", "motor",
                              "fan motor", "generator"],
    },
    {
        "component_name": "Thermostat",
        "component_type": "control",
        "role": "Controls temperature set-point and cycles equipment on/off",
        "trigger_keywords": ["thermostat", "wrong temperature", "won't turn on",
                              "always running", "temperature off",
                              "t-stat", "temperature sensor"],
        "system_keywords":  ["refrigerator", "fridge", "hvac", "furnace",
                              "air conditioner", "water heater", "cooling",
                              "heating"],
    },
    {
        "component_name": "Evaporator Coil",
        "component_type": "mechanical",
        "role": "Absorbs heat inside the refrigerated space",
        "trigger_keywords": ["evaporator", "frozen coil", "iced up", "frost buildup",
                              "not cooling inside", "ice on coil"],
        "system_keywords":  ["refrigerator", "fridge", "air conditioner", "freezer"],
    },
    {
        "component_name": "Condenser Coil",
        "component_type": "mechanical",
        "role": "Releases absorbed heat to the outside air",
        "trigger_keywords": ["condenser", "dirty coils", "not cooling",
                              "overheating ac", "outside unit hot"],
        "system_keywords":  ["refrigerator", "air conditioner", "hvac", "fridge"],
    },
    {
        "component_name": "Fan / Blower Motor",
        "component_type": "mechanical",
        "role": "Circulates air across coils or through the system",
        "trigger_keywords": ["fan", "blower", "no airflow", "fan not spinning",
                              "fan motor", "loud fan", "fan noise"],
        "system_keywords":  ["refrigerator", "air conditioner", "hvac", "furnace",
                              "cooling", "heating", "laptop", "generator"],
    },
    {
        "component_name": "Cooling Unit (Absorption)",
        "component_type": "mechanical",
        "role": "Ammonia-based cooling unit in RV absorption refrigerators",
        "trigger_keywords": ["ammonia smell", "yellow stain", "cooling unit",
                              "absorption fridge not cooling",
                              "not cooling on electric or gas"],
        "system_keywords":  ["rv fridge", "rv refrigerator", "dometic", "norcold",
                              "absorption"],
    },

    # ── Electrical ──────────────────────────────────────────────────────────
    {
        "component_name": "Circuit Breaker",
        "component_type": "electrical",
        "role": "Protects a circuit by tripping when current exceeds safe levels",
        "trigger_keywords": ["breaker", "circuit breaker", "trips",
                              "breaker tripped", "keeps tripping",
                              "blown breaker", "reset breaker"],
        "system_keywords":  ["outlet", "circuit", "panel", "electrical",
                              "power", "electrical panel"],
    },
    {
        "component_name": "Fuse",
        "component_type": "electrical",
        "role": "One-time overcurrent protection device",
        "trigger_keywords": ["fuse", "blown fuse", "fuse blown", "fuse box"],
        "system_keywords":  ["electrical", "power", "circuit", "12v",
                              "water pump", "slide", "rv"],
    },
    {
        "component_name": "GFCI Outlet",
        "component_type": "electrical",
        "role": "Ground-fault circuit interrupter protecting against electrocution",
        "trigger_keywords": ["gfci", "outlet dead", "outlet not working",
                              "reset button", "test button"],
        "system_keywords":  ["outlet", "bathroom", "kitchen", "electrical"],
    },
    {
        "component_name": "Relay / Contactor",
        "component_type": "electrical",
        "role": "Electrically-controlled switch for high-current loads",
        "trigger_keywords": ["relay", "contactor", "clicking relay",
                              "starter relay", "compressor relay",
                              "start relay"],
        "system_keywords":  ["compressor", "starter", "motor", "ac",
                              "refrigerator", "generator"],
    },
    {
        "component_name": "Battery",
        "component_type": "electrical",
        "role": "Stores and delivers electrical energy",
        "trigger_keywords": ["battery", "dead battery", "battery dead",
                              "battery draining", "no power", "won't start",
                              "wont start", "battery not charging", "weak battery",
                              "clicking", "just clicks", "single click",
                              "rapid clicking", "click when starting"],
        "system_keywords":  ["car", "truck", "rv", "slide", "leveling",
                              "laptop", "phone", "tablet", "smartphone"],
    },
    {
        "component_name": "Alternator",
        "component_type": "electrical",
        "role": "Charges the battery while the engine runs",
        "trigger_keywords": ["alternator", "battery not charging while driving",
                              "charging warning light", "battery light on"],
        "system_keywords":  ["car", "truck", "vehicle", "engine"],
    },
    {
        "component_name": "Inverter / Converter",
        "component_type": "electrical",
        "role": "Converts between AC and DC power",
        "trigger_keywords": ["inverter", "converter", "no 120v",
                              "no ac power", "inverter not working",
                              "inverter alarm"],
        "system_keywords":  ["rv", "battery", "shore power", "12v", "120v"],
    },
    {
        "component_name": "Wiring / Connections",
        "component_type": "electrical",
        "role": "Conducts electricity between components",
        "trigger_keywords": ["loose wire", "bad connection", "burnt wire",
                              "melted wire", "wire shorting", "corrosion",
                              "wiring harness"],
        "system_keywords":  ["electrical", "circuit", "power", "panel"],
    },

    # ── Electronic / Control ────────────────────────────────────────────────
    {
        "component_name": "Control Board / PCB",
        "component_type": "electronic",
        "role": "Main electronic brain controlling equipment operation",
        "trigger_keywords": ["control board", "circuit board", "pcb",
                              "main board", "error code", "fault code",
                              "won't respond", "display error",
                              "board failed"],
        "system_keywords":  ["refrigerator", "furnace", "hvac", "generator",
                              "water heater", "washer", "dishwasher"],
    },
    {
        "component_name": "Display / Screen",
        "component_type": "electronic",
        "role": "Visual output interface",
        "trigger_keywords": ["screen", "display", "blank screen",
                              "cracked screen", "no display", "screen dead",
                              "screen flickering", "display not working"],
        "system_keywords":  ["laptop", "phone", "tablet", "tv", "monitor",
                              "smartphone", "iphone"],
    },
    {
        "component_name": "Sensor (Temperature / Pressure / Flow)",
        "component_type": "electronic",
        "role": "Measures physical conditions and reports to the control system",
        "trigger_keywords": ["sensor", "temp sensor", "pressure sensor",
                              "flow sensor", "bad sensor", "sensor fault",
                              "sensor error", "o2 sensor", "maf sensor"],
        "system_keywords":  ["engine", "hvac", "water heater", "furnace",
                              "rv", "generator"],
    },
    {
        "component_name": "Charging Port",
        "component_type": "electronic",
        "role": "Physical connector for charging the device battery",
        "trigger_keywords": ["charging port", "usb port", "won't charge",
                              "not charging", "charging port broken",
                              "loose charging port"],
        "system_keywords":  ["phone", "laptop", "tablet", "iphone",
                              "smartphone"],
    },

    # ── Plumbing / Fluid ────────────────────────────────────────────────────
    {
        "component_name": "Water Pump",
        "component_type": "mechanical",
        "role": "Pressurises fresh water for distribution through the plumbing",
        "trigger_keywords": ["water pump", "no water", "pump not working",
                              "pump runs but no water", "pump won't turn on",
                              "pump noisy"],
        "system_keywords":  ["water", "rv", "plumbing", "fresh water tank"],
    },
    {
        "component_name": "Inlet Strainer / Filter",
        "component_type": "mechanical",
        "role": "Prevents debris from entering the pump or appliance",
        "trigger_keywords": ["strainer", "clogged filter", "no water flow",
                              "low water pressure", "filter blocked"],
        "system_keywords":  ["water pump", "water heater", "washing machine",
                              "plumbing"],
    },
    {
        "component_name": "Valve (Water / Shut-off)",
        "component_type": "fluid",
        "role": "Controls water flow in the plumbing system",
        "trigger_keywords": ["shut-off valve", "valve stuck", "valve closed",
                              "no water", "water valve"],
        "system_keywords":  ["plumbing", "water", "toilet", "sink"],
    },
    {
        "component_name": "Pipe / Hose",
        "component_type": "fluid",
        "role": "Conducts water, gas, or other fluids between components",
        "trigger_keywords": ["pipe", "hose", "leaking pipe", "burst pipe",
                              "cracked hose", "hose loose", "pipe leak"],
        "system_keywords":  ["plumbing", "water", "coolant", "hydraulic",
                              "propane", "gas"],
    },
    {
        "component_name": "Seal / Gasket / O-ring",
        "component_type": "mechanical",
        "role": "Creates a leak-proof connection between components",
        "trigger_keywords": ["seal", "gasket", "o-ring", "leaking seal",
                              "bad gasket", "seal failure", "oil leak",
                              "water leak"],
        "system_keywords":  ["pump", "engine", "water heater", "compressor",
                              "plumbing"],
    },

    # ── Mechanical ──────────────────────────────────────────────────────────
    {
        "component_name": "Motor",
        "component_type": "mechanical",
        "role": "Converts electrical energy into mechanical motion",
        "trigger_keywords": ["motor", "motor failed", "motor not running",
                              "motor seized", "motor noise"],
        "system_keywords":  ["pump", "fan", "slide", "awning", "door",
                              "washer", "blower"],
    },
    {
        "component_name": "Starter Motor",
        "component_type": "mechanical",
        "role": "Cranks the engine to initiate combustion",
        "trigger_keywords": ["starter", "won't crank", "clicking when starting",
                              "starter motor", "starter solenoid",
                              "won't turn over"],
        "system_keywords":  ["car", "truck", "engine", "generator",
                              "vehicle"],
    },
    {
        "component_name": "Carburetor",
        "component_type": "mechanical",
        "role": "Mixes fuel and air for the engine",
        "trigger_keywords": ["carburetor", "carb", "carb clogged",
                              "starts then dies", "surging", "hard to start",
                              "carb dirty"],
        "system_keywords":  ["generator", "small engine", "lawn mower",
                              "outboard"],
    },
    {
        "component_name": "Spark Plug",
        "component_type": "electrical",
        "role": "Ignites the air-fuel mixture inside the engine cylinder",
        "trigger_keywords": ["spark plug", "misfiring", "rough idle",
                              "won't start", "fouled plug"],
        "system_keywords":  ["engine", "generator", "car", "truck",
                              "small engine"],
    },
    {
        "component_name": "Drive Belt / Chain",
        "component_type": "mechanical",
        "role": "Transfers power between rotating components",
        "trigger_keywords": ["belt", "chain", "squealing belt", "broken belt",
                              "belt slipping", "timing belt", "drive belt",
                              "chain loose"],
        "system_keywords":  ["engine", "alternator", "ac", "washer",
                              "generator", "motorcycle"],
    },
    {
        "component_name": "Bearing",
        "component_type": "mechanical",
        "role": "Reduces friction in rotating components",
        "trigger_keywords": ["bearing", "grinding noise", "wheel bearing",
                              "bearing noise", "worn bearing"],
        "system_keywords":  ["motor", "pump", "fan", "wheel", "axle"],
    },
    {
        "component_name": "Radiator",
        "component_type": "fluid",
        "role": "Dissipates engine heat through coolant circulation",
        "trigger_keywords": ["radiator", "overheating", "coolant leak",
                              "radiator leak", "temp gauge high",
                              "coolant low"],
        "system_keywords":  ["engine", "car", "truck", "vehicle", "coolant"],
    },

    # ── Structural / Body ───────────────────────────────────────────────────
    {
        "component_name": "Slide-Out Mechanism",
        "component_type": "mechanical",
        "role": "Extends and retracts the slide-out room",
        "trigger_keywords": ["slide", "slide-out", "won't retract", "won't extend",
                              "slide stuck", "slide won't move"],
        "system_keywords":  ["rv", "motorhome", "camper", "travel trailer"],
    },
    {
        "component_name": "Roof Shingles / Membrane",
        "component_type": "structural",
        "role": "Weatherproofing layer on the roof",
        "trigger_keywords": ["shingles", "roof leak", "missing shingles",
                              "roof membrane", "leaking roof"],
        "system_keywords":  ["roof", "home", "building", "house"],
    },
    {
        "component_name": "Door / Hinge / Lock",
        "component_type": "structural",
        "role": "Provides access and security for an enclosure",
        "trigger_keywords": ["door won't open", "door stuck", "hinge broken",
                              "lock jammed", "garage door won't close"],
        "system_keywords":  ["door", "garage", "entry"],
    },
    {
        "component_name": "Hydraulic Cylinder / Hose",
        "component_type": "fluid",
        "role": "Actuates movement using pressurised hydraulic fluid",
        "trigger_keywords": ["hydraulic leak", "cylinder", "hydraulic hose",
                              "slow hydraulic", "hydraulic not working"],
        "system_keywords":  ["excavator", "tractor", "leveling jacks",
                              "slide", "heavy equipment"],
    },
]

# ---------------------------------------------------------------------------
# Normalisation: strip noise so keywords match more naturally
# ---------------------------------------------------------------------------

_NOISE_WORDS = frozenset(
    "my the a an is it in on at to of for and or but not so very just i "
    "we you he she they my our your his her its this that these those "
    "will won't wont can can't cant does doesn't dont do did didn't didn't "
    "has have had was were are been being get got make made say says let "
    "good well right now then also both each few more most some such no "
    "nor up out about after before over under again further once only own "
    "same so than too very just how all while".split()
)


def _clean(text: str) -> str:
    return text.lower().strip()


# ===========================================================================
# ComponentIdentifier
# ===========================================================================

class ComponentIdentifier:
    """
    Component Identification Engine.

    Identifies every component involved in a repair query and annotates
    each with type, role, and whether it is the suspected failing part.
    """

    def identify(self, raw_query: str) -> dict[str, Any]:
        """
        Identify all components involved in the query.

        Parameters
        ----------
        raw_query : str   The user's raw repair query.

        Returns
        -------
        dict:
        {
          "query":        "My RV fridge won't light on propane",
          "total":        3,
          "components": [
            {
              "component_name": "Burner Orifice",
              "component_type": "gas",
              "role":           "Meters propane/gas flow to the burner",
              "suspect":        true,
              "match_reason":   "keyword: won't light"
            },
            ...
          ]
        }
        """
        text = _clean(raw_query)
        seen: set[str] = set()
        results: list[dict[str, Any]] = []

        for entry in _CATALOGUE:
            name   = entry["component_name"]
            if name in seen:
                continue

            trigger_match = self._first_match(text, entry["trigger_keywords"])
            system_match  = self._first_match(text, entry["system_keywords"])

            if trigger_match:
                seen.add(name)
                results.append({
                    "component_name": name,
                    "component_type": entry["component_type"],
                    "role":           entry["role"],
                    "suspect":        True,
                    "match_reason":   f"keyword: {trigger_match}",
                })
            elif system_match:
                seen.add(name)
                results.append({
                    "component_name": name,
                    "component_type": entry["component_type"],
                    "role":           entry["role"],
                    "suspect":        False,
                    "match_reason":   f"related system: {system_match}",
                })

        # Sort: suspects first, then alphabetically by name
        results.sort(key=lambda c: (not c["suspect"], c["component_name"]))

        return {
            "query":      raw_query,
            "total":      len(results),
            "suspects":   sum(1 for c in results if c["suspect"]),
            "components": results,
        }

    @staticmethod
    def _first_match(text: str, keywords: list[str]) -> str | None:
        """Return the first keyword that appears in text, or None."""
        for kw in sorted(keywords, key=len, reverse=True):
            if kw.lower() in text:
                return kw
        return None

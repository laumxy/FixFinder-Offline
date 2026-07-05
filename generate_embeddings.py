"""
generate_embeddings.py
Generates deterministic 768-dim synthetic embeddings for all 3 FixFinder versions.
Uses SHA-256 hashing to produce stable, reproducible float vectors.

Output:
  Version_1/06_Embeddings/embeddings.json
  Version_2/06_Embeddings/embeddings.json
  Version_3/06_Embeddings/embeddings.json
"""

import hashlib
import json
import os
import numpy as np


# ===========================================================================
# EmbeddingGenerator class
# ===========================================================================

class EmbeddingGenerator:
    """Generates deterministic synthetic embeddings via SHA-256 hashing."""

    def __init__(self, dimension: int = 768):
        self.dimension = dimension

    def generate_synthetic_embedding(self, text: str) -> list[float]:
        """
        Produce a deterministic, normalized 768-dim float vector from text.

        Strategy:
          1. Hash the text with SHA-256 to get a 32-byte seed.
          2. Use the seed to initialize a NumPy RandomState for reproducibility.
          3. Draw `dimension` samples from a standard normal distribution.
          4. L2-normalize the vector so it lives on the unit hypersphere
             (consistent with real sentence-embedding conventions).
        """
        seed_bytes = hashlib.sha256(text.encode("utf-8")).digest()
        # Convert 32 bytes to a 32-bit integer seed numpy can consume
        seed_int = int.from_bytes(seed_bytes[:4], "big")
        rng = np.random.RandomState(seed=seed_int)
        vec = rng.randn(self.dimension).astype(np.float32)
        # L2 normalise
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return [round(float(v), 6) for v in vec]

    def _make_entry(
        self,
        entity_type: str,
        entity_id: str,
        text: str,
    ) -> dict:
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "text": text,
            "embedding": self.generate_synthetic_embedding(text),
        }

    def generate_embeddings_for_version(
        self,
        version: str,
        systems: list[dict],
        symptoms: list[dict],
        repairs: list[dict],
    ) -> dict:
        """
        Build the full embeddings payload for one version.

        Each item list is a dict with at minimum:
          systems  -> id, system_name, brand, subcategory, specifications (optional)
          symptoms -> id, symptom_name, severity, causes
          repairs  -> id, name, difficulty, estimated_time, steps (list of dicts)
        """
        embeddings = []

        for sys in systems:
            specs = sys.get("specifications", "")
            text = (
                f"{sys['system_name']} {sys['brand']} {sys['subcategory']} {specs}"
            ).strip()
            embeddings.append(self._make_entry("system", sys["id"], text))

        for sym in symptoms:
            text = (
                f"{sym['symptom_name']} severity:{sym['severity']} causes:{sym['causes']}"
            )
            embeddings.append(self._make_entry("symptom", sym["id"], text))

        for rep in repairs:
            step_text = " ".join(
                s.get("title", "") for s in rep.get("steps", [])
            )
            text = (
                f"{rep['name']} difficulty:{rep['difficulty']} "
                f"time:{rep['estimated_time']} steps:{step_text}"
            )
            embeddings.append(self._make_entry("repair", rep["id"], text))

        return {
            "version": version,
            "dimension": self.dimension,
            "total_embeddings": len(embeddings),
            "embeddings": embeddings,
        }


# ===========================================================================
# VERSION DATA
# ===========================================================================

# ---------------------------------------------------------------------------
# Version 1 – Home Maintenance
# ---------------------------------------------------------------------------

V1_SYSTEMS = [
    {"id": "ROF-001", "system_name": "Asphalt Shingle Roof",       "brand": "GAF",           "subcategory": "Asphalt Shingles",   "specifications": "20-year lifespan 3-tab architectural shingle"},
    {"id": "ROF-002", "system_name": "Metal Roof",                 "brand": "Englert",       "subcategory": "Metal Roofing",      "specifications": "50-year lifespan standing seam steel panel"},
    {"id": "ROF-003", "system_name": "Flat Roof EPDM",             "brand": "Firestone",     "subcategory": "Flat Roofing",       "specifications": "25-year rubber membrane 45-mil thickness"},
    {"id": "PLM-001", "system_name": "Copper Plumbing",            "brand": "Mueller",       "subcategory": "Supply Lines",       "specifications": "1/2 inch type L copper 50-year lifespan"},
    {"id": "PLM-003", "system_name": "Gas Water Heater",           "brand": "Rheem",         "subcategory": "Water Heaters",      "specifications": "40-gallon natural gas 12-year lifespan 40000 BTU"},
    {"id": "ELC-001", "system_name": "200A Electrical Panel",      "brand": "Square D",      "subcategory": "Electrical Panels",  "specifications": "200 amp main breaker 40-space load center"},
    {"id": "HVC-001", "system_name": "Central Air Conditioner",    "brand": "Carrier",       "subcategory": "Cooling Systems",    "specifications": "3-ton 16 SEER split system 15-year lifespan"},
    {"id": "HVC-002", "system_name": "Gas Furnace",                "brand": "Lennox",        "subcategory": "Heating Systems",    "specifications": "80000 BTU 96% AFUE 20-year lifespan"},
    {"id": "WIN-001", "system_name": "Double-Pane Windows",        "brand": "Andersen",      "subcategory": "Windows",            "specifications": "Low-E argon-filled insulated glass 20-year lifespan"},
    {"id": "SMP-001", "system_name": "Sump Pump",                  "brand": "Zoeller",       "subcategory": "Water Management",   "specifications": "1/2 HP cast iron submersible 10-year lifespan"},
]

V1_SYMPTOMS = [
    {"id": "PRB-ROF-001", "symptom_name": "Missing Shingles",           "severity": "High",     "causes": "Wind damage age weathering"},
    {"id": "PRB-ROF-002", "symptom_name": "Roof Leak",                  "severity": "High",     "causes": "Damaged flashing cracked shingles ice dam"},
    {"id": "PRB-ROF-003", "symptom_name": "Sagging Roof Deck",          "severity": "Critical", "causes": "Water damage structural failure rot"},
    {"id": "PRB-PLM-001", "symptom_name": "Dripping Faucet",            "severity": "Low",      "causes": "Worn washer O-ring cartridge failure"},
    {"id": "PRB-PLM-002", "symptom_name": "Low Water Pressure",         "severity": "Medium",   "causes": "Mineral buildup faulty pressure regulator partial shutoff"},
    {"id": "PRB-PLM-004", "symptom_name": "No Hot Water",               "severity": "High",     "causes": "Failed heating element pilot light out tripped reset"},
    {"id": "PRB-ELC-001", "symptom_name": "Tripping Breaker",           "severity": "High",     "causes": "Overloaded circuit short circuit faulty appliance"},
    {"id": "PRB-ELC-002", "symptom_name": "Dead Outlet",                "severity": "Medium",   "causes": "Tripped GFCI faulty wiring loose connection"},
    {"id": "PRB-HVC-001", "symptom_name": "AC Not Cooling",             "severity": "High",     "causes": "Low refrigerant dirty coils failed capacitor"},
    {"id": "PRB-HVC-002", "symptom_name": "Furnace Not Heating",        "severity": "High",     "causes": "Faulty ignitor dirty filter cracked heat exchanger"},
]

V1_REPAIRS = [
    {
        "id": "RP-ROF-001", "name": "Replacing Asphalt Shingles",
        "difficulty": "Moderate", "estimated_time": "2-3 hours",
        "steps": [
            {"title": "Secure the Work Area"},
            {"title": "Remove Damaged Shingles"},
            {"title": "Inspect and Repair Underlayment"},
            {"title": "Install New Shingle"},
            {"title": "Re-nail Overlying Shingles"},
        ],
    },
    {
        "id": "RP-PLB-001", "name": "Replacing Toilet Flapper",
        "difficulty": "Easy", "estimated_time": "15-30 minutes",
        "steps": [
            {"title": "Shut Off Water Supply"},
            {"title": "Remove Tank Lid"},
            {"title": "Remove Old Flapper"},
            {"title": "Install New Flapper"},
            {"title": "Test and Adjust"},
        ],
    },
    {
        "id": "RP-ELC-001", "name": "Circuit Breaker Replacement",
        "difficulty": "Moderate", "estimated_time": "30-60 minutes",
        "steps": [
            {"title": "Turn Off Main Breaker"},
            {"title": "Remove Panel Cover"},
            {"title": "Disconnect the Wire from Faulty Breaker"},
            {"title": "Remove the Faulty Breaker"},
            {"title": "Install the New Breaker"},
            {"title": "Connect Wire and Restore Power"},
        ],
    },
    {
        "id": "RP-APL-001", "name": "Refrigerator Start Relay Replacement",
        "difficulty": "Easy", "estimated_time": "30-45 minutes",
        "steps": [
            {"title": "Unplug and Access Compressor"},
            {"title": "Locate the Start Relay"},
            {"title": "Remove the Old Relay"},
            {"title": "Test with Multimeter"},
            {"title": "Install New Relay"},
        ],
    },
    {
        "id": "RP-HVC-001", "name": "AC Capacitor Replacement",
        "difficulty": "Moderate", "estimated_time": "30-45 minutes",
        "steps": [
            {"title": "Disconnect Power at Breaker"},
            {"title": "Open Condenser Unit Panel"},
            {"title": "Discharge Old Capacitor Safely"},
            {"title": "Note and Disconnect Wires"},
            {"title": "Install New Capacitor"},
            {"title": "Restore Power and Test"},
        ],
    },
    {
        "id": "RP-PLM-002", "name": "Water Heater Anode Rod Replacement",
        "difficulty": "Moderate", "estimated_time": "45-60 minutes",
        "steps": [
            {"title": "Shut Off Water and Gas"},
            {"title": "Relieve Tank Pressure"},
            {"title": "Locate Anode Rod Port"},
            {"title": "Remove Old Anode Rod"},
            {"title": "Install New Anode Rod"},
            {"title": "Restore Water and Check for Leaks"},
        ],
    },
    {
        "id": "RP-WIN-001", "name": "Window Weatherstrip Replacement",
        "difficulty": "Easy", "estimated_time": "20-40 minutes",
        "steps": [
            {"title": "Remove Old Weatherstrip"},
            {"title": "Clean the Frame Channel"},
            {"title": "Measure and Cut New Strip"},
            {"title": "Press New Strip Into Channel"},
            {"title": "Test Window Seal"},
        ],
    },
    {
        "id": "RP-FND-001", "name": "Foundation Crack Sealing",
        "difficulty": "Moderate", "estimated_time": "1-2 hours",
        "steps": [
            {"title": "Clean and Dry the Crack"},
            {"title": "Insert Injection Ports"},
            {"title": "Seal Crack Surface"},
            {"title": "Inject Epoxy or Polyurethane"},
            {"title": "Allow to Cure"},
            {"title": "Apply Waterproof Coating"},
        ],
    },
    {
        "id": "RP-ROF-002", "name": "Roof Flashing Re-Sealing",
        "difficulty": "Moderate", "estimated_time": "1-2 hours",
        "steps": [
            {"title": "Clean Around Flashing"},
            {"title": "Remove Old Caulk and Sealant"},
            {"title": "Inspect for Physical Damage"},
            {"title": "Apply Roof Cement Under Lifted Edges"},
            {"title": "Apply Lap Sealant Over Flashing Edges"},
        ],
    },
    {
        "id": "RP-ELC-002", "name": "GFCI Outlet Replacement",
        "difficulty": "Easy", "estimated_time": "20-30 minutes",
        "steps": [
            {"title": "Turn Off Circuit Breaker"},
            {"title": "Verify Power Is Off"},
            {"title": "Remove Old Outlet"},
            {"title": "Connect New GFCI Outlet"},
            {"title": "Install and Test GFCI"},
        ],
    },
]

# ---------------------------------------------------------------------------
# Version 2 – Electronics
# ---------------------------------------------------------------------------

V2_SYSTEMS = [
    {"id": "PHN-001", "system_name": "iPhone 15 Pro Max",        "brand": "Apple",      "subcategory": "Smartphones",     "specifications": "6-year lifespan A17 Pro chip 4422mAh USB-C"},
    {"id": "PHN-002", "system_name": "Samsung Galaxy S24 Ultra", "brand": "Samsung",    "subcategory": "Smartphones",     "specifications": "5-year lifespan Snapdragon 8 Gen 3 5000mAh"},
    {"id": "PHN-003", "system_name": "Google Pixel 8 Pro",       "brand": "Google",     "subcategory": "Smartphones",     "specifications": "5-year lifespan Tensor G3 5050mAh"},
    {"id": "LAP-001", "system_name": "MacBook Pro 16",           "brand": "Apple",      "subcategory": "Laptops",         "specifications": "7-year lifespan M3 Pro chip 100Wh battery MagSafe"},
    {"id": "LAP-002", "system_name": "Dell XPS 15",              "brand": "Dell",       "subcategory": "Laptops",         "specifications": "6-year lifespan Intel Core i7 86Wh battery"},
    {"id": "DKT-001", "system_name": "Custom Gaming PC",         "brand": "Custom",     "subcategory": "Desktops",        "specifications": "7-year lifespan DDR5 PCIe 5.0 ATX form factor"},
    {"id": "TV-001",  "system_name": "Samsung QLED 65",          "brand": "Samsung",    "subcategory": "Televisions",     "specifications": "7-year lifespan 4K 120Hz HDR10+ HDMI 2.1"},
    {"id": "TV-002",  "system_name": "LG OLED C3 55",            "brand": "LG",         "subcategory": "Televisions",     "specifications": "7-year lifespan WOLED 4K 120Hz HDMI 2.1 webOS"},
    {"id": "GAM-001", "system_name": "PlayStation 5",            "brand": "Sony",       "subcategory": "Game Consoles",   "specifications": "7-year lifespan AMD Zen 2 825GB NVMe HDMI 2.1"},
    {"id": "NET-001", "system_name": "Cisco RV340 Router",       "brand": "Cisco",      "subcategory": "Networking",      "specifications": "8-year lifespan dual WAN Gigabit VPN AC1900"},
]

V2_SYMPTOMS = [
    {"id": "PRB-PHN-001", "symptom_name": "Battery Not Charging",       "severity": "High",     "causes": "Port damage faulty cable battery failure"},
    {"id": "PRB-PHN-002", "symptom_name": "Cracked Screen",             "severity": "High",     "causes": "Physical impact drop damage"},
    {"id": "PRB-PHN-003", "symptom_name": "Rapid Battery Drain",        "severity": "Medium",   "causes": "Background apps degraded battery software bug"},
    {"id": "PRB-PHN-004", "symptom_name": "Phone Overheating",          "severity": "High",     "causes": "Overloaded CPU faulty battery blocked vents"},
    {"id": "PRB-LAP-001", "symptom_name": "Laptop Overheating",         "severity": "High",     "causes": "Clogged fan dried thermal paste dust buildup"},
    {"id": "PRB-LAP-002", "symptom_name": "Keyboard Keys Not Working",  "severity": "Medium",   "causes": "Spill damage mechanical failure driver issue"},
    {"id": "PRB-LAP-003", "symptom_name": "No Display Output",          "severity": "Critical", "causes": "GPU failure display cable backlight failure"},
    {"id": "PRB-DKT-001", "symptom_name": "Blue Screen of Death BSOD",  "severity": "Critical", "causes": "Driver conflict RAM failure storage failure"},
    {"id": "PRB-TV-001",  "symptom_name": "Dead Pixels Screen Lines",   "severity": "High",     "causes": "Panel damage T-Con board failure"},
    {"id": "PRB-GAM-001", "symptom_name": "Disc Drive Not Reading",     "severity": "Medium",   "causes": "Laser lens dirty motor failure worn drive"},
]

V2_REPAIRS = [
    {
        "id": "RP-PHN-001", "name": "iPhone Battery Replacement",
        "difficulty": "Moderate", "estimated_time": "45-60 minutes",
        "steps": [
            {"title": "Remove Bottom Screws"},
            {"title": "Apply Heat and Open Display"},
            {"title": "Disconnect Battery Connector"},
            {"title": "Remove Display Assembly"},
            {"title": "Remove Old Battery"},
            {"title": "Install New Battery"},
            {"title": "Reconnect Display and Close"},
            {"title": "Reinstall Pentalobe Screws and Test"},
        ],
    },
    {
        "id": "RP-PHN-002", "name": "Samsung Galaxy Screen Replacement",
        "difficulty": "Expert", "estimated_time": "60-90 minutes",
        "steps": [
            {"title": "Heat and Remove Back Glass"},
            {"title": "Disconnect Battery"},
            {"title": "Disconnect All Flex Cables"},
            {"title": "Heat and Remove Front Display"},
            {"title": "Clean Frame"},
            {"title": "Install New Screen Assembly"},
            {"title": "Reconnect Everything and Test"},
            {"title": "Apply Back Glass"},
        ],
    },
    {
        "id": "RP-LAP-001", "name": "MacBook Thermal Paste Replacement",
        "difficulty": "Moderate", "estimated_time": "30-45 minutes",
        "steps": [
            {"title": "Remove Bottom Case"},
            {"title": "Disconnect Battery"},
            {"title": "Remove Heat Sink"},
            {"title": "Clean Old Thermal Paste"},
            {"title": "Apply New Thermal Paste"},
            {"title": "Reinstall Heat Sink and Close"},
        ],
    },
    {
        "id": "RP-CON-001", "name": "PS5 Liquid Metal Application",
        "difficulty": "Expert", "estimated_time": "45-60 minutes",
        "steps": [
            {"title": "Remove PS5 Shell"},
            {"title": "Remove Fan and Heat Sink"},
            {"title": "Clean Old Liquid Metal"},
            {"title": "Mask Surrounding Area"},
            {"title": "Apply Liquid Metal"},
            {"title": "Reinstall Heat Sink"},
            {"title": "Reassemble and Test"},
        ],
    },
    {
        "id": "RP-LAP-002", "name": "Laptop RAM Upgrade",
        "difficulty": "Easy", "estimated_time": "15-30 minutes",
        "steps": [
            {"title": "Power Off and Unplug"},
            {"title": "Remove Bottom Panel"},
            {"title": "Disconnect Battery Connector"},
            {"title": "Remove Old RAM Sticks"},
            {"title": "Install New RAM Sticks"},
            {"title": "Reassemble and Test"},
        ],
    },
    {
        "id": "RP-DKT-001", "name": "Desktop GPU Replacement",
        "difficulty": "Easy", "estimated_time": "20-30 minutes",
        "steps": [
            {"title": "Power Down and Unplug PC"},
            {"title": "Open Case Side Panel"},
            {"title": "Uninstall Old GPU Drivers"},
            {"title": "Remove Old GPU"},
            {"title": "Seat New GPU in PCIe Slot"},
            {"title": "Connect Power Cables and Test"},
        ],
    },
    {
        "id": "RP-TV-001", "name": "TV Backlight Strip Replacement",
        "difficulty": "Moderate", "estimated_time": "1-2 hours",
        "steps": [
            {"title": "Unplug and Remove TV Stand"},
            {"title": "Remove Back Panel Screws"},
            {"title": "Separate Front Bezel"},
            {"title": "Remove Diffuser Layers"},
            {"title": "Replace Failed LED Strips"},
            {"title": "Reassemble and Test"},
        ],
    },
    {
        "id": "RP-PHN-003", "name": "Phone Charging Port Cleaning",
        "difficulty": "Easy", "estimated_time": "10-15 minutes",
        "steps": [
            {"title": "Power Off the Device"},
            {"title": "Inspect Port with Flashlight"},
            {"title": "Remove Lint with Wooden Toothpick"},
            {"title": "Use Compressed Air to Clear Debris"},
            {"title": "Test Charging"},
        ],
    },
    {
        "id": "RP-NET-001", "name": "Router Firmware Update",
        "difficulty": "Easy", "estimated_time": "15-20 minutes",
        "steps": [
            {"title": "Log into Router Admin Panel"},
            {"title": "Navigate to Firmware Section"},
            {"title": "Download Latest Firmware from Vendor"},
            {"title": "Upload and Apply Firmware"},
            {"title": "Verify Router Reboots and Reconnects"},
        ],
    },
    {
        "id": "RP-GAM-001", "name": "PS5 Disc Drive Laser Replacement",
        "difficulty": "Expert", "estimated_time": "45-60 minutes",
        "steps": [
            {"title": "Remove Shell and Disc Drive"},
            {"title": "Disassemble Drive Housing"},
            {"title": "Remove Old Laser Assembly"},
            {"title": "Install New Laser Unit"},
            {"title": "Reassemble Drive"},
            {"title": "Reinstall and Test Disc Reading"},
        ],
    },
]

# ---------------------------------------------------------------------------
# Version 3 – Industrial / Automotive
# ---------------------------------------------------------------------------

V3_SYSTEMS = [
    {"id": "CAR-001", "system_name": "Toyota Camry",               "brand": "Toyota",      "subcategory": "Sedans",            "specifications": "15-year lifespan 2.5L I4 DOHC 203HP FWD"},
    {"id": "CAR-002", "system_name": "Ford F-150",                 "brand": "Ford",        "subcategory": "Trucks",            "specifications": "15-year lifespan 3.5L EcoBoost 400HP 4WD tow 14000lb"},
    {"id": "CAR-003", "system_name": "Tesla Model 3",              "brand": "Tesla",       "subcategory": "Electric Vehicles", "specifications": "12-year lifespan 358mi range 82kWh battery dual motor"},
    {"id": "HVY-001", "system_name": "Caterpillar 320 Excavator",  "brand": "Caterpillar", "subcategory": "Heavy Equipment",   "specifications": "20-year lifespan 162HP Cat C7.1 engine 20-ton operating weight"},
    {"id": "HVY-002", "system_name": "John Deere 5075E Tractor",   "brand": "John Deere",  "subcategory": "Agricultural",      "specifications": "20-year lifespan 75HP PowerTech engine 4WD PTO"},
    {"id": "GEN-001", "system_name": "Diesel Generator 20kW",      "brand": "Cummins",     "subcategory": "Generators",        "specifications": "20-year lifespan 20kW 3-phase 1800RPM diesel"},
    {"id": "CMP-001", "system_name": "Air Compressor 60 Gallon",   "brand": "Ingersoll Rand","subcategory": "Compressors",     "specifications": "15-year lifespan 5HP 60gal 175PSI two-stage"},
    {"id": "MOT-001", "system_name": "AC Induction Motor 5HP",     "brand": "ABB",         "subcategory": "Electric Motors",   "specifications": "20-year lifespan 5HP 1750RPM TEFC 230V/460V"},
    {"id": "MCY-001", "system_name": "Harley-Davidson Sportster",  "brand": "Harley-Davidson","subcategory": "Motorcycles",   "specifications": "20-year lifespan 883cc V-Twin air-cooled chain drive"},
    {"id": "SUV-001", "system_name": "Toyota Land Cruiser",        "brand": "Toyota",      "subcategory": "SUVs",              "specifications": "20-year lifespan 4.0L V6 270HP 4WD locking differentials"},
]

V3_SYMPTOMS = [
    {"id": "PRB-CAR-001", "symptom_name": "Check Engine Light",          "severity": "Variable", "causes": "O2 sensor MAF sensor catalytic converter EVAP leak"},
    {"id": "PRB-CAR-002", "symptom_name": "Engine Overheating",          "severity": "Critical", "causes": "Low coolant failed thermostat blown head gasket blocked radiator"},
    {"id": "PRB-CAR-003", "symptom_name": "Hard to Start No Start",      "severity": "High",     "causes": "Dead battery faulty starter fuel pump failure bad ignition"},
    {"id": "PRB-CAR-004", "symptom_name": "Rough Idle Engine Misfires",  "severity": "High",     "causes": "Fouled spark plugs dirty injectors vacuum leak low compression"},
    {"id": "PRB-CAR-005", "symptom_name": "Brake Grinding Squealing",    "severity": "Critical", "causes": "Worn brake pads warped rotors seized caliper low brake fluid"},
    {"id": "PRB-HVY-001", "symptom_name": "Hydraulic System Leak",       "severity": "High",     "causes": "Seal failure cracked hose damaged cylinder fitting corrosion"},
    {"id": "PRB-HVY-002", "symptom_name": "Equipment Power Loss",        "severity": "High",     "causes": "Clogged air filter fuel restriction turbocharger failure EGR"},
    {"id": "PRB-GEN-001", "symptom_name": "Generator Won't Start",       "severity": "Critical", "causes": "Dead battery fuel starvation governor fault injector failure"},
    {"id": "PRB-MOT-001", "symptom_name": "Electric Motor Overheating",  "severity": "High",     "causes": "Overload condition blocked ventilation bearing failure voltage unbalance"},
    {"id": "PRB-MCY-001", "symptom_name": "Motorcycle Chain Slack Noise","severity": "High",     "causes": "Stretched chain worn sprocket improper tension adjustment"},
]

V3_REPAIRS = [
    {
        "id": "RP-CAR-001", "name": "O2 Sensor Replacement",
        "difficulty": "Easy", "estimated_time": "30-60 minutes",
        "steps": [
            {"title": "Locate the Faulty Sensor"},
            {"title": "Disconnect Electrical Connector"},
            {"title": "Remove Old Sensor"},
            {"title": "Clean Threads"},
            {"title": "Install New Sensor"},
            {"title": "Clear Codes and Test"},
        ],
    },
    {
        "id": "RP-HEQ-001", "name": "Excavator Track Replacement",
        "difficulty": "Expert", "estimated_time": "8-12 hours",
        "steps": [
            {"title": "Position and Secure Machine"},
            {"title": "Release Track Tension"},
            {"title": "Raise the Track Off the Ground"},
            {"title": "Remove the Master Pin"},
            {"title": "Remove Old Track"},
            {"title": "Inspect Undercarriage Components"},
            {"title": "Install New Track and Master Pin"},
        ],
    },
    {
        "id": "RP-GEN-001", "name": "Generator Control Panel Repair",
        "difficulty": "Expert", "estimated_time": "2-4 hours",
        "steps": [
            {"title": "Shut Down and Lock Out Generator"},
            {"title": "Access Control Panel"},
            {"title": "Test Individual Components"},
            {"title": "Replace Faulty Component"},
            {"title": "Clean Connections"},
            {"title": "Test and Validate"},
        ],
    },
    {
        "id": "RP-SOL-001", "name": "Solar Panel Cleaning",
        "difficulty": "Easy", "estimated_time": "1-3 hours",
        "steps": [
            {"title": "Shut Down the Solar System"},
            {"title": "Rinse Panels with Water"},
            {"title": "Scrub with Soft Brush"},
            {"title": "Rinse and Squeegee"},
            {"title": "Dry and Inspect"},
            {"title": "Restart System and Compare Output"},
        ],
    },
    {
        "id": "RP-CAR-002", "name": "Brake Pad and Rotor Replacement",
        "difficulty": "Moderate", "estimated_time": "1.5-2.5 hours",
        "steps": [
            {"title": "Loosen Lug Nuts and Lift Vehicle"},
            {"title": "Remove Wheel and Caliper"},
            {"title": "Remove Old Rotor"},
            {"title": "Install New Rotor"},
            {"title": "Install New Brake Pads"},
            {"title": "Reinstall Caliper and Wheel"},
            {"title": "Bed In New Brakes"},
        ],
    },
    {
        "id": "RP-CAR-003", "name": "Spark Plug Replacement",
        "difficulty": "Easy", "estimated_time": "30-60 minutes",
        "steps": [
            {"title": "Allow Engine to Cool"},
            {"title": "Remove Ignition Coils"},
            {"title": "Remove Old Spark Plugs"},
            {"title": "Gap New Spark Plugs"},
            {"title": "Install New Spark Plugs"},
            {"title": "Reinstall Coils and Test"},
        ],
    },
    {
        "id": "RP-HVY-002", "name": "Hydraulic Hose Replacement",
        "difficulty": "Moderate", "estimated_time": "1-2 hours",
        "steps": [
            {"title": "Relieve System Hydraulic Pressure"},
            {"title": "Identify and Tag Hose Ends"},
            {"title": "Remove Old Hose Assembly"},
            {"title": "Fabricate or Match Replacement Hose"},
            {"title": "Install New Hose and Fittings"},
            {"title": "Bleed System and Pressure Test"},
        ],
    },
    {
        "id": "RP-GEN-002", "name": "Generator Fuel Filter Replacement",
        "difficulty": "Easy", "estimated_time": "20-30 minutes",
        "steps": [
            {"title": "Shut Down Generator"},
            {"title": "Close Fuel Shutoff Valve"},
            {"title": "Remove Old Fuel Filter"},
            {"title": "Install New Filter with Correct Flow Direction"},
            {"title": "Open Valve and Bleed Air"},
            {"title": "Start Generator and Check for Leaks"},
        ],
    },
    {
        "id": "RP-MOT-001", "name": "Electric Motor Bearing Replacement",
        "difficulty": "Moderate", "estimated_time": "2-3 hours",
        "steps": [
            {"title": "Lock Out Tag Out Motor"},
            {"title": "Remove Motor from Machine"},
            {"title": "Disassemble End Bells"},
            {"title": "Press Out Old Bearings"},
            {"title": "Press In New Bearings"},
            {"title": "Reassemble Motor and Test"},
        ],
    },
    {
        "id": "RP-MCY-001", "name": "Motorcycle Chain and Sprocket Replacement",
        "difficulty": "Moderate", "estimated_time": "1.5-2 hours",
        "steps": [
            {"title": "Lift Rear Wheel"},
            {"title": "Remove Master Clip and Old Chain"},
            {"title": "Remove Front and Rear Sprockets"},
            {"title": "Install New Sprockets"},
            {"title": "Route and Join New Chain"},
            {"title": "Adjust Chain Tension and Alignment"},
            {"title": "Test Ride"},
        ],
    },
]


# ===========================================================================
# Main – generate all versions
# ===========================================================================

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_json(filepath: str, data: dict) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    count = data.get("total_embeddings", len(data.get("embeddings", [])))
    print(f"  [OK] {filepath}  ({count} embeddings)")


def main() -> None:
    gen = EmbeddingGenerator(dimension=768)

    versions = [
        {
            "label":    "Version 1 – Home Maintenance",
            "version":  "1.0",
            "out_dir":  "Version_1/06_Embeddings",
            "systems":  V1_SYSTEMS,
            "symptoms": V1_SYMPTOMS,
            "repairs":  V1_REPAIRS,
        },
        {
            "label":    "Version 2 – Electronics",
            "version":  "2.0",
            "out_dir":  "Version_2/06_Embeddings",
            "systems":  V2_SYSTEMS,
            "symptoms": V2_SYMPTOMS,
            "repairs":  V2_REPAIRS,
        },
        {
            "label":    "Version 3 – Industrial / Automotive",
            "version":  "3.0",
            "out_dir":  "Version_3/06_Embeddings",
            "systems":  V3_SYSTEMS,
            "symptoms": V3_SYMPTOMS,
            "repairs":  V3_REPAIRS,
        },
    ]

    for cfg in versions:
        print(f"\n=== {cfg['label']} ===")
        ensure_dir(cfg["out_dir"])

        payload = gen.generate_embeddings_for_version(
            version  = cfg["version"],
            systems  = cfg["systems"],
            symptoms = cfg["symptoms"],
            repairs  = cfg["repairs"],
        )

        out_path = os.path.join(cfg["out_dir"], "embeddings.json")
        write_json(out_path, payload)

        # Quick breakdown
        types = {}
        for e in payload["embeddings"]:
            types[e["entity_type"]] = types.get(e["entity_type"], 0) + 1
        for t, n in types.items():
            print(f"    {t:10s}: {n}")

    print("\nAll embeddings generated successfully.")


if __name__ == "__main__":
    main()

"""
generate_csvs.py
Generates all CSV files for Version 1 (Home Maintenance),
Version 2 (Electronics), and Version 3 (Industrial / Automotive).
Output directories: Version_X/04_CSV/
"""

import csv
import os

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_csv(filepath: str, fieldnames: list, rows: list) -> None:
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  [OK] {filepath}  ({len(rows)} rows)")


# ===========================================================================
# VERSION 1 – Home Maintenance
# ===========================================================================

V1_DIR = "Version_1/04_CSV"

V1_SYSTEMS = [
    # id, system, subcategory, brand, lifespan, maintenance
    {"id": "ROF-001", "system": "Asphalt Shingle Roof",         "subcategory": "Asphalt Shingles",       "brand": "GAF",          "lifespan": 20, "maintenance": 12},
    {"id": "ROF-002", "system": "Metal Roof",                   "subcategory": "Metal Roofing",          "brand": "Englert",      "lifespan": 50, "maintenance": 24},
    {"id": "ROF-003", "system": "Flat Roof (EPDM)",             "subcategory": "Flat Roofing",           "brand": "Firestone",    "lifespan": 25, "maintenance": 12},
    {"id": "FND-001", "system": "Poured Concrete Foundation",   "subcategory": "Foundations",            "brand": "Generic",      "lifespan": 80, "maintenance": 60},
    {"id": "FND-002", "system": "Crawl Space",                  "subcategory": "Foundations",            "brand": "Generic",      "lifespan": 50, "maintenance": 12},
    {"id": "PLM-001", "system": "Copper Plumbing",              "subcategory": "Supply Lines",           "brand": "Mueller",      "lifespan": 50, "maintenance": 12},
    {"id": "PLM-002", "system": "PVC Drain Lines",              "subcategory": "Drain Lines",            "brand": "Charlotte",    "lifespan": 40, "maintenance": 12},
    {"id": "PLM-003", "system": "Water Heater (Gas)",           "subcategory": "Water Heaters",          "brand": "Rheem",        "lifespan": 12, "maintenance": 12},
    {"id": "ELC-001", "system": "200A Electrical Panel",        "subcategory": "Electrical Panels",      "brand": "Square D",     "lifespan": 40, "maintenance": 24},
    {"id": "ELC-002", "system": "GFCI Outlets",                 "subcategory": "Outlets",                "brand": "Leviton",      "lifespan": 15, "maintenance": 12},
    {"id": "HVC-001", "system": "Central Air Conditioner",      "subcategory": "Cooling Systems",        "brand": "Carrier",      "lifespan": 15, "maintenance": 6},
    {"id": "HVC-002", "system": "Gas Furnace",                  "subcategory": "Heating Systems",        "brand": "Lennox",       "lifespan": 20, "maintenance": 12},
    {"id": "HVC-003", "system": "Heat Pump",                    "subcategory": "Heating/Cooling",        "brand": "Trane",        "lifespan": 15, "maintenance": 6},
    {"id": "EXT-001", "system": "Vinyl Siding",                 "subcategory": "Exterior Cladding",      "brand": "CertainTeed", "lifespan": 30, "maintenance": 12},
    {"id": "EXT-002", "system": "Fiber Cement Siding",          "subcategory": "Exterior Cladding",      "brand": "HardiePlank",  "lifespan": 50, "maintenance": 12},
    {"id": "WIN-001", "system": "Double-Pane Windows",          "subcategory": "Windows",                "brand": "Andersen",     "lifespan": 20, "maintenance": 12},
    {"id": "GRG-001", "system": "Garage Door Opener",           "subcategory": "Garage Systems",         "brand": "Chamberlain",  "lifespan": 15, "maintenance": 12},
    {"id": "SMP-001", "system": "Sump Pump",                    "subcategory": "Water Management",       "brand": "Zoeller",      "lifespan": 10, "maintenance": 6},
]

V1_SYMPTOMS = [
    # id, category, symptom, severity, causes
    {"id": "PRB-ROF-001", "category": "Roofing",      "symptom": "Missing Shingles",           "severity": "High",     "causes": "Wind damage/age"},
    {"id": "PRB-ROF-002", "category": "Roofing",      "symptom": "Roof Leak",                  "severity": "High",     "causes": "Damaged flashing/cracked shingles"},
    {"id": "PRB-ROF-003", "category": "Roofing",      "symptom": "Sagging Roof Deck",          "severity": "Critical", "causes": "Water damage/structural failure"},
    {"id": "PRB-ROF-004", "category": "Roofing",      "symptom": "Granule Loss on Shingles",   "severity": "Medium",   "causes": "Age/weathering"},
    {"id": "PRB-FND-001", "category": "Foundation",   "symptom": "Foundation Cracks",          "severity": "High",     "causes": "Settling/hydrostatic pressure"},
    {"id": "PRB-FND-002", "category": "Foundation",   "symptom": "Water Intrusion in Basement","severity": "High",     "causes": "Poor drainage/crack in foundation"},
    {"id": "PRB-PLM-001", "category": "Plumbing",     "symptom": "Dripping Faucet",            "severity": "Low",      "causes": "Worn washer/O-ring"},
    {"id": "PRB-PLM-002", "category": "Plumbing",     "symptom": "Low Water Pressure",         "severity": "Medium",   "causes": "Buildup/faulty pressure regulator"},
    {"id": "PRB-PLM-003", "category": "Plumbing",     "symptom": "Slow Drain",                 "severity": "Medium",   "causes": "Clog/grease buildup"},
    {"id": "PRB-PLM-004", "category": "Plumbing",     "symptom": "No Hot Water",               "severity": "High",     "causes": "Failed heating element/pilot light out"},
    {"id": "PRB-ELC-001", "category": "Electrical",   "symptom": "Tripping Breaker",           "severity": "High",     "causes": "Overloaded circuit/short circuit"},
    {"id": "PRB-ELC-002", "category": "Electrical",   "symptom": "Dead Outlet",                "severity": "Medium",   "causes": "Tripped GFCI/faulty wiring"},
    {"id": "PRB-HVC-001", "category": "HVAC",         "symptom": "AC Not Cooling",             "severity": "High",     "causes": "Low refrigerant/dirty coils"},
    {"id": "PRB-HVC-002", "category": "HVAC",         "symptom": "Furnace Not Heating",        "severity": "High",     "causes": "Faulty ignitor/dirty filter"},
    {"id": "PRB-HVC-003", "category": "HVAC",         "symptom": "Unusual HVAC Noise",         "severity": "Medium",   "causes": "Loose parts/failing motor"},
    {"id": "PRB-HVC-004", "category": "HVAC",         "symptom": "High Energy Bills",          "severity": "Medium",   "causes": "Dirty filter/duct leaks/aging unit"},
    {"id": "PRB-EXT-001", "category": "Exterior",     "symptom": "Peeling Paint/Siding",       "severity": "Medium",   "causes": "Moisture infiltration/UV damage"},
    {"id": "PRB-WIN-001", "category": "Windows",      "symptom": "Foggy Window Panes",         "severity": "Medium",   "causes": "Failed seal on double pane"},
    {"id": "PRB-WIN-002", "category": "Windows",      "symptom": "Drafty Windows",             "severity": "Medium",   "causes": "Worn weatherstripping/failed caulk"},
    {"id": "PRB-GRG-001", "category": "Garage",       "symptom": "Garage Door Won't Open",     "severity": "Medium",   "causes": "Dead battery/broken spring/misaligned sensor"},
    {"id": "PRB-SMP-001", "category": "Basement",     "symptom": "Sump Pump Failure",          "severity": "Critical", "causes": "Power failure/float stuck/burned motor"},
]

V1_PARTS = [
    # id, part_name, unit, cost, coverage
    {"id": "PT-ROF-001", "part_name": "Asphalt Shingles Bundle",        "unit": "Bundle",   "cost": 25.99,   "coverage": "33.3 sq ft"},
    {"id": "PT-ROF-002", "part_name": "Roofing Felt (15 lb)",           "unit": "Roll",     "cost": 18.49,   "coverage": "400 sq ft"},
    {"id": "PT-ROF-003", "part_name": "Step Flashing Kit",              "unit": "Kit",      "cost": 34.99,   "coverage": "1 roof section"},
    {"id": "PT-ROF-004", "part_name": "Ridge Cap Shingles",             "unit": "Bundle",   "cost": 38.00,   "coverage": "35 lin ft"},
    {"id": "PT-ROF-005", "part_name": "Roof Deck Nails (1 lb)",         "unit": "Box",      "cost": 7.49,    "coverage": "1 square"},
    {"id": "PT-FND-001", "part_name": "Hydraulic Cement (10 lb)",       "unit": "Bag",      "cost": 14.99,   "coverage": "3 lin ft crack"},
    {"id": "PT-FND-002", "part_name": "Waterproofing Membrane (5 gal)", "unit": "Pail",     "cost": 89.99,   "coverage": "100 sq ft"},
    {"id": "PT-PLM-001", "part_name": "1/2\" Copper Pipe (10 ft)",      "unit": "Length",   "cost": 12.50,   "coverage": "10 ft run"},
    {"id": "PT-PLM-002", "part_name": "Faucet Repair Kit",              "unit": "Kit",      "cost": 8.99,    "coverage": "1 faucet"},
    {"id": "PT-PLM-003", "part_name": "PVC P-Trap",                     "unit": "Unit",     "cost": 6.49,    "coverage": "1 drain"},
    {"id": "PT-PLM-004", "part_name": "Water Heater Anode Rod",         "unit": "Unit",     "cost": 19.99,   "coverage": "1 water heater"},
    {"id": "PT-PLM-005", "part_name": "Heating Element (4500W)",        "unit": "Unit",     "cost": 15.99,   "coverage": "1 water heater"},
    {"id": "PT-ELC-001", "part_name": "20A Breaker (Single Pole)",      "unit": "Unit",     "cost": 11.99,   "coverage": "1 circuit"},
    {"id": "PT-ELC-002", "part_name": "GFCI Outlet 15A",                "unit": "Unit",     "cost": 16.49,   "coverage": "1 outlet"},
    {"id": "PT-ELC-003", "part_name": "14/2 Romex Wire (50 ft)",        "unit": "Roll",     "cost": 34.99,   "coverage": "50 ft circuit"},
    {"id": "PT-HVC-001", "part_name": "16x25x1 HVAC Filter",            "unit": "Unit",     "cost": 9.99,    "coverage": "1 HVAC system"},
    {"id": "PT-HVC-002", "part_name": "Furnace Ignitor",                "unit": "Unit",     "cost": 29.99,   "coverage": "1 furnace"},
    {"id": "PT-HVC-003", "part_name": "Capacitor (45+5 MFD)",           "unit": "Unit",     "cost": 18.99,   "coverage": "1 AC unit"},
    {"id": "PT-HVC-004", "part_name": "Thermostat (Programmable)",      "unit": "Unit",     "cost": 49.99,   "coverage": "1 HVAC system"},
    {"id": "PT-EXT-001", "part_name": "Vinyl Siding Panel (12 ft)",     "unit": "Panel",    "cost": 5.99,    "coverage": "12 sq ft"},
    {"id": "PT-WIN-001", "part_name": "Window Weatherstrip (10 ft)",    "unit": "Roll",     "cost": 7.99,    "coverage": "1 window"},
    {"id": "PT-GRG-001", "part_name": "Torsion Spring (Garage Door)",   "unit": "Pair",     "cost": 54.99,   "coverage": "1 garage door"},
    {"id": "PT-SMP-001", "part_name": "Sump Pump 1/2 HP",               "unit": "Unit",     "cost": 149.99,  "coverage": "1 sump pit"},
]

# ===========================================================================
# VERSION 2 – Electronics
# ===========================================================================

V2_DIR = "Version_2/04_CSV"

V2_SYSTEMS = [
    {"id": "PHN-001", "system": "iPhone 15 Pro Max",        "subcategory": "Smartphones",    "brand": "Apple",      "lifespan": 6,  "maintenance": 0},
    {"id": "PHN-002", "system": "Samsung Galaxy S24 Ultra", "subcategory": "Smartphones",    "brand": "Samsung",    "lifespan": 5,  "maintenance": 0},
    {"id": "PHN-003", "system": "Google Pixel 8 Pro",       "subcategory": "Smartphones",    "brand": "Google",     "lifespan": 5,  "maintenance": 0},
    {"id": "TAB-001", "system": "iPad Pro 12.9\"",          "subcategory": "Tablets",        "brand": "Apple",      "lifespan": 6,  "maintenance": 0},
    {"id": "TAB-002", "system": "Samsung Galaxy Tab S9",    "subcategory": "Tablets",        "brand": "Samsung",    "lifespan": 5,  "maintenance": 0},
    {"id": "LAP-001", "system": "MacBook Pro 16\"",         "subcategory": "Laptops",        "brand": "Apple",      "lifespan": 7,  "maintenance": 0},
    {"id": "LAP-002", "system": "Dell XPS 15",              "subcategory": "Laptops",        "brand": "Dell",       "lifespan": 6,  "maintenance": 0},
    {"id": "LAP-003", "system": "HP Spectre x360",          "subcategory": "Laptops",        "brand": "HP",         "lifespan": 5,  "maintenance": 0},
    {"id": "DKT-001", "system": "iMac 27\"",                "subcategory": "Desktops",       "brand": "Apple",      "lifespan": 8,  "maintenance": 0},
    {"id": "DKT-002", "system": "Custom Gaming PC",         "subcategory": "Desktops",       "brand": "Custom",     "lifespan": 7,  "maintenance": 6},
    {"id": "TV-001",  "system": "Samsung QLED 65\"",        "subcategory": "Televisions",    "brand": "Samsung",    "lifespan": 7,  "maintenance": 0},
    {"id": "TV-002",  "system": "LG OLED C3 55\"",         "subcategory": "Televisions",    "brand": "LG",         "lifespan": 7,  "maintenance": 0},
    {"id": "AUD-001", "system": "Sony WH-1000XM5",          "subcategory": "Headphones",     "brand": "Sony",       "lifespan": 4,  "maintenance": 0},
    {"id": "CAM-001", "system": "Canon EOS R5",             "subcategory": "DSLR/Mirrorless","brand": "Canon",      "lifespan": 8,  "maintenance": 12},
    {"id": "NET-001", "system": "Cisco RV340 Router",       "subcategory": "Networking",     "brand": "Cisco",      "lifespan": 8,  "maintenance": 12},
    {"id": "GAM-001", "system": "PlayStation 5",            "subcategory": "Game Consoles",  "brand": "Sony",       "lifespan": 7,  "maintenance": 0},
    {"id": "WRB-001", "system": "Apple Watch Series 9",     "subcategory": "Wearables",      "brand": "Apple",      "lifespan": 4,  "maintenance": 0},
]

V2_SYMPTOMS = [
    {"id": "PRB-PHN-001", "category": "Phones",     "symptom": "Battery Not Charging",         "severity": "High",     "causes": "Port damage/faulty cable/battery failure"},
    {"id": "PRB-PHN-002", "category": "Phones",     "symptom": "Cracked Screen",               "severity": "High",     "causes": "Physical impact/drop damage"},
    {"id": "PRB-PHN-003", "category": "Phones",     "symptom": "Rapid Battery Drain",          "severity": "Medium",   "causes": "Background apps/degraded battery/software bug"},
    {"id": "PRB-PHN-004", "category": "Phones",     "symptom": "Phone Overheating",            "severity": "High",     "causes": "Overloaded CPU/faulty battery/blocked vents"},
    {"id": "PRB-PHN-005", "category": "Phones",     "symptom": "No Cellular Signal",           "severity": "High",     "causes": "SIM failure/antenna damage/carrier issue"},
    {"id": "PRB-TAB-001", "category": "Tablets",    "symptom": "Touch Screen Unresponsive",    "severity": "High",     "causes": "Digitizer failure/software crash/moisture"},
    {"id": "PRB-TAB-002", "category": "Tablets",    "symptom": "Won't Turn On",                "severity": "Critical", "causes": "Dead battery/logic board failure"},
    {"id": "PRB-LAP-001", "category": "Laptops",    "symptom": "Laptop Overheating",           "severity": "High",     "causes": "Clogged fan/dried thermal paste"},
    {"id": "PRB-LAP-002", "category": "Laptops",    "symptom": "Keyboard Keys Not Working",    "severity": "Medium",   "causes": "Spill damage/mechanical failure/driver issue"},
    {"id": "PRB-LAP-003", "category": "Laptops",    "symptom": "No Display Output",            "severity": "Critical", "causes": "GPU failure/display cable/backlight failure"},
    {"id": "PRB-LAP-004", "category": "Laptops",    "symptom": "Battery Not Holding Charge",   "severity": "Medium",   "causes": "Battery cell degradation/charge cycles exhausted"},
    {"id": "PRB-DKT-001", "category": "Desktops",   "symptom": "Blue Screen of Death (BSOD)",  "severity": "Critical", "causes": "Driver conflict/RAM failure/storage failure"},
    {"id": "PRB-DKT-002", "category": "Desktops",   "symptom": "PC Won't POST",                "severity": "Critical", "causes": "Faulty RAM/CPU/dead PSU/BIOS issue"},
    {"id": "PRB-TV-001",  "category": "TVs",        "symptom": "Dead Pixels / Screen Lines",   "severity": "High",     "causes": "Panel damage/T-Con board failure"},
    {"id": "PRB-TV-002",  "category": "TVs",        "symptom": "No Picture but Has Sound",     "severity": "High",     "causes": "Backlight failure/mainboard issue"},
    {"id": "PRB-NET-001", "category": "Networking", "symptom": "Slow Wi-Fi / Drops",           "severity": "Medium",   "causes": "Interference/firmware issue/antenna failure"},
    {"id": "PRB-GAM-001", "category": "Gaming",     "symptom": "Disc Drive Not Reading",       "severity": "Medium",   "causes": "Laser lens dirty/motor failure"},
    {"id": "PRB-CAM-001", "category": "Cameras",    "symptom": "Autofocus Not Working",        "severity": "Medium",   "causes": "Dirty lens contacts/AF motor failure"},
]

V2_PARTS = [
    # id, part_name, unit, cost, coverage
    {"id": "PT-PHN-001", "part_name": "Screen Assembly (iPhone 15 Pro Max)", "unit": "Unit",  "cost": 279.99, "coverage": "1 device"},
    {"id": "PT-PHN-002", "part_name": "iPhone 15 Battery (3274 mAh)",        "unit": "Unit",  "cost": 69.99,  "coverage": "1 device"},
    {"id": "PT-PHN-003", "part_name": "Lightning/USB-C Charging Port Flex",  "unit": "Unit",  "cost": 29.99,  "coverage": "1 device"},
    {"id": "PT-PHN-004", "part_name": "Rear Camera Module (iPhone 15)",      "unit": "Unit",  "cost": 149.99, "coverage": "1 device"},
    {"id": "PT-PHN-005", "part_name": "Samsung Galaxy S24 AMOLED Screen",   "unit": "Unit",  "cost": 249.99, "coverage": "1 device"},
    {"id": "PT-TAB-001", "part_name": "iPad Pro 12.9 Display Assembly",      "unit": "Unit",  "cost": 349.99, "coverage": "1 device"},
    {"id": "PT-TAB-002", "part_name": "iPad Battery Replacement Kit",        "unit": "Kit",   "cost": 49.99,  "coverage": "1 device"},
    {"id": "PT-LAP-001", "part_name": "MacBook Pro 16 Battery",              "unit": "Unit",  "cost": 199.99, "coverage": "1 device"},
    {"id": "PT-LAP-002", "part_name": "Dell XPS 15 Keyboard Assembly",       "unit": "Unit",  "cost": 89.99,  "coverage": "1 device"},
    {"id": "PT-LAP-003", "part_name": "Laptop Thermal Paste (3g)",           "unit": "Tube",  "cost": 8.99,   "coverage": "1 device"},
    {"id": "PT-LAP-004", "part_name": "Laptop Cooling Fan (Generic 60mm)",   "unit": "Unit",  "cost": 24.99,  "coverage": "1 device"},
    {"id": "PT-DKT-001", "part_name": "DDR5 16GB RAM Stick",                 "unit": "Unit",  "cost": 59.99,  "coverage": "1 slot"},
    {"id": "PT-DKT-002", "part_name": "500W ATX Power Supply",               "unit": "Unit",  "cost": 79.99,  "coverage": "1 system"},
    {"id": "PT-DKT-003", "part_name": "1TB NVMe SSD (PCIe 4.0)",            "unit": "Unit",  "cost": 89.99,  "coverage": "1 device"},
    {"id": "PT-TV-001",  "part_name": "TV Backlight Strip (55\")",           "unit": "Set",   "cost": 34.99,  "coverage": "1 TV panel"},
    {"id": "PT-TV-002",  "part_name": "T-Con Board (Universal 4K)",          "unit": "Unit",  "cost": 44.99,  "coverage": "1 TV"},
    {"id": "PT-GAM-001", "part_name": "PS5 Disc Drive Laser Lens",           "unit": "Unit",  "cost": 39.99,  "coverage": "1 console"},
    {"id": "PT-CAM-001", "part_name": "Canon EOS R5 Shutter Assembly",       "unit": "Unit",  "cost": 299.99, "coverage": "1 camera"},
]

# ===========================================================================
# VERSION 3 – Industrial / Automotive
# ===========================================================================

V3_DIR = "Version_3/04_CSV"

V3_SYSTEMS = [
    # id, system, subcategory, brand, lifespan, maintenance
    {"id": "CAR-001", "system": "Toyota Camry",              "subcategory": "Sedans",           "brand": "Toyota",      "lifespan": 15, "maintenance": 6},
    {"id": "CAR-002", "system": "Honda Civic",               "subcategory": "Sedans",           "brand": "Honda",       "lifespan": 14, "maintenance": 6},
    {"id": "CAR-003", "system": "Ford F-150",                "subcategory": "Trucks",           "brand": "Ford",        "lifespan": 15, "maintenance": 6},
    {"id": "CAR-004", "system": "Chevrolet Silverado 1500",  "subcategory": "Trucks",           "brand": "Chevrolet",   "lifespan": 14, "maintenance": 6},
    {"id": "CAR-005", "system": "Tesla Model 3",             "subcategory": "Electric Vehicles", "brand": "Tesla",      "lifespan": 12, "maintenance": 12},
    {"id": "CAR-006", "system": "BMW 3 Series",              "subcategory": "Luxury Sedans",    "brand": "BMW",         "lifespan": 12, "maintenance": 6},
    {"id": "MCY-001", "system": "Harley-Davidson Sportster", "subcategory": "Motorcycles",      "brand": "Harley-Davidson", "lifespan": 20, "maintenance": 6},
    {"id": "MCY-002", "system": "Honda CBR600RR",            "subcategory": "Sport Bikes",      "brand": "Honda",       "lifespan": 15, "maintenance": 6},
    {"id": "HVY-001", "system": "Caterpillar 320 Excavator", "subcategory": "Heavy Equipment",  "brand": "Caterpillar", "lifespan": 20, "maintenance": 3},
    {"id": "HVY-002", "system": "John Deere 5075E Tractor",  "subcategory": "Agricultural",     "brand": "John Deere",  "lifespan": 20, "maintenance": 3},
    {"id": "HVY-003", "system": "Forklift (Toyota 8FGU25)",  "subcategory": "Material Handling", "brand": "Toyota",     "lifespan": 15, "maintenance": 3},
    {"id": "GEN-001", "system": "Diesel Generator (20kW)",   "subcategory": "Generators",       "brand": "Cummins",     "lifespan": 20, "maintenance": 6},
    {"id": "CMP-001", "system": "Air Compressor (60 gal)",   "subcategory": "Compressors",      "brand": "Ingersoll Rand", "lifespan": 15, "maintenance": 6},
    {"id": "PMP-001", "system": "Industrial Centrifugal Pump","subcategory": "Pumps",           "brand": "Grundfos",    "lifespan": 15, "maintenance": 6},
    {"id": "MOT-001", "system": "AC Induction Motor (5HP)",  "subcategory": "Electric Motors",  "brand": "ABB",         "lifespan": 20, "maintenance": 6},
    {"id": "VAN-001", "system": "Ford Transit Van",           "subcategory": "Commercial Vans",  "brand": "Ford",        "lifespan": 12, "maintenance": 6},
    {"id": "SUV-001", "system": "Toyota Land Cruiser",        "subcategory": "SUVs",             "brand": "Toyota",      "lifespan": 20, "maintenance": 6},
]

V3_SYMPTOMS = [
    # id, category, symptom, severity, causes
    {"id": "PRB-CAR-001", "category": "Cars",             "symptom": "Check Engine Light",          "severity": "Variable", "causes": "O2 sensor/MAF sensor/catalytic converter"},
    {"id": "PRB-CAR-002", "category": "Cars",             "symptom": "Engine Overheating",          "severity": "Critical", "causes": "Low coolant/failed thermostat/blown head gasket"},
    {"id": "PRB-CAR-003", "category": "Cars",             "symptom": "Hard to Start / No Start",    "severity": "High",     "causes": "Dead battery/faulty starter/fuel pump failure"},
    {"id": "PRB-CAR-004", "category": "Cars",             "symptom": "Rough Idle / Misfires",       "severity": "High",     "causes": "Fouled spark plugs/dirty injectors/vacuum leak"},
    {"id": "PRB-CAR-005", "category": "Cars",             "symptom": "Brake Grinding / Squealing",  "severity": "Critical", "causes": "Worn pads/warped rotors"},
    {"id": "PRB-CAR-006", "category": "Cars",             "symptom": "Transmission Slipping",       "severity": "High",     "causes": "Low fluid/worn clutch pack/solenoid failure"},
    {"id": "PRB-CAR-007", "category": "Cars",             "symptom": "Power Steering Loss",         "severity": "High",     "causes": "Low fluid/pump failure/broken belt"},
    {"id": "PRB-CAR-008", "category": "Cars",             "symptom": "AC Not Blowing Cold",         "severity": "Medium",   "causes": "Low refrigerant/compressor failure/condenser leak"},
    {"id": "PRB-TRK-001", "category": "Trucks",           "symptom": "Diesel Smoke (Black/White)",  "severity": "High",     "causes": "Injector issue/glow plug failure/EGR clog"},
    {"id": "PRB-EV-001",  "category": "Electric Vehicles","symptom": "Reduced Range",               "severity": "Medium",   "causes": "Battery degradation/cold weather/auxiliary load"},
    {"id": "PRB-EV-002",  "category": "Electric Vehicles","symptom": "Charging Failure",            "severity": "High",     "causes": "Charger fault/BMS error/charge port damage"},
    {"id": "PRB-MCY-001", "category": "Motorcycles",      "symptom": "Chain Slack / Noise",         "severity": "High",     "causes": "Stretched chain/worn sprocket"},
    {"id": "PRB-HVY-001", "category": "Heavy Equipment",  "symptom": "Hydraulic Leak",              "severity": "High",     "causes": "Seal failure/cracked hose/damaged cylinder"},
    {"id": "PRB-HVY-002", "category": "Heavy Equipment",  "symptom": "Engine Power Loss",           "severity": "High",     "causes": "Clogged air filter/fuel restriction/turbo failure"},
    {"id": "PRB-GEN-001", "category": "Generators",       "symptom": "Generator Won't Start",       "severity": "Critical", "causes": "Dead battery/fuel issue/governor fault"},
    {"id": "PRB-CMP-001", "category": "Compressors",      "symptom": "Compressor Won't Build Pressure","severity": "High", "causes": "Worn rings/valve failure/belt slip"},
    {"id": "PRB-MOT-001", "category": "Motors",           "symptom": "Motor Overheating",           "severity": "High",     "causes": "Overload/blocked ventilation/bearing failure"},
]

V3_PARTS = [
    # id, part_name, unit, cost, coverage
    {"id": "PT-CAR-001", "part_name": "Oil Filter",                        "unit": "Unit",  "cost": 9.99,    "coverage": "5,000 miles"},
    {"id": "PT-CAR-002", "part_name": "Engine Air Filter",                 "unit": "Unit",  "cost": 14.99,   "coverage": "15,000 miles"},
    {"id": "PT-CAR-003", "part_name": "Spark Plug Set (4-pack)",           "unit": "Set",   "cost": 24.99,   "coverage": "30,000 miles"},
    {"id": "PT-CAR-004", "part_name": "Front Brake Pads (Ceramic)",        "unit": "Set",   "cost": 39.99,   "coverage": "1 axle"},
    {"id": "PT-CAR-005", "part_name": "Front Brake Rotor",                 "unit": "Unit",  "cost": 49.99,   "coverage": "1 wheel"},
    {"id": "PT-CAR-006", "part_name": "Serpentine Belt",                   "unit": "Unit",  "cost": 29.99,   "coverage": "1 engine"},
    {"id": "PT-CAR-007", "part_name": "Car Battery (Group 24F)",           "unit": "Unit",  "cost": 129.99,  "coverage": "1 vehicle"},
    {"id": "PT-CAR-008", "part_name": "Oxygen Sensor (Upstream)",          "unit": "Unit",  "cost": 44.99,   "coverage": "1 sensor"},
    {"id": "PT-CAR-009", "part_name": "Cabin Air Filter",                  "unit": "Unit",  "cost": 12.99,   "coverage": "12,000 miles"},
    {"id": "PT-CAR-010", "part_name": "Fuel Filter",                       "unit": "Unit",  "cost": 19.99,   "coverage": "30,000 miles"},
    {"id": "PT-CAR-011", "part_name": "Thermostat + Gasket Kit",           "unit": "Kit",   "cost": 22.99,   "coverage": "1 engine"},
    {"id": "PT-CAR-012", "part_name": "Radiator Coolant (1 gal)",          "unit": "Jug",   "cost": 16.99,   "coverage": "1 flush"},
    {"id": "PT-CAR-013", "part_name": "Power Steering Fluid (32 oz)",      "unit": "Bottle","cost": 9.49,    "coverage": "1 top-up"},
    {"id": "PT-HVY-001", "part_name": "Hydraulic Hose Assembly (3/4\")",   "unit": "Unit",  "cost": 89.99,   "coverage": "1 circuit"},
    {"id": "PT-HVY-002", "part_name": "Hydraulic Cylinder Seal Kit",       "unit": "Kit",   "cost": 54.99,   "coverage": "1 cylinder"},
    {"id": "PT-HVY-003", "part_name": "Cat 320 Final Drive Filter",        "unit": "Unit",  "cost": 39.99,   "coverage": "1000 hours"},
    {"id": "PT-GEN-001", "part_name": "Generator Fuel Filter (Diesel)",    "unit": "Unit",  "cost": 14.99,   "coverage": "250 hours"},
    {"id": "PT-MOT-001", "part_name": "AC Motor Bearing Set (6205 2RS)",   "unit": "Set",   "cost": 18.99,   "coverage": "1 motor"},
    {"id": "PT-MCY-001", "part_name": "Motorcycle Drive Chain (530)",      "unit": "Unit",  "cost": 59.99,   "coverage": "1 motorcycle"},
    {"id": "PT-MCY-002", "part_name": "Motorcycle Brake Pads (Front)",     "unit": "Set",   "cost": 19.99,   "coverage": "1 caliper"},
]


# ===========================================================================
# MAIN – write all CSVs
# ===========================================================================

SYSTEMS_FIELDS  = ["id", "system", "subcategory", "brand", "lifespan", "maintenance"]
SYMPTOMS_FIELDS = ["id", "category", "symptom", "severity", "causes"]
PARTS_FIELDS    = ["id", "part_name", "unit", "cost", "coverage"]


def generate_version_1():
    print("\n=== VERSION 1 – Home Maintenance ===")
    ensure_dir(V1_DIR)
    write_csv(f"{V1_DIR}/systems.csv",  SYSTEMS_FIELDS,  V1_SYSTEMS)
    write_csv(f"{V1_DIR}/symptoms.csv", SYMPTOMS_FIELDS, V1_SYMPTOMS)
    write_csv(f"{V1_DIR}/parts.csv",    PARTS_FIELDS,    V1_PARTS)


def generate_version_2():
    print("\n=== VERSION 2 – Electronics ===")
    ensure_dir(V2_DIR)
    write_csv(f"{V2_DIR}/systems.csv",  SYSTEMS_FIELDS,  V2_SYSTEMS)
    write_csv(f"{V2_DIR}/symptoms.csv", SYMPTOMS_FIELDS, V2_SYMPTOMS)
    write_csv(f"{V2_DIR}/parts.csv",    PARTS_FIELDS,    V2_PARTS)


def generate_version_3():
    print("\n=== VERSION 3 – Industrial / Automotive ===")
    ensure_dir(V3_DIR)
    write_csv(f"{V3_DIR}/systems.csv",  SYSTEMS_FIELDS,  V3_SYSTEMS)
    write_csv(f"{V3_DIR}/symptoms.csv", SYMPTOMS_FIELDS, V3_SYMPTOMS)
    write_csv(f"{V3_DIR}/parts.csv",    PARTS_FIELDS,    V3_PARTS)


if __name__ == "__main__":
    generate_version_1()
    generate_version_2()
    generate_version_3()
    print("\nAll CSVs generated successfully.")

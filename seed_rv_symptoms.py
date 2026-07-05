"""
seed_rv_symptoms.py
Adds RV-specific and missing appliance symptoms to Version_1 database
so the knowledge base can answer real RV repair queries properly.

Run once:
    python seed_rv_symptoms.py
"""
import sqlite3, json, os

DB = "Version_1/03_SQLite_Database/fixfinder_v1.db"

# New symptoms to add — each maps to an existing system in the DB
NEW_SYMPTOMS = [
    # (symptom_code, symptom_name, category_name, system_code_match, severity,
    #  description, common_causes list, diagnostic_time, difficulty, parts, tools)
    (
        "sym_propane_nolite",
        "Propane appliance won't light",
        "Appliances",
        "sys_app_sam",   # fallback to appliances category
        "High",
        "Propane-powered appliance (stove, oven, furnace) fails to ignite",
        ["Pilot light out", "Clogged burner orifice", "Low propane tank", "Faulty igniter",
         "Tripped thermal cutoff", "Dirty thermocouple"],
        25, "Moderate",
        ["Thermocouple", "Igniter", "Burner orifice"],
        ["Lighter", "Screwdriver", "Soft brush"]
    ),
    (
        "sym_propane_smell",
        "Propane gas smell inside",
        "Appliances",
        "sys_app_sam",
        "Critical",
        "Smell of propane or gas inside the vehicle or building — potential leak",
        ["Loose fitting", "Cracked hose", "Faulty regulator", "Open burner valve",
         "Deteriorated O-ring"],
        10, "Expert",
        ["Gas hose", "Regulator", "Leak detector fluid", "O-rings"],
        ["Gas leak detector spray", "Adjustable wrench", "Pipe thread sealant"]
    ),
    (
        "sym_fridge_propane",
        "RV refrigerator not cooling on propane",
        "Appliances",
        "sys_app_sam",
        "High",
        "Absorption refrigerator runs but does not cool when on propane/gas mode",
        ["Clogged burner orifice", "Faulty thermocouple", "Low propane pressure",
         "Dirty or blocked flue", "Failed cooling unit", "Leveling issue"],
        45, "Moderate",
        ["Thermocouple", "Burner orifice", "Flue brush"],
        ["Multimeter", "Screwdriver set", "Soft brush", "Level"]
    ),
    (
        "sym_fridge_both",
        "RV refrigerator not cooling on electric or propane",
        "Appliances",
        "sys_app_sam",
        "High",
        "Absorption refrigerator fails to cool on both 120V and propane/gas modes",
        ["Failed cooling unit (ammonia leak)", "Blocked ammonia flow", "Control board failure",
         "Heating element burnt out"],
        60, "Hard",
        ["Heating element", "Control board", "Cooling unit"],
        ["Multimeter", "Wrench set", "Screwdriver set"]
    ),
    (
        "sym_water_pump_nowater",
        "Water pump runs but no water",
        "Plumbing",
        "sys_plumb_copper",
        "High",
        "12V water pump runs and hums but no water comes out of faucets",
        ["Empty fresh water tank", "Closed tank valve", "Blocked inlet strainer",
         "Air-locked pump", "Pump priming lost", "Cracked inlet fitting"],
        20, "Easy",
        ["Inlet strainer", "Pump inlet hose"],
        ["Screwdriver", "Pliers", "Water tank gauge"]
    ),
    (
        "sym_water_pump_nostart",
        "Water pump not turning on",
        "Plumbing",
        "sys_plumb_copper",
        "High",
        "Water pump does not run at all when faucet is opened",
        ["Blown 12V fuse", "Dead pump motor", "No 12V power at pump",
         "Faulty pressure switch", "Loose wire connection"],
        25, "Moderate",
        ["12V fuse", "Pump motor", "Pressure switch"],
        ["Multimeter", "Screwdriver", "Fuse puller"]
    ),
    (
        "sym_slide_stuck",
        "Slide-out stuck or not moving",
        "Garage",
        "sys_door_chamb",
        "High",
        "Slide-out room does not extend or retract fully or stops midway",
        ["Low battery voltage", "Motor failure", "Obstructed slide mechanism",
         "Stripped gear", "Faulty control switch", "Slide seal binding"],
        30, "Moderate",
        ["Slide motor", "Control switch", "Drive gear"],
        ["Multimeter", "12V power supply", "Slide lube", "Wrench set"]
    ),
    (
        "sym_generator_dies",
        "Generator starts then dies",
        "HVAC",
        "sys_hvac_carrier",
        "High",
        "Generator or engine starts but shuts off shortly after starting",
        ["Dirty carburetor", "Old or stale fuel", "Clogged fuel filter",
         "Low oil shutoff triggered", "Overload", "Choke stuck closed"],
        30, "Moderate",
        ["Carburetor kit", "Fuel filter", "Engine oil"],
        ["Screwdriver", "Carb cleaner", "Spark plug wrench"]
    ),
    (
        "sym_awning_stuck",
        "Awning won't retract or extend",
        "Exterior",
        "sys_door_chamb",
        "Medium",
        "Power awning motor runs but awning does not move, or won't respond",
        ["Dead motor", "Blown fuse", "Stripped gear", "Arm binding",
         "Low battery voltage", "Faulty remote/switch"],
        20, "Moderate",
        ["Awning motor", "Fuse"],
        ["Ladder", "Screwdriver", "Multimeter"]
    ),
    (
        "sym_leveling_fail",
        "Auto leveling system failure",
        "Foundation",
        "sys_plumb_copper",
        "Medium",
        "Automatic leveling jacks do not extend, retract, or system shows error",
        ["Low battery voltage", "Hydraulic fluid low", "Faulty level sensor",
         "Blown fuse", "Pump failure"],
        30, "Hard",
        ["Hydraulic fluid", "Level sensor", "Fuse"],
        ["Multimeter", "Hydraulic fluid wrench", "Jack wrench"]
    ),
]

def run():
    if not os.path.exists(DB):
        print(f"DB not found: {DB}")
        return

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    inserted = skipped = 0

    for (code, name, cat_name, system_code, severity,
         description, causes, diag_time, difficulty, parts, tools) in NEW_SYMPTOMS:

        # Skip if already exists
        exists = cur.execute(
            "SELECT 1 FROM symptoms WHERE symptom_code = ?", (code,)
        ).fetchone()
        if exists:
            print(f"  [SKIP] {code} already exists")
            skipped += 1
            continue

        # Get category_id
        cat = cur.execute(
            "SELECT category_id FROM categories WHERE category_name = ?",
            (cat_name,)
        ).fetchone()
        if not cat:
            # Try partial match
            cat = cur.execute(
                "SELECT category_id FROM categories WHERE category_name LIKE ?",
                (f"%{cat_name}%",)
            ).fetchone()
        category_id = cat["category_id"] if cat else 1

        # Get a system_id from that category
        system = cur.execute(
            "SELECT system_id FROM systems WHERE system_code = ?",
            (system_code,)
        ).fetchone()
        if not system:
            # fallback: first system in category
            system = cur.execute(
                "SELECT s.system_id FROM systems s "
                "JOIN subcategories sc ON s.subcategory_id = sc.subcategory_id "
                "JOIN categories c ON sc.category_id = c.category_id "
                "WHERE c.category_id = ? LIMIT 1",
                (category_id,)
            ).fetchone()
        system_id = system["system_id"] if system else 1

        cur.execute(
            """INSERT INTO symptoms
               (system_id, category_id, symptom_name, symptom_code,
                severity, description, common_causes,
                diagnostic_time_minutes, difficulty, parts_needed, tools_needed)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                system_id, category_id, name, code,
                severity, description,
                json.dumps(causes),
                diag_time, difficulty,
                json.dumps(parts),
                json.dumps(tools),
            )
        )
        print(f"  [ADD]  {code:<30s} {name}")
        inserted += 1

    conn.commit()
    conn.close()
    print(f"\nDone: {inserted} inserted, {skipped} skipped.")

if __name__ == "__main__":
    run()

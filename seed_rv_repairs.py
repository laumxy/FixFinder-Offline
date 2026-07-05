"""
seed_rv_repairs.py
Adds repair procedures for the RV-specific symptoms to Version_1 SQLite DB.
Also extends Version_1/05_JSON/repair_procedures.json with the new entries.

Run once (idempotent — skips existing codes):
    python seed_rv_repairs.py
"""
import sqlite3, json, os

DB       = "Version_1/03_SQLite_Database/fixfinder_v1.db"
JSON_DIR = "Version_1/05_JSON"

# ── New repair procedures ─────────────────────────────────────────────────────

NEW_REPAIRS = {
    "RP-PROPANE-001": {
        "id": "RP-PROPANE-001",
        "name": "Propane Appliance Igniter & Orifice Service",
        "category": "Appliances",
        "difficulty": "Easy",
        "estimated_time": "20-40 minutes",
        "estimated_time_minutes": 30,
        "tools_required": [
            "Soft wire brush", "Compressed air can", "Screwdriver",
            "Lighter or match (for pilot relight)", "Flashlight"
        ],
        "materials_required": [
            "Replacement thermocouple (if faulty)",
            "Orifice cleaner wire or needle",
            "Dish soap and water (leak check)"
        ],
        "safety_notes": "Always shut OFF propane at the tank valve before disassembling any burner assembly. Allow all parts to cool fully before touching.",
        "pre_repair_checks": [
            "Confirm propane tank is not empty — check gauge or weight",
            "Verify main propane shutoff valve is fully OPEN",
            "Look for bent or damaged gas lines before proceeding"
        ],
        "procedure_steps": [
            {"step": 1, "title": "Shut Off Propane at Tank", "detail": "Turn the propane tank valve clockwise until fully closed. If multiple appliances share the line, close the individual appliance shutoff valve."},
            {"step": 2, "title": "Remove Burner Cover / Access Panel", "detail": "Remove any top grates, burner caps, or access panels to expose the burner assembly and orifice."},
            {"step": 3, "title": "Inspect and Clean the Burner Orifice", "detail": "Locate the small brass orifice jet at the base of the burner. Use a thin needle or orifice cleaning wire to gently clear any blockage. Do NOT drill or ream the orifice — this changes the gas flow rate. Use compressed air to blow out debris."},
            {"step": 4, "title": "Check and Clean the Thermocouple", "detail": "The thermocouple is a small metal probe that sits in the pilot flame. Gently sand the tip with fine sandpaper to remove oxidation. If the tip is cracked or bent, replace it. Reconnect firmly at both the pilot assembly and the gas valve."},
            {"step": 5, "title": "Inspect the Igniter Electrode", "detail": "Check the spark igniter tip for carbon buildup or cracks. Clean with a dry cloth. The gap between the electrode and the burner should be 3–6mm. If the ceramic is cracked, replace the igniter."},
            {"step": 6, "title": "Reassemble and Test", "detail": "Reinstall all components. Open the propane valve slowly. Attempt ignition per the appliance procedure. Hold the control knob down for 30–60 seconds after ignition to allow the thermocouple to heat up fully before releasing."},
            {"step": 7, "title": "Leak Check", "detail": "Mix dish soap with water and apply to all fittings and connections. Open the propane valve. Bubbles indicate a leak — tighten fittings or replace O-rings if bubbles appear."}
        ],
        "post_repair_checks": [
            "Confirm pilot stays lit for at least 60 seconds when knob is released",
            "Verify all burners ignite normally within 4 seconds",
            "Perform soap-bubble leak check on all connections"
        ],
        "warnings": [
            "Never use an open flame to check for gas leaks — use soap solution only",
            "If propane smell persists after repair, ventilate immediately and contact a certified technician"
        ]
    },

    "RP-PROPANE-002": {
        "id": "RP-PROPANE-002",
        "name": "RV Refrigerator Propane Burner Cleaning",
        "category": "Appliances",
        "difficulty": "Moderate",
        "estimated_time": "45-90 minutes",
        "estimated_time_minutes": 67,
        "tools_required": [
            "Screwdriver set (Phillips and flathead)",
            "Needle-nose pliers",
            "Soft wire brush", "Compressed air",
            "Multimeter (for thermocouple test)",
            "Flashlight", "Level"
        ],
        "materials_required": [
            "Replacement thermocouple (if failed)",
            "Flue brush kit (12mm)",
            "Replacement burner orifice (if clogged beyond cleaning)"
        ],
        "safety_notes": "Absorption refrigerators contain ammonia solution. If you smell ammonia (sharp, pungent odor like cat urine), the cooling unit has leaked — do NOT attempt repair, ventilate immediately and replace the unit.",
        "pre_repair_checks": [
            "Check that the RV is level — absorption fridges require level operation within 3 degrees",
            "Verify propane tank level and main valve open",
            "Check that the exterior lower vent is not blocked by debris or a bird nest"
        ],
        "procedure_steps": [
            {"step": 1, "title": "Access the Burner Compartment", "detail": "Open the exterior lower access door at the back of the fridge (usually lower left of the RV exterior). Remove the burner cover or baffle plate."},
            {"step": 2, "title": "Inspect the Flue Tube", "detail": "Using a flashlight, look up the flue tube above the burner. Insects (especially wasps and spiders) build nests in the flue that block combustion gases. Use the flue brush to thoroughly sweep down the tube. Blow out with compressed air."},
            {"step": 3, "title": "Clean the Burner Assembly", "detail": "Remove the burner assembly by unscrewing the retaining screws. Use a soft wire brush to clean the burner head of carbon deposits. Clean the orifice jet with a thin needle — never enlarge the hole."},
            {"step": 4, "title": "Test and Replace Thermocouple", "detail": "Disconnect the thermocouple wire from the gas valve. Set multimeter to resistance (Ω). With thermocouple at room temperature, resistance should be 1–5 Ω. Heat the tip with a lighter for 30 seconds — voltage should be 15–35 mV. If out of spec, replace."},
            {"step": 5, "title": "Check Burner Flame", "detail": "Reassemble and light the burner. The flame should be steady blue with minimal yellow tips. A flickering or yellow flame indicates incomplete combustion — recheck orifice and air supply."},
            {"step": 6, "title": "Verify Cooling", "detail": "Set fridge to medium-high cooling. Allow 6–8 hours for an absorption fridge to reach temperature. Interior temp should drop below 40°F (4°C)."}
        ],
        "post_repair_checks": [
            "Confirm burner stays lit continuously in both auto and manual modes",
            "Check that the fridge reaches operating temperature within 8 hours",
            "Verify no ammonia odor from the rear of the fridge"
        ],
        "warnings": [
            "Ammonia odor means cooling unit failure — do not repair, replace the unit",
            "Never run the fridge on propane while driving — regulations and safety require electric or battery mode while in transit"
        ]
    },

    "RP-PUMP-001": {
        "id": "RP-PUMP-001",
        "name": "RV Water Pump Diagnosis and Repair",
        "category": "Plumbing",
        "difficulty": "Easy",
        "estimated_time": "20-45 minutes",
        "estimated_time_minutes": 32,
        "tools_required": [
            "Multimeter", "Screwdriver", "Flashlight",
            "Pliers", "Bucket"
        ],
        "materials_required": [
            "Water pump inlet strainer (if blocked)",
            "Teflon tape",
            "12V fuse for pump circuit (check rating on existing fuse)"
        ],
        "safety_notes": "Turn off the water pump switch before opening any connections. 12V DC systems are generally safe but can cause sparks — disconnect the battery negative if working on pump wiring.",
        "pre_repair_checks": [
            "Check fresh water tank level — pump cannot prime if tank is empty",
            "Verify the pump switch inside the RV is turned ON",
            "Check the pump fuse in the 12V fuse panel"
        ],
        "procedure_steps": [
            {"step": 1, "title": "Check Tank Level and Valve", "detail": "Confirm the fresh water tank has at least 1/4 tank of water. Locate the tank outlet valve (often under a dinette or in a storage bay) and verify it is fully open."},
            {"step": 2, "title": "Check the 12V Fuse", "detail": "Find the water pump fuse in the 12V fuse panel (usually 10–15A). Remove and inspect — replace if blown. If the new fuse blows immediately, there is a short in the pump wiring."},
            {"step": 3, "title": "Test Voltage at the Pump", "detail": "Set multimeter to DC voltage. With pump switch ON, probe the pump's power connector terminals. Should read 12–13.5V. If no voltage, trace the wiring from the fuse panel."},
            {"step": 4, "title": "Clean the Inlet Strainer", "detail": "The pump inlet has a small mesh strainer that catches debris. Disconnect the inlet hose, remove the strainer, and rinse under running water. Reinstall and reconnect."},
            {"step": 5, "title": "Prime the Pump", "detail": "If the pump has lost prime (runs but no water): disconnect the outlet hose, pour water directly into the outlet port to prime, reconnect. Some pumps have a priming port — use it if available."},
            {"step": 6, "title": "Test the Pressure Switch", "detail": "Turn on a faucet and listen — the pump should run. Close the faucet — the pump should stop within 3 seconds as pressure builds. If pump runs continuously with no faucet open, the pressure switch needs adjustment or replacement."}
        ],
        "post_repair_checks": [
            "Verify water flows from all faucets at normal pressure",
            "Confirm pump stops automatically when faucets are closed",
            "Check all hose connections for leaks after pressurization"
        ],
        "warnings": [
            "Never run the 12V water pump dry for more than 30 seconds — can burn out the motor",
            "Do not use the pump if the water lines are frozen — thaw first"
        ]
    },

    "RP-SLIDE-001": {
        "id": "RP-SLIDE-001",
        "name": "RV Slide-Out Troubleshooting and Manual Override",
        "category": "Garage",
        "difficulty": "Moderate",
        "estimated_time": "30-60 minutes",
        "estimated_time_minutes": 45,
        "tools_required": [
            "Multimeter", "Screwdriver set",
            "Manual override crank or hex key (check owner's manual for size)",
            "Slide-out lubricant (Protect-All or equivalent)"
        ],
        "materials_required": [
            "Slide-out gear lubricant",
            "Slide-out seal conditioner",
            "Replacement fuse (check rating)"
        ],
        "safety_notes": "Never stand in the path of an extending or retracting slide-out. Ensure no objects, wiring, or hoses are in the slide mechanism path before operating.",
        "pre_repair_checks": [
            "Check coach battery voltage — must be above 12.2V for slide motor operation",
            "Verify all items inside are cleared away from the slide walls",
            "Check for visible obstructions in the slide track or gear rack"
        ],
        "procedure_steps": [
            {"step": 1, "title": "Check Battery Voltage", "detail": "Low battery is the #1 cause of slide failure. Measure battery voltage at the terminals — must be above 12.2V at rest, 11.8V under load. Connect to shore power or run the generator to charge before attempting slide operation."},
            {"step": 2, "title": "Check Slide Fuse", "detail": "Find the slide-out fuse — usually a 30–50A fuse near the battery or in the main fuse panel. Inspect and replace if blown."},
            {"step": 3, "title": "Test the Slide Switch", "detail": "Measure voltage at the slide motor connector with the switch pressed. Should show 12V+. No voltage indicates a faulty switch, relay, or controller."},
            {"step": 4, "title": "Manual Override — Electric Slide", "detail": "Most electric slides have a manual override hex port on the motor or gearbox. Locate it (usually covered by a small rubber plug near the slide motor). Insert the correct hex key and turn slowly. Consult the owner's manual for override direction."},
            {"step": 5, "title": "Manual Override — Hydraulic Slide", "detail": "For hydraulic systems: locate the manual override valve on the hydraulic pump. Open it to release hydraulic lock, then push the slide manually. Close the valve before powering up the system."},
            {"step": 6, "title": "Lubricate and Inspect the Mechanism", "detail": "Once the slide is operable, inspect the gear rack, rollers, and slide rails. Clean and apply slide lubricant to all moving parts. Check the rubber seals for tears or hardening — apply seal conditioner."}
        ],
        "post_repair_checks": [
            "Test full extension and retraction 2–3 times",
            "Check slide-to-wall seals are seated fully all around",
            "Verify no water ingress at corners after a simulated rain test"
        ],
        "warnings": [
            "Never force a slide with the manual crank — if it won't move, stop and diagnose first",
            "Do not drive with the slide extended"
        ]
    },

    "RP-GEN-003": {
        "id": "RP-GEN-003",
        "name": "Generator Carburetor Cleaning (Runs Then Dies)",
        "category": "HVAC",
        "difficulty": "Moderate",
        "estimated_time": "30-60 minutes",
        "estimated_time_minutes": 45,
        "tools_required": [
            "Screwdriver set", "Pliers", "Small bowl",
            "Soft brush", "Compressed air can"
        ],
        "materials_required": [
            "Carburetor cleaner spray",
            "Fresh gasoline",
            "Carburetor rebuild kit (optional)",
            "Fuel stabilizer"
        ],
        "safety_notes": "Work in a well-ventilated area away from sparks or open flames. Gasoline is highly flammable. Disconnect the spark plug wire before disassembling the carburetor.",
        "pre_repair_checks": [
            "Check oil level — many generators have a low-oil shutdown sensor",
            "Check that the choke is not stuck in the closed position",
            "Drain and replace old fuel if it has been sitting more than 30 days"
        ],
        "procedure_steps": [
            {"step": 1, "title": "Check Oil Level and Low-Oil Sensor", "detail": "Check oil on the dipstick. Low oil triggers the automatic low-oil shutdown — the generator will start and immediately die. Top up to the full mark with the correct oil grade."},
            {"step": 2, "title": "Drain Old Fuel", "detail": "Turn the fuel petcock to OFF. Disconnect the fuel line from the carburetor and drain into a container. Old, stale fuel leaves a varnish residue that clogs the main jet."},
            {"step": 3, "title": "Remove Carburetor", "detail": "Disconnect the fuel line, throttle linkage, and choke cable. Remove the 2–4 mounting bolts holding the carburetor to the intake manifold. Remove the float bowl at the bottom of the carb."},
            {"step": 4, "title": "Clean the Float Bowl and Main Jet", "detail": "Spray carburetor cleaner into all passages and ports. The main jet is a small brass screw with a hole — remove it and confirm the hole is fully clear (light should pass through). Use a thin wire or compressed air — never drill."},
            {"step": 5, "title": "Reassemble and Install", "detail": "Reinstall the main jet, float bowl, and gasket. Reinstall the carburetor on the engine. Reconnect all linkages and fuel line."},
            {"step": 6, "title": "Add Fresh Fuel and Test", "detail": "Add fresh gasoline and add fuel stabilizer. Turn petcock to ON. Set choke to CLOSED for cold start. Pull or press start. Once running, gradually open choke. Generator should run smoothly at rated RPM."}
        ],
        "post_repair_checks": [
            "Generator should run continuously for 30 minutes under light load",
            "Check for fuel leaks at carburetor base and fuel line",
            "Measure output voltage — should be 120V ±5%"
        ],
        "warnings": [
            "Never run generator indoors or in enclosed spaces — carbon monoxide risk",
            "Allow generator to cool before refueling"
        ]
    }
}


def seed_db_repairs():
    """Add repair procedures to the SQLite database."""
    if not os.path.exists(DB):
        print(f"DB not found: {DB}")
        return

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    inserted = skipped = 0

    for repair_id, rep in NEW_REPAIRS.items():
        exists = cur.execute(
            "SELECT 1 FROM repair_procedures WHERE repair_code = ?", (repair_id,)
        ).fetchone()
        if exists:
            print(f"  [SKIP] {repair_id} already exists")
            skipped += 1
            continue

        # Get a tree_id and system_id — use first available as fallback
        tree_id = cur.execute(
            "SELECT tree_id FROM diagnostic_trees LIMIT 1"
        ).fetchone()
        tree_id = tree_id["tree_id"] if tree_id else 1

        system_id = cur.execute(
            "SELECT system_id FROM systems LIMIT 1"
        ).fetchone()
        system_id = system_id["system_id"] if system_id else 1

        steps = rep.get("procedure_steps", [])
        step_strings = [f'{s["title"]}: {s["detail"]}' for s in steps]

        cur.execute(
            """INSERT INTO repair_procedures
               (tree_id, system_id, repair_name, repair_code, overview,
                tools_required, materials_required, pre_repair_checks,
                procedure_steps, post_repair_checks,
                estimated_time_minutes, difficulty, warnings, safety_notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                tree_id,
                system_id,
                rep["name"],
                repair_id,
                rep.get("safety_notes", "")[:200],
                json.dumps(rep.get("tools_required", [])),
                json.dumps(rep.get("materials_required", [])),
                json.dumps(rep.get("pre_repair_checks", [])),
                json.dumps(step_strings),
                json.dumps(rep.get("post_repair_checks", [])),
                rep.get("estimated_time_minutes", 60),
                rep.get("difficulty", "Moderate"),
                json.dumps(rep.get("warnings", [])),
                rep.get("safety_notes", ""),
            )
        )
        print(f"  [ADD-DB] {repair_id:<20s} {rep['name']}")
        inserted += 1

    conn.commit()
    conn.close()
    print(f"\nDB: {inserted} inserted, {skipped} skipped.")


def seed_json_repairs():
    """Add repair procedures to the JSON file."""
    json_path = os.path.join(JSON_DIR, "repair_procedures.json")
    os.makedirs(JSON_DIR, exist_ok=True)

    # Load existing
    existing = {}
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            existing = json.load(f)

    added = skipped = 0
    for repair_id, rep in NEW_REPAIRS.items():
        if repair_id in existing:
            skipped += 1
            continue
        existing[repair_id] = rep
        print(f"  [ADD-JSON] {repair_id}")
        added += 1

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    print(f"JSON: {added} added, {skipped} skipped  → {json_path}")


if __name__ == "__main__":
    print("\n=== Seeding RV repair procedures ===\n")
    seed_db_repairs()
    print()
    seed_json_repairs()
    print("\nDone.")

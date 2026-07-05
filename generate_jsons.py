"""
generate_jsons.py
Generates all JSON files for Version 1 (Home Maintenance),
Version 2 (Electronics), and Version 3 (Industrial / Automotive).
Output directories: Version_X/05_JSON/
"""

import json
import os

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_json(filepath: str, data: dict) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  [OK] {filepath}  ({len(data)} entries)")


# ===========================================================================
# VERSION 1 – HOME MAINTENANCE
# ===========================================================================

V1_DIR = "Version_1/05_JSON"

# ---------------------------------------------------------------------------
# V1 – diagnostic_trees.json
# ---------------------------------------------------------------------------

V1_DIAGNOSTIC_TREES = {
    "DT-ROF-001": {
        "id": "DT-ROF-001",
        "name": "Roof Leak Diagnostic Tree",
        "symptom_code": "PRB-ROF-002",
        "category": "Roofing",
        "total_steps": 5,
        "avg_resolution_time_minutes": 45,
        "success_rate_percentage": 92.0,
        "steps": [
            {
                "step": 1,
                "title": "Locate the Entry Point",
                "instruction": "Inspect the attic with a flashlight during or just after rain. Look for water stains, mold, or wet insulation to trace the water trail back to its entry point.",
                "tools": ["Flashlight", "Moisture meter"],
                "decision": "Is the entry point visible in the attic?"
            },
            {
                "step": 2,
                "title": "Inspect Flashing",
                "instruction": "Check all metal flashing around chimneys, vents, skylights, and valleys. Look for lifted edges, cracks, or gaps in sealant.",
                "tools": ["Binoculars", "Pry bar", "Caulk gun"],
                "decision": "Is the flashing damaged or missing sealant?"
            },
            {
                "step": 3,
                "title": "Inspect Shingles",
                "instruction": "Walk the roof safely and check for missing, cracked, curled, or blistered shingles. Pay special attention to areas above the interior water stain.",
                "tools": ["Safety harness", "Roofing ladder"],
                "decision": "Are shingles missing or visibly damaged?"
            },
            {
                "step": 4,
                "title": "Check Roof Valleys and Gutters",
                "instruction": "Inspect the roof valleys for debris buildup and damaged valley flashing. Check gutters for blockages that could cause water to back up under shingles.",
                "tools": ["Gutter scoop", "Garden hose"],
                "decision": "Is there debris or damage in the valley/gutter area?"
            },
            {
                "step": 5,
                "title": "Water Test",
                "instruction": "With a helper inside the attic, slowly run a hose over different roof sections from bottom to top, starting at the suspected area. Wait several minutes per section.",
                "tools": ["Garden hose", "Two-way radio"],
                "decision": "Did the helper observe water entry during the hose test?"
            }
        ],
        "decision_points": [
            {"id": "DP-1", "question": "Is flashing the source?",    "yes": "RP-ROF-002", "no": "Check shingles"},
            {"id": "DP-2", "question": "Are shingles the source?",   "yes": "RP-ROF-001", "no": "Check valleys"},
            {"id": "DP-3", "question": "Is valley/gutter the cause?","yes": "RP-ROF-003", "no": "Consult professional roofer"}
        ],
        "resolution_paths": [
            {
                "path_id": "RES-1",
                "condition": "Damaged or missing shingles identified",
                "action": "Replace damaged shingles",
                "repair_code": "RP-ROF-001",
                "estimated_time_minutes": 120,
                "difficulty": "Moderate"
            },
            {
                "path_id": "RES-2",
                "condition": "Flashing cracked or poorly sealed",
                "action": "Re-seal or replace flashing",
                "repair_code": "RP-ROF-002",
                "estimated_time_minutes": 60,
                "difficulty": "Moderate"
            },
            {
                "path_id": "RES-3",
                "condition": "Valley debris or gutter backup",
                "action": "Clear gutters and repair valley flashing",
                "repair_code": "RP-ROF-003",
                "estimated_time_minutes": 90,
                "difficulty": "Easy"
            },
            {
                "path_id": "RES-4",
                "condition": "Source cannot be located",
                "action": "Engage licensed roofing contractor for full inspection",
                "repair_code": None,
                "estimated_time_minutes": None,
                "difficulty": "Expert"
            }
        ]
    },

    "DT-PLB-001": {
        "id": "DT-PLB-001",
        "name": "Low Water Pressure Diagnostic Tree",
        "symptom_code": "PRB-PLM-002",
        "category": "Plumbing",
        "total_steps": 4,
        "avg_resolution_time_minutes": 30,
        "success_rate_percentage": 88.0,
        "steps": [
            {
                "step": 1,
                "title": "Verify Scope",
                "instruction": "Turn on multiple faucets throughout the house. Determine if low pressure is isolated to one fixture, one area (hot or cold only), or house-wide.",
                "tools": ["Pressure gauge"],
                "decision": "Is the low pressure isolated to one fixture?"
            },
            {
                "step": 2,
                "title": "Check the Pressure Regulator",
                "instruction": "Locate the pressure reducing valve (PRV) near the main shutoff. Attach a pressure gauge to an outdoor hose bib. Normal is 40-80 psi. Below 40 psi indicates PRV or supply issue.",
                "tools": ["Water pressure gauge", "Adjustable wrench"],
                "decision": "Is pressure below 40 psi at the main?"
            },
            {
                "step": 3,
                "title": "Inspect Shutoff Valves",
                "instruction": "Confirm the main shutoff valve and any secondary shutoffs are fully open. A partially closed valve is a common cause of sudden pressure drops.",
                "tools": ["Flashlight"],
                "decision": "Are all shutoff valves fully open?"
            },
            {
                "step": 4,
                "title": "Check for Mineral Buildup",
                "instruction": "Remove aerators from affected faucets and clean them. Inspect showerheads for mineral deposits. For galvanized pipes, buildup may require pipe replacement.",
                "tools": ["Pliers", "Vinegar solution", "Brush"],
                "decision": "Did cleaning aerators/showerheads restore pressure?"
            }
        ],
        "decision_points": [
            {"id": "DP-1", "question": "Single fixture affected?",      "yes": "Clean aerator/showerhead", "no": "Check main pressure"},
            {"id": "DP-2", "question": "PRV pressure out of range?",    "yes": "RP-PLB-002",               "no": "Check shutoffs"},
            {"id": "DP-3", "question": "Shutoff partially closed?",     "yes": "Open valve fully",         "no": "Check for pipe buildup/leak"}
        ],
        "resolution_paths": [
            {
                "path_id": "RES-1",
                "condition": "Clogged aerator or showerhead",
                "action": "Clean or replace aerator/showerhead",
                "repair_code": "RP-PLB-003",
                "estimated_time_minutes": 15,
                "difficulty": "Easy"
            },
            {
                "path_id": "RES-2",
                "condition": "Faulty pressure reducing valve",
                "action": "Adjust or replace PRV",
                "repair_code": "RP-PLB-002",
                "estimated_time_minutes": 60,
                "difficulty": "Moderate"
            },
            {
                "path_id": "RES-3",
                "condition": "Partially closed shutoff valve",
                "action": "Fully open the shutoff valve",
                "repair_code": None,
                "estimated_time_minutes": 5,
                "difficulty": "Easy"
            }
        ]
    },

    "DT-ELC-001": {
        "id": "DT-ELC-001",
        "name": "Outlet Not Working Diagnostic Tree",
        "symptom_code": "PRB-ELC-002",
        "category": "Electrical",
        "total_steps": 3,
        "avg_resolution_time_minutes": 20,
        "success_rate_percentage": 95.0,
        "steps": [
            {
                "step": 1,
                "title": "Test the Outlet",
                "instruction": "Plug a known-working device into the dead outlet. Also test adjacent outlets. Use a non-contact voltage tester to confirm whether voltage is present at the outlet.",
                "tools": ["Non-contact voltage tester", "Outlet tester"],
                "decision": "Does the voltage tester detect power at the outlet?"
            },
            {
                "step": 2,
                "title": "Check GFCI Outlets and Breaker",
                "instruction": "Locate any GFCI outlets in the same bathroom, kitchen, garage, or exterior. Press the RESET button firmly on all GFCI outlets. Also check the main panel for a tripped breaker (switch in middle position).",
                "tools": ["Flashlight"],
                "decision": "Did resetting the GFCI or breaker restore power?"
            },
            {
                "step": 3,
                "title": "Inspect Wiring at Outlet",
                "instruction": "Turn off the breaker for that circuit. Remove the outlet cover and outlet from the box. Inspect wires for loose connections, burn marks, or broken wires.",
                "tools": ["Screwdrivers", "Needle-nose pliers", "Voltage tester"],
                "decision": "Are wires loose or is there visible burn damage?"
            }
        ],
        "decision_points": [
            {"id": "DP-1", "question": "No voltage at outlet?",         "yes": "Check GFCI/breaker", "no": "Faulty device, outlet OK"},
            {"id": "DP-2", "question": "GFCI or breaker reset fixed it?","yes": "Monitor for recurrence", "no": "Inspect outlet wiring"},
            {"id": "DP-3", "question": "Wiring loose or burnt?",        "yes": "RP-ELC-001",         "no": "Replace outlet receptacle"}
        ],
        "resolution_paths": [
            {
                "path_id": "RES-1",
                "condition": "Tripped GFCI or breaker",
                "action": "Reset GFCI or reset circuit breaker",
                "repair_code": None,
                "estimated_time_minutes": 5,
                "difficulty": "Easy"
            },
            {
                "path_id": "RES-2",
                "condition": "Loose wiring at outlet",
                "action": "Re-secure wire connections and replace outlet",
                "repair_code": "RP-ELC-002",
                "estimated_time_minutes": 30,
                "difficulty": "Moderate"
            },
            {
                "path_id": "RES-3",
                "condition": "Breaker trips repeatedly",
                "action": "Replace circuit breaker",
                "repair_code": "RP-ELC-001",
                "estimated_time_minutes": 45,
                "difficulty": "Moderate"
            }
        ]
    },

    "DT-APL-001": {
        "id": "DT-APL-001",
        "name": "Refrigerator Not Cooling Diagnostic Tree",
        "symptom_code": "PRB-APL-001",
        "category": "Appliances",
        "total_steps": 4,
        "avg_resolution_time_minutes": 35,
        "success_rate_percentage": 85.0,
        "steps": [
            {
                "step": 1,
                "title": "Verify Temperature and Power",
                "instruction": "Check thermostat setting (should be 37°F fridge / 0°F freezer). Confirm the unit is plugged in and the compressor is running (listen for hum at the back bottom).",
                "tools": ["Refrigerator thermometer"],
                "decision": "Is the compressor running?"
            },
            {
                "step": 2,
                "title": "Inspect Condenser Coils",
                "instruction": "Pull the refrigerator away from the wall. Locate condenser coils at the back or underneath. Check for heavy dust buildup which restricts heat dissipation.",
                "tools": ["Coil brush", "Vacuum with brush attachment"],
                "decision": "Are condenser coils heavily coated with dust?"
            },
            {
                "step": 3,
                "title": "Check Door Seals",
                "instruction": "Close the door on a piece of paper. If the paper pulls out easily, the door gasket is failing and warm air is entering. Inspect the full perimeter of both doors.",
                "tools": ["Paper test strip", "Flashlight"],
                "decision": "Is the door gasket failing the paper test?"
            },
            {
                "step": 4,
                "title": "Test Start Relay",
                "instruction": "Unplug the fridge. Pull the start relay off the compressor side terminal. Shake it next to your ear. A rattling sound indicates a failed relay.",
                "tools": ["Multimeter", "Nut driver"],
                "decision": "Does the start relay rattle or fail continuity test?"
            }
        ],
        "decision_points": [
            {"id": "DP-1", "question": "Compressor not running?",           "yes": "Test start relay",         "no": "Check airflow/seals"},
            {"id": "DP-2", "question": "Condenser coils heavily dusty?",    "yes": "Clean coils",              "no": "Check door seals"},
            {"id": "DP-3", "question": "Door gasket failing?",              "yes": "Replace door gasket",      "no": "Test start relay"},
            {"id": "DP-4", "question": "Start relay rattles/fails test?",   "yes": "RP-APL-001",               "no": "Compressor likely failed – call technician"}
        ],
        "resolution_paths": [
            {
                "path_id": "RES-1",
                "condition": "Dusty condenser coils",
                "action": "Clean condenser coils with brush and vacuum",
                "repair_code": "RP-APL-002",
                "estimated_time_minutes": 20,
                "difficulty": "Easy"
            },
            {
                "path_id": "RES-2",
                "condition": "Failing door gasket",
                "action": "Replace refrigerator door gasket",
                "repair_code": "RP-APL-003",
                "estimated_time_minutes": 30,
                "difficulty": "Easy"
            },
            {
                "path_id": "RES-3",
                "condition": "Failed start relay",
                "action": "Replace compressor start relay",
                "repair_code": "RP-APL-001",
                "estimated_time_minutes": 20,
                "difficulty": "Easy"
            }
        ]
    }
}

# ---------------------------------------------------------------------------
# V1 – repair_procedures.json
# ---------------------------------------------------------------------------

V1_REPAIR_PROCEDURES = {
    "RP-ROF-001": {
        "id": "RP-ROF-001",
        "name": "Replacing Asphalt Shingles",
        "category": "Roofing",
        "difficulty": "Moderate",
        "estimated_time": "2-3 hours",
        "estimated_time_minutes": 150,
        "tools_required": [
            "Safety harness and roof anchor",
            "Roofing ladder with standoffs",
            "Pry bar / flat bar",
            "Hammer",
            "Utility knife",
            "Caulk gun",
            "Chalk line",
            "Tape measure"
        ],
        "materials_required": [
            "Matching asphalt shingles",
            "Roofing nails (1-3/4 inch)",
            "Roofing cement / sealant",
            "Roofing felt (if underlayment damaged)"
        ],
        "safety_notes": "Always wear a safety harness on any roof above 6/12 pitch. Work in dry conditions only. Never work on a wet or icy roof.",
        "pre_repair_checks": [
            "Confirm weather forecast is clear for at least 24 hours",
            "Inspect attic for any additional water damage",
            "Verify replacement shingles match in color and style"
        ],
        "procedure_steps": [
            {
                "step": 1,
                "title": "Secure the Work Area",
                "detail": "Set up roofing ladder with standoffs so it does not rest on gutters. Attach safety harness to a properly installed roof anchor at the ridge. Clear any debris from the work area."
            },
            {
                "step": 2,
                "title": "Remove Damaged Shingles",
                "detail": "Slide the pry bar under the damaged shingle to break the adhesive seal. Remove the roofing nails from the damaged shingle and the two shingles above it that overlap it. Slide out the damaged shingle without disturbing surrounding ones."
            },
            {
                "step": 3,
                "title": "Inspect and Repair Underlayment",
                "detail": "Check the roofing felt/underlayment beneath the removed shingle. If torn or wet, cut out the damaged section and patch with a new piece of felt, overlapping 6 inches and securing with roofing nails. Apply roofing cement over the patch edges."
            },
            {
                "step": 4,
                "title": "Install New Shingle",
                "detail": "Slide the new shingle into position, aligning it with the surrounding shingles and the chalk line. Nail it down with four roofing nails, placing them 1 inch from each side and 1 inch above the bottom of the overlying shingle's cutout. Do not over-drive nails."
            },
            {
                "step": 5,
                "title": "Re-nail Overlying Shingles",
                "detail": "Replace the nails removed from the overlying shingles. Lift each tab carefully, apply a small dab of roofing cement under the lifted tabs to re-activate adhesion, and nail back in place."
            }
        ],
        "post_repair_checks": [
            "Press down on all shingle tabs to ensure adhesive contact",
            "Seal all nail heads with roofing cement",
            "Check from the ground that the repaired section aligns visually",
            "Monitor the attic for 48 hours after next rainfall"
        ],
        "warnings": [
            "Do not walk on shingles in hot weather as they can crack",
            "Never use a pressure washer on asphalt shingles"
        ]
    },

    "RP-PLB-001": {
        "id": "RP-PLB-001",
        "name": "Replacing Toilet Flapper",
        "category": "Plumbing",
        "difficulty": "Easy",
        "estimated_time": "15-30 minutes",
        "estimated_time_minutes": 22,
        "tools_required": [
            "Adjustable wrench (optional)",
            "Sponge or towel",
            "Bucket"
        ],
        "materials_required": [
            "Universal toilet flapper (or model-specific flapper)",
            "Rubber gloves"
        ],
        "safety_notes": "No electrical hazard. Wear rubber gloves. Water may be cold.",
        "pre_repair_checks": [
            "Confirm flapper is the issue: add food coloring to tank — if color appears in bowl without flushing, flapper is leaking",
            "Note the toilet brand/model to get a matching flapper"
        ],
        "procedure_steps": [
            {
                "step": 1,
                "title": "Shut Off Water Supply",
                "detail": "Turn the shutoff valve behind the toilet clockwise until fully closed. Flush the toilet to drain most of the tank water."
            },
            {
                "step": 2,
                "title": "Remove Tank Lid",
                "detail": "Lift the porcelain tank lid and set it aside safely on a folded towel to avoid cracking it."
            },
            {
                "step": 3,
                "title": "Remove Old Flapper",
                "detail": "Unhook the flapper ears from the overflow tube pegs on both sides. Disconnect the chain from the flush handle arm. Remove the old flapper and discard it."
            },
            {
                "step": 4,
                "title": "Install New Flapper",
                "detail": "Slide the new flapper ears over the overflow tube pegs. Attach the chain to the flush handle arm, leaving about 1/2 inch of slack — enough for the flapper to seat fully but lift completely when flushed."
            },
            {
                "step": 5,
                "title": "Test and Adjust",
                "detail": "Turn the water supply back on and allow the tank to fill. Flush several times and observe the flapper seating. Adjust chain length if needed. Verify no water leaks into the bowl by adding food coloring to the tank."
            }
        ],
        "post_repair_checks": [
            "Confirm tank fills to the fill line without overflowing",
            "Check food coloring test after 15 minutes with no flush",
            "Ensure the flapper sits flush with no gaps around the seal"
        ],
        "warnings": [
            "A chain that is too short will keep the flapper from seating",
            "A chain with too much slack can get caught under the flapper"
        ]
    },

    "RP-ELC-001": {
        "id": "RP-ELC-001",
        "name": "Circuit Breaker Replacement",
        "category": "Electrical",
        "difficulty": "Moderate",
        "estimated_time": "30-60 minutes",
        "estimated_time_minutes": 45,
        "tools_required": [
            "Non-contact voltage tester",
            "Flathead screwdriver",
            "Phillips screwdriver",
            "Needle-nose pliers",
            "Electrical tape",
            "Flashlight"
        ],
        "materials_required": [
            "Replacement breaker (same brand, amperage, and pole type as original)",
            "Rubber-soled work boots"
        ],
        "safety_notes": "WARNING: The main lugs in the panel remain live even with the main breaker off. Do not touch the large wires at the top of the panel. If uncomfortable, hire a licensed electrician.",
        "pre_repair_checks": [
            "Identify the failed breaker (tripped to middle position or won't reset)",
            "Purchase exact-match replacement breaker (brand and model number on side of breaker)",
            "Notify household occupants that power will be off"
        ],
        "procedure_steps": [
            {
                "step": 1,
                "title": "Turn Off Main Breaker",
                "detail": "Flip the main breaker at the top of the panel to OFF. Use a non-contact tester to verify branch circuits are de-energized. Note: the main service wires at the top of the panel are still live — do not touch them."
            },
            {
                "step": 2,
                "title": "Remove Panel Cover",
                "detail": "Unscrew the panel cover screws with a screwdriver and carefully remove the cover. Set it aside. Take a photo of the wiring layout before proceeding."
            },
            {
                "step": 3,
                "title": "Disconnect the Wire from the Faulty Breaker",
                "detail": "Locate the breaker to replace. Loosen the terminal screw and pull the hot wire (typically black) free. Note which terminal it came from."
            },
            {
                "step": 4,
                "title": "Remove the Faulty Breaker",
                "detail": "Grip the breaker and pull the outer edge away from the panel bus bar with a firm rocking motion until it unclips. Slide it out of the panel."
            },
            {
                "step": 5,
                "title": "Install the New Breaker",
                "detail": "Hook the new breaker onto the bus bar at the inner edge first, then press the outer edge firmly until it clicks into place. The breaker should be in the OFF position."
            },
            {
                "step": 6,
                "title": "Connect Wire and Restore Power",
                "detail": "Insert the hot wire into the new breaker's terminal and tighten the screw firmly. Replace the panel cover. Turn the main breaker back ON, then flip the new breaker to ON. Test the circuit with the voltage tester and by operating affected devices."
            }
        ],
        "post_repair_checks": [
            "Verify correct amperage on new breaker matches circuit wire gauge",
            "Test all outlets and fixtures on the replaced circuit",
            "Monitor for 24 hours to confirm breaker does not trip again"
        ],
        "warnings": [
            "Main service lugs remain energized even with main breaker off",
            "Never replace a breaker with a higher-amperage unit to stop tripping"
        ]
    },

    "RP-APL-001": {
        "id": "RP-APL-001",
        "name": "Refrigerator Start Relay Replacement",
        "category": "Appliances",
        "difficulty": "Easy",
        "estimated_time": "30-45 minutes",
        "estimated_time_minutes": 37,
        "tools_required": [
            "Nut driver or 1/4\" socket",
            "Flathead screwdriver",
            "Multimeter (optional)"
        ],
        "materials_required": [
            "Replacement start relay (model-specific — check sticker inside fridge door for model number)"
        ],
        "safety_notes": "Unplug the refrigerator before any repair. Allow capacitors to discharge for 5 minutes after unplugging.",
        "pre_repair_checks": [
            "Confirm compressor is not running (no hum from bottom-rear of fridge)",
            "Verify fridge is getting power (interior light on)",
            "Identify refrigerator model number and order correct relay"
        ],
        "procedure_steps": [
            {
                "step": 1,
                "title": "Unplug and Access Compressor",
                "detail": "Unplug the refrigerator from the wall outlet. Pull it away from the wall. Remove the rear access panel (if present) using the nut driver to expose the compressor at the bottom."
            },
            {
                "step": 2,
                "title": "Locate the Start Relay",
                "detail": "Find the start relay — a small rectangular or cylindrical component plugged into the side of the compressor. It may have a wire harness attached."
            },
            {
                "step": 3,
                "title": "Remove the Old Relay",
                "detail": "Disconnect the wire harness. Pull the relay straight off the compressor terminal pins with firm, even pressure. Shake it next to your ear — a rattle confirms it is faulty."
            },
            {
                "step": 4,
                "title": "Test with Multimeter (Optional)",
                "detail": "Set multimeter to continuity or resistance mode. Place probes on the relay terminals. A failed relay shows no continuity between the start and run terminals."
            },
            {
                "step": 5,
                "title": "Install New Relay",
                "detail": "Press the new relay firmly onto the compressor terminal pins in the same orientation as the original. Reconnect the wire harness. Replace the access panel."
            }
        ],
        "post_repair_checks": [
            "Plug the refrigerator back in and listen for compressor hum within 5 minutes",
            "Check fridge temperature after 4 hours — should be at or below 40°F",
            "Monitor for 24 hours to confirm stable cooling"
        ],
        "warnings": [
            "Do not operate the compressor without the relay — it will burn out",
            "Ensure the relay orientation matches the original; some are polarized"
        ]
    }
}

# ===========================================================================
# VERSION 2 – ELECTRONICS
# ===========================================================================

V2_DIR = "Version_2/05_JSON"

# ---------------------------------------------------------------------------
# V2 – diagnostic_trees.json
# ---------------------------------------------------------------------------

V2_DIAGNOSTIC_TREES = {
    "DT-PHN-001": {
        "id": "DT-PHN-001",
        "name": "Phone Battery Not Charging Diagnostic Tree",
        "symptom_code": "PRB-PHN-001",
        "category": "Phones",
        "total_steps": 4,
        "avg_resolution_time_minutes": 25,
        "success_rate_percentage": 90.0,
        "steps": [
            {
                "step": 1,
                "title": "Test Cable and Charger",
                "instruction": "Try a different certified cable and wall adapter. Attempt charging from a different outlet and also via a PC USB port. If the phone charges with a different cable, the cable is at fault.",
                "tools": ["Alternate charging cable", "Alternate charger"],
                "decision": "Does the phone charge with a different cable/charger?"
            },
            {
                "step": 2,
                "title": "Inspect Charging Port",
                "instruction": "Shine a flashlight into the charging port. Look for lint, debris, bent pins, or corrosion. Use a wooden toothpick or soft brush to carefully remove any debris. Do not use metal tools inside the port.",
                "tools": ["Flashlight", "Wooden toothpick", "Soft brush"],
                "decision": "Is debris or damage visible in the port?"
            },
            {
                "step": 3,
                "title": "Soft Reset and Software Check",
                "instruction": "Perform a soft reset (hold Power + Volume Down for 10 seconds). Boot into safe mode to rule out a rogue app consuming power. Check battery health in Settings > Battery.",
                "tools": ["Phone only"],
                "decision": "Does the phone charge normally after soft reset?"
            },
            {
                "step": 4,
                "title": "Battery Health Assessment",
                "instruction": "Check battery health percentage (iOS: Settings > Battery > Battery Health; Android: use a battery diagnostic app). Below 80% capacity is considered degraded and replacement is recommended.",
                "tools": ["Battery diagnostic app"],
                "decision": "Is battery health below 80%?"
            }
        ],
        "decision_points": [
            {"id": "DP-1", "question": "Cable/charger swap fixes it?", "yes": "Replace cable or charger", "no": "Inspect port"},
            {"id": "DP-2", "question": "Port has debris/damage?",       "yes": "Clean port or RP-PHN-003", "no": "Try soft reset"},
            {"id": "DP-3", "question": "Battery health below 80%?",     "yes": "RP-PHN-001",               "no": "Logic board issue — professional service"}
        ],
        "resolution_paths": [
            {
                "path_id": "RES-1",
                "condition": "Faulty charging cable or adapter",
                "action": "Replace with MFi-certified cable and charger",
                "repair_code": None,
                "estimated_time_minutes": 5,
                "difficulty": "Easy"
            },
            {
                "path_id": "RES-2",
                "condition": "Debris or lint in charging port",
                "action": "Clean charging port carefully",
                "repair_code": "RP-PHN-003",
                "estimated_time_minutes": 10,
                "difficulty": "Easy"
            },
            {
                "path_id": "RES-3",
                "condition": "Degraded battery (below 80% health)",
                "action": "Replace phone battery",
                "repair_code": "RP-PHN-001",
                "estimated_time_minutes": 60,
                "difficulty": "Moderate"
            }
        ]
    },

    "DT-PHN-002": {
        "id": "DT-PHN-002",
        "name": "Cracked Screen Diagnosis",
        "symptom_code": "PRB-PHN-002",
        "category": "Phones",
        "total_steps": 3,
        "avg_resolution_time_minutes": 15,
        "success_rate_percentage": 98.0,
        "steps": [
            {
                "step": 1,
                "title": "Assess Display Functionality",
                "instruction": "Check if the display still shows an image. Tap, swipe, and type across the entire screen to test touch responsiveness. Note any dark spots, lines, or areas with no touch response.",
                "tools": ["None"],
                "decision": "Is the display showing an image and responding to touch?"
            },
            {
                "step": 2,
                "title": "Check for Digitizer Damage",
                "instruction": "Test touch response in all four corners and the center. Try drawing or writing in a notes app. Dead zones or erratic touch indicate digitizer failure, not just a glass crack.",
                "tools": ["Stylus (optional)"],
                "decision": "Are there dead zones or erratic touch behavior?"
            },
            {
                "step": 3,
                "title": "Evaluate Repair vs. Replace",
                "instruction": "Compare cost of screen replacement (typically $120-$350 for flagship phones) against device trade-in or replacement cost. If device is over 3 years old, factor in battery and overall condition.",
                "tools": ["None"],
                "decision": "Is screen repair cost less than 50% of device replacement cost?"
            }
        ],
        "decision_points": [
            {"id": "DP-1", "question": "Display dead or no image?",       "yes": "Full OLED/LCD assembly needed — RP-PHN-002", "no": "Assess touch function"},
            {"id": "DP-2", "question": "Touch digitizer unresponsive?",   "yes": "RP-PHN-002 (full assembly)",                 "no": "Glass-only replacement feasible"},
            {"id": "DP-3", "question": "Repair cost-effective?",          "yes": "RP-PHN-002",                                 "no": "Consider device replacement"}
        ],
        "resolution_paths": [
            {
                "path_id": "RES-1",
                "condition": "Glass cracked but display and touch intact",
                "action": "Apply tempered glass screen protector as temp fix; schedule glass-only replacement",
                "repair_code": None,
                "estimated_time_minutes": 10,
                "difficulty": "Easy"
            },
            {
                "path_id": "RES-2",
                "condition": "Display dead or touch digitizer failed",
                "action": "Replace full screen assembly (OLED + digitizer)",
                "repair_code": "RP-PHN-002",
                "estimated_time_minutes": 60,
                "difficulty": "Expert"
            }
        ]
    },

    "DT-LAP-001": {
        "id": "DT-LAP-001",
        "name": "Laptop Won't Turn On Diagnostic Tree",
        "symptom_code": "PRB-LAP-003",
        "category": "Laptops",
        "total_steps": 4,
        "avg_resolution_time_minutes": 30,
        "success_rate_percentage": 82.0,
        "steps": [
            {
                "step": 1,
                "title": "Check Power Supply",
                "instruction": "Verify the charger LED is lit and charger is firmly connected. Try a different outlet. Inspect the charging port and cable for damage. Remove battery (if removable) and run on AC power only.",
                "tools": ["Multimeter (to test charger output voltage)", "Alternate charger"],
                "decision": "Does the laptop show any sign of life with confirmed-good charger?"
            },
            {
                "step": 2,
                "title": "Perform Hard Reset",
                "instruction": "Disconnect the charger. Hold the power button for 30 seconds to drain residual power. Reconnect charger and attempt power-on. This clears stuck power states common after updates or crashes.",
                "tools": ["None"],
                "decision": "Does the laptop power on after hard reset?"
            },
            {
                "step": 3,
                "title": "Check RAM Seating",
                "instruction": "Open the bottom access panel. Remove and firmly re-seat each RAM stick. Try booting with one stick at a time in the primary slot. A beep code on power-on indicates RAM is being detected.",
                "tools": ["Phillips screwdriver", "Anti-static wrist strap"],
                "decision": "Does the laptop POST (show manufacturer logo) with RAM re-seated?"
            },
            {
                "step": 4,
                "title": "External Display Test",
                "instruction": "Connect the laptop to an external monitor via HDMI or DisplayPort. Power on and check if the external display shows activity. This isolates whether the issue is the internal display or the motherboard/GPU.",
                "tools": ["HDMI cable", "External monitor"],
                "decision": "Does the external display show output?"
            }
        ],
        "decision_points": [
            {"id": "DP-1", "question": "No power with known-good charger?", "yes": "Likely dead battery or DC jack — service needed", "no": "Try hard reset"},
            {"id": "DP-2", "question": "Hard reset resolved it?",            "yes": "Monitor and update BIOS/firmware",               "no": "Check RAM"},
            {"id": "DP-3", "question": "External display has output?",       "yes": "Replace internal display/cable",                 "no": "Motherboard/GPU failure — professional service"}
        ],
        "resolution_paths": [
            {
                "path_id": "RES-1",
                "condition": "Stuck power state",
                "action": "Hard reset resolves the issue",
                "repair_code": None,
                "estimated_time_minutes": 5,
                "difficulty": "Easy"
            },
            {
                "path_id": "RES-2",
                "condition": "Overheating causing shutdown/no boot",
                "action": "Clean fan and replace thermal paste",
                "repair_code": "RP-LAP-001",
                "estimated_time_minutes": 45,
                "difficulty": "Moderate"
            },
            {
                "path_id": "RES-3",
                "condition": "Internal display failure with external output OK",
                "action": "Replace display panel or display cable",
                "repair_code": "RP-LAP-002",
                "estimated_time_minutes": 60,
                "difficulty": "Moderate"
            }
        ]
    },

    "DT-CON-001": {
        "id": "DT-CON-001",
        "name": "Console HDMI Port Failure Diagnostic Tree",
        "symptom_code": "PRB-CON-001",
        "category": "Gaming",
        "total_steps": 3,
        "avg_resolution_time_minutes": 20,
        "success_rate_percentage": 88.0,
        "steps": [
            {
                "step": 1,
                "title": "Isolate Cable and TV",
                "instruction": "Test the same HDMI cable on another device connected to the same TV port. Then try a different HDMI cable on the console. Test the console on a different TV or monitor.",
                "tools": ["Spare HDMI 2.1 cable", "Second display"],
                "decision": "Does the console output video on a different TV/cable combination?"
            },
            {
                "step": 2,
                "title": "Inspect HDMI Port",
                "instruction": "Shine a flashlight into the console's HDMI port. Look for bent or pushed-in pins, debris, or visible damage. A single bent pin is often repairable with fine tweezers.",
                "tools": ["Flashlight", "Fine-tip tweezers", "Magnifying glass"],
                "decision": "Are pins bent or is there visible port damage?"
            },
            {
                "step": 3,
                "title": "Safe Mode / Software Check",
                "instruction": "Boot the console in Safe Mode (hold power button until second beep). Select 'Change Resolution' or 'Reset Video Output'. This can resolve black-screen issues from incorrect resolution settings.",
                "tools": ["Console controller"],
                "decision": "Did Safe Mode video reset restore output?"
            }
        ],
        "decision_points": [
            {"id": "DP-1", "question": "Works on different TV/cable?",      "yes": "Replace HDMI cable or fix TV HDMI port", "no": "Inspect console port"},
            {"id": "DP-2", "question": "Port pins bent/damaged?",           "yes": "RP-CON-001 (HDMI port replacement)",     "no": "Try Safe Mode reset"},
            {"id": "DP-3", "question": "Safe Mode reset restored output?",  "yes": "Adjust display settings",               "no": "HDMI IC chip failure — professional service"}
        ],
        "resolution_paths": [
            {
                "path_id": "RES-1",
                "condition": "Faulty HDMI cable",
                "action": "Replace with HDMI 2.1 certified cable",
                "repair_code": None,
                "estimated_time_minutes": 5,
                "difficulty": "Easy"
            },
            {
                "path_id": "RES-2",
                "condition": "Damaged HDMI port on console",
                "action": "Replace console HDMI port",
                "repair_code": "RP-CON-001",
                "estimated_time_minutes": 45,
                "difficulty": "Expert"
            }
        ]
    }
}

# ---------------------------------------------------------------------------
# V2 – repair_procedures.json
# ---------------------------------------------------------------------------

V2_REPAIR_PROCEDURES = {
    "RP-PHN-001": {
        "id": "RP-PHN-001",
        "name": "iPhone Battery Replacement",
        "category": "Phones",
        "difficulty": "Moderate",
        "estimated_time": "45-60 minutes",
        "estimated_time_minutes": 52,
        "tools_required": [
            "Pentalobe P2 screwdriver",
            "Phillips #000 screwdriver",
            "Suction cup handle",
            "Plastic opening picks",
            "Spudger",
            "Tweezers",
            "Heat gun or iOpener",
            "Anti-static mat"
        ],
        "materials_required": [
            "OEM-grade replacement battery (model-specific)",
            "Replacement Pentalobe screws (included in most battery kits)",
            "Adhesive strips for battery",
            "90% or higher isopropyl alcohol",
            "Lint-free cloth"
        ],
        "safety_notes": "Discharge battery to below 25% before repair to reduce fire risk. Do not puncture the old battery. If battery is swollen, use extra caution — the device may need to stay in a fireproof container.",
        "pre_repair_checks": [
            "Back up all data via iCloud or iTunes",
            "Confirm correct battery model for your iPhone variant",
            "Discharge battery to 25% or less"
        ],
        "procedure_steps": [
            {
                "step": 1,
                "title": "Remove Bottom Screws",
                "detail": "Power off the iPhone. Remove the two Pentalobe P2 screws on either side of the Lightning/USB-C port at the bottom of the device."
            },
            {
                "step": 2,
                "title": "Apply Heat and Open Display",
                "detail": "Apply heat along the bottom edge of the display for 90 seconds with a heat gun on low or an iOpener bag. This softens the adhesive. Attach suction cup to the lower display and gently pull while inserting a plastic pick at the bottom gap. Slide picks around the perimeter to cut adhesive. Do not open more than 90 degrees — the display cables run up the right side."
            },
            {
                "step": 3,
                "title": "Disconnect Battery Connector",
                "detail": "Remove the screws from the battery connector bracket. Use a spudger to gently pry the battery flex cable connector straight up off the logic board. This prevents current flow during repair."
            },
            {
                "step": 4,
                "title": "Remove Display Assembly",
                "detail": "Disconnect the display and digitizer flex cables using the spudger. Lift the display assembly free and set aside on the anti-static mat."
            },
            {
                "step": 5,
                "title": "Remove Old Battery",
                "detail": "Locate the battery adhesive pull-tabs (typically 2-3 strips). Pull each tab slowly at a low angle (almost parallel to the battery) to stretch and release the adhesive. If tabs break, use isopropyl alcohol at the battery edges to dissolve remaining adhesive."
            },
            {
                "step": 6,
                "title": "Install New Battery",
                "detail": "Peel the backing off the new adhesive strips and position the new battery in the same orientation. Press firmly for 10 seconds. Reconnect the battery flex cable connector — press down until it clicks."
            },
            {
                "step": 7,
                "title": "Reconnect Display and Close",
                "detail": "Reconnect the display and digitizer connectors. Replace their bracket and screws. Close the display by pressing first at the top and working down to the bottom edge. Press all edges firmly to re-seat adhesive."
            },
            {
                "step": 8,
                "title": "Reinstall Pentalobe Screws and Test",
                "detail": "Replace the two Pentalobe screws at the bottom. Power on the device. Navigate to Settings > Battery > Battery Health to confirm the new battery is recognized and shows 100% capacity."
            }
        ],
        "post_repair_checks": [
            "Verify battery health shows 100% in Settings",
            "Perform a full charge cycle to calibrate the battery",
            "Check all buttons, cameras, and sensors work correctly"
        ],
        "warnings": [
            "Never use metal tools to pry the battery — puncture causes thermal runaway",
            "Do not overtighten screws in the logic board brackets — stripped screws are a common mistake"
        ]
    },

    "RP-PHN-002": {
        "id": "RP-PHN-002",
        "name": "Samsung Galaxy Screen Replacement",
        "category": "Phones",
        "difficulty": "Expert",
        "estimated_time": "60-90 minutes",
        "estimated_time_minutes": 75,
        "tools_required": [
            "T3 Torx screwdriver",
            "Phillips #000 screwdriver",
            "Heat gun",
            "Suction cup handle",
            "Plastic opening picks and spudger",
            "Tweezers",
            "UV lamp (if using UV adhesive)",
            "Anti-static mat and wrist strap"
        ],
        "materials_required": [
            "OEM or OEM-grade AMOLED screen assembly with frame",
            "B7000 or UV-cure LOCA adhesive",
            "Pre-cut adhesive gasket",
            "90% isopropyl alcohol",
            "Lint-free cloth"
        ],
        "safety_notes": "Samsung OLED displays are fragile and glued directly to the frame. Rushing heat or prying will crack the display. Disconnect the battery FIRST before any other step.",
        "pre_repair_checks": [
            "Back up all data",
            "Confirm the exact model number (e.g., SM-S928B vs SM-S928U — parts differ)",
            "Order a frame-included assembly to avoid adhesive re-gluing of the panel"
        ],
        "procedure_steps": [
            {
                "step": 1,
                "title": "Heat and Remove Back Glass",
                "detail": "Apply heat to the back panel for 2 minutes on medium. Attach suction cup and slowly peel the back glass using picks. Work slowly — Samsung back glass is extremely thin and cracks easily. Remove all back panel screws after removing the back glass."
            },
            {
                "step": 2,
                "title": "Disconnect Battery",
                "detail": "Locate the battery connector and use a spudger to disconnect it immediately. Do not proceed with any other disassembly until the battery is disconnected."
            },
            {
                "step": 3,
                "title": "Disconnect All Flex Cables",
                "detail": "Systematically disconnect the charging port flex, fingerprint sensor, and any mid-frame antenna cables. Label or photograph each connection point."
            },
            {
                "step": 4,
                "title": "Heat and Remove Front Display",
                "detail": "Apply heat to the display edges for 2-3 minutes. Insert a pick at one corner with a suction cup pulling gently. Work picks along all four edges cutting the LOCA adhesive. The OLED panel bonds directly to the glass — do not flex it."
            },
            {
                "step": 5,
                "title": "Clean Frame",
                "detail": "Remove all old adhesive residue from the frame using isopropyl alcohol and a plastic scraper. The mating surface must be completely clean and flat for proper adhesion of the new screen."
            },
            {
                "step": 6,
                "title": "Install New Screen Assembly",
                "detail": "Apply new adhesive gasket to the frame. Press the new screen assembly into the frame evenly, starting from the top. Apply firm, even pressure around all edges for 60 seconds."
            },
            {
                "step": 7,
                "title": "Reconnect Everything and Test",
                "detail": "Reconnect all flex cables in reverse order of removal. Reconnect the battery last. Power on to test display, touch, fingerprint, and all sensors before applying the back glass."
            },
            {
                "step": 8,
                "title": "Apply Back Glass",
                "detail": "Apply new pre-cut back glass adhesive. Press back glass firmly for 90 seconds. Replace all screws and verify waterproofing adhesive is fully seated."
            }
        ],
        "post_repair_checks": [
            "Test full touch digitizer response across entire screen",
            "Test fingerprint sensor, front camera, Face ID equivalents",
            "Run display burn-in test (uniform color test)",
            "Verify IP rating adhesive is intact"
        ],
        "warnings": [
            "OLED panels crack instantly if over-bent — never force open",
            "Heat gun distance must be maintained — direct contact will burn the panel"
        ]
    },

    "RP-LAP-001": {
        "id": "RP-LAP-001",
        "name": "MacBook Thermal Paste Replacement",
        "category": "Laptops",
        "difficulty": "Moderate",
        "estimated_time": "30-45 minutes",
        "estimated_time_minutes": 37,
        "tools_required": [
            "Pentalobe P5 screwdriver (bottom case)",
            "Torx T3 screwdriver",
            "Plastic spudger",
            "Thermal paste applicator / plastic spreader",
            "Lint-free cloth",
            "Anti-static mat and wrist strap"
        ],
        "materials_required": [
            "High-quality thermal compound (e.g., Thermal Grizzly Kryonaut or MX-6)",
            "90% isopropyl alcohol",
            "Cotton swabs"
        ],
        "safety_notes": "Discharge battery or disconnect it before touching the logic board. Ground yourself with an anti-static wrist strap before touching any components.",
        "pre_repair_checks": [
            "Confirm overheating by checking fan speed and CPU temps with iStatMenus or Activity Monitor",
            "Verify MacBook is out of AppleCare before opening (opening voids warranty on some models)"
        ],
        "procedure_steps": [
            {
                "step": 1,
                "title": "Remove Bottom Case",
                "detail": "Remove the eight Pentalobe P5 screws on the bottom of the MacBook. Note that two screws near the hinge are longer than the rest. Gently pry the bottom case off with a plastic spudger inserted near the rear vents."
            },
            {
                "step": 2,
                "title": "Disconnect Battery",
                "detail": "Locate the battery connector (a flat ZIF connector near the logic board). Use a spudger to gently lift and disconnect it. This prevents accidental power during repairs."
            },
            {
                "step": 3,
                "title": "Remove Heat Sink",
                "detail": "Locate the screws securing the heat sink to the CPU/GPU. Remove them in a cross pattern (opposite corners) to release pressure evenly. Gently lift the heat sink straight up — do not slide it, as this can damage the CPU die."
            },
            {
                "step": 4,
                "title": "Clean Old Thermal Paste",
                "detail": "Use cotton swabs and 90% isopropyl alcohol to completely remove old thermal paste from both the CPU/GPU die and the heat sink contact plate. Allow to dry fully before applying new paste."
            },
            {
                "step": 5,
                "title": "Apply New Thermal Paste",
                "detail": "Apply a rice-grain-sized dot of thermal compound to the center of the CPU die. For MacBooks with a larger heat spreader (e.g., M1/M2 chips), use a thin spread method. Less is more — excess paste causes no benefit and may contact board components."
            },
            {
                "step": 6,
                "title": "Reinstall Heat Sink and Close",
                "detail": "Lower the heat sink straight down onto the CPU. Replace screws in a cross pattern, tightening gradually and evenly. Reconnect the battery. Reattach the bottom case and replace all Pentalobe screws."
            }
        ],
        "post_repair_checks": [
            "Boot the MacBook and verify it powers on normally",
            "Run CPU stress test (e.g., Geekbench or Prime95) for 15 minutes",
            "Monitor CPU temperature — should stay below 85°C under full load",
            "Confirm fan noise has decreased compared to before repair"
        ],
        "warnings": [
            "Only apply thermal paste to the CPU/GPU die — not the surrounding board",
            "Do not over-tighten heat sink screws — apply even, moderate torque only"
        ]
    },

    "RP-CON-001": {
        "id": "RP-CON-001",
        "name": "PS5 Liquid Metal Application",
        "category": "Gaming",
        "difficulty": "Expert",
        "estimated_time": "45-60 minutes",
        "estimated_time_minutes": 52,
        "tools_required": [
            "Phillips #1 screwdriver",
            "Torx T8 screwdriver",
            "Plastic spudger and pry tool",
            "Anti-static mat and wrist strap",
            "Liquid metal applicator pen or small brush",
            "Electrical tape or liquid metal barrier pen",
            "Magnifying glass"
        ],
        "materials_required": [
            "Thermal Grizzly Conductonaut liquid metal compound (or equivalent)",
            "90% isopropyl alcohol",
            "Cotton swabs",
            "Kapton tape (for masking)"
        ],
        "safety_notes": "CRITICAL: Liquid metal is electrically conductive. Any contact with surrounding SMD components or the PCB will cause a short circuit and permanent damage. Work slowly and mask all surrounding areas with Kapton tape before applying liquid metal.",
        "pre_repair_checks": [
            "Confirm PS5 is overheating (thermal throttling, loud fan, shutdowns under load)",
            "Gather all tools before opening — reassembly must happen the same session",
            "Watch a model-specific disassembly video (Disc vs. Digital editions differ slightly)"
        ],
        "procedure_steps": [
            {
                "step": 1,
                "title": "Remove PS5 Shell",
                "detail": "Stand the PS5 vertically. Pull the white top panel upward and toward you — it unclips without screws. Repeat for the second panel. Remove the corner screw holding the fan shroud."
            },
            {
                "step": 2,
                "title": "Remove Fan and Heat Sink",
                "detail": "Unplug the fan connector. Remove the four screws holding the large heat sink — use a cross pattern. Gently lift the heat sink from the APU (Accelerated Processing Unit) die."
            },
            {
                "step": 3,
                "title": "Clean Old Liquid Metal",
                "detail": "Sony uses liquid metal from the factory. Use cotton swabs with 90% isopropyl alcohol to carefully clean both the APU die and the copper heat sink contact plate. The APU die is small — work carefully around it."
            },
            {
                "step": 4,
                "title": "Mask Surrounding Area",
                "detail": "Apply Kapton tape or the electrical barrier from the liquid metal kit to protect all SMD components and board traces within 5mm of the APU die. Liquid metal will short out anything it touches."
            },
            {
                "step": 5,
                "title": "Apply Liquid Metal",
                "detail": "Apply a tiny amount of liquid metal to the center of the APU die — approximately the size of a small pea. Use the applicator pen or a small brush to spread it in a thin, even layer covering only the die surface. Apply the same thin layer to the copper heat sink contact plate."
            },
            {
                "step": 6,
                "title": "Reinstall Heat Sink",
                "detail": "Carefully lower the heat sink straight down onto the APU — any sliding motion will spread liquid metal onto unmasked areas. Tighten screws in cross pattern to manufacturer torque. Remove Kapton tape masking."
            },
            {
                "step": 7,
                "title": "Reassemble and Test",
                "detail": "Reconnect the fan. Reattach the heat sink shroud and screw. Replace the PS5 shell panels. Power on and run a demanding game for 30 minutes while monitoring temperatures with a thermal logger app on a linked smartphone."
            }
        ],
        "post_repair_checks": [
            "APU temperature under full load should drop 10-20°C vs. before repair",
            "Fan noise should decrease noticeably under gaming load",
            "Verify no artifacts or crashes during extended gameplay"
        ],
        "warnings": [
            "NEVER let liquid metal contact any area other than the die surface and heat sink plate",
            "Never tilt the console while liquid metal is fresh — it can flow off the die",
            "This repair voids all remaining warranty"
        ]
    }
}

# ===========================================================================
# VERSION 3 – INDUSTRIAL / AUTOMOTIVE
# ===========================================================================

V3_DIR = "Version_3/05_JSON"

# ---------------------------------------------------------------------------
# V3 – diagnostic_trees.json
# ---------------------------------------------------------------------------

V3_DIAGNOSTIC_TREES = {
    "DT-CAR-001": {
        "id": "DT-CAR-001",
        "name": "Check Engine Light Diagnostic Tree",
        "symptom_code": "PRB-CAR-001",
        "category": "Cars",
        "total_steps": 4,
        "avg_resolution_time_minutes": 40,
        "success_rate_percentage": 87.0,
        "steps": [
            {
                "step": 1,
                "title": "Read Fault Codes",
                "instruction": "Connect an OBD-II scanner to the port under the dashboard (driver's side). Read all stored and pending DTCs. Note all codes before clearing. A solid CEL is non-urgent; a flashing CEL indicates an active misfire — do not drive at highway speed.",
                "tools": ["OBD-II scanner or Bluetooth dongle + app"],
                "decision": "Are there any P0 (powertrain) codes stored?"
            },
            {
                "step": 2,
                "title": "Research Code Priority",
                "instruction": "Identify the primary code (first stored code). Group codes: fuel system (P01xx), ignition (P03xx), catalyst/emissions (P04xx), oxygen sensors (P013x-P015x). Address primary code first — secondary codes often clear once root cause is fixed.",
                "tools": ["OBD-II scanner", "Repair manual or AllData"],
                "decision": "Is the primary code related to oxygen sensor or fuel system?"
            },
            {
                "step": 3,
                "title": "Inspect Oxygen Sensors",
                "instruction": "With the engine warm, use a live data scanner to monitor O2 sensor waveforms. Upstream sensor should oscillate 0.1-0.9V rapidly. A flat waveform or stuck voltage indicates a failed sensor.",
                "tools": ["OBD-II scanner with live data", "Digital multimeter"],
                "decision": "Is the upstream or downstream O2 sensor waveform abnormal?"
            },
            {
                "step": 4,
                "title": "Inspect MAF Sensor and Vacuum Lines",
                "instruction": "Check the MAF sensor reading at idle (should be ~2-7 g/s for most 4-cyl engines). Inspect all vacuum hoses for cracks, disconnections, or collapse. Spray carburetor cleaner around intake manifold gaskets to detect vacuum leaks.",
                "tools": ["OBD-II live data scanner", "Carburetor cleaner spray", "Vacuum gauge"],
                "decision": "Is MAF reading out of spec or are vacuum leaks detected?"
            }
        ],
        "decision_points": [
            {"id": "DP-1", "question": "Flashing CEL (active misfire)?",      "yes": "Do not drive — diagnose immediately; P0300 misfires", "no": "Read and prioritize codes"},
            {"id": "DP-2", "question": "O2 sensor code with flat waveform?",  "yes": "RP-CAR-001",                                          "no": "Check MAF and vacuum"},
            {"id": "DP-3", "question": "Vacuum leak detected?",               "yes": "Repair intake gaskets/hoses",                         "no": "Further diagnostics or dealer scan"}
        ],
        "resolution_paths": [
            {
                "path_id": "RES-1",
                "condition": "Faulty oxygen sensor confirmed by waveform or code",
                "action": "Replace oxygen sensor",
                "repair_code": "RP-CAR-001",
                "estimated_time_minutes": 45,
                "difficulty": "Easy"
            },
            {
                "path_id": "RES-2",
                "condition": "Vacuum leak at intake",
                "action": "Replace intake manifold gasket or repair vacuum hose",
                "repair_code": "RP-CAR-002",
                "estimated_time_minutes": 120,
                "difficulty": "Moderate"
            },
            {
                "path_id": "RES-3",
                "condition": "MAF sensor out of range",
                "action": "Clean or replace MAF sensor",
                "repair_code": "RP-CAR-003",
                "estimated_time_minutes": 30,
                "difficulty": "Easy"
            }
        ]
    },

    "DT-HEQ-001": {
        "id": "DT-HEQ-001",
        "name": "Excavator Hydraulic System Diagnostic Tree",
        "symptom_code": "PRB-HVY-001",
        "category": "Heavy Equipment",
        "total_steps": 4,
        "avg_resolution_time_minutes": 60,
        "success_rate_percentage": 85.0,
        "steps": [
            {
                "step": 1,
                "title": "Check Hydraulic Fluid Level and Condition",
                "instruction": "With the machine on level ground and all cylinders retracted, check the hydraulic tank sight glass. Level should be at or above the MIN mark. Check fluid color: milky = water contamination; dark/burnt smell = overheating degradation.",
                "tools": ["Sight glass check (no tools)", "Sample bottle for fluid analysis"],
                "decision": "Is fluid level low or fluid condition degraded?"
            },
            {
                "step": 2,
                "title": "Inspect for External Leaks",
                "instruction": "Walk around the machine and inspect all hydraulic hoses, cylinders, and fittings. Look for wet areas, fluid trails, or pooling under the machine. Clean suspected areas with rags and cycle the circuit to identify active leak points.",
                "tools": ["Clean rags", "Flashlight", "Pressure-safe gloves"],
                "decision": "Is an external leak source visible?"
            },
            {
                "step": 3,
                "title": "Measure System Pressure",
                "instruction": "Connect a hydraulic pressure gauge at the main relief valve port. Start the engine and measure standby pressure (typically 200-350 bar depending on machine). Then stall the circuit against a solid load and measure relief pressure. Compare to service manual specs.",
                "tools": ["Hydraulic pressure test gauge (0-600 bar)", "Service manual"],
                "decision": "Is main relief pressure below specification?"
            },
            {
                "step": 4,
                "title": "Cylinder Drift Test",
                "instruction": "Lift a full bucket load and raise the boom. Shut off the engine. Observe for cylinder drift over 5 minutes. Drift indicates internal cylinder seal leak or control valve leak. Identify which cylinder is drifting.",
                "tools": ["Full load in bucket", "Stopwatch"],
                "decision": "Is there measurable cylinder drift after engine shutdown?"
            }
        ],
        "decision_points": [
            {"id": "DP-1", "question": "Fluid low or contaminated?",       "yes": "Top up/change fluid and inspect for source", "no": "Check for leaks"},
            {"id": "DP-2", "question": "External leak found?",             "yes": "RP-HEQ-002 (hose/seal repair)",              "no": "Measure system pressure"},
            {"id": "DP-3", "question": "Relief pressure below spec?",      "yes": "Adjust or replace main relief valve",         "no": "Perform cylinder drift test"}
        ],
        "resolution_paths": [
            {
                "path_id": "RES-1",
                "condition": "Ruptured hydraulic hose",
                "action": "Replace hydraulic hose assembly",
                "repair_code": "RP-HEQ-002",
                "estimated_time_minutes": 90,
                "difficulty": "Moderate"
            },
            {
                "path_id": "RES-2",
                "condition": "Failed cylinder seals (cylinder drift)",
                "action": "Rebuild or replace hydraulic cylinder",
                "repair_code": "RP-HEQ-003",
                "estimated_time_minutes": 240,
                "difficulty": "Expert"
            },
            {
                "path_id": "RES-3",
                "condition": "Main relief valve pressure low",
                "action": "Adjust or replace main relief valve",
                "repair_code": "RP-HEQ-004",
                "estimated_time_minutes": 120,
                "difficulty": "Expert"
            }
        ]
    },

    "DT-GEN-001": {
        "id": "DT-GEN-001",
        "name": "Generator Not Starting Diagnostic Tree",
        "symptom_code": "PRB-GEN-001",
        "category": "Generators",
        "total_steps": 4,
        "avg_resolution_time_minutes": 35,
        "success_rate_percentage": 88.0,
        "steps": [
            {
                "step": 1,
                "title": "Check Battery and Starter Circuit",
                "instruction": "Test battery voltage with a multimeter — should be 12.4V or above at rest. Test voltage during cranking — should not drop below 9.5V. Check battery terminals for corrosion. Verify the E-Stop (emergency stop) button is released.",
                "tools": ["Multimeter", "Battery load tester"],
                "decision": "Is battery voltage above 12.4V and cranking voltage above 9.5V?"
            },
            {
                "step": 2,
                "title": "Check Fuel System",
                "instruction": "Verify fuel tank is at least 1/4 full. Check fuel shutoff valve is open. Inspect the fuel filter for clogging (replace if not changed in last 500 hours). Check fuel lines for kinks or cracks. For diesel, check for air in fuel lines (bleed if needed).",
                "tools": ["Fuel pressure gauge", "Flashlight"],
                "decision": "Is there adequate clean fuel reaching the injection system?"
            },
            {
                "step": 3,
                "title": "Inspect Air Intake and Filter",
                "instruction": "Remove and inspect the air filter. A clogged filter causes hard starting and black smoke. Check the intake for obstructions (bird nests are common in outdoor generators).",
                "tools": ["None"],
                "decision": "Is the air filter heavily clogged or intake obstructed?"
            },
            {
                "step": 4,
                "title": "Check Governor and Throttle",
                "instruction": "Inspect the throttle linkage for binding or damage. Verify the governor arm moves freely. Check for fault codes on the generator control module if equipped with digital controls.",
                "tools": ["Generator diagnostic software (if available)", "Inspection mirror"],
                "decision": "Is the throttle/governor mechanism binding or are control module faults present?"
            }
        ],
        "decision_points": [
            {"id": "DP-1", "question": "Battery/starting circuit issue?",   "yes": "Charge or replace battery / repair starter",    "no": "Check fuel"},
            {"id": "DP-2", "question": "Fuel starvation confirmed?",        "yes": "Replace fuel filter / bleed fuel lines",        "no": "Check air intake"},
            {"id": "DP-3", "question": "Governor/throttle binding?",        "yes": "RP-GEN-001",                                    "no": "Injector or compression test needed"}
        ],
        "resolution_paths": [
            {
                "path_id": "RES-1",
                "condition": "Dead or weak starting battery",
                "action": "Charge or replace generator battery",
                "repair_code": "RP-GEN-002",
                "estimated_time_minutes": 30,
                "difficulty": "Easy"
            },
            {
                "path_id": "RES-2",
                "condition": "Clogged fuel filter or air in diesel fuel",
                "action": "Replace fuel filter and bleed fuel system",
                "repair_code": "RP-GEN-003",
                "estimated_time_minutes": 45,
                "difficulty": "Moderate"
            },
            {
                "path_id": "RES-3",
                "condition": "Governor or control panel fault",
                "action": "Repair or replace generator control panel",
                "repair_code": "RP-GEN-001",
                "estimated_time_minutes": 180,
                "difficulty": "Expert"
            }
        ]
    },

    "DT-SOL-001": {
        "id": "DT-SOL-001",
        "name": "Solar Output Dropping Diagnostic Tree",
        "symptom_code": "PRB-SOL-001",
        "category": "Solar Systems",
        "total_steps": 4,
        "avg_resolution_time_minutes": 45,
        "success_rate_percentage": 91.0,
        "steps": [
            {
                "step": 1,
                "title": "Compare Output to Baseline",
                "instruction": "Review inverter monitoring data or app. Compare current daily output (kWh) to the same period in prior years and to the manufacturer's performance ratio. A drop over 20% vs. baseline warrants investigation.",
                "tools": ["Inverter monitoring app / web portal", "Irradiance data (pvwatts.nrel.gov)"],
                "decision": "Is output more than 20% below historical baseline for this season?"
            },
            {
                "step": 2,
                "title": "Inspect Panels for Shading and Soiling",
                "instruction": "Visually inspect all panels from ground level with binoculars or drone. Look for: bird droppings, pollen/dust buildup, leaves, nearby tree growth causing new shading, or physical damage (cracks, delamination, discoloration).",
                "tools": ["Binoculars or drone", "Flashlight"],
                "decision": "Is soiling, shading, or physical damage observed on any panel?"
            },
            {
                "step": 3,
                "title": "Check Inverter Faults and String Voltages",
                "instruction": "Access the inverter display or monitoring portal. Check for fault codes or alarm logs. Use a multimeter to measure open-circuit voltage (Voc) at each string input on the inverter. Compare measured Voc to spec (typically: panels_in_string × Voc_per_panel × 0.85 for temperature correction).",
                "tools": ["Multimeter (1000V DC rated)", "Wiring diagram", "Inverter manual"],
                "decision": "Is any string voltage significantly below expected value?"
            },
            {
                "step": 4,
                "title": "Isolate Underperforming Panels",
                "instruction": "Use a clamp meter to measure current at each panel or use a thermal camera to identify hotspots (failed cells appear as hot spots). An IV curve tracer gives the most precise panel-level data.",
                "tools": ["DC clamp meter", "IV curve tracer (optional)", "Thermal camera"],
                "decision": "Is one or more panels producing significantly less current?"
            }
        ],
        "decision_points": [
            {"id": "DP-1", "question": "Output within 20% of baseline?",    "yes": "Seasonal variation — no action needed",  "no": "Inspect panels"},
            {"id": "DP-2", "question": "Soiling or shading confirmed?",     "yes": "RP-SOL-001 (panel cleaning) / trim trees", "no": "Check inverter strings"},
            {"id": "DP-3", "question": "String voltage low on one string?", "yes": "Isolate individual panels in that string",   "no": "Inverter internal fault — contact installer"}
        ],
        "resolution_paths": [
            {
                "path_id": "RES-1",
                "condition": "Panel soiling (dust, pollen, bird droppings)",
                "action": "Clean all panels",
                "repair_code": "RP-SOL-001",
                "estimated_time_minutes": 90,
                "difficulty": "Easy"
            },
            {
                "path_id": "RES-2",
                "condition": "Faulty panel with hotspot or failed cell string",
                "action": "Replace failed solar panel",
                "repair_code": "RP-SOL-002",
                "estimated_time_minutes": 120,
                "difficulty": "Moderate"
            },
            {
                "path_id": "RES-3",
                "condition": "Inverter fault code or internal failure",
                "action": "Reset or replace inverter / contact manufacturer",
                "repair_code": "RP-SOL-003",
                "estimated_time_minutes": 180,
                "difficulty": "Expert"
            }
        ]
    }
}

# ---------------------------------------------------------------------------
# V3 – repair_procedures.json
# ---------------------------------------------------------------------------

V3_REPAIR_PROCEDURES = {
    "RP-CAR-001": {
        "id": "RP-CAR-001",
        "name": "O2 Sensor Replacement",
        "category": "Cars",
        "difficulty": "Easy",
        "estimated_time": "30-60 minutes",
        "estimated_time_minutes": 45,
        "tools_required": [
            "OBD-II scanner",
            "O2 sensor socket (22mm with wire slot)",
            "Ratchet and extensions",
            "Breaker bar",
            "Penetrating oil (PB Blaster or equivalent)",
            "Jack and jack stands (if sensor is underneath)",
            "Safety glasses"
        ],
        "materials_required": [
            "Replacement O2 sensor (match exact part number from OBD code and vehicle VIN)",
            "Anti-seize compound (if not pre-applied to new sensor)"
        ],
        "safety_notes": "Allow exhaust system to cool fully before touching. Hot exhaust pipes cause severe burns. Use jack stands — never work under a vehicle supported only by a floor jack.",
        "pre_repair_checks": [
            "Confirm which sensor is faulty: Bank 1/Bank 2, Sensor 1 (upstream) or Sensor 2 (downstream)",
            "Apply penetrating oil to sensor threads the evening before repair if possible",
            "Verify replacement sensor is the correct type (wideband vs. narrowband)"
        ],
        "procedure_steps": [
            {
                "step": 1,
                "title": "Locate the Faulty Sensor",
                "detail": "Using the DTC code and OBD-II data, identify which sensor needs replacement. Bank 1 Sensor 1 is upstream on the engine side with cylinder #1. Trace the sensor wire to physically locate it on the exhaust pipe or manifold."
            },
            {
                "step": 2,
                "title": "Disconnect Electrical Connector",
                "detail": "Trace the sensor wire to its electrical connector, typically clipped to the firewall or frame. Press the tab and pull the connector apart. Do not pull on the wires themselves."
            },
            {
                "step": 3,
                "title": "Remove Old Sensor",
                "detail": "Apply penetrating oil around the sensor base and let it soak for 10 minutes. Use the O2 sensor socket with a breaker bar to break the sensor loose — turn counterclockwise. If it won't budge, apply more penetrating oil and wait. Forcing it risks rounding the sensor or stripping threads."
            },
            {
                "step": 4,
                "title": "Clean Threads",
                "detail": "Inspect the thread bung in the exhaust pipe. Clean any debris with a wire brush or thread chaser tap. If threads are damaged, a thread repair kit will be needed."
            },
            {
                "step": 5,
                "title": "Install New Sensor",
                "detail": "Apply anti-seize compound to the new sensor threads if not pre-applied. Thread the sensor in by hand first to avoid cross-threading. Tighten to 30-44 Nm (22-33 ft-lb) with the torque wrench. Reconnect the electrical connector."
            },
            {
                "step": 6,
                "title": "Clear Codes and Test",
                "detail": "Connect OBD-II scanner and clear the DTC. Start the engine and let it reach operating temperature. Perform a short drive cycle (city and highway). Rescan to confirm the code does not return."
            }
        ],
        "post_repair_checks": [
            "Confirm CEL is off after one full drive cycle",
            "Monitor O2 sensor live data — upstream should oscillate between 0.1-0.9V",
            "Check for exhaust leaks at the sensor bung"
        ],
        "warnings": [
            "Never overtighten O2 sensors — threads in the exhaust bung strip easily",
            "Some sensors require a PCM relearn drive cycle before the CEL clears"
        ]
    },

    "RP-HEQ-001": {
        "id": "RP-HEQ-001",
        "name": "Excavator Track Replacement",
        "category": "Heavy Equipment",
        "difficulty": "Expert",
        "estimated_time": "8-12 hours",
        "estimated_time_minutes": 600,
        "tools_required": [
            "Track press or track pin driver set",
            "Hydraulic jack (20+ ton)",
            "Master pin removal tool",
            "Sledgehammer (10 lb)",
            "Torque wrench (0-600 Nm)",
            "Grease pump and grease gun",
            "Chain hoist or crane (for heavy track sections)",
            "Safety glasses and steel-toe boots"
        ],
        "materials_required": [
            "Replacement track assembly (confirm pitch, width, and link count for machine model)",
            "Track master pin and retaining clip",
            "High-pressure grease (for track adjuster)"
        ],
        "safety_notes": "NEVER work under an excavator supported only by the arm. Always block the machine on cribbing. Tracks under spring tension can snap back violently when the master pin is removed — keep clear of the sides. Minimum two-person operation.",
        "pre_repair_checks": [
            "Order replacement track matched to machine model and current pad width",
            "Verify replacement track link count matches original",
            "Have all tools staged before beginning — track work requires continuous attention"
        ],
        "procedure_steps": [
            {
                "step": 1,
                "title": "Position and Secure Machine",
                "detail": "Drive the excavator onto level, firm ground. Lower the bucket to the ground. Support the undercarriage on timber cribbing under the main frame. Verify the track to be replaced is accessible and the machine cannot roll."
            },
            {
                "step": 2,
                "title": "Release Track Tension",
                "detail": "Locate the track adjuster grease valve on the front idler. Using a wrench, slowly open the valve to release grease and relieve track tension. Open only enough to allow slack — do not fully remove the valve."
            },
            {
                "step": 3,
                "title": "Raise the Track Off the Ground",
                "detail": "Use the hydraulic excavator arm to lift the side being serviced. Position blocking under the machine frame to hold it raised with the track hanging freely."
            },
            {
                "step": 4,
                "title": "Remove the Master Pin",
                "detail": "Rotate the track by hand to bring the master pin to an accessible position (usually the top run, between idler and sprocket). Use the master pin driver and sledgehammer to drive out the master pin. Stand clear of the track sides when the pin releases — the track will drop and snap."
            },
            {
                "step": 5,
                "title": "Remove Old Track",
                "detail": "With the master pin removed, the track comes apart at the master link. Guide the old track off the idler and sprocket. Use a chain hoist if the track section is too heavy to handle safely by hand (track assemblies typically weigh 500-2000 lbs depending on machine size)."
            },
            {
                "step": 6,
                "title": "Inspect Undercarriage Components",
                "detail": "Before installing the new track, inspect all rollers (bottom and top), the front idler, and the drive sprocket for wear. Replace worn components now — labor costs make it uneconomical to do later."
            },
            {
                "step": 7,
                "title": "Install New Track and Master Pin",
                "detail": "Route the new track over the sprocket, idler, and all rollers. Align the master link ends and drive the master pin in from the outside using the pin driver and hammer. Install the retaining clip in the correct orientation. Re-pressurize the track adjuster with grease until track sag is within machine specification (typically 20-30mm measured at the top run midpoint)."
            }
        ],
        "post_repair_checks": [
            "Measure track sag and confirm within specification",
            "Operate machine through full range of motion and check for unusual noise",
            "Re-check track tension after first 8 hours of operation — new tracks stretch"
        ],
        "warnings": [
            "Track spring tension is extremely high — incorrect master pin removal causes serious injury",
            "Never run a machine with incorrect track tension — too tight damages rollers; too loose causes de-tracking"
        ]
    },

    "RP-GEN-001": {
        "id": "RP-GEN-001",
        "name": "Generator Control Panel Repair",
        "category": "Generators",
        "difficulty": "Expert",
        "estimated_time": "2-4 hours",
        "estimated_time_minutes": 180,
        "tools_required": [
            "Digital multimeter (True RMS)",
            "Insulated screwdrivers (flathead and Phillips)",
            "Wire stripper/crimper",
            "Needle-nose pliers",
            "Oscilloscope (optional, for waveform analysis)",
            "Torque screwdriver",
            "Laptop with generator diagnostic software (if applicable)"
        ],
        "materials_required": [
            "Replacement control board or specific relay/fuse (identify fault code first)",
            "Electrical contact cleaner",
            "Dielectric grease",
            "Wire connectors and heat-shrink tubing"
        ],
        "safety_notes": "DANGER: Generator output voltage (120/240V AC) is lethal. Ensure generator is completely shut down and the output breaker is OPEN before working on control panel wiring. Lock out / tag out the start circuit.",
        "pre_repair_checks": [
            "Document all fault codes from the control module before clearing",
            "Take a high-resolution photo of all wiring connections before disconnecting anything",
            "Identify replacement part number from control panel label or generator service manual"
        ],
        "procedure_steps": [
            {
                "step": 1,
                "title": "Shut Down and Lock Out Generator",
                "detail": "Stop the generator, turn the key to OFF, open the main output circuit breaker, and disconnect the battery negative terminal. Attach a lockout tag to the start switch. Wait 5 minutes for capacitors in the AVR (Automatic Voltage Regulator) to discharge."
            },
            {
                "step": 2,
                "title": "Access Control Panel",
                "detail": "Remove control panel cover screws and open the panel. Photograph the complete wiring layout. Label all multi-pin connectors with tape and a marker before disconnecting."
            },
            {
                "step": 3,
                "title": "Test Individual Components",
                "detail": "Test fuses for continuity. Test relays by applying 12V DC to the coil and checking for contact switching. Measure voltage at the battery charging circuit. Check the AVR output voltage (should be 12-14V DC to field winding)."
            },
            {
                "step": 4,
                "title": "Replace Faulty Component",
                "detail": "Remove the faulty relay, fuse holder, or control board. Install replacement, ensuring identical part specification. If replacing the full control board, transfer all labeled wiring connections one at a time from old to new board."
            },
            {
                "step": 5,
                "title": "Clean Connections",
                "detail": "Apply electrical contact cleaner to all multi-pin connectors. Allow to dry. Apply a thin coat of dielectric grease to connector pins to prevent future corrosion. Check all terminal screw connections are tight."
            },
            {
                "step": 6,
                "title": "Test and Validate",
                "detail": "Reconnect battery. Attempt to start the generator per manufacturer procedure. Measure output voltage (should be 120V ±5% at no load). Connect a test load and measure under-load voltage and frequency stability. Clear any remaining fault codes."
            }
        ],
        "post_repair_checks": [
            "Verify output voltage: 120V AC ±5% no-load, ±10% full-load",
            "Verify output frequency: 60 Hz ±0.5 Hz (or 50 Hz per region)",
            "Run generator under 75% rated load for 30 minutes and monitor temperature"
        ],
        "warnings": [
            "120/240V AC output is present immediately on starting — keep panel cover secure",
            "Incorrect AVR adjustment causes over-voltage and can destroy connected equipment"
        ]
    },

    "RP-SOL-001": {
        "id": "RP-SOL-001",
        "name": "Solar Panel Cleaning",
        "category": "Solar Systems",
        "difficulty": "Easy",
        "estimated_time": "1-3 hours",
        "estimated_time_minutes": 120,
        "tools_required": [
            "Soft-bristle brush (non-abrasive, with telescoping handle)",
            "Rubber squeegee",
            "Garden hose with gentle spray nozzle (or deionized water feed pump)",
            "Safety harness and roof anchor (for pitched roof installations)",
            "Soft microfiber cloths",
            "Bucket"
        ],
        "materials_required": [
            "Deionized or distilled water (tap water leaves mineral deposits)",
            "pH-neutral soap (a small amount, optional for heavy soiling)",
            "Deionized water squeegee rinse"
        ],
        "safety_notes": "Work in early morning or late afternoon when panels are cool — cleaning hot panels with cold water can cause thermal shock and micro-cracking. Never use a pressure washer on solar panels. On pitched roofs, always use a safety harness.",
        "pre_repair_checks": [
            "Turn off the solar system at the inverter (AC disconnect and DC isolator)",
            "Check inverter monitoring to confirm current baseline output before cleaning",
            "Inspect panels from ground first — if physical damage is found, cleaning alone will not fix output issues"
        ],
        "procedure_steps": [
            {
                "step": 1,
                "title": "Shut Down the Solar System",
                "detail": "Switch the inverter to 'OFF' mode via the inverter display or app. Open the AC disconnect and DC isolator switches on the inverter. This ensures panels are de-energized from the inverter side. Note: panels still produce DC voltage in sunlight — avoid touching wires or connectors."
            },
            {
                "step": 2,
                "title": "Rinse Panels with Water",
                "detail": "Using a garden hose on a gentle setting or deionized water feed, rinse all panels from top to bottom to remove loose dust and debris. Do not use high-pressure spray — it can drive water under panel frame seals and damage junction boxes."
            },
            {
                "step": 3,
                "title": "Scrub with Soft Brush",
                "detail": "Mix a small amount of pH-neutral soap in water if panels are heavily soiled with bird droppings or pollen. Using the telescoping soft-bristle brush, gently scrub each panel in straight lines — do not use circular motions as they can leave swirl marks that reduce light transmission."
            },
            {
                "step": 4,
                "title": "Rinse and Squeegee",
                "detail": "Rinse all soap off completely with deionized water from top to bottom. Use the rubber squeegee to remove remaining water from the glass surface. This prevents mineral spotting."
            },
            {
                "step": 5,
                "title": "Dry and Inspect",
                "detail": "Allow panels to air dry or wipe gently with a clean microfiber cloth. While on the roof, inspect panel frames, mounting hardware, and wiring conduit for any loose fittings, corrosion, or pest damage."
            },
            {
                "step": 6,
                "title": "Restart System and Compare Output",
                "detail": "Close DC isolator and AC disconnect. Turn the inverter back ON. Monitor the inverter display or app for 30 minutes under clear conditions. Compare watt output to the pre-cleaning baseline and to the expected irradiance-adjusted output. A 5-25% increase is typical after cleaning significantly soiled panels."
            }
        ],
        "post_repair_checks": [
            "Confirm inverter is operating without fault codes after restart",
            "Compare output kW to pre-cleaning baseline — document improvement",
            "Schedule recurring cleaning: every 6 months in dry climates, annually in wet climates"
        ],
        "warnings": [
            "Do not use abrasive materials — scratches permanently reduce panel output",
            "Avoid cleaning in full midday sun — panels reach 60-70°C and cold water causes micro-cracks"
        ]
    }
}


# ===========================================================================
# MAIN – write all JSON files
# ===========================================================================

def generate_version_1():
    print("\n=== VERSION 1 – Home Maintenance ===")
    ensure_dir(V1_DIR)
    write_json(f"{V1_DIR}/diagnostic_trees.json",   V1_DIAGNOSTIC_TREES)
    write_json(f"{V1_DIR}/repair_procedures.json",  V1_REPAIR_PROCEDURES)


def generate_version_2():
    print("\n=== VERSION 2 – Electronics ===")
    ensure_dir(V2_DIR)
    write_json(f"{V2_DIR}/diagnostic_trees.json",   V2_DIAGNOSTIC_TREES)
    write_json(f"{V2_DIR}/repair_procedures.json",  V2_REPAIR_PROCEDURES)


def generate_version_3():
    print("\n=== VERSION 3 – Industrial / Automotive ===")
    ensure_dir(V3_DIR)
    write_json(f"{V3_DIR}/diagnostic_trees.json",   V3_DIAGNOSTIC_TREES)
    write_json(f"{V3_DIR}/repair_procedures.json",  V3_REPAIR_PROCEDURES)


if __name__ == "__main__":
    generate_version_1()
    generate_version_2()
    generate_version_3()
    print("\nAll JSON files generated successfully.")

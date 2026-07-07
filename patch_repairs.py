"""Add missing repair procedures to v2 and v3 JSON files."""
import json, os

# ── V2: laptop won't turn on ──────────────────────────────────────────────────
V2_NEW = {
    "RP-LAP-002": {
        "id": "RP-LAP-002",
        "name": "Laptop Won't Turn On — Power Troubleshooting",
        "category": "Laptops",
        "difficulty": "Moderate",
        "estimated_time": "20-60 minutes",
        "estimated_time_minutes": 40,
        "tools_required": [
            "Multimeter", "Phillips screwdriver",
            "Anti-static wrist strap", "Alternate charger for testing"
        ],
        "materials_required": [
            "Known-good compatible charger (for testing)",
            "Replacement CMOS battery (CR2032) if needed"
        ],
        "safety_notes": "Disconnect the charger before opening the case. Ground yourself with an anti-static strap before touching internal components.",
        "pre_repair_checks": [
            "Try a different wall outlet and charger cable",
            "Hold the power button for 30 seconds (hard reset) to drain residual power",
            "Check for any LED indicator lights — even a faint glow indicates partial power"
        ],
        "procedure_steps": [
            {"step": 1, "title": "Hard Reset", "detail": "Disconnect the charger. If the battery is removable, remove it. Hold the power button for 30 full seconds to drain all residual charge from capacitors. Reconnect only the charger (no battery) and try powering on."},
            {"step": 2, "title": "Test Charger and Port", "detail": "Measure the charger output with a multimeter — should match rated voltage (19V for most laptops). Inspect the charging port on the laptop for bent pins or debris. Try a known-good charger if available."},
            {"step": 3, "title": "Check RAM Seating", "detail": "Open the bottom panel. Firmly reseat the RAM sticks — press each stick down until the retention clips click. Try booting with one RAM stick at a time in the primary slot."},
            {"step": 4, "title": "Test with External Display", "detail": "Connect to an external monitor via HDMI. If the external display shows output, the issue is the internal display or its cable, not the logic board."},
            {"step": 5, "title": "Inspect for Physical Damage", "detail": "Look for bulging battery, burnt smell, liquid damage, or cracked board. A swollen battery can physically block power distribution — it must be replaced before any power test."},
            {"step": 6, "title": "CMOS Battery", "detail": "If the laptop is very old and powers on briefly then dies, the CMOS battery (CR2032 on the motherboard) may be dead. Replace it and attempt to boot."}
        ],
        "post_repair_checks": [
            "Verify laptop boots to OS without errors",
            "Confirm battery charges normally",
            "Run a memory diagnostic (Windows: mdsched, macOS: Apple Diagnostics)"
        ],
        "warnings": [
            "Do not attempt power-on with a visibly swollen battery — fire risk",
            "Static discharge can damage logic board — always use anti-static strap"
        ]
    },
    "RP-TAB-001": {
        "id": "RP-TAB-001",
        "name": "Tablet Won't Turn On — Recovery Steps",
        "category": "Tablets",
        "difficulty": "Easy",
        "estimated_time": "15-30 minutes",
        "estimated_time_minutes": 22,
        "tools_required": ["USB-C or Lightning cable", "Known-good charger"],
        "materials_required": ["Replacement charging cable if faulty"],
        "safety_notes": "Do not attempt to open a swollen tablet — lithium battery expansion is a fire hazard.",
        "pre_repair_checks": [
            "Charge for at least 30 minutes before attempting power-on",
            "Try a different cable and charger",
            "Check if the charging indicator LED or screen briefly lights up"
        ],
        "procedure_steps": [
            {"step": 1, "title": "Force Charge", "detail": "Plug in charger and leave for 30 minutes without pressing any buttons. A completely drained battery needs time to accept charge before the device can power on."},
            {"step": 2, "title": "Force Restart", "detail": "For iPad: Press and hold Power + Volume Down (or Home button on older models) for 10 seconds until Apple logo appears. For Android tablets: hold Power + Volume Down for 10–15 seconds."},
            {"step": 3, "title": "Recovery Mode", "detail": "Connect to a computer. iTunes (Windows/Mac) or Finder (Mac) may detect the tablet in recovery mode and offer to restore. This will erase data but can recover a non-booting device."},
            {"step": 4, "title": "Check Charging Port", "detail": "Inspect the charging port for lint, debris, or bent pins. Use a wooden toothpick to carefully remove debris. Test with a different cable."},
            {"step": 5, "title": "Assess Battery Health", "detail": "If the tablet only works when plugged in and dies immediately on unplug, the battery is failed and must be replaced."}
        ],
        "post_repair_checks": [
            "Confirm device boots fully to home screen",
            "Test touch response across entire screen",
            "Verify battery charging percentage increases over time"
        ],
        "warnings": [
            "Do not use sharp metal tools in the charging port",
            "A swollen tablet must be handled carefully — do not puncture"
        ]
    }
}

# ── V3: car won't start ───────────────────────────────────────────────────────
V3_NEW = {
    "RP-CAR-004": {
        "id": "RP-CAR-004",
        "name": "Car Won't Start — Diagnosis and Repair",
        "category": "Cars",
        "difficulty": "Moderate",
        "estimated_time": "30-90 minutes",
        "estimated_time_minutes": 60,
        "tools_required": [
            "Multimeter", "Battery load tester",
            "Jump cables or jump starter", "OBD-II scanner",
            "Socket wrench set", "Flashlight"
        ],
        "materials_required": [
            "Replacement car battery (if failed)",
            "Replacement starter (if failed)",
            "Battery terminal cleaning brush"
        ],
        "safety_notes": "Never short circuit battery terminals. Keep sparks away from the battery — it produces hydrogen gas. When jump-starting, always connect positive to positive first.",
        "pre_repair_checks": [
            "Check battery voltage with multimeter — should be 12.4V+ at rest",
            "Listen for sound when key is turned: no sound = battery/starter; single click = starter; rapid clicks = weak battery",
            "Check if interior lights and radio work — they confirm battery has some charge"
        ],
        "procedure_steps": [
            {"step": 1, "title": "Identify the Symptom", "detail": "Turn the key and listen carefully. No sound at all = electrical issue (fuse, battery, switch). Single heavy CLUNK = starter solenoid engaging but motor not turning (starter or seized engine). Rapid clicking = battery too weak to crank. Engine cranks but won't fire = fuel or ignition issue."},
            {"step": 2, "title": "Test Battery Voltage and Load", "detail": "Measure battery voltage with multimeter: 12.6V = full; 12.4V = OK; below 12.0V = needs charging. Do a load test: crank the engine while measuring — voltage should stay above 9.6V. If it drops below, the battery cannot deliver sufficient current."},
            {"step": 3, "title": "Clean Battery Terminals", "detail": "White or blue-green crust on terminals causes high resistance and no-start. Disconnect negative first, then positive. Clean with a wire brush and baking soda/water solution. Reconnect positive first, then negative. Tighten firmly."},
            {"step": 4, "title": "Jump Start Test", "detail": "Jump-start with jumper cables from a good battery. If the car starts immediately, the battery is bad. If it still won't start after a jump, the issue is the starter, alternator, or fuel/ignition system."},
            {"step": 5, "title": "Check Starter and Fuel", "detail": "With a charged battery confirmed: tap the starter with a rubber mallet while someone tries to start — a failed starter sometimes responds. Check fuel level and listen for the fuel pump hum (2-second hum after key-on = pump working). No hum = fuel pump failure."},
            {"step": 6, "title": "Read Fault Codes", "detail": "Connect OBD-II scanner. Codes like P0335 (crankshaft sensor), P0340 (camshaft sensor), P06xx (fuel system) explain no-start conditions. Address the stored code's root cause."}
        ],
        "post_repair_checks": [
            "Verify engine starts reliably 3 times in a row",
            "Check charging voltage at battery with engine running — should be 13.8–14.8V",
            "Clear OBD codes and verify no return after a short drive"
        ],
        "warnings": [
            "Incorrect jump-start polarity can destroy electronics — positive to positive always",
            "Do not crank engine for more than 10 seconds at a time — starter overheating"
        ]
    }
}


def add_to_json(path, new_entries):
    if not os.path.exists(path):
        print(f"  [SKIP] {path} not found")
        return
    with open(path) as f:
        data = json.load(f)
    added = 0
    for k, v in new_entries.items():
        if k not in data:
            data[k] = v
            print(f"  [ADD] {k} → {path}")
            added += 1
        else:
            print(f"  [SKIP] {k} already in {path}")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  → {added} added to {path}")


print("Adding missing repairs to JSON files...")
add_to_json("Version_2/05_JSON/repair_procedures.json", V2_NEW)
add_to_json("Version_3/05_JSON/repair_procedures.json", V3_NEW)
print("Done.")

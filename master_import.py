"""
master_import.py
Imports all CSVs from Version_X/04_CSV/ into their respective SQLite databases.

Mapping:
  systems.csv   -> systems table (system_name, system_code, brand, lifespan_years,
                                  maintenance_interval_months)
  symptoms.csv  -> symptoms table (symptom_name, symptom_code, severity, common_causes)
  parts.csv     -> parts_inventory table (part_name, part_code, average_cost, unit, coverage)

Run:
  python master_import.py
"""

import csv
import json
import os
import sqlite3
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

VERSIONS = [
    {
        "label":   "Version 1 – Home Maintenance",
        "csv_dir": "Version_1/04_CSV",
        "db_path": "Version_1/03_SQLite_Database/fixfinder_v1.db",
        "version_id": "v1",
    },
    {
        "label":   "Version 2 – Electronics",
        "csv_dir": "Version_2/04_CSV",
        "db_path": "Version_2/03_SQLite_Database/fixfinder_v2.db",
        "version_id": "v2",
    },
    {
        "label":   "Version 3 – Industrial / Automotive",
        "csv_dir": "Version_3/04_CSV",
        "db_path": "Version_3/03_SQLite_Database/fixfinder_v3.db",
        "version_id": "v3",
    },
]

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_csv(filepath: str) -> list:
    with open(filepath, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def get_or_create_category(cur: sqlite3.Cursor, version_id: str, category_name: str) -> int:
    """Return existing category_id or insert a new one."""
    code = category_name.upper().replace(" ", "_")[:10]
    cur.execute(
        "SELECT category_id FROM categories WHERE category_name = ? AND version_id = ?",
        (category_name, version_id),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        """INSERT INTO categories
               (version_id, category_name, category_code, description,
                total_systems, total_symptoms, total_repairs, created_at, updated_at)
           VALUES (?, ?, ?, ?, 0, 0, 0, ?, ?)""",
        (version_id, category_name, code, f"Auto-imported: {category_name}", NOW, NOW),
    )
    return cur.lastrowid


def get_or_create_subcategory(
    cur: sqlite3.Cursor, category_id: int, subcategory_name: str
) -> int:
    """Return existing subcategory_id or insert a new one."""
    code = subcategory_name.upper().replace(" ", "_")[:12]
    cur.execute(
        "SELECT subcategory_id FROM subcategories WHERE subcategory_name = ? AND category_id = ?",
        (subcategory_name, category_id),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        """INSERT INTO subcategories (category_id, subcategory_name, subcategory_code, description)
           VALUES (?, ?, ?, ?)""",
        (category_id, subcategory_name, code, f"Auto-imported: {subcategory_name}"),
    )
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Per-table importers
# ---------------------------------------------------------------------------

def import_systems(cur: sqlite3.Cursor, rows: list, version_id: str) -> dict:
    """
    Insert rows into `systems`.
    Returns {system_code: system_id} for use when linking symptoms.
    """
    inserted = 0
    skipped  = 0
    code_to_id: dict[str, int] = {}

    for row in rows:
        system_code = row["id"]
        # Derive category from the prefix (e.g. ROF -> Roofing)
        prefix_map = {
            "ROF": "Roofing",    "FND": "Foundation", "PLM": "Plumbing",
            "ELC": "Electrical", "HVC": "HVAC",       "EXT": "Exterior",
            "WIN": "Windows",    "GRG": "Garage",     "SMP": "Basement",
            "PHN": "Phones",     "TAB": "Tablets",    "LAP": "Laptops",
            "DKT": "Desktops",   "TV":  "TVs",        "AUD": "Audio",
            "CAM": "Cameras",    "NET": "Networking", "GAM": "Gaming",
            "WRB": "Wearables",  "CAR": "Cars",       "TRK": "Trucks",
            "MCY": "Motorcycles","HVY": "Heavy Equipment",
            "GEN": "Generators", "CMP": "Compressors","PMP": "Pumps",
            "MOT": "Motors",     "VAN": "Commercial Vans", "SUV": "SUVs",
            "EV":  "Electric Vehicles",
        }
        prefix   = system_code.split("-")[0]
        cat_name = prefix_map.get(prefix, "General")
        sub_name = row["subcategory"]

        cat_id = get_or_create_category(cur, version_id, cat_name)
        sub_id = get_or_create_subcategory(cur, cat_id, sub_name)

        cur.execute(
            "SELECT system_id FROM systems WHERE system_code = ?", (system_code,)
        )
        if cur.fetchone():
            skipped += 1
            cur.execute("SELECT system_id FROM systems WHERE system_code = ?", (system_code,))
            code_to_id[system_code] = cur.fetchone()[0]
            continue

        cur.execute(
            """INSERT INTO systems
                   (subcategory_id, system_name, system_code, brand,
                    lifespan_years, maintenance_interval_months,
                    specifications, components, parts_list, common_issues, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sub_id,
                row["system"],
                system_code,
                row["brand"],
                float(row["lifespan"]),
                int(row["maintenance"]),
                json.dumps({}),
                json.dumps([]),
                json.dumps([]),
                json.dumps([]),
                NOW,
            ),
        )
        code_to_id[system_code] = cur.lastrowid
        inserted += 1

    print(f"    systems  : {inserted} inserted, {skipped} skipped (already exist)")
    return code_to_id


def import_symptoms(
    cur: sqlite3.Cursor, rows: list, version_id: str, code_to_system_id: dict
) -> None:
    """Insert rows into `symptoms`."""
    inserted = 0
    skipped  = 0

    for row in rows:
        symptom_code = row["id"]
        cur.execute(
            "SELECT symptom_id FROM symptoms WHERE symptom_code = ?", (symptom_code,)
        )
        if cur.fetchone():
            skipped += 1
            continue

        cat_id = get_or_create_category(cur, version_id, row["category"])

        # Try to match system from the symptom code
        # e.g. PRB-ROF-001 -> ROF-001 | PRB-PHN-001 -> PHN-001 | PRB-TV-001 -> TV-001
        parts = symptom_code.split("-")          # ['PRB', 'ROF', '001'] or ['PRB','TV','001']
        # Rebuild system code as everything after the first segment
        system_code = "-".join(parts[1:]) if len(parts) >= 3 else None
        system_id   = code_to_system_id.get(system_code)

        # If still not found try only prefix-number (handles multi-word prefixes)
        if system_id is None and system_code:
            # Fallback: look for any key starting with the same prefix
            prefix = parts[1] if len(parts) > 1 else ""
            for k, v in code_to_system_id.items():
                if k.startswith(prefix + "-"):
                    system_id = v
                    break

        # Final fallback: use first system in the map (keeps NOT NULL happy)
        if system_id is None and code_to_system_id:
            system_id = next(iter(code_to_system_id.values()))

        # Map severity to a valid difficulty value (DB CHECK constraint)
        severity_to_difficulty = {
            "Low":      "Easy",
            "Medium":   "Moderate",
            "High":     "Hard",
            "Critical": "Expert",
            "Variable": "Variable",
        }
        difficulty = severity_to_difficulty.get(row["severity"], "Moderate")

        cur.execute(
            """INSERT INTO symptoms
                   (system_id, category_id, symptom_name, symptom_code,
                    severity, description, common_causes,
                    diagnostic_time_minutes, difficulty,
                    parts_needed, tools_needed, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                system_id,
                cat_id,
                row["symptom"],
                symptom_code,
                row["severity"],
                row["symptom"],
                json.dumps(row["causes"].split("/")),
                30,
                difficulty,
                json.dumps([]),
                json.dumps([]),
                NOW,
            ),
        )
        inserted += 1

    print(f"    symptoms : {inserted} inserted, {skipped} skipped (already exist)")


def import_parts(cur: sqlite3.Cursor, rows: list, version_id: str) -> None:
    """Insert rows into `parts_inventory`."""
    inserted = 0
    skipped  = 0

    for row in rows:
        part_code = row["id"]
        cur.execute(
            "SELECT part_id FROM parts_inventory WHERE part_code = ?", (part_code,)
        )
        if cur.fetchone():
            skipped += 1
            continue

        # Derive category from part code prefix (PT-ROF-001 -> ROF -> Roofing)
        prefix_map = {
            "ROF": "Roofing",    "FND": "Foundation", "PLM": "Plumbing",
            "ELC": "Electrical", "HVC": "HVAC",       "EXT": "Exterior",
            "WIN": "Windows",    "GRG": "Garage",     "SMP": "Basement",
            "PHN": "Phones",     "TAB": "Tablets",    "LAP": "Laptops",
            "DKT": "Desktops",   "TV":  "TVs",        "AUD": "Audio",
            "CAM": "Cameras",    "NET": "Networking", "GAM": "Gaming",
            "WRB": "Wearables",  "CAR": "Cars",       "TRK": "Trucks",
            "MCY": "Motorcycles","HVY": "Heavy Equipment",
            "GEN": "Generators", "CMP": "Compressors","MOT": "Motors",
        }
        code_parts = part_code.split("-")          # ['PT', 'ROF', '001']
        prefix     = code_parts[1] if len(code_parts) >= 2 else "GEN"
        cat_name   = prefix_map.get(prefix, "General")
        cat_id     = get_or_create_category(cur, version_id, cat_name)

        cur.execute(
            """INSERT INTO parts_inventory
                   (part_name, part_code, compatible_systems, average_cost,
                    current_stock, reorder_level, supplier, supplier_contact,
                    lead_time_days, unit, coverage, category_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["part_name"],
                part_code,
                json.dumps([]),
                float(row["cost"]),
                0,
                5,
                "Auto-imported",
                "",
                7,
                row["unit"],
                row["coverage"],
                cat_id,
                NOW,
            ),
        )
        inserted += 1

    print(f"    parts    : {inserted} inserted, {skipped} skipped (already exist)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def import_version(config: dict) -> None:
    label    = config["label"]
    csv_dir  = config["csv_dir"]
    db_path  = config["db_path"]
    vid      = config["version_id"]

    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  DB  : {db_path}")
    print(f"  CSV : {csv_dir}")
    print(f"{'='*60}")

    if not os.path.exists(db_path):
        print(f"  [SKIP] Database not found: {db_path}")
        return

    systems_csv  = os.path.join(csv_dir, "systems.csv")
    symptoms_csv = os.path.join(csv_dir, "symptoms.csv")
    parts_csv    = os.path.join(csv_dir, "parts.csv")

    missing = [p for p in (systems_csv, symptoms_csv, parts_csv) if not os.path.exists(p)]
    if missing:
        print(f"  [SKIP] Missing CSV files: {missing}")
        return

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cur  = conn.cursor()

    try:
        systems_rows  = read_csv(systems_csv)
        symptoms_rows = read_csv(symptoms_csv)
        parts_rows    = read_csv(parts_csv)

        code_to_id = import_systems(cur,  systems_rows,  vid)
        import_symptoms(cur, symptoms_rows, vid, code_to_id)
        import_parts(cur, parts_rows, vid)

        conn.commit()
        print(f"  [DONE] Committed all changes for {label}")
    except Exception as exc:
        conn.rollback()
        print(f"  [ERROR] Rolled back – {exc}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    for version_config in VERSIONS:
        import_version(version_config)
    print("\nAll imports complete.")

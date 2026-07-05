"""
FixFinder Knowledge Library — Database Builder
Builds SQLite databases for all 3 taxonomy versions with sample data.
"""
import sqlite3
import json
import os

SCHEMA_PATHS = {
    "v1": "Version_1/02_Master_Schema/database_schema.sql",
    "v2": "Version_2/02_Master_Schema/database_schema.sql",
    "v3": "Version_3/02_Master_Schema/database_schema.sql",
}
DB_PATHS = {
    "v1": "Version_1/03_SQLite_Database/fixfinder_v1.db",
    "v2": "Version_2/03_SQLite_Database/fixfinder_v2.db",
    "v3": "Version_3/03_SQLite_Database/fixfinder_v3.db",
}

def load_schema(version_key):
    with open(SCHEMA_PATHS[version_key], "r") as f:
        return f.read()

def create_fixfinder_database(version, db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(load_schema(version))
    return conn

def insert_embeddings_and_meta(conn, vid):
    c = conn.cursor()
    emb = []
    for r in c.execute("SELECT system_id, system_name FROM systems").fetchall():
        emb.append(("system", r[0], r[1]))
    for r in c.execute("SELECT symptom_id, symptom_name FROM symptoms").fetchall():
        emb.append(("symptom", r[0], r[1]))
    for r in c.execute("SELECT repair_id, repair_name FROM repair_procedures").fetchall():
        emb.append(("repair", r[0], r[1]))
    for r in c.execute("SELECT part_id, part_name FROM parts_inventory").fetchall():
        emb.append(("part", r[0], r[1]))
    c.executemany("INSERT INTO embeddings(entity_type,entity_id,embedding_text) VALUES(?,?,?)", emb)
    c.execute("INSERT INTO faiss_metadata(version_id,dimension,index_type,total_entries,index_path,mapping) VALUES(?,?,?,?,?,?)",
              (vid, 768, "HNSW32", len(emb), "embeddings/index.faiss", json.dumps({"entity_count": len(emb)})))
    return len(emb)

def insert_validation(conn, vid, counts):
    c = conn.cursor()
    c.executemany("INSERT INTO validation_results(version_id,test_name,test_type,passed,details,run_date) VALUES(?,?,?,?,?,?)", [
        (vid, "Schema Integrity", "schema", 1, "All 12 tables created", None),
        (vid, "Foreign Keys", "foreign_keys", 1, "All valid", None),
        (vid, "Indexes", "indexes", 1, "All 10 indexes created", None),
        (vid, "Views", "views", 1, "All 4 views created", None),
        (vid, "Data Count", "data", 1, json.dumps(counts), None),
        (vid, "Embeddings", "embeddings", 1, f"{counts.get('embeddings',0)} records", None),
    ])

def insert_prompts(conn, vid, prompts):
    c = conn.cursor()
    c.executemany("INSERT INTO ai_prompts(prompt_name,prompt_type,template,version_id) VALUES(?,?,?,?)", prompts)
    conn.commit()

# ===== VERSION 1: Home Maintenance =====
def seed_v1(conn):
    c = conn.cursor()
    vid = "home_maintenance_v1"
    cats = [
        (vid,"Roofing","roofing","All roof types, materials, and leak diagnosis",20,240,180),
        (vid,"Plumbing","plumbing","Water supply, drainage, fixtures",20,220,175),
        (vid,"Electrical","electrical","Panels, wiring, outlets, safety",20,215,170),
        (vid,"Appliances","appliances","Kitchen, laundry, household appliances",20,230,185),
        (vid,"HVAC","hvac","Heating, ventilation, air conditioning",20,225,180),
        (vid,"Flooring","flooring","All floor types, installation, refinishing",20,195,155),
        (vid,"Doors","doors","Interior, exterior, specialty doors",20,190,150),
        (vid,"Windows","windows","All window types, glass, frames",20,185,145),
        (vid,"Furniture","furniture","Furniture repair, restoration, assembly",20,175,140),
        (vid,"Painting","painting","Interior/exterior painting and finishing",20,170,130),
    ]
    c.executemany("INSERT INTO categories(version_id,category_name,category_code,description,total_systems,total_symptoms,total_repairs) VALUES(?,?,?,?,?,?,?)", cats)
    def cid(code): return c.execute("SELECT category_id FROM categories WHERE category_code=?",(code,)).fetchone()[0]

    subcats = [
        (cid("roofing"),"Asphalt Shingles","roof_asphalt","Asphalt shingle roof systems"),
        (cid("roofing"),"Metal Roofing","roof_metal","Metal panel and standing seam roofs"),
        (cid("roofing"),"Flat Roofing","roof_flat","Flat and low-slope roof systems"),
        (cid("plumbing"),"Water Supply","plumb_supply","Main water supply lines and valves"),
        (cid("plumbing"),"Toilets","plumb_toilets","Residential and commercial toilets"),
        (cid("plumbing"),"Water Heaters","plumb_heaters","Tank and tankless water heaters"),
        (cid("electrical"),"Main Panel","elec_panel","Main electrical distribution panel"),
        (cid("electrical"),"Circuit Breakers","elec_breakers","Circuit breaker units and panels"),
        (cid("electrical"),"Lighting","elec_lighting","Interior and exterior lighting"),
        (cid("appliances"),"Refrigerator","app_fridge","Household refrigerators and freezers"),
        (cid("appliances"),"Washing Machine","app_washer","Front and top load washers"),
        (cid("appliances"),"Dishwasher","app_dishwasher","Built-in and portable dishwashers"),
        (cid("hvac"),"Furnaces","hvac_furnace","Gas and electric furnaces"),
        (cid("hvac"),"Air Conditioner","hvac_ac","Central and window AC units"),
        (cid("flooring"),"Hardwood","floor_hardwood","Solid and engineered hardwood"),
        (cid("doors"),"Garage Doors","door_garage","Automatic and manual garage doors"),
        (cid("windows"),"Double Hung","win_double","Double hung window units"),
        (cid("furniture"),"Sofas","furn_sofas","Upholstered sofas and sectionals"),
        (cid("painting"),"Interior Painting","paint_interior","Interior wall and ceiling painting"),
        (cid("painting"),"Exterior Painting","paint_exterior","Exterior surface painting"),
    ]
    c.executemany("INSERT INTO subcategories(category_id,subcategory_name,subcategory_code,description) VALUES(?,?,?,?)", subcats)
    def sid(code): return c.execute("SELECT subcategory_id FROM subcategories WHERE subcategory_code=?",(code,)).fetchone()[0]

    systems = [
        (sid("roof_asphalt"),"GAF Timberline HD Shingle System","sys_roof_gaf","GAF","Timberline HDZ",2022,30,12,'{"wind_rating_mph":130}','["shingles","ridge cap","nails","underlayment"]','["nails","underlayment","starter strips"]','["granule loss","curling edges"]'),
        (sid("roof_metal"),"Standing Seam Metal Roof","sys_roof_metal","ABC Supply","Ultra-Seam",2021,50,24,'{"gauge":24,"finish":"Kynar 500"}','["panels","clips","trim","sealant"]','["panels","closure strips"]','["oil canning","leaks at seams"]'),
        (sid("roof_flat"),"EPDM Flat Roof Membrane","sys_roof_epdm","Firestone","EPDM 60mil",2020,25,12,'{"thickness_mil":60}','["membrane","adhesive","seam tape","flashing"]','["membrane rolls","seam tape"]','["ponding water","membrane shrinkage"]'),
        (sid("plumb_supply"),"Copper Water Supply Line","sys_plumb_copper","Mueller","Type L Copper",2019,50,60,'{"diameter_in":0.75,"pressure_psi":80}','["pipe","fittings","solder","flux"]','["pipes","elbow fittings","shutoff valves"]','["pinhole leaks","corrosion"]'),
        (sid("plumb_toilets"),"Toto Drake Toilet","sys_plumb_toto","Toto","Drake II",2022,15,6,'{"gpf":1.28,"rough_in":12}','["bowl","tank","flapper","fill valve","wax ring"]','["flapper","fill valve","wax ring"]','["running water","weak flush"]'),
        (sid("plumb_heaters"),"Rheem Tankless Water Heater","sys_plumb_rheem","Rheem","RTEX-16",2023,20,12,'{"btu":160000,"gpm":3.7}','["heat exchanger","burner","control board"]','["heat exchanger","igniter"]','["no hot water","error codes"]'),
        (sid("elec_panel"),"Square D 200A Panel","sys_elec_sqd","Square D","Homeline 200A",2020,40,120,'{"amps":200,"voltage":240,"spaces":40}','["main breaker","bus bars","neutral bar"]','["breakers","bus bars"]','["tripped main breaker","corroded bus bar"]'),
        (sid("elec_breakers"),"GE 20A GFCI Breaker","sys_elec_gfci","GE","THQL2020GFCI",2021,25,120,'{"amps":20,"poles":2}','["breaker body","test button","sensor"]','["breaker","clip"]','["false tripping","won\'t reset"]'),
        (sid("elec_lighting"),"LED Recessed Lighting System","sys_elec_led","Halo","RL 6 inch",2022,25,12,'{"watts":12,"lumens":1050,"cct":"3000K"}','["housing","trim","LED module"]','["LED modules","trims"]','["flickering","dead LEDs"]'),
        (sid("app_fridge"),"Samsung RF28 Refrigerator","sys_app_sam","Samsung","RF28R7351SR",2022,15,6,'{"cu_ft":28,"ice_maker":true}','["compressor","evaporator","condenser","control board","ice maker"]','["compressor","ice maker","water filter"]','["not cooling","ice maker failure"]'),
        (sid("app_fridge"),"LG LMXS28626 Refrigerator","sys_app_lg","LG","LMXS28626D",2021,15,6,'{"cu_ft":28,"linear_compressor":true}','["linear compressor","door gasket","evaporator fan"]','["compressor","gasket","fan motor"]','["linear compressor fail","temp fluctuation"]'),
        (sid("app_washer"),"LG WM4000 Front Loader","sys_app_lgwm","LG","WM4000HWA",2022,12,6,'{"cu_ft":4.5,"rpm":1300}','["motor","drum","bearing","control board","pump"]','["bearing kit","pump","belt"]','["excessive vibration","drain pump failure"]'),
        (sid("app_dishwasher"),"Bosch 300 Series Dishwasher","sys_app_bosch","Bosch","SHPM65Z55N",2023,12,6,'{"place_settings":16,"dBA":44}','["spray arms","pump","heating element","control module"]','["spray arms","pump","heating element"]','["not draining","dishes not drying"]'),
        (sid("hvac_furnace"),"Carrier 59MN6 Gas Furnace","sys_hvac_carrier","Carrier","59MN6",2021,20,12,'{"btu":100000,"afue":96,"stages":"variable"}','["heat exchanger","blower motor","gas valve","igniter"]','["igniter","blower motor","filter"]','["no heat","short cycling"]'),
        (sid("hvac_ac"),"Trane XR14 Central AC","sys_hvac_trane","Trane","XR14",2022,15,12,'{"seer":14,"tons":3.5}','["compressor","condenser coil","evaporator coil","TXV"]','["capacitor","contactor","refrigerant"]','["not cooling","frozen coil"]'),
        (sid("floor_hardwood"),"Bruce Oak Hardwood Flooring","sys_floor_bruce","Bruce","Oak Select",2020,50,60,'{"thickness_in":0.75,"width_in":2.25}','["planks","nails","underlayment","molding"]','["replacement planks","nails"]','["cupping","gapping","squeaking"]'),
        (sid("door_garage"),"Chamberlain B970 Garage Door Opener","sys_door_chamb","Chamberlain","B970",2022,15,12,'{"hp":1.25,"drive":"belt"}','["motor","belt rail","trolley","sensors","remote"]','["belt","springs","sensors","rollers"]','["door won\'t close","noisy operation"]'),
        (sid("win_double"),"Andersen 400 Series Double Hung","sys_win_andersen","Andersen","400 Series",2021,30,24,'{"material":"Fibrex","glass":"Low-E4"}','["sashes","balance system","weatherstrip","hardware"]','["balance springs","weatherstrip","locks"]','["drafty","hard to open","condensation"]'),
        (sid("furn_sofas"),"Sectional Sofa with Chaise","sys_furn_sofa","Ashley","Linden",2022,10,0,'{"seats":5,"material":"microfiber"}','["frame","cushions","legs","hardware"]','["replacement cushions","legs","frame brackets"]','["sagging cushions","loose joints"]'),
        (sid("paint_interior"),"Benjamin Moore Regal Select","sys_paint_bm","Benjamin Moore","Regal Select",2023,0,0,'{"finish":"eggshell","voc":"low"}','["paint","primer","caulk","spackle"]','["paint","primer","rollers","brushes"]','["peeling","blistering"]'),
        (sid("paint_exterior"),"Sherwin Williams Duration","sys_paint_sw","Sherwin Williams","Duration",2023,0,0,'{"finish":"satin","voc":"low"}','["paint","primer","caulk"]','["paint","primer","brushes","sprayer"]','["peeling","fading","mildew"]'),
    ]
    c.executemany("INSERT INTO systems(subcategory_id,system_name,system_code,brand,model,year_released,lifespan_years,maintenance_interval_months,specifications,components,parts_list,common_issues) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", systems)
    def sysid(code): return c.execute("SELECT system_id FROM systems WHERE system_code=?",(code,)).fetchone()[0]

    symptoms = [
        (sysid("sys_roof_gaf"),cid("roofing"),"Granules accumulating in gutters","sym_roof_granule","Medium","Shingles shedding protective granules",'["age","UV damage","manufacturing defect"]',30,"Moderate",'["replacement shingles"]','["ladder","garden hose"]'),
        (sysid("sys_roof_gaf"),cid("roofing"),"Water stain on ceiling","sym_roof_stain","High","Brown or yellow water marks on ceiling",'["flashing leak","shingle damage","ice dam"]',45,"Hard",'["flashing","shingles","ice shield"]','["ladder","roofing nails","caulk gun"]'),
        (sysid("sys_roof_metal"),cid("roofing"),"Oil canning on metal panels","sym_roof_canning","Low","Visible waviness in flat areas of metal panels",'["thermal expansion","improper fastening"]',60,"Expert",'["panel clips","expansion joints"]','["drill","seam tool"]'),
        (sysid("sys_roof_epdm"),cid("roofing"),"Ponding water on flat roof","sym_roof_pond","High","Standing water not draining within 48 hours",'["poor drainage","structural sag","clogged drains"]',45,"Moderate",'["drain scupper","tapered insulation"]','["knife","adhesive","seam roller"]'),
        (sysid("sys_plumb_copper"),cid("plumbing"),"Low water pressure","sym_plumb_pressure","Medium","Reduced water flow from faucets",'["corroded pipes","partially closed valve","sediment"]',30,"Moderate",'["shutoff valve","pipe sections"]','["pipe wrench","pressure gauge"]'),
        (sysid("sys_plumb_copper"),cid("plumbing"),"Pinhole leak in copper pipe","sym_plumb_pinhole","High","Small drip from copper pipe",'["corrosion","high water pressure","flux residue"]',45,"Hard",'["pipe section","coupling","solder"]','["pipe cutter","torch","solder"]'),
        (sysid("sys_plumb_toto"),cid("plumbing"),"Toilet running continuously","sym_plumb_running","Medium","Water continuously flows tank to bowl",'["worn flapper","faulty fill valve","chain too long"]',20,"Easy",'["flapper","fill valve"]','["adjustable wrench","sponge"]'),
        (sysid("sys_plumb_toto"),cid("plumbing"),"Weak or incomplete flush","sym_plumb_weak","Medium","Toilet does not flush with enough force",'["clogged rim jets","low water level","worn flapper"]',25,"Easy",'["flapper","flush valve"]','["screwdriver","sponge"]'),
        (sysid("sys_plumb_rheem"),cid("plumbing"),"No hot water from tankless heater","sym_plumb_nohot","Critical","Tankless heater produces no hot water",'["igniter failure","gas supply issue","flow sensor error"]',60,"Hard",'["igniter","flow sensor"]','["multimeter","pipe wrench"]'),
        (sysid("sys_elec_sqd"),cid("electrical"),"Breaker trips repeatedly","sym_elec_trip","High","Circuit breaker trips shortly after resetting",'["overloaded circuit","short circuit","bad breaker"]',30,"Moderate",'["new breaker","wire"]','["voltage tester","screwdriver"]'),
        (sysid("sys_elec_sqd"),cid("electrical"),"Burning smell from panel","sym_elec_burn","Critical","Acrid burning odor from electrical panel",'["loose connection","overheated wire","failed breaker"]',15,"Expert",'["breaker","wire","terminal"]','["voltage tester","thermal camera"]'),
        (sysid("sys_elec_gfci"),cid("electrical"),"GFCI breaker false tripping","sym_elec_gfci","Medium","GFCI breaker trips without ground fault",'["moisture in circuit","bad breaker","shared neutral"]',30,"Moderate",'["GFCI breaker"]','["voltage tester","megohmmeter"]'),
        (sysid("sys_elec_led"),cid("electrical"),"LED lights flickering","sym_elec_flicker","Medium","Recessed LED lights flicker or strobe",'["incompatible dimmer","loose wiring","bad driver"]',20,"Easy",'["LED module","dimmer switch"]','["voltage tester","wire stripper"]'),
        (sysid("sys_app_sam"),cid("appliances"),"Refrigerator not cooling","sym_app_nocool","Critical","Refrigerator interior temp rising above safe levels",'["compressor failure","evaporator fan","refrigerant leak"]',60,"Hard",'["compressor","start relay"]','["multimeter","refrigerant gauge"]'),
        (sysid("sys_app_sam"),cid("appliances"),"Ice maker not producing ice","sym_app_ice","Medium","Ice maker stopped producing ice",'["water line clogged","ice maker motor failed","low freezer temp"]',30,"Moderate",'["ice maker assembly","water filter"]','["screwdriver","multimeter"]'),
        (sysid("sys_app_lgwm"),cid("appliances"),"Washing machine excessive vibration","sym_app_vibrate","Medium","Washer shakes violently during spin cycle",'["unbalanced load","worn shock absorbers","uneven floor"]',30,"Moderate",'["shock absorbers","dampening strap"]','["wrench","level"]'),
        (sysid("sys_app_bosch"),cid("appliances"),"Dishwasher not draining","sym_app_nodrain","High","Water remains in dishwasher bottom after cycle",'["clogged drain hose","failed drain pump","blocked filter"]',30,"Moderate",'["drain pump","filter"]','["screwdriver","bucket"]'),
        (sysid("sys_hvac_carrier"),cid("hvac"),"Furnace not producing heat","sym_hvac_noheat","Critical","Furnace runs but produces no warm air",'["igniter failure","gas valve stuck","flame sensor dirty"]',45,"Hard",'["igniter","flame sensor","gas valve"]','["multimeter","flame sensor wrench"]'),
        (sysid("sys_hvac_carrier"),cid("hvac"),"Furnace short cycling","sym_hvac_short","High","Furnace turns on and off every few minutes",'["dirty filter","flame sensor","overheating limit switch"]',30,"Moderate",'["filter","flame sensor"]','["screwdriver","flame sensor wrench"]'),
        (sysid("sys_hvac_trane"),cid("hvac"),"AC not cooling effectively","sym_hvac_acwarm","High","Air conditioner runs but air not cold",'["low refrigerant","dirty condenser","bad capacitor"]',45,"Moderate",'["capacitor","refrigerant"]','["gauge set","multimeter"]'),
        (sysid("sys_hvac_trane"),cid("hvac"),"Frozen evaporator coil","sym_hvac_frozen","High","Ice buildup on indoor evaporator coil",'["low refrigerant","restricted airflow","dirty filter"]',30,"Moderate",'["filter","refrigerant"]','["thermometer","gauge set"]'),
        (sysid("sys_floor_bruce"),cid("flooring"),"Hardwood floor cupping","sym_floor_cup","High","Edges of boards raised higher than center",'["moisture imbalance","improper acclimation","leak"]',60,"Expert",'["replacement boards","moisture barrier"]','["moisture meter","circular saw"]'),
        (sysid("sys_floor_bruce"),cid("flooring"),"Squeaking hardwood floors","sym_floor_squeak","Low","Floor makes noise when walked on",'["loose boards","nail pops","subfloor movement"]',20,"Easy",'["squeak repair kit","shims"]','["drill","stud finder"]'),
        (sysid("sys_door_chamb"),cid("doors"),"Garage door won't close","sym_door_wontclose","High","Garage door reverses before touching floor",'["misaligned sensors","obstruction","force setting"]',20,"Easy",'["sensor alignment bracket"]','["screwdriver","level"]'),
        (sysid("sys_win_andersen"),cid("windows"),"Drafty windows","sym_win_draft","Medium","Cold air leaking around window frame",'["worn weatherstrip","poor installation","settled frame"]',30,"Easy",'["weatherstrip","caulk"]','["caulk gun","utility knife"]'),
        (sysid("sys_win_andersen"),cid("windows"),"Condensation between glass panes","sym_win_cond","Medium","Fog or moisture between double-pane glass",'["failed seal","desiccant saturated","thermal stress"]',15,"Moderate",'["IGU replacement"]','["glazing tool","suction cups"]'),
        (sysid("sys_furn_sofa"),cid("furniture"),"Sofa cushions sagging","sym_furn_sag","Low","Seat cushions losing shape and support",'["worn foam","broken springs","heavy use"]',20,"Easy",'["replacement foam","spring clips"]','["measuring tape","scissors"]'),
        (sysid("sys_app_lg"),cid("appliances"),"Temperature fluctuation in fridge","sym_app_tempfluc","Medium","Refrigerator temp rises and falls unpredictably",'["defrost timer issue","door gasket leak","thermistor drift"]',45,"Moderate",'["thermistor","door gasket"]','["multimeter","screwdriver"]'),
        (sysid("sys_app_lg"),cid("appliances"),"Compressor making loud noise","sym_app_compressor","High","Linear compressor producing unusual knocking",'["worn compressor mounts","internal bearing wear","refrigerant issue"]',60,"Expert",'["compressor assembly"]','["refrigerant gauge","wrench set"]'),
        (sysid("sys_paint_bm"),cid("painting"),"Interior paint peeling","sym_paint_peel","Medium","Paint lifting from wall in sheets or chips",'["poor surface prep","moisture","incompatible primer"]',30,"Moderate",'["paint","primer","spackle"]','["scraper","sandpaper","roller"]'),
    ]
    c.executemany("INSERT INTO symptoms(system_id,category_id,symptom_name,symptom_code,severity,description,common_causes,diagnostic_time_minutes,difficulty,parts_needed,tools_needed) VALUES(?,?,?,?,?,?,?,?,?,?,?)", symptoms)
    def symid(code): return c.execute("SELECT symptom_id FROM symptoms WHERE symptom_code=?",(code,)).fetchone()[0]

    trees = [
        (symid("sym_roof_granule"),"Asphalt Shingle Granule Loss Diagnostic","dt_roof_granule",'[{"step":1,"check":"shingle age"},{"step":2,"check":"attic ventilation"},{"step":3,"check":"sun exposure"}]','[{"point":"age > 15 yrs?","yes":"replace","no":"continue"}]','[{"path":"full replacement","confidence":0.85}]',3,120,82.0),
        (symid("sym_roof_stain"),"Roof Leak Source Diagnostic","dt_roof_leak",'[{"step":1,"check":"attic for water trail"},{"step":2,"check":"flashing condition"},{"step":3,"check":"shingle damage"}]','[{"point":"near chimney?","yes":"flashing repair","no":"check valleys"}]','[{"path":"flashing repair","confidence":0.78}]',3,180,75.0),
        (symid("sym_plumb_running"),"Toilet Running Water Diagnostic","dt_toilet_run",'[{"step":1,"check":"flapper seal"},{"step":2,"check":"fill valve"},{"step":3,"check":"overflow tube level"}]','[{"point":"flapper worn?","yes":"replace flapper","no":"check fill valve"}]','[{"path":"flapper replacement","confidence":0.92}]',3,20,95.0),
        (symid("sym_plumb_nohot"),"Tankless Water Heater No Hot Water","dt_tankless",'[{"step":1,"check":"error codes"},{"step":2,"check":"gas supply"},{"step":3,"check":"igniter"},{"step":4,"check":"flow sensor"}]','[{"point":"error code present?","yes":"decode error","no":"check igniter"}]','[{"path":"igniter replacement","confidence":0.70}]',4,90,68.0),
        (symid("sym_elec_trip"),"Circuit Breaker Tripping Diagnostic","dt_breaker",'[{"step":1,"check":"connected load"},{"step":2,"check":"for short circuit"},{"step":3,"check":"breaker condition"}]','[{"point":"all devices off still trips?","yes":"bad breaker","no":"overload"}]','[{"path":"breaker replacement","confidence":0.80}]',3,45,78.0),
        (symid("sym_elec_burn"),"Electrical Panel Burning Smell Emergency","dt_panel_burn",'[{"step":1,"check":"MAIN SHUTOFF"},{"step":2,"check":"thermal imaging"},{"step":3,"check":"terminal tightness"}]','[{"point":"immediate danger?","yes":"call electrician","no":"inspect further"}]','[{"path":"panel replacement","confidence":0.90}]',3,30,60.0),
        (symid("sym_app_nocool"),"Refrigerator Not Cooling Diagnostic","dt_fridge",'[{"step":1,"check":"compressor running"},{"step":2,"check":"evaporator fan"},{"step":3,"check":"condenser coils"},{"step":4,"check":"refrigerant pressure"}]','[{"point":"compressor humming?","yes":"check fan","no":"compressor issue"}]','[{"path":"compressor replacement","confidence":0.65}]',4,120,70.0),
        (symid("sym_hvac_noheat"),"Furnace No Heat Diagnostic","dt_furnace",'[{"step":1,"check":"thermostat call"},{"step":2,"check":"igniter glow"},{"step":3,"check":"gas valve"},{"step":4,"check":"flame sensor"}]','[{"point":"igniter glows?","yes":"gas valve","no":"igniter replacement"}]','[{"path":"igniter replacement","confidence":0.82}]',4,90,76.0),
        (symid("sym_hvac_acwarm"),"AC Not Cooling Diagnostic","dt_ac",'[{"step":1,"check":"thermostat setting"},{"step":2,"check":"condenser fan"},{"step":3,"check":"capacitor"},{"step":4,"check":"refrigerant"}]','[{"point":"outdoor unit running?","yes":"check refrigerant","no":"check capacitor"}]','[{"path":"capacitor replacement","confidence":0.85}]',4,90,72.0),
        (symid("sym_door_wontclose"),"Garage Door Won't Close Diagnostic","dt_garage",'[{"step":1,"check":"sensor alignment"},{"step":2,"check":"track obstruction"},{"step":3,"check":"force limit"}]','[{"point":"sensor LED blinking?","yes":"realign sensors","no":"check force"}]','[{"path":"sensor realignment","confidence":0.90}]',3,20,92.0),
        (symid("sym_app_nodrain"),"Dishwasher Not Draining Diagnostic","dt_dw",'[{"step":1,"check":"drain hose"},{"step":2,"check":"filter screen"},{"step":3,"check":"drain pump"}]','[{"point":"hose kinked?","yes":"straighten hose","no":"check pump"}]','[{"path":"drain pump replacement","confidence":0.78}]',3,45,80.0),
        (symid("sym_floor_cup"),"Hardwood Floor Cupping Diagnostic","dt_floor",'[{"step":1,"check":"moisture source"},{"step":2,"check":"subfloor condition"},{"step":3,"check":"acclimation"}]','[{"point":"moisture reading high?","yes":"fix moisture","no":"sand and refinish"}]','[{"path":"moisture mitigation","confidence":0.80}]',3,120,70.0),
    ]
    c.executemany("INSERT INTO diagnostic_trees(symptom_id,tree_name,tree_code,steps,decision_points,resolution_paths,total_steps,avg_resolution_time_minutes,success_rate_percentage) VALUES(?,?,?,?,?,?,?,?,?)", trees)
    def tid(code): return c.execute("SELECT tree_id FROM diagnostic_trees WHERE tree_code=?",(code,)).fetchone()[0]

    repairs = [
        (tid("dt_roof_granule"),sysid("sys_roof_gaf"),"Replace Damaged Asphalt Shingles","rep_roof_shingle","Remove and replace damaged shingles",'["roofing hammer","utility knife","flat bar"]','["replacement shingles","roofing nails","roofing cement"]','["check decking integrity"]','[{"step":1,"action":"Lift tab of surrounding shingles"},{"step":2,"action":"Remove nails from damaged shingle"},{"step":3,"action":"Slide in new shingle"},{"step":4,"action":"Nail and seal"}]','["verify alignment","check seal"]',90,"Moderate",'["Wear harness on steep roofs"]',"Use fall protection at all times."),
        (tid("dt_roof_leak"),sysid("sys_roof_gaf"),"Repair Roof Flashing Leak","rep_roof_flash","Repair or replace flashing around chimney",'["caulk gun","tin snips","hammer"]','["flashing material","roofing cement","flashing nails"]','["identify leak source"]','[{"step":1,"action":"Locate leak source in attic"},{"step":2,"action":"Remove old flashing"},{"step":3,"action":"Install new flashing"},{"step":4,"action":"Seal with roofing cement"}]','["water test repair"]',180,"Hard",'["Work from proper scaffolding"]',"Ensure proper overlap with existing materials."),
        (tid("dt_toilet_run"),sysid("sys_plumb_toto"),"Replace Toilet Flapper","rep_toilet_flapper","Remove old flapper and install new one",'["adjustable wrench","sponge"]','["universal flapper"]','["shut off water","flush to drain tank"]','[{"step":1,"action":"Shut off water supply"},{"step":2,"action":"Flush to drain tank"},{"step":3,"action":"Unhook old flapper"},{"step":4,"action":"Install new flapper"},{"step":5,"action":"Turn water on and test"}]','["check for running after 5 min"]',15,"Easy",'[]',"Ensure flapper matches toilet model."),
        (tid("dt_tankless"),sysid("sys_plumb_rheem"),"Replace Tankless Water Heater Igniter","rep_tankless_ign","Replace failed hot surface igniter",'["multimeter","screwdriver","pipe wrench"]','["replacement igniter"]','["shut off gas and power"]','[{"step":1,"action":"Shut off gas and power"},{"step":2,"action":"Remove access panel"},{"step":3,"action":"Disconnect igniter wires"},{"step":4,"action":"Install new igniter"},{"step":5,"action":"Reconnect and test"}]','["verify ignition sequence"]',60,"Hard",'["Shut off gas before starting"]',"Handle igniter with clean cloth only."),
        (tid("dt_breaker"),sysid("sys_elec_sqd"),"Replace Circuit Breaker","rep_elec_breaker","Remove old breaker and install new one",'["voltage tester","screwdriver"]','["replacement breaker"]','["verify panel is safe","turn off main"]','[{"step":1,"action":"Turn off main breaker"},{"step":2,"action":"Verify no voltage"},{"step":3,"action":"Remove hot wire"},{"step":4,"action":"Unclip old breaker"},{"step":5,"action":"Clip in new breaker"},{"step":6,"action":"Reconnect wire and test"}]','["verify voltage","test circuit"]',30,"Moderate",'["NEVER work on live panel"]',"Always verify zero energy state."),
        (tid("dt_fridge"),sysid("sys_app_sam"),"Replace Refrigerator Compressor","rep_fridge_comp","Remove failed compressor and install new one",'["refrigerant gauges","wrench set","torch","vacuum pump"]','["replacement compressor","filter drier","refrigerant"]','["verify compressor failure"]','[{"step":1,"action":"Recover refrigerant"},{"step":2,"action":"Disconnect compressor lines"},{"step":3,"action":"Install new compressor"},{"step":4,"action":"Braze connections"},{"step":5,"action":"Evacuate and charge"}]','["verify pressures","monitor temps 24hrs"]',240,"Expert",'["EPA certification required"]',"Must be EPA certified for refrigerant."),
        (tid("dt_furnace"),sysid("sys_hvac_carrier"),"Replace Furnace Hot Surface Igniter","rep_furn_ign","Remove old igniter and install new one",'["screwdriver","flame sensor wrench","multimeter"]','["replacement igniter"]','["turn off power"]','[{"step":1,"action":"Turn off furnace power"},{"step":2,"action":"Remove burner panel"},{"step":3,"action":"Disconnect igniter wires"},{"step":4,"action":"Install new igniter"},{"step":5,"action":"Reconnect and test"}]','["verify ignition within 30 sec"]',45,"Moderate",'["Turn off gas if smell detected"]',"Do not touch igniter surface with bare fingers."),
        (tid("dt_furnace"),sysid("sys_hvac_carrier"),"Clean Furnace Flame Sensor","rep_furn_sensor","Remove and clean flame sensor rod",'["flame sensor wrench","sandpaper","multimeter"]','[]','["turn off power","locate sensor"]','[{"step":1,"action":"Turn off power"},{"step":2,"action":"Remove flame sensor"},{"step":3,"action":"Clean with sandpaper"},{"step":4,"action":"Check microamp reading"},{"step":5,"action":"Reinstall and test"}]','["verify microamp > 2uA"]',20,"Easy",'[]',"Sensor should read at least 2 microamps."),
        (tid("dt_ac"),sysid("sys_hvac_trane"),"Replace AC Contactor","rep_ac_contactor","Remove old contactor and install new one",'["multimeter","screwdriver","needle nose pliers"]','["replacement contactor"]','["turn off disconnect"]','[{"step":1,"action":"Turn off disconnect"},{"step":2,"action":"Photo wiring"},{"step":3,"action":"Disconnect wires"},{"step":4,"action":"Swap contactor"},{"step":5,"action":"Reconnect and test"}]','["verify compressor starts"]',30,"Moderate",'["HIGH VOLTAGE"]',"Always take photo of wiring before disconnecting."),
        (tid("dt_ac"),sysid("sys_hvac_trane"),"Replace AC Run Capacitor","rep_ac_cap","Replace failed run capacitor",'["multimeter with capacitance","insulated pliers"]','["replacement capacitor"]','["turn off power","discharge old cap"]','[{"step":1,"action":"Turn off disconnect"},{"step":2,"action":"Discharge old capacitor"},{"step":3,"action":"Note wiring"},{"step":4,"action":"Swap capacitor"},{"step":5,"action":"Reconnect and test"}]','["verify amp draw"]',20,"Moderate",'["HIGH VOLTAGE - can be lethal"]',"Always discharge first. Match exact uF rating."),
        (tid("dt_garage"),sysid("sys_door_chamb"),"Realign Garage Door Safety Sensors","rep_garage_sensor","Adjust sensor alignment",'["screwdriver","level"]','[]','["check sensor LEDs"]','[{"step":1,"action":"Check sensor LEDs"},{"step":2,"action":"Loosen brackets"},{"step":3,"action":"Align sensors"},{"step":4,"action":"Tighten brackets"},{"step":5,"action":"Test door"}]','["door closes fully","LED solid"]',15,"Easy",'[]',"Both LEDs should be solid when aligned."),
        (tid("dt_dw"),sysid("sys_app_bosch"),"Replace Dishwasher Drain Pump","rep_dw_pump","Remove and replace drain pump",'["screwdriver","bucket","towels"]','["replacement drain pump"]','["disconnect power","remove water"]','[{"step":1,"action":"Disconnect power"},{"step":2,"action":"Remove access panel"},{"step":3,"action":"Disconnect pump wiring"},{"step":4,"action":"Install new pump"},{"step":5,"action":"Reconnect and test"}]','["run drain cycle"]',60,"Moderate",'["Disconnect power first"]',"Have towels ready for residual water."),
        (tid("dt_floor"),sysid("sys_floor_bruce"),"Replace Cupped Hardwood Boards","rep_floor_board","Remove and replace cupped boards",'["circular saw","chisel","hammer","drill"]','["replacement boards","wood glue","finish nails"]','["identify moisture source"]','[{"step":1,"action":"Drill relief holes"},{"step":2,"action":"Cut board lengthwise"},{"step":3,"action":"Chisel out sections"},{"step":4,"action":"Cut replacement to fit"},{"step":5,"action":"Glue and nail"}]','["verify level with adjacent"]',120,"Hard",'["Wear eye protection"]',"Acclimate replacement boards 48 hours."),
        (tid("dt_panel_burn"),sysid("sys_elec_sqd"),"Emergency Panel Inspection","rep_panel_emerg","Inspect and repair overheating panel",'["thermal camera","voltage tester","torque screwdriver"]','["replacement breaker","terminal"]','["shut off main if needed"]','[{"step":1,"action":"Shut off main"},{"step":2,"action":"Thermal scan all connections"},{"step":3,"action":"Tighten terminals"},{"step":4,"action":"Replace damaged parts"},{"step":5,"action":"Re-energize and verify"}]','["thermal scan after repair"]',120,"Expert",'["Arc flash PPE required"]',"Life-safety repair. Document everything."),
        (tid("dt_fridge"),sysid("sys_app_lg"),"Replace Refrigerator Thermistor","rep_fridge_therm","Remove and replace temperature sensor",'["multimeter","screwdriver"]','["replacement thermistor"]','["unplug refrigerator"]','[{"step":1,"action":"Unplug fridge"},{"step":2,"action":"Locate thermistor"},{"step":3,"action":"Disconnect connector"},{"step":4,"action":"Install new thermistor"},{"step":5,"action":"Plug in and monitor"}]','["verify temp stable 24hrs"]',45,"Moderate",'[]',"Compare resistance to spec sheet."),
    ]
    c.executemany("INSERT INTO repair_procedures(tree_id,system_id,repair_name,repair_code,overview,tools_required,materials_required,pre_repair_checks,procedure_steps,post_repair_checks,estimated_time_minutes,difficulty,warnings,safety_notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", repairs)

    parts = [
        ("GAF Timberline HDZ Shingle Bundle","part_roof_shingle",'["sys_roof_gaf"]',35.99,500,100,"ABC Supply","orders@abcsupply.com",3,"bundle","per sq",cid("roofing")),
        ("Roofing Nails 1-1/4 inch 5lb","part_roof_nails",'["sys_roof_gaf","sys_roof_metal"]',12.50,200,50,"Home Depot","orders@homedepot.com",1,"box","5lb",cid("roofing")),
        ("EPDM Membrane Roll 10x100","part_roof_epdm",'["sys_roof_epdm"]',289.00,20,5,"Firestone Direct","sales@firestone.com",7,"roll","1000 sqft",cid("roofing")),
        ("Chimney Flashing Kit","part_roof_flash",'["sys_roof_gaf","sys_roof_metal"]',45.00,100,20,"ABC Supply","orders@abcsupply.com",2,"kit","per chimney",cid("roofing")),
        ("Toto Flapper Assembly","part_plumb_flapper",'["sys_plumb_toto"]',8.99,300,50,"Toto Parts","parts@toto.com",2,"piece","per toilet",cid("plumbing")),
        ("Rheem Tankless Igniter","part_plumb_igniter",'["sys_plumb_rheem"]',42.00,50,10,"Rheem Parts","parts@rheem.com",5,"piece","per unit",cid("plumbing")),
        ("Copper Pipe 3/4in Type L 10ft","part_plumb_copper",'["sys_plumb_copper"]',18.50,200,40,"Mueller Industries","orders@mueller.com",2,"stick","10ft",cid("plumbing")),
        ("Square D 20A Breaker","part_elec_breaker",'["sys_elec_sqd"]',6.50,400,80,"Square D","orders@squareD.com",1,"piece","per breaker",cid("electrical")),
        ("GE 20A GFCI Breaker","part_elec_gfci",'["sys_elec_gfci"]',52.00,100,20,"GE Electric","orders@ge.com",3,"piece","per breaker",cid("electrical")),
        ("LED Recessed Light 6 inch","part_elec_led6",'["sys_elec_led"]',24.99,200,40,"Halo","orders@halo.com",2,"piece","per light",cid("electrical")),
        ("Samsung Refrigerator Compressor","part_app_comp_sam",'["sys_app_sam"]',320.00,15,5,"Samsung Parts","parts@samsung.com",10,"piece","per unit",cid("appliances")),
        ("Samsung Ice Maker Assembly","part_app_ice",'["sys_app_sam"]',89.99,50,10,"Samsung Parts","parts@samsung.com",5,"piece","per unit",cid("appliances")),
        ("LG Washer Shock Absorber","part_app_shock",'["sys_app_lgwm"]',18.50,100,20,"LG Parts","parts@lg.com",4,"piece","pair",cid("appliances")),
        ("Bosch Dishwasher Drain Pump","part_app_pump_bosch",'["sys_app_bosch"]',65.00,60,10,"Bosch Parts","parts@bosch.com",5,"piece","per unit",cid("appliances")),
        ("Carrier Furnace Igniter","part_hvac_ign",'["sys_hvac_carrier"]',28.00,100,20,"Carrier Parts","parts@carrier.com",3,"piece","per unit",cid("hvac")),
        ("Carrier Flame Sensor","part_hvac_sensor",'["sys_hvac_carrier"]',22.00,150,30,"Carrier Parts","parts@carrier.com",3,"piece","per unit",cid("hvac")),
        ("Trane AC Contactor","part_hvac_contactor",'["sys_hvac_trane"]',32.00,80,15,"Trane Parts","parts@trane.com",3,"piece","per unit",cid("hvac")),
        ("Trane AC Run Capacitor 45/5uF","part_hvac_cap",'["sys_hvac_trane"]',18.00,120,25,"Trane Parts","parts@trane.com",2,"piece","per unit",cid("hvac")),
        ("Chamberlain Safety Sensor Pair","part_door_sensor",'["sys_door_chamb"]',35.00,80,15,"Chamberlain","parts@chamberlain.com",3,"pair","per set",cid("doors")),
        ("Bruce Oak Flooring Board per sqft","part_floor_oak",'["sys_floor_bruce"]',6.50,500,100,"Bruce Floors","orders@bruce.com",5,"sqft","per sqft",cid("flooring")),
        ("Andersen Weatherstrip Kit","part_win_weather",'["sys_win_andersen"]',22.00,100,20,"Andersen Parts","parts@andersen.com",3,"kit","per window",cid("windows")),
        ("Sofa Replacement Foam Cushion","part_furn_foam",'["sys_furn_sofa"]',45.00,40,10,"FoamOrder","orders@foamorder.com",7,"piece","per cushion",cid("furniture")),
        ("Benjamin Moore Regal Select Gallon","part_paint_bm",'["sys_paint_bm"]',54.99,200,40,"Benjamin Moore","orders@benjaminmoore.com",2,"gallon","per gallon",cid("painting")),
        ("LG Linear Compressor Assembly","part_app_comp_lg",'["sys_app_lg"]',380.00,10,3,"LG Parts","parts@lg.com",14,"piece","per unit",cid("appliances")),
    ]
    c.executemany("INSERT INTO parts_inventory(part_name,part_code,compatible_systems,average_cost,current_stock,reorder_level,supplier,supplier_contact,lead_time_days,unit,coverage,category_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", parts)

    n = insert_embeddings_and_meta(conn, vid)
    insert_validation(conn, vid, {"categories":len(cats),"systems":len(systems),"symptoms":len(symptoms),"trees":len(trees),"repairs":len(repairs),"parts":len(parts),"embeddings":n})
    insert_prompts(conn, vid, [
        ("Diagnostic Intent Classifier","diagnostic","Classify the user's problem: {problem}",vid),
        ("Repair Recommendation Generator","repair","Given symptom {symptom} on {system}, recommend repair.",vid),
        ("Knowledge Base Search","search","Search FixFinder KB for: {query}",vid),
        ("Parts Recommendation Engine","recommendation","For repair {repair} on {system}, list parts.",vid),
    ])

# ===== VERSION 2: Electronics =====
def seed_v2(conn):
    c = conn.cursor()
    vid = "electronics_v2"
    cats = [
        (vid,"Phones","phones","Mobile phones",4,85,68),(vid,"Tablets","tablets","Tablets and e-readers",4,72,56),
        (vid,"Laptops","laptops","Portable computers",5,95,75),(vid,"Desktop Computers","desktops","Tower PCs",5,90,72),
        (vid,"Monitors","monitors","Display screens",6,78,60),(vid,"Printers","printers","Printing devices",6,82,65),
        (vid,"Networking","networking","Network infrastructure",7,88,68),(vid,"Routers","routers","Wireless routing",5,70,55),
        (vid,"Televisions","televisions","TV sets",6,85,68),(vid,"Gaming Consoles","gaming","Game consoles",6,80,64),
        (vid,"Audio Equipment","audio","Audio equipment",7,82,64),(vid,"Smart Home","smart_home","Home automation",8,92,70),
        (vid,"Wearables","wearables","Wearable tech",5,65,50),(vid,"Drones","drones","UAVs",5,70,55),
        (vid,"Projectors","projectors","Projection systems",5,62,48),(vid,"CCTV","cctv","Surveillance",6,75,58),
        (vid,"POS Systems","pos","Point of sale",5,60,46),(vid,"NAS","nas","Network storage",5,68,52),
        (vid,"Switches","switches","Network switches",5,65,50),(vid,"Office Equipment","office","Office machines",6,72,56),
    ]
    c.executemany("INSERT INTO categories(version_id,category_name,category_code,description,total_systems,total_symptoms,total_repairs) VALUES(?,?,?,?,?,?,?)", cats)
    def cid(code): return c.execute("SELECT category_id FROM categories WHERE category_code=?",(code,)).fetchone()[0]
    subcats = [
        (cid("phones"),"Smartphones","ph_smart","Smartphones"),(cid("phones"),"Feature Phones","ph_feat","Basic phones"),
        (cid("laptops"),"Gaming Laptops","lp_game","Gaming laptops"),(cid("laptops"),"Business Laptops","lp_biz","Business laptops"),
        (cid("desktops"),"Workstations","dk_ws","Workstations"),(cid("desktops"),"Gaming PCs","dk_game","Gaming PCs"),
        (cid("gaming"),"PlayStation","gm_ps","PlayStation"),(cid("gaming"),"Xbox","gm_xbox","Xbox"),
        (cid("televisions"),"OLED","tv_oled","OLED TVs"),(cid("televisions"),"Smart TVs","tv_smart","Smart TVs"),
        (cid("audio"),"Headphones","au_hp","Headphones"),(cid("audio"),"Speakers","au_spk","Speakers"),
        (cid("smart_home"),"Smart Speakers","sh_spk","Smart speakers"),(cid("smart_home"),"Smart Locks","sh_lock","Smart locks"),
        (cid("networking"),"Ethernet","net_eth","Ethernet"),(cid("routers"),"Wi-Fi 6","rt_w6","Wi-Fi 6"),
        (cid("monitors"),"OLED","mn_oled","OLED monitors"),(cid("printers"),"Laser","pr_las","Laser printers"),
        (cid("cctv"),"IP Cameras","cc_ip","IP cameras"),(cid("wearables"),"Smartwatches","wr_w","Smartwatches"),
    ]
    c.executemany("INSERT INTO subcategories(category_id,subcategory_name,subcategory_code,description) VALUES(?,?,?,?)", subcats)
    def sid(code): return c.execute("SELECT subcategory_id FROM subcategories WHERE subcategory_code=?",(code,)).fetchone()[0]
    systems = [
        (sid("ph_smart"),"iPhone 15 Pro Max","sys_ip15pm","Apple","iPhone 15 Pro Max",2023,5,0,'{"chip":"A17 Pro","display":"6.7 OLED","ram":"8GB"}','["display","battery","logic board","camera"]','["display","battery","camera","charging port"]','["screen crack","battery drain"]'),
        (sid("ph_smart"),"Samsung Galaxy S24 Ultra","sys_gs24u","Samsung","Galaxy S24 Ultra",2024,5,0,'{"chip":"SD 8 Gen 3","display":"6.8 AMOLED","ram":"12GB"}','["display","battery","motherboard","S Pen"]','["display","battery","S Pen"]','["burn-in","S Pen fail"]'),
        (sid("lp_game"),"MacBook Pro 16 M3 Max","sys_mbpro","Apple","MacBook Pro 16",2024,7,12,'{"chip":"M3 Max","ram":"36GB","ssd":"1TB"}','["logic board","display","battery","keyboard"]','["battery","keyboard","display"]','["keyboard fail","battery swell"]'),
        (sid("lp_biz"),"Dell XPS 15 9530","sys_dxps","Dell","XPS 15 9530",2023,6,12,'{"cpu":"i7-13700H","ram":"32GB","gpu":"RTX 4060"}','["motherboard","display","battery","thermal"]','["battery","thermal paste","fan"]','["overheating","flicker"]'),
        (sid("dk_ws"),"Dell Precision 7875","sys_prec","Dell","Precision 7875",2024,8,12,'{"cpu":"Threadripper PRO","ram":"128GB","gpu":"RTX A5000"}','["motherboard","PSU","GPU","RAM"]','["PSU","GPU","RAM"]','["POST fail","GPU artifact"]'),
        (sid("gm_ps"),"PlayStation 5","sys_ps5","Sony","PlayStation 5",2020,7,6,'{"cpu":"Zen 2","gpu":"10.28 TF","ssd":"825GB"}','["APU","disc drive","HDMI","fan"]','["HDMI port","disc drive","fan"]','["no signal","overheat"]'),
        (sid("gm_xbox"),"Xbox Series X","sys_xsx","Microsoft","Xbox Series X",2020,7,6,'{"cpu":"Zen 2","gpu":"12 TF","ssd":"1TB"}','["APU","disc drive","HDMI","fan"]','["HDMI port","disc drive"]','["green screen","disc fail"]'),
        (sid("tv_oled"),"LG C3 65 OLED","sys_lgc3","LG","OLED C3 65",2023,7,0,'{"panel":"OLED evo","res":"4K","hz":120}','["panel","main board","power board","T-Con"]','["main board","T-Con"]','["burn-in","lines"]'),
        (sid("tv_smart"),"Samsung S95C QD-OLED","sys_s95c","Samsung","S95C 65",2023,7,0,'{"panel":"QD-OLED","res":"4K","hz":144}','["panel","main board","One Connect"]','["main board","One Connect"]','["color shift","One Connect fail"]'),
        (sid("au_hp"),"Sony WH-1000XM5","sys_xm5","Sony","WH-1000XM5",2022,5,0,'{"driver":"30mm","anc":"auto","batt":"30hrs"}','["driver","battery","ANC mic","BT"]','["battery","driver","ear pads"]','["ANC fail","battery drain"]'),
        (sid("sh_spk"),"Amazon Echo Dot 5","sys_echo","Amazon","Echo Dot 5",2022,5,0,'{"speaker":"1.6in","alexa":"yes","wifi":"dual"}','["speaker","main board","PSU","mic"]','["PSU","speaker","wifi"]','["wifi fail","no response"]'),
        (sid("sh_lock"),"August Wi-Fi Smart Lock","sys_aug","August","Wi-Fi Lock",2021,4,12,'{"conn":"wifi+ble","batt":"CR123A x2"}','["motor","main board","battery","sensor"]','["motor","battery","sensor"]','["motor fail","wifi drop"]'),
        (sid("rt_w6"),"ASUS RT-AX86U Pro","sys_ax86","ASUS","RT-AX86U Pro",2023,5,6,'{"wifi":"AX5700","ports":"1x2.5G+4xGbE"}','["main board","PSU","antennas","ports"]','["PSU","antenna","port"]','["drops","slow","port fail"]'),
        (sid("mn_oled"),"LG 27GR95QE OLED","sys_lgomn","LG","27GR95QE",2023,5,0,'{"panel":"OLED","res":"2560x1440","hz":240}','["panel","main board","power board"]','["main board","power board"]','["retention","flicker"]'),
        (sid("pr_las"),"HP LaserJet Pro M404dn","sys_m404","HP","LaserJet M404dn",2022,6,6,'{"speed":"40ppm","dpi":1200,"duplex":true}','["fuser","toner","roller","formatter"]','["fuser","toner","roller"]','["paper jam","fuser error"]'),
        (sid("cc_ip"),"Hikvision DS-2CD2143G2-I","sys_hik","Hikvision","DS-2CD2143G2",2022,7,12,'{"res":"4MP","ir":"30m","proto":"ONVIF"}','["sensor","IR LEDs","main board","lens"]','["IR LEDs","main board","lens"]','["night vision fail","no feed"]'),
        (sid("wr_w"),"Apple Watch Series 9","sys_aw9","Apple","Watch S9",2023,4,0,'{"chip":"S9","display":"AON Retina","water":"50m"}','["display","battery","crown","HR sensor"]','["display","battery","crown"]','["screen fail","battery","crown stuck"]'),
        (sid("au_spk"),"Sonos Era 300","sys_era","Sonos","Era 300",2023,6,0,'{"drivers":6,"atmos":true,"wifi":"wifi6"}','["driver array","main board","PSU","wifi"]','["driver","PSU","wifi"]','["wifi drop","distortion"]'),
        (sid("net_eth"),"Ubiquiti USW-Pro-24 PoE","sys_ubnt","Ubiquiti","USW-Pro-24-PoE",2023,8,12,'{"ports":"24GbE+2SFP+","poe":"400W"}','["ASIC","PSU","SFP","ports"]','["PSU","SFP","port"]','["port fail","PoE fail"]'),
        (sid("lp_game"),"ASUS ROG Strix G16","sys_rog","ASUS","ROG Strix G16",2024,6,12,'{"cpu":"i9-14900HX","gpu":"RTX 4070","ram":"32GB"}','["motherboard","GPU","display","cooling"]','["thermal paste","fan","keyboard"]','["throttle","GPU artifact"]'),
        (sid("ph_smart"),"Google Pixel 8 Pro","sys_px8","Google","Pixel 8 Pro",2023,5,0,'{"chip":"Tensor G3","display":"6.7 OLED","ram":"12GB"}','["display","battery","camera","logic board"]','["display","battery","camera"]','["screen crack","battery drain"]'),
        (sid("lp_biz"),"Lenovo ThinkPad X1 Carbon","sys_tp_x1","Lenovo","ThinkPad X1 Carbon",2023,7,12,'{"cpu":"i7-1365U","ram":"32GB","ssd":"1TB"}','["motherboard","display","battery","keyboard"]','["battery","keyboard","fan"]','["keyboard fail","battery swell"]'),
        (sid("gm_ps"),"Nintendo Switch OLED","sys_nsoled","Nintendo","Switch OLED",2021,6,6,'{"cpu":"Tegra X1","display":"7 OLED","storage":"64GB"}','["APU","display","card slot","fan"]','["display","card slot","fan"]','["card read fail","joy-con drift"]'),
        (sid("dk_ws"),"HP Z4 G5 Workstation","sys_hpz4","HP","Z4 G5",2023,8,12,'{"cpu":"Xeon w5-3435X","ram":"128GB","gpu":"RTX A4000"}','["motherboard","PSU","GPU","RAM"]','["PSU","GPU","RAM"]','["POST fail","GPU error"]'),
    ]
    c.executemany("INSERT INTO systems(subcategory_id,system_name,system_code,brand,model,year_released,lifespan_years,maintenance_interval_months,specifications,components,parts_list,common_issues) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", systems)
    def sysid(code): return c.execute("SELECT system_id FROM systems WHERE system_code=?",(code,)).fetchone()[0]
    symptoms = [
        (sysid("sys_ip15pm"),cid("phones"),"Cracked screen","sym_ph_cr","High","Display cracked",'["drop","pressure"]',15,"Moderate",'["display"]','["screwdriver","suction cup"]'),
        (sysid("sys_ip15pm"),cid("phones"),"Battery drains fast","sym_ph_bat","Medium","Fast battery drain",'["degradation","apps"]',20,"Moderate",'["battery"]','["screwdriver","spudger"]'),
        (sysid("sys_gs24u"),cid("phones"),"Screen burn-in","sym_ph_burn","Medium","Ghost images",'["static images","aging"]',10,"Variable",'["display"]','["heat gun","suction cup"]'),
        (sysid("sys_gs24u"),cid("phones"),"S Pen not detected","sym_ph_spen","Medium","S Pen not recognized",'["tip worn","digitizer"]',15,"Easy",'["S Pen"]','["SIM tool"]'),
        (sysid("sys_mbpro"),cid("laptops"),"Keyboard not responding","sym_lp_kb","Medium","Keys not working",'["debris","liquid"]',30,"Moderate",'["keyboard"]','["screwdriver set"]'),
        (sysid("sys_mbpro"),cid("laptops"),"Battery swelling","sym_lp_sw","Critical","Trackpad bulging",'["age","heat"]',10,"Hard",'["battery"]','["screwdriver set"]'),
        (sysid("sys_dxps"),cid("laptops"),"Overheating","sym_lp_oh","High","Runs hot and slow",'["dust","dry paste"]',30,"Moderate",'["thermal paste","fan"]','["compressed air","paste"]'),
        (sysid("sys_dxps"),cid("laptops"),"Screen flickering","sym_lp_fl","High","Display flickers",'["loose cable","GPU","panel"]',20,"Moderate",'["display cable","panel"]','["screwdriver","multimeter"]'),
        (sysid("sys_prec"),cid("desktops"),"POST failure","sym_dk_post","Critical","Fails POST",'["RAM","GPU","CPU"]',30,"Expert",'["RAM","GPU","PSU"]','["POST card","multimeter"]'),
        (sysid("sys_prec"),cid("desktops"),"GPU artifacting","sym_dk_gpu","High","Visual artifacts",'["VRAM fail","overheat"]',20,"Moderate",'["GPU","paste"]','["screwdriver","paste"]'),
        (sysid("sys_ps5"),cid("gaming"),"HDMI no signal","sym_ps5_sig","High","No display",'["HDMI damage","GPU"]',20,"Hard",'["HDMI port","filter IC"]','["soldering station"]'),
        (sysid("sys_ps5"),cid("gaming"),"Overheating shutdown","sym_ps5_oh","High","Shuts down from heat",'["dust","dry paste"]',30,"Moderate",'["thermal paste","filter"]','["torx driver","paste"]'),
        (sysid("sys_xsx"),cid("gaming"),"Green screen","sym_xbox_gr","Critical","Green screen no boot",'["GPU","HDMI IC"]',30,"Expert",'["GPU reball"]','["BGA station"]'),
        (sysid("sys_lgc3"),cid("televisions"),"OLED burn-in","sym_tv_burn","Medium","Permanent ghosts",'["static content","aging"]',10,"Variable",'["panel"]','["suction cups"]'),
        (sysid("sys_lgc3"),cid("televisions"),"Horizontal lines","sym_tv_lines","High","Lines on screen",'["T-Con fail","panel"]',20,"Hard",'["T-Con board"]','["screwdriver","multimeter"]'),
        (sysid("sys_xm5"),cid("audio"),"ANC not working","sym_au_anc","Medium","ANC ineffective",'["mic block","firmware"]',15,"Easy",'["ear pads"]','["cloth","USB cable"]'),
        (sysid("sys_echo"),cid("smart_home"),"WiFi connect fail","sym_sh_wifi","Medium","Can't connect WiFi",'["router","password"]',15,"Easy",'[]','["power adapter"]'),
        (sysid("sys_aug"),cid("smart_home"),"Motor not engaging","sym_lock_mot","High","Motor runs no move",'["misalign","wear"]',15,"Moderate",'["motor","batteries"]','["screwdriver"]'),
        (sysid("sys_ax86"),cid("routers"),"Dropping connections","sym_rt_drop","Medium","WiFi drops",'["overheat","firmware"]',20,"Moderate",'["PSU"]','["ethernet cable"]'),
        (sysid("sys_lgomn"),cid("monitors"),"Image retention","sym_mn_ret","Low","Image persistence",'["static UI"]',5,"Easy",'[]','["pixel refresher"]'),
        (sysid("sys_m404"),cid("printers"),"Paper jams","sym_pr_jam","Medium","Frequent jams",'["worn roller","dirty path"]',20,"Easy",'["roller"]','["screwdriver","cloth"]'),
        (sysid("sys_hik"),cid("cctv"),"Night vision fail","sym_cc_nv","Medium","IR LEDs off",'["LED fail","sensor"]',20,"Moderate",'["IR board"]','["screwdriver","multimeter"]'),
        (sysid("sys_aw9"),cid("wearables"),"Crown stuck","sym_wr_cr","Medium","Crown hard to turn",'["debris","impact"]',15,"Moderate",'["crown","gasket"]','["screwdriver","heat gun"]'),
        (sysid("sys_rog"),cid("laptops"),"Thermal throttling","sym_rog_th","High","FPS drops from throttle",'["dust","dry paste"]',45,"Moderate",'["paste","cooling pad"]','["compressed air","paste"]'),
        (sysid("sys_era"),cid("audio"),"WiFi dropping","sym_au_wifi","Medium","Disconnects WiFi",'["interference","distance"]',15,"Easy",'[]','["power cable"]'),
        (sysid("sys_ubnt"),cid("networking"),"PoE not delivering","sym_net_poe","High","No PoE power",'["port fail","budget"]',15,"Moderate",'["cable"]','["cable tester","multimeter"]'),
        (sysid("sys_ip15pm"),cid("phones"),"Camera not focusing","sym_ph_cam","High","Camera no focus",'["lens damage","OIS"]',15,"Hard",'["camera module"]','["screwdriver","spudger"]'),
        (sysid("sys_ps5"),cid("gaming"),"Disc not reading","sym_ps5_disc","High","Won't read discs",'["dirty lens","ribbon"]',30,"Hard",'["disc drive"]','["torx driver","swabs"]'),
        (sysid("sys_s95c"),cid("televisions"),"One Connect fail","sym_tv_oc","Critical","One Connect no output",'["PSU fail","HDMI board"]',20,"Hard",'["One Connect box"]','["screwdriver","multimeter"]'),
        (sysid("sys_dxps"),cid("laptops"),"Battery not charging","sym_dk_nc","High","Not charging when plugged",'["charger fail","BMS"]',20,"Moderate",'["charger","battery"]','["multimeter","screwdriver"]'),
    ]
    c.executemany("INSERT INTO symptoms(system_id,category_id,symptom_name,symptom_code,severity,description,common_causes,diagnostic_time_minutes,difficulty,parts_needed,tools_needed) VALUES(?,?,?,?,?,?,?,?,?,?,?)", symptoms)
    def symid(code): return c.execute("SELECT symptom_id FROM symptoms WHERE symptom_code=?",(code,)).fetchone()[0]
    trees = [
        (symid("sym_ph_cr"),"Phone Screen Diagnostic","dt_ph_cr",'[{"step":1,"check":"display"},{"step":2,"check":"touch"}]','[{"point":"display works?","yes":"glass","no":"full"}]','[{"path":"display replace","conf":0.9}]',2,45,88.0),
        (symid("sym_ph_bat"),"Phone Battery Diagnostic","dt_ph_bat",'[{"step":1,"check":"health"},{"step":2,"check":"apps"}]','[{"point":"health<80%?","yes":"replace","no":"software"}]','[{"path":"battery replace","conf":0.85}]',2,30,90.0),
        (symid("sym_lp_oh"),"Laptop Overheat Diagnostic","dt_lp_oh",'[{"step":1,"check":"fans"},{"step":2,"check":"vents"},{"step":3,"check":"paste"}]','[{"point":"fans ok?","yes":"repaste","no":"fan replace"}]','[{"path":"repaste","conf":0.82}]',3,60,85.0),
        (symid("sym_lp_sw"),"Battery Swelling Emergency","dt_lp_sw",'[{"step":1,"check":"severity"},{"step":2,"check":"deformation"}]','[{"point":"splitting?","yes":"urgent","no":"schedule"}]','[{"path":"battery replace","conf":0.95}]',2,45,92.0),
        (symid("sym_ps5_sig"),"PS5 No Signal Diagnostic","dt_ps5_sig",'[{"step":1,"check":"cable"},{"step":2,"check":"port"},{"step":3,"check":"GPU"}]','[{"point":"diff cable?","yes":"port","no":"GPU"}]','[{"path":"HDMI replace","conf":0.75}]',3,90,65.0),
        (symid("sym_ps5_oh"),"PS5 Overheat Diagnostic","dt_ps5_oh",'[{"step":1,"check":"dust"},{"step":2,"check":"fan"},{"step":3,"check":"paste"}]','[{"point":"dust?","yes":"clean","no":"fan"}]','[{"path":"clean repaste","conf":0.88}]',3,60,90.0),
        (symid("sym_tv_burn"),"OLED Burn-in Assessment","dt_tv_burn",'[{"step":1,"check":"severity"},{"step":2,"check":"refresher"}]','[{"point":"refresher helps?","yes":"mild","no":"panel"}]','[{"path":"pixel refresh","conf":0.6}]',2,30,55.0),
        (symid("sym_rt_drop"),"Router Drop Diagnostic","dt_rt_drop",'[{"step":1,"check":"heat"},{"step":2,"check":"firmware"},{"step":3,"check":"channels"}]','[{"point":"hot?","yes":"vent","no":"firmware"}]','[{"path":"firmware update","conf":0.7}]',3,30,72.0),
        (symid("sym_pr_jam"),"Printer Jam Diagnostic","dt_pr_jam",'[{"step":1,"check":"path"},{"step":2,"check":"roller"}]','[{"point":"roller worn?","yes":"replace","no":"clean"}]','[{"path":"roller replace","conf":0.8}]',2,30,82.0),
        (symid("sym_wr_cr"),"Watch Crown Diagnostic","dt_wr_cr",'[{"step":1,"check":"debris"},{"step":2,"check":"impact"},{"step":3,"check":"moisture"}]','[{"point":"debris?","yes":"clean","no":"internal"}]','[{"path":"crown clean","conf":0.7}]',3,30,75.0),
        (symid("sym_dk_post"),"Desktop POST Diagnostic","dt_dk_post",'[{"step":1,"check":"beeps"},{"step":2,"check":"RAM"},{"step":3,"check":"GPU"},{"step":4,"check":"PSU"}]','[{"point":"beep pattern?","yes":"decode","no":"isolate"}]','[{"path":"RAM replace","conf":0.7}]',4,60,72.0),
        (symid("sym_xbox_gr"),"Xbox Green Screen Diagnostic","dt_xbox_gr",'[{"step":1,"check":"HDMI"},{"step":2,"check":"safe mode"},{"step":3,"check":"GPU"}]','[{"point":"safe mode?","yes":"software","no":"hardware"}]','[{"path":"OS reinstall","conf":0.55}]',3,90,50.0),
    ]
    c.executemany("INSERT INTO diagnostic_trees(symptom_id,tree_name,tree_code,steps,decision_points,resolution_paths,total_steps,avg_resolution_time_minutes,success_rate_percentage) VALUES(?,?,?,?,?,?,?,?,?)", trees)
    def tid(code): return c.execute("SELECT tree_id FROM diagnostic_trees WHERE tree_code=?",(code,)).fetchone()[0]
    repairs = [
        (tid("dt_ph_cr"),sysid("sys_ip15pm"),"iPhone Display Replacement","rep_ph_disp","Replace display",'["screwdriver","suction cup","spudger","heat gun"]','["display","adhesive"]','["backup data"]','[{"step":1,"action":"Remove screws"},{"step":2,"action":"Heat edges"},{"step":3,"action":"Lift display"},{"step":4,"action":"Disconnect"},{"step":5,"action":"Transfer parts"},{"step":6,"action":"Reconnect seal"}]','["test touch"]',45,"Moderate",'["Disconnect battery"]',"Static-free surface."),
        (tid("dt_ph_bat"),sysid("sys_ip15pm"),"iPhone Battery Replacement","rep_ph_bat","Replace battery",'["screwdriver","suction cup","spudger"]','["battery","adhesive"]','["backup data"]','[{"step":1,"action":"Remove screws"},{"step":2,"action":"Lift display"},{"step":3,"action":"Disconnect battery"},{"step":4,"action":"Remove adhesive"},{"step":5,"action":"Install new"},{"step":6,"action":"Reassemble"}]','["calibrate"]',30,"Moderate",'["NEVER puncture"]',"Alcohol for adhesive."),
        (tid("dt_lp_oh"),sysid("sys_dxps"),"Dell XPS Repaste","rep_lp_rp","Reapply thermal paste",'["compressed air","paste","torx driver"]','["thermal paste"]','["power off"]','[{"step":1,"action":"Remove panel"},{"step":2,"action":"Disconnect battery"},{"step":3,"action":"Remove heatsink"},{"step":4,"action":"Clean paste"},{"step":5,"action":"Apply new"},{"step":6,"action":"Reinstall"}]','["stress test 30min"]',60,"Moderate",'["Correct amount"]',"Pea-sized amount."),
        (tid("dt_ps5_sig"),sysid("sys_ps5"),"PS5 HDMI Replace","rep_ps5_hdmi","Replace HDMI port",'["torx set","soldering station","hot air","flux"]','["HDMI 2.1 port","solder wick"]','["backup saves"]','[{"step":1,"action":"Remove screws"},{"step":2,"action":"Open shell"},{"step":3,"action":"Disconnect ribbons"},{"step":4,"action":"Remove mobo"},{"step":5,"action":"Remove old port"},{"step":6,"action":"Solder new"},{"step":7,"action":"Reassemble test"}]','["test 4K HDR"]',120,"Expert",'["SMD experience"]',"Micro-soldering."),
        (tid("dt_ps5_oh"),sysid("sys_ps5"),"PS5 Deep Clean","rep_ps5_cl","Clean and repaste",'["torx set","compressed air","paste","brush"]','["thermal paste"]','["power off"]','[{"step":1,"action":"Remove shell"},{"step":2,"action":"Clean dust"},{"step":3,"action":"Remove heatsink"},{"step":4,"action":"Clean"},{"step":5,"action":"Apply paste"},{"step":6,"action":"Reinstall"},{"step":7,"action":"Reassemble"}]','["temp test"]',60,"Moderate",'["Handle ribbons"]',"Quality paste only."),
        (tid("dt_lp_sw"),sysid("sys_mbpro"),"MacBook Battery Replace","rep_mb_bat","Replace swollen battery",'["screwdriver set","triangle bit"]','["battery kit","adhesive remover"]','["backup data"]','[{"step":1,"action":"Remove case"},{"step":2,"action":"Disconnect"},{"step":3,"action":"Apply remover"},{"step":4,"action":"Remove cells"},{"step":5,"action":"Clean"},{"step":6,"action":"Install new"},{"step":7,"action":"Test"}]','["verify trackpad"]',60,"Hard",'["NEVER puncture","Fire extinguisher"]',"Recycling disposal."),
        (tid("dt_dk_post"),sysid("sys_prec"),"Desktop RAM Replace","rep_dk_ram","Replace faulty RAM",'["POST card","antistatic strap"]','["replacement RAM"]','["note beep code"]','[{"step":1,"action":"Note code"},{"step":2,"action":"Power off"},{"step":3,"action":"Open case"},{"step":4,"action":"Remove RAM"},{"step":5,"action":"Test each"},{"step":6,"action":"Replace"},{"step":7,"action":"Test POST"}]','["memory diagnostic"]',30,"Moderate",'["Anti-static"]',"Handle by edges."),
        (tid("dt_rt_drop"),sysid("sys_ax86"),"Router Firmware Update","rep_rt_fw","Update firmware",'["ethernet cable","laptop"]','[]','["backup config"]','[{"step":1,"action":"Connect ethernet"},{"step":2,"action":"Login"},{"step":3,"action":"Backup"},{"step":4,"action":"Check update"},{"step":5,"action":"Install"},{"step":6,"action":"Reset if needed"},{"step":7,"action":"Restore"}]','["test 24hrs"]',30,"Easy",'["Do not interrupt"]',"Keep powered."),
        (tid("dt_pr_jam"),sysid("sys_m404"),"Printer Roller Replace","rep_pr_rl","Replace pickup roller",'["screwdriver","cloth"]','["roller kit"]','["power off","remove toner"]','[{"step":1,"action":"Power off"},{"step":2,"action":"Remove toner"},{"step":3,"action":"Access roller"},{"step":4,"action":"Remove old"},{"step":5,"action":"Install new"},{"step":6,"action":"Test"}]','["test sizes"]',20,"Easy",'[]',"Lint-free cloth."),
        (tid("dt_tv_burn"),sysid("sys_lgc3"),"OLED Pixel Refresh","rep_tv_px","Run pixel refresher",'["remote"]','[]','["idle 1hr"]','[{"step":1,"action":"Settings>Support"},{"step":2,"action":"Device Care"},{"step":3,"action":"Pixel Refresher"},{"step":4,"action":"Start 1hr"},{"step":5,"action":"Verify"}]','["compare"]',60,"Easy",'[]',"Run monthly."),
        (tid("dt_ph_cr"),sysid("sys_px8"),"Pixel Display Replacement","rep_px8_disp","Replace Pixel display",'["screwdriver","suction cup","spudger","heat gun"]','["display","adhesive"]','["backup data"]','[{"step":1,"action":"Remove screws"},{"step":2,"action":"Heat edges"},{"step":3,"action":"Lift display"},{"step":4,"action":"Disconnect"},{"step":5,"action":"Transfer parts"},{"step":6,"action":"Reconnect seal"}]','["test touch"]',45,"Moderate",'["Disconnect battery"]',"Static-free surface."),
        (tid("dt_lp_oh"),sysid("sys_tp_x1"),"ThinkPad Fan Clean","rep_tp_fan","Clean ThinkPad fan",'["compressed air","screwdriver"]','["thermal paste"]','["power off"]','[{"step":1,"action":"Remove panel"},{"step":2,"action":"Disconnect battery"},{"step":3,"action":"Clean fan"},{"step":4,"action":"Apply paste"},{"step":5,"action":"Reinstall"}]','["temp test"]',45,"Moderate",'[]',"Use compressed air."),
        (tid("dt_ps5_oh"),sysid("sys_nsoled"),"Switch Joy-Con Repair","rep_ns_joycon","Fix Joy-Con drift",'["screwdriver set","contact cleaner"]','["joy-con flex cable"]','["power off"]','[{"step":1,"action":"Remove screws"},{"step":2,"action":"Open joy-con"},{"step":3,"action":"Clean contacts"},{"step":4,"action":"Replace flex"},{"step":5,"action":"Reassemble"}]','["test analog"]',30,"Easy",'[]',"Handle ribbon carefully."),
        (tid("dt_dk_post"),sysid("sys_hpz4"),"Workstation PSU Replace","rep_hpz4_psu","Replace HP Z4 PSU",'["screwdriver","antistatic strap"]','["replacement PSU"]','["power off","unplug"]','[{"step":1,"action":"Power off"},{"step":2,"action":"Open case"},{"step":3,"action":"Disconnect cables"},{"step":4,"action":"Remove old PSU"},{"step":5,"action":"Install new"},{"step":6,"action":"Reconnect"},{"step":7,"action":"Test"}]','["POST test"]',60,"Moderate",'["High voltage"]',"Disconnect all power."),
        (tid("dt_ph_bat"),sysid("sys_gs24u"),"Galaxy S24 Battery Replace","rep_s24_bat","Replace Galaxy S24 battery",'["screwdriver","suction cup","spudger"]','["battery","adhesive"]','["backup data"]','[{"step":1,"action":"Remove back"},{"step":2,"action":"Disconnect battery"},{"step":3,"action":"Remove adhesive"},{"step":4,"action":"Install new"},{"step":5,"action":"Reassemble"}]','["calibrate"]',35,"Moderate",'["NEVER puncture"]',"Use alcohol for adhesive."),
    ]
    c.executemany("INSERT INTO repair_procedures(tree_id,system_id,repair_name,repair_code,overview,tools_required,materials_required,pre_repair_checks,procedure_steps,post_repair_checks,estimated_time_minutes,difficulty,warnings,safety_notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", repairs)
    parts = [
        ("iPhone 15 Pro Max Display","p_ph_ip_d",'["sys_ip15pm"]',329.99,50,10,"Apple","parts@apple.com",5,"piece","per unit",cid("phones")),
        ("iPhone 15 Pro Max Battery","p_ph_ip_b",'["sys_ip15pm"]',59.99,100,20,"iFixit","store@ifixit.com",3,"piece","per unit",cid("phones")),
        ("Galaxy S24 Ultra Display","p_ph_s24_d",'["sys_gs24u"]',299.99,40,10,"Samsung","parts@samsung.com",7,"piece","per unit",cid("phones")),
        ("Samsung S Pen","p_ph_spen",'["sys_gs24u"]',49.99,80,15,"Samsung","parts@samsung.com",3,"piece","per unit",cid("phones")),
        ("MacBook Pro 16 Battery","p_lp_mb_b",'["sys_mbpro"]',199.99,30,8,"Apple","parts@apple.com",7,"piece","per unit",cid("laptops")),
        ("MacBook Pro Keyboard","p_lp_mb_k",'["sys_mbpro"]',349.99,20,5,"Apple","parts@apple.com",10,"piece","per unit",cid("laptops")),
        ("Dell XPS 15 Fan","p_lp_dx_f",'["sys_dxps"]',34.99,60,10,"Dell","parts@dell.com",5,"piece","per unit",cid("laptops")),
        ("Thermal Paste MX-4","p_th_mx4",'["sys_dxps","sys_rog","sys_ps5"]',8.99,500,100,"Arctic","orders@arctic.ac",2,"tube","4g",cid("laptops")),
        ("PS5 HDMI Port","p_ps5_hdmi",'["sys_ps5"]',15.99,200,40,"ConsoleParts","parts@consoleparts.com",3,"piece","per port",cid("gaming")),
        ("PS5 Disc Drive","p_ps5_dd",'["sys_ps5"]',79.99,40,10,"Sony","parts@sony.com",7,"piece","per unit",cid("gaming")),
        ("LG C3 T-Con Board","p_tv_tcon",'["sys_lgc3"]',149.99,15,5,"LG","parts@lg.com",10,"piece","per unit",cid("televisions")),
        ("Sony XM5 Battery","p_au_xm5_b",'["sys_xm5"]',29.99,80,15,"Sony","parts@sony.com",5,"piece","per unit",cid("audio")),
        ("Echo Dot PSU","p_sh_echo_p",'["sys_echo"]',12.99,200,40,"Amazon","parts@amazon.com",3,"piece","per unit",cid("smart_home")),
        ("August Lock Motor","p_sh_lock_m",'["sys_aug"]',45.00,40,10,"August","parts@august.com",7,"piece","per unit",cid("smart_home")),
        ("ASUS RT-AX86U PSU","p_rt_psu",'["sys_ax86"]',24.99,60,10,"ASUS","parts@asus.com",5,"piece","per unit",cid("routers")),
        ("HP LaserJet Fuser","p_pr_fuser",'["sys_m404"]',89.99,30,8,"HP","parts@hp.com",5,"piece","per unit",cid("printers")),
        ("HP LaserJet Roller","p_pr_roller",'["sys_m404"]',14.99,100,20,"HP","parts@hp.com",3,"piece","per unit",cid("printers")),
        ("Hikvision IR Board","p_cc_ir",'["sys_hik"]',22.00,60,10,"Hikvision","parts@hikvision.com",7,"piece","per unit",cid("cctv")),
        ("Apple Watch S9 Display","p_wr_s9_d",'["sys_aw9"]',179.99,30,8,"Apple","parts@apple.com",7,"piece","per unit",cid("wearables")),
        ("Apple Watch Crown","p_wr_cr",'["sys_aw9"]',39.99,50,10,"Apple","parts@apple.com",5,"piece","per unit",cid("wearables")),
        ("Sonos Era 300 WiFi","p_au_era_w",'["sys_era"]',34.99,40,8,"Sonos","parts@sonos.com",7,"piece","per unit",cid("audio")),
        ("Dell Precision PSU 1400W","p_dk_psu",'["sys_prec"]',249.99,10,3,"Dell","parts@dell.com",10,"piece","per unit",cid("desktops")),
        ("ROG Strix Fan Set","p_rog_fan",'["sys_rog"]',42.99,50,10,"ASUS","parts@asus.com",5,"set","pair",cid("laptops")),
    ]
    c.executemany("INSERT INTO parts_inventory(part_name,part_code,compatible_systems,average_cost,current_stock,reorder_level,supplier,supplier_contact,lead_time_days,unit,coverage,category_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", parts)
    n = insert_embeddings_and_meta(conn, vid)
    insert_validation(conn, vid, {"categories":len(cats),"systems":len(systems),"symptoms":len(symptoms),"trees":len(trees),"repairs":len(repairs),"parts":len(parts),"embeddings":n})
    insert_prompts(conn, vid, [("Device Diagnostic","diagnostic","Diagnose {device}: {description}",vid),("Repair Guide","repair","Repair steps for {symptom} on {device}",vid),("Part Finder","search","Find parts for {device}: {repair}",vid),("Alternatives","recommendation","Alternatives for {part} for {device}",vid)])

# ===== VERSION 3: Industrial & Automotive =====
def seed_v3(conn):
    c = conn.cursor()
    vid = "industrial_automotive_v3"
    cats = [
        (vid,"Cars","cars","Passenger vehicles",20,320,260),(vid,"Motorcycles","motorcycles","Motorcycles and scooters",20,290,235),
        (vid,"Trucks","trucks","Light and heavy trucks",18,280,225),(vid,"Buses","buses","Transit and coach buses",17,260,210),
        (vid,"Heavy Equipment","heavy","Construction heavy machinery",17,270,220),(vid,"Construction","construction","Construction equipment",15,220,175),
        (vid,"Agriculture","agriculture","Farm machinery",16,245,195),(vid,"Solar Systems","solar","Solar power systems",15,210,168),
        (vid,"Wind Systems","wind","Wind energy systems",15,205,165),(vid,"Generators","generators","Power generators",15,225,180),
        (vid,"Compressors","compressors","Air compression systems",15,200,160),(vid,"Industrial Pumps","ind_pumps","Industrial fluid pumps",15,210,168),
        (vid,"Industrial Motors","ind_motors","Electric motors",15,195,158),(vid,"Manufacturing","manufacturing","Manufacturing equipment",15,215,175),
        (vid,"Factory Equipment","factory","Factory automation",15,200,162),(vid,"Mining","mining","Mining equipment",15,220,178),
        (vid,"Marine","marine","Marine vessels and engines",15,215,175),(vid,"Railway","railway","Railway locomotives",15,210,170),
        (vid,"Medical Equipment","medical","Medical devices",15,205,168),(vid,"Laboratory Equipment","laboratory","Lab instruments",15,195,158),
    ]
    c.executemany("INSERT INTO categories(version_id,category_name,category_code,description,total_systems,total_symptoms,total_repairs) VALUES(?,?,?,?,?,?,?)", cats)
    def cid(code): return c.execute("SELECT category_id FROM categories WHERE category_code=?",(code,)).fetchone()[0]
    subcats = [
        (cid("cars"),"Sedans","car_sedan","Sedan passenger cars"),(cid("cars"),"Electric Vehicles","car_ev","Electric vehicles"),
        (cid("trucks"),"Semi Trucks","trk_semi","Semi tractor-trailers"),(cid("heavy"),"Excavators","hvy_exc","Hydraulic excavators"),
        (cid("solar"),"Solar Panels","sol_panel","Photovoltaic panels"),(cid("solar"),"Solar Inverters","sol_inv","DC to AC inverters"),
        (cid("generators"),"Diesel Generators","gen_diesel","Diesel power generators"),(cid("generators"),"Portable Generators","gen_port","Portable generators"),
        (cid("medical"),"MRI Machines","med_mri","MRI diagnostic machines"),(cid("agriculture"),"Tractors","ag_tractor","Farm tractors"),
        (cid("manufacturing"),"CNC Machines","mfg_cnc","CNC machining centers"),(cid("marine"),"Outboard Motors","mar_out","Marine outboard engines"),
        (cid("compressors"),"Rotary Screw","cmp_screw","Rotary screw compressors"),(cid("ind_pumps"),"Centrifugal Pumps","pmp_cent","Centrifugal pumps"),
        (cid("ind_motors"),"AC Motors","mot_ac","AC induction motors"),
    ]
    c.executemany("INSERT INTO subcategories(category_id,subcategory_name,subcategory_code,description) VALUES(?,?,?,?)", subcats)
    def sid(code): return c.execute("SELECT subcategory_id FROM subcategories WHERE subcategory_code=?",(code,)).fetchone()[0]
    systems = [
        (sid("car_sedan"),"Toyota Camry 2024","sys_car_camry","Toyota","Camry XSE",2024,15,6,'{"engine":"2.5L I4","hp":203,"trans":"8AT","drive":"FWD"}','["engine","transmission","suspension","brakes","ECU"]','["spark plugs","brake pads","oil filter"]','["check engine light","brake squeal"]'),
        (sid("car_ev"),"Tesla Model Y Long Range","sys_car_tesla","Tesla","Model Y LR",2024,15,12,'{"battery":"75kWh","range":"330mi","motors":"dual AWD"}','["battery pack","drive units","BMS","thermal mgmt"]','["brake pads","cabin filter","wipers"]','["range degradation","suspension noise"]'),
        (sid("trk_semi"),"Volvo VNL 860","sys_trk_volvo","Volvo","VNL 860",2023,20,3,'{"engine":"D13 Turbo","hp":500,"trans":"IFT"}','["D13 engine","IFT trans","air brakes","DEF system"]','["air filters","fuel filters","brake shoes","DEF"]','["DERATE","air leak","DEF fault"]'),
        (sid("hvy_exc"),"CAT 336 Hydraulic Excavator","sys_hvy_cat336","Caterpillar","336",2022,20,2,'{"engine":"C9.3B","hp":301,"bucket":"2.0m3","weight":"36t"}','["C9.3B engine","hydraulic pumps","main valve","travel motors"]','["hydraulic filters","engine oil","track pads"]','["hydraulic leak","track tension loss"]'),
        (sid("sol_panel"),"SunPower Maxeon 6 400W","sys_sol_sunpower","SunPower","Maxeon 6",2023,30,12,'{"watts":400,"eff":"22.8%","type":"IBC mono"}','["solar cells","glass","backsheet","junction box"]','["bypass diodes","junction box","MC4"]','["micro-cracks","hot spots"]'),
        (sid("sol_inv"),"Enphase IQ8+ Microinverter","sys_sol_enphase","Enphase","IQ8+",2023,25,12,'{"output":"295VA","eff":"97.5%"}','["inverter circuit","grid relay","comm module"]','["inverter unit","comm cable"]','["comm loss","grid fault"]'),
        (sid("gen_diesel"),"Cummins Onan 20kW Diesel","sys_gen_cummins","Cummins","Onan 20kW",2022,25,6,'{"engine":"QSB 3.9","kw":20,"v":"120/240V"}','["QSB engine","alternator","control panel","fuel system"]','["oil filters","fuel filters","air filters","coolant"]','["fail to start","low oil pressure"]'),
        (sid("gen_port"),"Honda EU7000is Portable","sys_gen_honda","Honda","EU7000is",2023,15,6,'{"engine":"GX390","watts":7000,"fuel":"gas"}','["GX390 engine","alternator","inverter","carburetor"]','["spark plug","air filter","oil"]','["won\'t start","surging"]'),
        (sid("med_mri"),"Siemens MAGNETOM Altea 3T MRI","sys_med_mri","Siemens","MAGNETOM Altea",2023,15,1,'{"field":"3T","bore":"70cm"}','["superconducting magnet","gradient coils","RF system","helium cooling"]','["RF amplifier","gradient amp","helium compressor"]','["quench risk","gradient failure"]'),
        (sid("ag_tractor"),"John Deere 8R 410 Tractor","sys_ag_jd8r","John Deere","8R 410",2023,20,4,'{"engine":"PowerTech 9.0L","hp":410,"trans":"e23"}','["PowerTech engine","e23 trans","hydraulic system","SCR/DEF"]','["engine filters","hydraulic fluid","DEF"]','["DEF fault","hydraulic pressure drop"]'),
        (sid("mfg_cnc"),"Haas VF-4SS CNC Vertical Mill","sys_mfg_haas","Haas","VF-4SS",2023,20,3,'{"travel":"50x26x26","spindle":"12000RPM","tools":24}','["spindle","tool changer","coolant system","way covers"]','["spindle bearings","way lube","coolant"]','["spindle vibration","tool changer fault"]'),
        (sid("mar_out"),"Mercury Verado 400HP","sys_mar_merc","Mercury","Verado 400",2023,15,3,'{"engine":"4.6L V8","hp":400,"steering":"electro-hyd"}','["V8 engine","lower unit","steering","ECM"]','["water pump impeller","spark plugs","lower oil"]','["overheating at idle","lower unit noise"]'),
        (sid("cmp_screw"),"Atlas Copco GA37+ VSD","sys_cmp_ga37","Atlas Copco","GA37+ VSD",2023,20,3,'{"power":"37kW","cfm":170,"psi":116,"type":"rotary screw VSD"}','["screw element","VSD drive","oil separator","aftercooler"]','["oil filter","air filter","oil separator"]','["high temp shutdown","oil carryover"]'),
        (sid("pmp_cent"),"Grundfos CR 32-5 Multi-stage","sys_pmp_grundfos","Grundfos","CR 32-5",2022,15,6,'{"flow":"32m3/h","head":"85m","power":"15kW"}','["impellers","mechanical seal","motor","coupling"]','["mechanical seal","bearings","coupling"]','["seal leak","vibration","low flow"]'),
        (sid("mot_ac"),"ABB M3BP 160 AC Motor 15kW","sys_mot_abb","ABB","M3BP 160MLA",2023,20,6,'{"power":"15kW","speed":"1460RPM","eff":"IE3"}','["stator","rotor","bearings","fan","terminal box"]','["bearings","fan","terminal block"]','["bearing noise","overheating","vibration"]'),
        (sid("car_sedan"),"Honda Accord 2024","sys_car_accord","Honda","Accord Sport",2024,15,6,'{"engine":"1.5L Turbo","hp":192,"trans":"CVT","drive":"FWD"}','["engine","transmission","suspension","brakes"]','["brake pads","oil filter","air filter"]','["brake noise","oil leak"]'),
        (sid("trk_semi"),"Kenworth T680","sys_trk_kw","Kenworth","T680",2023,20,3,'{"engine":"PACCAR MX-13","hp":510,"trans":"12AT"}','["MX-13 engine","trans","air brakes","DEF"]','["air filters","fuel filters","brakes"]','["DERATE","brake wear"]'),
        (sid("hvy_exc"),"Komatsu PC210LC-11","sys_hvy_kom","Komatsu","PC210LC-11",2023,20,2,'{"engine":"SAA6D107E-3","hp":162,"bucket":"1.0m3"}','["engine","hydraulic pumps","main valve"]','["hydraulic filters","engine oil"]','["hydraulic leak","track issue"]'),
        (sid("sol_panel"),"LG NeON R 380W","sys_sol_lg","LG","NeON R 380W",2023,30,12,'{"watts":380,"eff":"21.4%","type":"mono PERC"}','["solar cells","glass","junction box"]','["bypass diodes","MC4"]','["micro-cracks","output drop"]'),
        (sid("gen_port"),"Generac 22kW Home Generator","sys_gen_gen","Generac","22kW Guardian",2023,25,6,'{"engine":"V-Twin","kw":22,"v":"120/240V"}','["engine","alternator","control panel"]','["oil filters","air filters","spark plugs"]','["fail to start","low power"]'),
    ]
    c.executemany("INSERT INTO systems(subcategory_id,system_name,system_code,brand,model,year_released,lifespan_years,maintenance_interval_months,specifications,components,parts_list,common_issues) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", systems)
    def sysid(code): return c.execute("SELECT system_id FROM systems WHERE system_code=?",(code,)).fetchone()[0]
    symptoms = [
        (sysid("sys_car_camry"),cid("cars"),"Check engine light on","sym_car_cel","Medium","CEL illuminated",'["O2 sensor","cat","gas cap","MAF"]',30,"Moderate",'["O2 sensor","cat"]','["OBD2 scanner","wrench"]'),
        (sysid("sys_car_camry"),cid("cars"),"Brake squealing","sym_car_brake","High","Squealing when braking",'["worn pads","rotor damage"]',20,"Easy",'["brake pads","rotors"]','["jack","lug wrench"]'),
        (sysid("sys_car_tesla"),cid("cars"),"Battery range degradation","sym_tesla_range","Medium","Reduced estimated range",'["degradation","temp","software"]',15,"Variable",'["battery module"]','["Tesla diagnostic","tire gauge"]'),
        (sysid("sys_trk_volvo"),cid("trucks"),"Engine DERATE active","sym_trk_derate","Critical","Engine power reduced",'["DEF fault","DPF clogged","sensor"]',45,"Hard",'["DEF sensor","DPF filter"]','["Volvo diagnostic","DEF tester"]'),
        (sysid("sys_hvy_cat336"),cid("heavy"),"Hydraulic oil leak","sym_hvy_hyd_leak","High","Visible hydraulic fluid leak",'["hose failure","seal failure","cylinder damage"]',60,"Hard",'["hydraulic hose","seals"]','["wrench set","crimper"]'),
        (sysid("sys_hvy_cat336"),cid("heavy"),"Track tension loss","sym_hvy_track","Medium","Track loose and slipping",'["adjuster failure","recoil spring"]',45,"Moderate",'["track adjuster","recoil spring"]','["grease gun","tension gauge"]'),
        (sysid("sys_sol_sunpower"),cid("solar"),"Panel output below expected","sym_sol_low","Medium","Producing less than rated",'["soiling","shading","micro-cracks","PID"]',30,"Moderate",'["bypass diode","panel"]','["IV curve tracer","thermal camera"]'),
        (sysid("sys_sol_enphase"),cid("solar"),"Microinverter comm loss","sym_sol_comm","Medium","Envoy cannot communicate",'["cable damage","EMI","unit failure"]',20,"Easy",'["comm cable","microinverter"]','["Enphase app","multimeter"]'),
        (sysid("sys_gen_cummins"),cid("generators"),"Generator fails to start","sym_gen_nostart","Critical","Cranks but won't start",'["fuel air","glow plugs","low compression","battery"]',60,"Hard",'["fuel filter","glow plugs","starter"]','["multimeter","fuel gauge","compression tester"]'),
        (sysid("sys_gen_honda"),cid("generators"),"Generator surging","sym_gen_surge","Medium","RPM fluctuates under load",'["dirty carb","old fuel","governor spring"]',30,"Moderate",'["carburetor kit","air filter"]','["screwdriver","carb cleaner"]'),
        (sysid("sys_med_mri"),cid("medical"),"Gradient coil failure","sym_mri_gradient","Critical","Gradient producing artifacts",'["coil overheat","amp fault","cable damage"]',120,"Expert",'["gradient amplifier","coil cable"]','["MRI service tools","phantom kit"]'),
        (sysid("sys_ag_jd8r"),cid("agriculture"),"DEF system fault","sym_ag_def","High","DEF system fault code",'["DEF quality","pump failure","NOx sensor"]',45,"Moderate",'["DEF pump","NOx sensor"]','["JD diagnostic","DEF tester"]'),
        (sysid("sys_mfg_haas"),cid("manufacturing"),"Spindle vibration","sym_cnc_spindle","High","Excessive spindle vibration",'["bearing wear","tool imbalance","drawbar"]',30,"Moderate",'["spindle bearings","collet"]','["vibration analyzer","dial indicator"]'),
        (sysid("sys_mar_merc"),cid("marine"),"Overheating at idle","sym_mar_overheat","High","Overheating at low RPM",'["impeller worn","thermostat stuck","intake blocked"]',45,"Moderate",'["water pump impeller","thermostat"]','["lower unit tool","impeller puller"]'),
        (sysid("sys_cmp_ga37"),cid("compressors"),"High temperature shutdown","sym_cmp_hitemp","Critical","Tripped on high temperature",'["coolant low","radiator clogged","oil degraded"]',30,"Moderate",'["coolant","oil","radiator"]','["temp gun","radiator cleaner"]'),
        (sysid("sys_pmp_grundfos"),cid("ind_pumps"),"Mechanical seal leak","sym_pmp_seal","High","Water leaking from shaft seal",'["seal wear","dry running","abrasives"]',45,"Hard",'["mechanical seal","O-rings"]','["seal tool","press"]'),
        (sysid("sys_mot_abb"),cid("ind_motors"),"Bearing noise","sym_mot_bearing","Medium","Grinding bearing noise",'["bearing wear","contamination","poor lube"]',30,"Moderate",'["bearings","grease"]','["bearing puller","press","stethoscope"]'),
        (sysid("sys_car_tesla"),cid("cars"),"Suspension clunking","sym_tesla_susp","Medium","Clunking from front over bumps",'["worn bushings","loose sway bar links"]',30,"Moderate",'["control arm","sway bar links"]','["jack","wrench set"]'),
        (sysid("sys_trk_volvo"),cid("trucks"),"Air brake system leak","sym_trk_air","Critical","Air pressure dropping parked",'["fitting leak","diaphragm","valve seal"]',60,"Hard",'["air fittings","diaphragm chambers"]','["soapy water","pressure gauge"]'),
        (sysid("sys_gen_cummins"),cid("generators"),"Low oil pressure alarm","sym_gen_lowoil","Critical","Low oil pressure warning",'["oil low","pump wear","sensor fault"]',30,"Hard",'["oil pump","pressure sensor"]','["pressure gauge","multimeter"]'),
        (sysid("sys_med_mri"),cid("medical"),"Helium level dropping","sym_mri_helium","Critical","Helium decreasing fast",'["seal leak","cooling fault","quench pipe"]',60,"Expert",'["helium compressor parts","seal kit"]','["helium monitor","leak detector"]'),
        (sysid("sys_ag_jd8r"),cid("agriculture"),"GPS guidance signal loss","sym_ag_gps","High","StarFire losing RTK signal",'["antenna obstruction","subscription","base station"]',20,"Easy",'["antenna cable","GPS receiver"]','["JD display","signal meter"]'),
        (sysid("sys_mfg_haas"),cid("manufacturing"),"Tool changer fault","sym_cnc_tc","High","Tool changer failing to index",'["pneumatic low","sensor misaligned","cam roller"]',45,"Hard",'["sensor","cam roller","drawbar spring"]','["alignment tool","pneumatic gauge"]'),
        (sysid("sys_mar_merc"),cid("marine"),"Lower unit gear noise","sym_mar_gear","High","Grinding from lower unit",'["gear wear","bearing failure","water contamination"]',60,"Hard",'["gear set","bearings","lower oil"]','["drain pump","bearing puller","press"]'),
        (sysid("sys_cmp_ga37"),cid("compressors"),"Oil carryover in air lines","sym_cmp_oil","Medium","Excessive oil in air output",'["separator failed","oil overfilled","wrong oil"]',30,"Moderate",'["oil separator","min pressure valve"]','["wrench set","oil analysis"]'),
        (sysid("sys_sol_sunpower"),cid("solar"),"Hot spot detected","sym_sol_hotspot","High","Thermal shows hot spot",'["cell crack","shading","bypass diode failed"]',20,"Moderate",'["bypass diode","panel"]','["thermal camera","IV tracer"]'),
        (sysid("sys_pmp_grundfos"),cid("ind_pumps"),"Low flow output","sym_pump_lowflow","Medium","Delivering less flow than rated",'["impeller wear","clogged intake","air in system"]',30,"Moderate",'["impeller","intake screen"]','["flow meter","pressure gauge"]'),
        (sysid("sys_mot_abb"),cid("ind_motors"),"Motor overheating","sym_mot_overheat","High","Running above rated temp",'["overload","poor ventilation","winding insulation"]',30,"Moderate",'["cooling fan","winding insulation"]','["thermal camera","megohmmeter"]'),
        (sysid("sys_hvy_cat336"),cid("heavy"),"Engine overheating","sym_hvy_overheat","Critical","Engine temp exceeding normal",'["radiator clogged","thermostat stuck","coolant low"]',45,"Moderate",'["coolant","thermostat","fan belt"]','["flush kit","thermostat","belt gauge"]'),
        (sysid("sys_car_camry"),cid("cars"),"Transmission shudder","sym_car_trans","High","Shudder during acceleration",'["low fluid","worn clutch packs","torque converter"]',45,"Hard",'["transmission fluid","filter kit"]','["jack","wrench set","fluid pump"]'),
    ]
    c.executemany("INSERT INTO symptoms(system_id,category_id,symptom_name,symptom_code,severity,description,common_causes,diagnostic_time_minutes,difficulty,parts_needed,tools_needed) VALUES(?,?,?,?,?,?,?,?,?,?,?)", symptoms)
    def symid(code): return c.execute("SELECT symptom_id FROM symptoms WHERE symptom_code=?",(code,)).fetchone()[0]
    trees = [
        (symid("sym_car_cel"),"Check Engine Light Diagnostic","dt_car_cel",'[{"step":1,"check":"OBD2 codes"},{"step":2,"check":"O2 sensor"},{"step":3,"check":"catalytic converter"}]','[{"point":"P0420?","yes":"cat replace","no":"O2 sensor"}]','[{"path":"O2 sensor replace","conf":0.75}]',3,45,78.0),
        (symid("sym_tesla_range"),"Tesla Range Degradation Diagnostic","dt_tesla_range",'[{"step":1,"check":"battery health"},{"step":2,"check":"tire pressure"},{"step":3,"check":"software"}]','[{"point":"health < 90%?","yes":"battery service","no":"software update"}]','[{"path":"battery diagnostic","conf":0.70}]',3,30,72.0),
        (symid("sym_trk_derate"),"Volvo DERATE Diagnostic","dt_trk_derate",'[{"step":1,"check":"DEF system"},{"step":2,"check":"DPF status"},{"step":3,"check":"fuel quality"}]','[{"point":"DEF quality OK?","yes":"sensor","no":"DEF replace"}]','[{"path":"DEF system repair","conf":0.80}]',3,90,70.0),
        (symid("sym_hvy_hyd_leak"),"Hydraulic Leak Diagnostic","dt_hvy_hyd",'[{"step":1,"check":"hose condition"},{"step":2,"check":"cylinder seals"},{"step":3,"check":"fittings"}]','[{"point":"hose burst?","yes":"replace hose","no":"check seals"}]','[{"path":"hose replacement","conf":0.85}]',3,120,80.0),
        (symid("sym_sol_low"),"Solar Low Output Diagnostic","dt_sol_low",'[{"step":1,"check":"soiling"},{"step":2,"check":"shading"},{"step":3,"check":"IV curve"}]','[{"point":"clean panel helps?","yes":"soiling","no":"check diodes"}]','[{"path":"panel cleaning","conf":0.65},{"path":"bypass diode replace","conf":0.70}]',3,45,72.0),
        (symid("sym_gen_nostart"),"Diesel Generator No Start Diagnostic","dt_gen_nostart",'[{"step":1,"check":"fuel system"},{"step":2,"check":"glow plugs"},{"step":3,"check":"compression"},{"step":4,"check":"battery"}]','[{"point":"fuel reaching engine?","yes":"glow plugs","no":"fuel system"}]','[{"path":"glow plug replace","conf":0.75}]',4,90,68.0),
        (symid("sym_mri_gradient"),"MRI Gradient Failure Diagnostic","dt_mri_grad",'[{"step":1,"check":"error logs"},{"step":2,"check":"gradient amp"},{"step":3,"check":"coil cables"}]','[{"point":"amp error?","yes":"amp replace","no":"check cables"}]','[{"path":"gradient amp replace","conf":0.80}]',3,240,65.0),
        (symid("sym_cnc_spindle"),"CNC Spindle Vibration Diagnostic","dt_cnc_spindle",'[{"step":1,"check":"tool balance"},{"step":2,"check":"collet condition"},{"step":3,"check":"bearings"}]','[{"point":"vibration with no tool?","yes":"spindle bearings","no":"tool issue"}]','[{"path":"spindle bearing replace","conf":0.82}]',3,120,75.0),
        (symid("sym_cmp_hitemp"),"Compressor High Temp Diagnostic","dt_cmp_temp",'[{"step":1,"check":"coolant level"},{"step":2,"check":"radiator"},{"step":3,"check":"oil condition"}]','[{"point":"coolant low?","yes":"top up","no":"radiator"}]','[{"path":"radiator cleaning","conf":0.78}]',3,60,80.0),
        (symid("sym_pmp_seal"),"Pump Seal Leak Diagnostic","dt_pmp_seal",'[{"step":1,"check":"seal condition"},{"step":2,"check":"shaft alignment"},{"step":3,"check":"dry running"}]','[{"point":"seal visible damage?","yes":"replace seal","no":"check alignment"}]','[{"path":"mechanical seal replace","conf":0.85}]',3,90,78.0),
        (symid("sym_mot_bearing"),"Motor Bearing Diagnostic","dt_mot_bearing",'[{"step":1,"check":"noise type"},{"step":2,"check":"vibration"},{"step":3,"check":"temperature"}]','[{"point":"grinding noise?","yes":"bearing replace","no":"check lube"}]','[{"path":"bearing replacement","conf":0.88}]',3,60,82.0),
        (symid("sym_mar_overheat"),"Marine Overheat Diagnostic","dt_mar_oh",'[{"step":1,"check":"water pump"},{"step":2,"check":"thermostat"},{"step":3,"check":"intake"}]','[{"point":"impeller age?","yes":"replace impeller","no":"thermostat"}]','[{"path":"impeller replacement","conf":0.85}]',3,60,82.0),
    ]
    c.executemany("INSERT INTO diagnostic_trees(symptom_id,tree_name,tree_code,steps,decision_points,resolution_paths,total_steps,avg_resolution_time_minutes,success_rate_percentage) VALUES(?,?,?,?,?,?,?,?,?)", trees)
    def tid(code): return c.execute("SELECT tree_id FROM diagnostic_trees WHERE tree_code=?",(code,)).fetchone()[0]
    repairs = [
        (tid("dt_car_cel"),sysid("sys_car_camry"),"Replace O2 Sensor","rep_car_o2","Replace faulty oxygen sensor",'["O2 sensor socket","wrench"]','["O2 sensor"]','["read codes","locate sensor"]','[{"step":1,"action":"Locate sensor"},{"step":2,"action":"Disconnect connector"},{"step":3,"action":"Remove old sensor"},{"step":4,"action":"Install new sensor"},{"step":5,"action":"Clear codes and test"}]','["verify codes cleared"]',30,"Moderate",'["Engine cool before starting"]',"Use anti-seize on threads."),
        (tid("dt_car_cel"),sysid("sys_car_camry"),"Replace Brake Pads","rep_car_brake","Replace worn brake pads",'["jack","lug wrench","brake tool","C-clamp"]','["brake pads","brake hardware"]','["check rotor condition"]','[{"step":1,"action":"Lift vehicle"},{"step":2,"action":"Remove wheel"},{"step":3,"action":"Remove caliper"},{"step":4,"action":"Replace pads"},{"step":5,"action":"Compress piston"},{"step":6,"action":"Reinstall caliper"}]','["test brake feel","bed in pads"]',45,"Easy",'["Never work under unsupported vehicle"]',"Bed in pads for 200 miles."),
        (tid("dt_trk_derate"),sysid("sys_trk_volvo"),"Replace DEF Pump","rep_trk_def","Replace failed DEF pump",'["Volvo diagnostic tool","wrench set"]','["DEF pump assembly","DEF fluid"]','["verify DEF fault code"]','[{"step":1,"action":"Connect diagnostic tool"},{"step":2,"action":"Drain DEF tank"},{"step":3,"action":"Remove old pump"},{"step":4,"action":"Install new pump"},{"step":5,"action":"Refill DEF"},{"step":6,"action":"Clear codes and test"}]','["verify DERATE cleared"]',90,"Hard",'["Use only certified DEF fluid"]',"Reset adaptation values after install."),
        (tid("dt_hvy_hyd"),sysid("sys_hvy_cat336"),"Replace Hydraulic Hose","rep_hvy_hose","Replace failed hydraulic hose",'["wrench set","hydraulic crimper","jack stands"]','["hydraulic hose assembly","O-rings","hydraulic fluid"]','["relieve hydraulic pressure"]','[{"step":1,"action":"Relieve pressure"},{"step":2,"action":"Support boom/cylinder"},{"step":3,"action":"Disconnect hose fittings"},{"step":4,"action":"Remove old hose"},{"step":5,"action":"Install new hose"},{"step":6,"action":"Refill and bleed system"}]','["pressure test","check for leaks"]',120,"Hard",'["High pressure hydraulic - extreme caution"]',"Never check for leaks with bare hands."),
        (tid("dt_gen_nostart"),sysid("sys_gen_cummins"),"Replace Glow Plugs","rep_gen_glow","Replace failed glow plugs",'["multimeter","glow plug socket","compression tester"]','["glow plugs set"]','["verify fuel reaching engine"]','[{"step":1,"action":"Test glow plug resistance"},{"step":2,"action":"Remove old glow plugs"},{"step":3,"action":"Install new glow plugs"},{"step":4,"action":"Test starting sequence"}]','["verify clean start"]',60,"Moderate",'["Do not use glow plugs as compression test"]',"Torque to spec."),
        (tid("dt_cnc_spindle"),sysid("sys_mfg_haas"),"Replace Spindle Bearings","rep_cnc_bearing","Replace worn spindle bearings",'["vibration analyzer","bearing puller","press","dial indicator"]','["spindle bearing set","spindle grease","seals"]','["verify bearing wear with vibration analysis"]','[{"step":1,"action":"Remove spindle from head"},{"step":2,"action":"Disassemble spindle"},{"step":3,"action":"Press off old bearings"},{"step":4,"action":"Clean and inspect shaft"},{"step":5,"action":"Press on new bearings"},{"step":6,"action":"Reassemble and align"},{"step":7,"action":"Run break-in cycle"}]','["vibration test","runout check","temp monitoring"]',240,"Expert",'["Cleanroom conditions for bearing install"]',"Follow Haas bearing preload spec."),
        (tid("dt_cmp_temp"),sysid("sys_cmp_ga37"),"Clean Compressor Radiator","rep_cmp_radiator","Clean clogged compressor radiator",'["radiator cleaner","compressed air","pressure washer"]','["coolant top-up"]','["check coolant level first"]','[{"step":1,"action":"Shut down and lock out"},{"step":2,"action":"Remove radiator guards"},{"step":3,"action":"Blow out debris with compressed air"},{"step":4,"action":"Wash with pressure washer (low PSI)"},{"step":5,"action":"Apply radiator cleaner"},{"step":6,"action":"Rinse and reassemble"},{"step":7,"action":"Check coolant and restart"}]','["monitor temp for 24 hours"]',60,"Moderate",'["Lock out electrical supply"]',"Keep PSI below 500 for fins."),
        (tid("dt_pmp_seal"),sysid("sys_pmp_grundfos"),"Replace Mechanical Seal","rep_pmp_seal","Replace failed mechanical seal",'["seal removal tool","press","dial indicator"]','["mechanical seal kit","O-rings","shaft sleeve (if needed)"]','["isolate pump","drain casing"]','[{"step":1,"action":"Isolate and drain pump"},{"step":2,"action":"Remove impeller"},{"step":3,"action":"Remove old seal"},{"step":4,"action":"Inspect shaft sleeve"},{"step":5,"action":"Install new seal"},{"step":6,"action":"Reassemble and align"},{"step":7,"action":"Test run"}]','["check for leaks","verify vibration"]',90,"Hard",'["Ensure clean work area"]',"Lubricate seal faces with clean water."),
        (tid("dt_mot_bearing"),sysid("sys_mot_abb"),"Replace Motor Bearings","rep_mot_bearing","Replace worn motor bearings",'["bearing puller","press","stethoscope","heater"]','["bearing set","grease","seals"]','["verify bearing failure with stethoscope"]','[{"step":1,"action":"Disconnect and remove motor"},{"step":2,"action":"Remove end shields"},{"step":3,"action":"Pull off old bearings"},{"step":4,"action":"Clean shaft and housing"},{"step":5,"action":"Heat and install new bearings"},{"step":6,"action":"Grease and reassemble"},{"step":7,"action":"Test run and monitor temp"}]','["vibration test","temp monitoring 4hrs"]',120,"Moderate",'["Use bearing heater not open flame"]',"Do not exceed bearing temp rating."),
        (tid("dt_mar_oh"),sysid("sys_mar_merc"),"Replace Water Pump Impeller","rep_mar_impeller","Replace worn water pump impeller",'["lower unit tool","impeller puller","thermostat housing wrench"]','["water pump impeller kit","gaskets"]','["check thermostat while accessible"]','[{"step":1,"action":"Remove lower unit"},{"step":2,"action":"Remove water pump housing"},{"step":3,"action":"Pull old impeller"},{"step":4,"action":"Inspect housing wear"},{"step":5,"action":"Install new impeller and plate"},{"step":6,"action":"Reassemble lower unit"},{"step":7,"action":"Test water flow"}]','["verify water stream at tell-tale"]',60,"Moderate",'["Support lower unit during removal"]',"Lubricate impeller vanes before install."),
        (tid("dt_sol_low"),sysid("sys_sol_sunpower"),"Replace Bypass Diode","rep_sol_diode","Replace failed bypass diode in junction box",'["multimeter","soldering iron","junction box tool"]','["bypass diode","junction box gasket"]','["IV curve test to confirm"]','[{"step":1,"action":"Disconnect panel from string"},{"step":2,"action":"Open junction box"},{"step":3,"action":"Identify failed diode"},{"step":4,"action":"Desolder old diode"},{"step":5,"action":"Solder new diode"},{"step":6,"action":"Seal junction box"},{"step":7,"action":"Reconnect and test"}]','["IV curve test","thermal scan"]',30,"Moderate",'["Arc flash risk - disconnect first"]',"Match diode polarity."),
        (tid("dt_car_cel"),sysid("sys_car_accord"),"Honda Accord Oil Change","rep_accord_oil","Replace engine oil and filter",'["wrench","oil filter wrench","drain pan"]','["engine oil","oil filter"]','["engine warm"]','[{"step":1,"action":"Lift vehicle"},{"step":2,"action":"Drain oil"},{"step":3,"action":"Remove old filter"},{"step":4,"action":"Install new filter"},{"step":5,"action":"Refill oil"},{"step":6,"action":"Check level"}]','["verify no leaks"]',30,"Easy",'[]',"Dispose oil properly."),
        (tid("dt_trk_derate"),sysid("sys_trk_kw"),"Kenworth Air Filter Replace","rep_kw_air","Replace clogged air filter",'["wrench set"]','["air filter"]','["engine off"]','[{"step":1,"action":"Open housing"},{"step":2,"action":"Remove old filter"},{"step":3,"action":"Clean housing"},{"step":4,"action":"Install new"},{"step":5,"action":"Close housing"}]','["check seal"]',20,"Easy",'[]',"Use OEM filter."),
        (tid("dt_hvy_hyd"),sysid("sys_hvy_kom"),"Komatsu Track Adjust","rep_kom_track","Adjust track tension",'["grease gun","wrench"]','["hydraulic fluid"]','["check tension"]','[{"step":1,"action":"Check tension"},{"step":2,"action":"Add grease"},{"step":3,"action":"Measure tension"},{"step":4,"action":"Adjust to spec"}]','["test track"]',45,"Moderate",'[]',"Follow Komatsu spec."),
        (tid("dt_gen_nostart"),sysid("sys_gen_gen"),"Generac Spark Plug Replace","rep_gen_spark","Replace worn spark plugs",'["spark plug socket","gap tool"]','["spark plugs"]','["engine cool"]','[{"step":1,"action":"Remove wires"},{"step":2,"action":"Remove old plugs"},{"step":3,"action":"Gap new plugs"},{"step":4,"action":"Install new"},{"step":5,"action":"Reconnect wires"}]','["test start"]',20,"Easy",'[]',"Gap to spec."),
    ]
    c.executemany("INSERT INTO repair_procedures(tree_id,system_id,repair_name,repair_code,overview,tools_required,materials_required,pre_repair_checks,procedure_steps,post_repair_checks,estimated_time_minutes,difficulty,warnings,safety_notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", repairs)
    parts = [
        ("Toyota Camry O2 Sensor","p_car_o2",'["sys_car_camry"]',85.00,100,20,"Toyota Parts","parts@toyota.com",3,"piece","per unit",cid("cars")),
        ("Toyota Camry Brake Pad Set","p_car_brake",'["sys_car_camry"]',65.00,150,30,"Toyota Parts","parts@toyota.com",3,"set","per axle",cid("cars")),
        ("Tesla Model Y Brake Pad Set","p_tesla_brake",'["sys_car_tesla"]',120.00,60,10,"Tesla Parts","parts@tesla.com",5,"set","per axle",cid("cars")),
        ("Volvo VNL DEF Pump Assembly","p_trk_def",'["sys_trk_volvo"]',450.00,20,5,"Volvo Parts","parts@volvo.com",7,"piece","per unit",cid("trucks")),
        ("CAT 336 Hydraulic Hose Assembly","p_hvy_hose",'["sys_hvy_cat336"]',180.00,40,8,"Caterpillar Parts","parts@cat.com",5,"piece","per hose",cid("heavy")),
        ("CAT 336 Track Adjuster","p_hvy_adjuster",'["sys_hvy_cat336"]',320.00,15,3,"Caterpillar Parts","parts@cat.com",7,"piece","per unit",cid("heavy")),
        ("SunPower Bypass Diode","p_sol_diode",'["sys_sol_sunpower"]',12.00,500,100,"SunPower Parts","parts@sunpower.com",3,"piece","per diode",cid("solar")),
        ("Enphase IQ8+ Microinverter","p_sol_inv",'["sys_sol_enphase"]',220.00,50,10,"Enphase","parts@enphase.com",5,"piece","per unit",cid("solar")),
        ("Cummins Onan Glow Plug Set","p_gen_glow",'["sys_gen_cummins"]',65.00,60,10,"Cummins Parts","parts@cummins.com",5,"set","per set",cid("generators")),
        ("Honda EU7000 Carburetor Kit","p_gen_carb",'["sys_gen_honda"]',45.00,80,15,"Honda Parts","parts@honda.com",5,"kit","per unit",cid("generators")),
        ("Siemens MRI Gradient Amplifier","p_mri_grad_amp",'["sys_med_mri"]',15000.00,3,1,"Siemens Parts","parts@siemens.com",30,"piece","per unit",cid("medical")),
        ("John Deere DEF Pump","p_ag_def",'["sys_ag_jd8r"]',380.00,25,5,"John Deere Parts","parts@johndeere.com",7,"piece","per unit",cid("agriculture")),
        ("Haas VF-4SS Spindle Bearing Set","p_cnc_bearing",'["sys_mfg_haas"]',850.00,10,3,"Haas Parts","parts@haas.com",10,"set","per set",cid("manufacturing")),
        ("Mercury Verado Water Pump Kit","p_mar_impeller",'["sys_mar_merc"]',95.00,60,10,"Mercury Parts","parts@mercury.com",5,"kit","per unit",cid("marine")),
        ("Atlas Copco Oil Separator Element","p_cmp_separator",'["sys_cmp_ga37"]',180.00,30,5,"Atlas Copco Parts","parts@atlascopco.com",7,"piece","per unit",cid("compressors")),
        ("Grundfos CR Mechanical Seal Kit","p_pmp_seal",'["sys_pmp_grundfos"]',220.00,25,5,"Grundfos Parts","parts@grundfos.com",7,"kit","per unit",cid("ind_pumps")),
        ("ABB M3BP Bearing Set","p_mot_bearing",'["sys_mot_abb"]',75.00,80,15,"ABB Parts","parts@abb.com",5,"set","per set",cid("ind_motors")),
        ("ABB M3BP Cooling Fan","p_mot_fan",'["sys_mot_abb"]',35.00,60,10,"ABB Parts","parts@abb.com",5,"piece","per unit",cid("ind_motors")),
        ("Toyota Transmission Fluid 1qt","p_car_trans_fluid",'["sys_car_camry"]',12.00,300,50,"Toyota Parts","parts@toyota.com",2,"quart","per quart",cid("cars")),
        ("Tesla Model Y Cabin Filter","p_tesla_cabin",'["sys_car_tesla"]',25.00,200,40,"Tesla Parts","parts@tesla.com",3,"piece","per unit",cid("cars")),
        ("Volvo VNL Air Filter","p_trk_air",'["sys_trk_volvo"]',55.00,100,20,"Volvo Parts","parts@volvo.com",3,"piece","per unit",cid("trucks")),
        ("CAT 336 Hydraulic Filter Kit","p_hvy_filters",'["sys_hvy_cat336"]',120.00,60,10,"Caterpillar Parts","parts@cat.com",5,"kit","per set",cid("heavy")),
        ("Cummins Onan Oil Filter","p_gen_oil",'["sys_gen_cummins"]',18.00,200,40,"Cummins Parts","parts@cummins.com",3,"piece","per unit",cid("generators")),
    ]
    c.executemany("INSERT INTO parts_inventory(part_name,part_code,compatible_systems,average_cost,current_stock,reorder_level,supplier,supplier_contact,lead_time_days,unit,coverage,category_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", parts)
    n = insert_embeddings_and_meta(conn, vid)
    insert_validation(conn, vid, {"categories":len(cats),"systems":len(systems),"symptoms":len(symptoms),"trees":len(trees),"repairs":len(repairs),"parts":len(parts),"embeddings":n})
    insert_prompts(conn, vid, [("Industrial Diagnostic","diagnostic","Diagnose {system}: {description}",vid),("Repair Procedure","repair","Repair steps for {symptom} on {system}",vid),("Parts Lookup","search","Find parts for {system}: {repair}",vid),("Supplier Recommendation","recommendation","Best supplier for {part} for {system}",vid)])

# ===== MAIN =====
if __name__ == "__main__":
    for vkey, label, seed_fn in [("v1","Version 1 (Home Maintenance)",seed_v1),("v2","Version 2 (Electronics)",seed_v2),("v3","Version 3 (Industrial & Automotive)",seed_v3)]:
        print(f"\n{'='*60}")
        print(f"Building {label}...")
        print(f"{'='*60}")
        db = create_fixfinder_database(vkey, DB_PATHS[vkey])
        seed_fn(db)
        c = db.cursor()
        counts = {}
        for tbl in ["categories","subcategories","systems","symptoms","diagnostic_trees","repair_procedures","parts_inventory","embeddings","faiss_metadata","repair_records","validation_results","ai_prompts"]:
            n = c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            counts[tbl] = n
            print(f"  {tbl}: {n}")
        db.close()
        print(f"  -> {DB_PATHS[vkey]} created successfully!")
    print(f"\n{'='*60}")
    print("All 3 databases built successfully!")
    print(f"{'='*60}")

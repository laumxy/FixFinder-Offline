from app.nlp.preprocess import ProcessedInput

# ── v3 industry keyword map ────────────────────────────────────────────────────
# Each entry maps a canonical category slug to a set of signal words.
# Words should be lower-case, no punctuation (matches the normalised token stream).
CATEGORY_KEYWORDS: dict[str, set[str]] = {
    # ── Version 1 ─────────────────────────────────────────────────────────────
    "roofing": {
        "roof", "ceiling", "shingle", "gutter", "flashing", "attic", "tile",
        "waterproofing", "rafter", "soffit", "fascia", "ridge", "valley",
        "downspout", "skylight", "leak", "rain", "slate", "metal-roof",
        "asphalt", "membrane", "truss", "joist", "eaves",
    },
    "plumbing": {
        "tap", "faucet", "pipe", "sink", "toilet", "drain", "valve", "plumbing",
        "sewage", "sewerage", "clog", "blockage", "water-heater", "geyser",
        "overflow", "flush", "cistern", "septic", "manhole", "trap",
        "water", "leaking", "leak", "burst", "pressure", "heater",
    },
    "electrical": {
        "breaker", "socket", "outlet", "wire", "wiring", "switch", "voltage",
        "circuit", "fuse", "earthing", "neutral", "live", "power", "current",
        "transformer", "inverter", "mcb", "rcd", "gfci", "surge", "panel",
        "light", "bulb", "lamp", "plug", "cord", "dimmer",
    },
    "appliances": {
        "fridge", "refrigerator", "washer", "dryer", "oven", "stove", "freezer",
        "microwave", "dishwasher", "laundry", "washing", "machine", "cooker",
        "blender", "kettle", "iron", "heater", "fan",
    },

    # ── Version 2 ─────────────────────────────────────────────────────────────
    "vehicles": {
        "car", "truck", "van", "bus", "gearbox", "transmission",
        "alternator", "starter", "ignition", "clutch", "brakes", "suspension",
        "radiator", "coolant", "exhaust", "turbo", "injector", "timing",
        "differential", "axle", "driveshaft", "catalytic", "obd",
        "vehicle", "auto", "automobile", "tyre", "tire", "wheel",
        "sedan", "suv", "pickup", "hatchback", "coupe", "minivan",
        "engine", "motor", "fuel", "petrol", "diesel", "brake",
        "steering", "bumper", "windshield", "headlight", "taillight",
        "radiator", "muffler", "spark-plug", "oil", "flat", "puncture",
        "alignment", "balancing", "hub", "rim", "lug", "jack",
    },
    "motorcycles": {
        "motorcycle", "motorbike", "bike", "scooter", "moped", "carburetor",
        "throttle", "chain", "sprocket", "kickstart", "piston", "cylinder",
        "two-stroke", "four-stroke", "clutch-lever", "brake-lever",
        "tyre", "tire", "wheel", "handlebar", "fork", "exhaust-pipe",
    },
    "phones": {
        "phone", "smartphone", "mobile", "screen", "display", "touch",
        "charging-port", "sim", "speaker", "microphone", "back-camera",
        "front-camera", "battery-swollen", "imei", "android", "ios",
        "charger", "charging", "battery", "cracked", "freeze", "restart",
    },
    "tablets": {
        "tablet", "ipad", "stylus", "digitizer", "tablet-screen",
        "tablet-battery", "tablet-charging",
    },
    "laptops": {
        "laptop", "notebook", "keyboard", "trackpad", "touchpad", "lid",
        "hinge", "ram", "ssd", "hdd", "thermal-paste", "fan-noise",
        "overheating", "bsod", "blue-screen", "boot",
    },
    "desktops": {
        "desktop", "tower", "motherboard", "cpu", "gpu", "graphics-card",
        "ram-stick", "power-supply", "psu", "post", "bios", "uefi", "beep",
    },
    "solar": {
        "solar", "panel", "photovoltaic", "pv", "inverter", "mppt",
        "charge-controller", "battery-bank", "deep-cycle", "off-grid",
        "grid-tie", "bypass-diode", "shading", "watt",
    },
    "generators": {
        "generator", "genset", "avr", "governor", "rpm",
        "carb", "recoil", "electric-start", "overload",
        "voltage-drop", "petrol-engine", "diesel-engine",
        "alternator-gen", "fuel-tank", "genset-engine",
    },
    "batteries": {
        "battery", "lead-acid", "agm", "lithium", "lifepo4", "cell",
        "sulfation", "electrolyte", "terminal", "charger", "bms",
        "state-of-charge", "soc", "deep-discharge",
    },

    # ── Version 3 ─────────────────────────────────────────────────────────────
    "agriculture": {
        "crop", "soil", "maize", "cassava", "beans", "wheat", "rice",
        "vegetable", "fertilizer", "pesticide", "herbicide", "fungicide",
        "irrigation", "seed", "germination", "harvest", "yield", "nitrogen",
        "phosphorus", "potassium", "compost", "mulch",
    },
    "livestock": {
        "cow", "cattle", "goat", "sheep", "pig", "poultry", "chicken",
        "hen", "duck", "rabbit", "hoof", "foot-rot", "mastitis", "bloat",
        "diarrhoea", "worm", "tick", "vaccination", "calving", "farrowing",
    },
    "irrigation": {
        "drip", "sprinkler", "furrow", "canal", "pump-irrigation",
        "flow-rate", "emitter", "lateral", "mainline", "filter-mesh",
        "pressure-regulator", "head-loss",
    },
    "industrial": {
        "machine", "conveyor", "hydraulic", "pneumatic", "valve-industrial",
        "bearing", "gear", "shaft", "coupling", "seal", "gasket", "lathe",
        "mill", "press", "compressor-industrial",
    },
    "construction": {
        "concrete", "cement", "rebar", "formwork", "scaffolding", "crane",
        "excavator", "bulldozer", "mixer", "vibrator", "foundation",
        "beam", "column", "slab",
    },
    "manufacturing": {
        "production", "assembly", "quality-control", "defect", "tolerance",
        "cnc", "welding", "cutting", "grinding", "drilling",
        "injection-moulding", "extrusion",
    },
    "hvac": {
        "hvac", "aircon", "air-conditioning", "air-conditioner", "refrigerant",
        "condenser", "evaporator", "expansion-valve", "thermostat", "duct",
        "diffuser", "damper", "chiller", "heat-pump", "freon", "r410a", "r22",
        "compressor", "cooling",
    },
    "water_pumps": {
        "pump", "centrifugal", "submersible", "impeller", "priming",
        "cavitation", "suction", "discharge", "pressure-switch",
        "flow-switch", "pump-seal",
    },
    "networking": {
        "router", "switch-network", "access-point", "ethernet", "wifi",
        "dhcp", "dns", "firewall", "vlan", "nat", "ping", "latency",
        "packet-loss", "bandwidth", "cable-network",
    },
    "printers": {
        "printer", "inkjet", "laser", "toner", "cartridge", "jam",
        "paper-feed", "fuser", "drum", "ribbon", "printhead", "spooler",
    },
}

# Human-readable display names for each category slug
CATEGORY_LABELS: dict[str, str] = {
    "roofing": "Roofing",
    "plumbing": "Plumbing",
    "electrical": "Electrical",
    "appliances": "Home Appliances",
    "vehicles": "Vehicles",
    "motorcycles": "Motorcycles",
    "phones": "Phones",
    "tablets": "Tablets",
    "laptops": "Laptops",
    "desktops": "Desktop Computers",
    "solar": "Solar Systems",
    "generators": "Generators",
    "batteries": "Batteries",
    "agriculture": "Agriculture",
    "livestock": "Livestock",
    "irrigation": "Irrigation",
    "industrial": "Industrial Equipment",
    "construction": "Construction Equipment",
    "manufacturing": "Manufacturing Equipment",
    "hvac": "HVAC",
    "water_pumps": "Water Pumps",
    "networking": "Networking Equipment",
    "printers": "Printers",
    "general": "General",
}

ALL_CATEGORIES: list[str] = list(CATEGORY_LABELS.keys())


class ProblemClassifier:
    def classify(self, processed: ProcessedInput) -> str:
        """Return the best-matching category slug, or 'general'."""
        keyword_set = set(processed.keywords)
        best_category = "general"
        best_score = 0

        for category, words in CATEGORY_KEYWORDS.items():
            score = len(keyword_set & words)
            if score > best_score:
                best_score = score
                best_category = category

        return best_category if best_score > 0 else "general"

    def classify_with_scores(self, processed: ProcessedInput) -> list[dict]:
        """Return all categories ranked by match score (for diagnostics / UI)."""
        keyword_set = set(processed.keywords)
        scores = []
        for category, words in CATEGORY_KEYWORDS.items():
            score = len(keyword_set & words)
            if score > 0:
                scores.append({
                    "category": category,
                    "label": CATEGORY_LABELS.get(category, category),
                    "score": score,
                })
        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores

    @staticmethod
    def label(category: str) -> str:
        return CATEGORY_LABELS.get(category, category.title())

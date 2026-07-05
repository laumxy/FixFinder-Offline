"""ICE Engine smoke tests."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ai_engine.rqu_engine import RQUEngine
from ai_engine.ice_engine import ICEEngine

rqu = RQUEngine()
ice = ICEEngine()

TESTS = [
    # (query, expected_primary)
    ("fridge won't light on propane",         "DIAGNOSE_PROBLEM"),
    ("smell gas inside the rv",               "SAFETY"),
    ("sparks from outlet burning smell",      "SAFETY"),
    ("how to replace the thermocouple",       "REPAIR_GUIDANCE"),
    ("what parts do i need for the pump",     "PART_LOOKUP"),
    ("how to install a new water heater",     "INSTALLATION"),
    ("car won't start fails to crank",        "DIAGNOSE_PROBLEM"),
    ("laptop screen dead won't turn on",      "DIAGNOSE_PROBLEM"),
    ("check engine light error code p0420",   "ERROR_CODE_LOOKUP"),
    ("time to service the generator",         "MAINTENANCE"),
    ("is the fridge repaired correctly now",  "VERIFY_REPAIR"),
    ("should i call a rv technician",         "ESCALATE"),
    ("configure wifi on the router",          "CONFIGURATION"),
    ("identify this part next to the furnace","IDENTIFY_COMPONENT"),
]

print()
print("=" * 68)
print("  ICE Engine — Intent Classification Tests")
print("=" * 68)

passed = failed = 0
for query, expected in TESTS:
    ruo = rqu.understand(query)
    ico = ice.classify(ruo)
    pi  = ico["primary_intent"]
    ok  = pi == expected
    icon = "PASS" if ok else "FAIL"
    if ok: passed += 1
    else:  failed += 1
    flag = "" if ok else f"  << expected {expected}"
    print(f"\n  [{icon}]  {query!r}")
    print(f"    primary  : {pi}{flag}")
    print(f"    secondary: {ico['secondary_intent']}")
    print(f"    goal     : {ico['user_goal'][:80]}")
    print(f"    conf     : {ico['intent_confidence']}  route: {ico['routing_hint'][:55]}")

print()
print("=" * 68)
print(f"  Results: {passed}/{passed+failed} passed")
print("=" * 68)

# Full JSON output for one sample
print("\nSample full ICO (JSON):")
ruo = rqu.understand("My RV fridge won't light on propane and I smell gas")
ico = ice.classify(ruo)
print(json.dumps(ico, indent=2))

sys.exit(0 if not failed else 1)

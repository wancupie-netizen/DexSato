"""
DexSato Smoke Test

Purpose
-------
Verify that all core DexSato modules can be imported successfully.

Smoke Test only checks module availability.

It does NOT:
- call APIs
- connect to Supabase
- perform market scans
- execute business logic
"""

from importlib import import_module


MODULES = {

    # Core Scanner
    "Runner": "scanner.runner",

    # Core Engines
    "Observation Builder": "scanner.observation_builder",
    "Signal Detector": "scanner.signal_detector",
    "Interpretation Engine": "scanner.interpretation_engine",
    "Decision Engine": "scanner.decision_engine",
    "Intelligence Engine": "scanner.intelligence_engine",

    # Knowledge Layer
    "Knowledge Gate": "scanner.knowledge_gate",
    "Intelligence Store": "scanner.intelligence_store",
    "Knowledge Fingerprint": "scanner.knowledge_fingerprint",

}


def run():

    print("Running Smoke Test...\n")

    passed = 0
    failed = 0

    details = []

    for name, module in MODULES.items():

        try:

            import_module(module)

            print(f"[PASS] {name}")

            details.append(name)

            passed += 1

        except Exception as e:

            print(f"[FAIL] {name}")

            print(f"       {e}")

            failed += 1

    print()

    return {

        "name": "Smoke Test",

        "status": "PASS" if failed == 0 else "FAIL",

        "passed": passed,

        "failed": failed,

        "details": details,

    }
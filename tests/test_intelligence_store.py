"""
DexSato Intelligence Store Test

This test verifies that Intelligence Store
accepts a serialized payload.
"""

from pprint import pprint

from scanner.intelligence_store import (
    save_intelligence,
)


print("=" * 60)
print("Intelligence Store Test")
print("=" * 60)


payload = {

    "token": "BTC",

    "decision": "WATCH",

    "confidence": "HIGH",

    "knowledge_fingerprint":
        "WATCH|ACCUMULATION",

    "intelligence_package": {

        "token": "BTC",

        "observation": {

            "price_change_pct": 2.5,

        },

        "signals": [

            "PRICE_UP",

        ],

        "interpretations": [

            "BULLISH",

        ],

        "decision": {

            "recommended_action":
                "WATCH",

            "confidence":
                "HIGH",

            "summary":
                "Bullish momentum detected.",

        },

    },

}


print("Payload")
print("-" * 60)

pprint(payload)

print("\nSaving...")

save_intelligence(
    payload,
)

print("\nPASS")
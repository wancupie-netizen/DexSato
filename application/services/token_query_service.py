"""
DexSato Token Query Service

Application Service responsible for retrieving
Token Detail payloads.

Responsibilities
----------------
- Load latest Market Event
- Load latest Intelligence Package
- Load latest Outcome
- Load latest Learning
- Load latest Knowledge
- Deserialize stored Intelligence
- Deserialize stored Outcome
- Deserialize stored Learning
- Deserialize stored Knowledge
- Build Product Layer payload

This module does NOT:
- perform market analysis
- build DTOs
- access HTTP
- perform serialization
"""

from scanner.market_store import (
    load_latest_market_event,
)

from scanner.intelligence_store import (
    load_latest_intelligence,
)

from scanner.outcome_store import (
    load_latest_outcome,
)

from scanner.learning_store import (
    load_latest_learning,
)

from scanner.knowledge_store import (
    load_latest_knowledge,
)

from scanner.deserializers.intelligence_deserializer import (
    deserialize_package,
)

from scanner.deserializers.outcome_deserializer import (
    deserialize_outcome,
)

from scanner.deserializers.learning_deserializer import (
    deserialize_learning,
)

from scanner.deserializers.knowledge_deserializer import (
    deserialize_knowledge,
)


class TokenQueryService:
    """
    Application service responsible for
    building Token Detail payloads.
    """

    def get_token(
        self,
        symbol: str,
    ) -> dict | None:
        """
        Retrieve latest Token Detail payload.

        Parameters
        ----------
        symbol : str

        Returns
        -------
        dict | None
        """

        symbol = symbol.upper()

        market = load_latest_market_event(
            symbol,
        )

        package = load_latest_intelligence(
            symbol,
        )

        outcome_payload = load_latest_outcome(
            symbol,
        )

        learning_payload = load_latest_learning(
            symbol,
        )

        knowledge_payload = load_latest_knowledge(
            symbol,
        )

        if package is None:

            return None

        intelligence = deserialize_package(
            package,
        )

        outcome = None

        if outcome_payload is not None:

            outcome = deserialize_outcome(
                outcome_payload,
            )

        learning = None

        if learning_payload is not None:

            learning = deserialize_learning(
                learning_payload,
            )

        knowledge = None

        if knowledge_payload is not None:

            knowledge = deserialize_knowledge(
                knowledge_payload,
            )

        header = {

            "symbol":
                market["token"]
                if market
                else intelligence["token"],

            # Pair is not yet stored in market_events.
            "pair":
                None,

            "chain":
                market["chain"]
                if market
                else None,

            "price":
                market["price"]
                if market
                else None,

            "liquidity":
                market["liquidity"]
                if market
                else None,

            "volume_24h":
                market["volume_24h"]
                if market
                else None,

            "market_cap":
                market["market_cap"]
                if market
                else None,

            "fdv":
                market["fdv"]
                if market
                else None,

            "last_updated":
                market["scanned_at"]
                if market
                else intelligence["decision"].metadata.timestamp,

        }

        return {

            "header":
                header,

            "observation":
                intelligence["observation"],

            "signals":
                intelligence["signals"],

            "interpretations":
                intelligence["interpretations"],

            "decision":
                intelligence["decision"],

            "outcome":
                outcome,

            "learning":
                learning,

            "knowledge":
                [knowledge]
                if knowledge is not None
                else [],

        }
"""
DexSato Founder Daily Command.

Manual V1 operating workflow:

    python founder_daily.py

The command:

1. Generates the latest five-market snapshot.
2. Displays a concise decision summary.
3. Asks whether the snapshot should be sent to Telegram.
4. Sends the stored snapshot when the founder confirms.

Environment variables required for Telegram:

    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID

This command does NOT:

- start the FastAPI dashboard
- schedule future scans
- run continuously
- send Telegram without confirmation
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from typing import Any

import requests

from application.founder_snapshot_service import (
    generate_latest_snapshot,
    read_latest_snapshot,
)

from application.telegram_notifier import (
    send_telegram_alert,
)


# ==========================================================
# Display
# ==========================================================

def print_heading() -> None:
    """
    Display the Founder Daily command heading.
    """

    print()
    print("=" * 60)
    print("DexSato Founder Daily")
    print("=" * 60)
    print()


def build_decision_counts(
    coins: list[dict[str, object]],
) -> Counter[str]:
    """
    Count snapshot coins by decision or availability state.
    """

    counts: Counter[str] = Counter()

    for coin in coins:

        if coin.get(
            "available",
            False,
        ) is not True:

            counts["UNAVAILABLE"] += 1

            continue

        decision = str(
            coin.get(
                "decision",
                "UNKNOWN",
            )
        ).strip().upper()

        counts[
            decision or "UNKNOWN"
        ] += 1

    return counts


def print_snapshot_summary(
    snapshot: dict[str, Any],
) -> None:
    """
    Display one concise snapshot summary.
    """

    coins = snapshot.get(
        "coins",
    )

    if not isinstance(
        coins,
        list,
    ):

        raise RuntimeError(
            "Latest DexSato snapshot coin data is invalid."
        )

    counts = build_decision_counts(
        coins,
    )

    print("Snapshot completed")
    print("-" * 60)

    print(
        "Generated at      : "
        f"{snapshot.get('generated_at', 'UNKNOWN')}"
    )

    print(
        "Total coins       : "
        f"{snapshot.get('total_coins', len(coins))}"
    )

    print(
        "Available coins   : "
        f"{snapshot.get('available_coins', 0)}"
    )

    print(
        "Unavailable coins : "
        f"{snapshot.get('unavailable_coins', 0)}"
    )

    print()
    print("Decision summary")
    print("-" * 60)

    display_order = (
        "BUY",
        "WATCH",
        "REVIEW",
        "SELL",
        "IGNORE",
        "UNAVAILABLE",
        "UNKNOWN",
    )

    displayed = False

    for decision in display_order:

        count = counts.get(
            decision,
            0,
        )

        if count <= 0:

            continue

        print(
            f"{decision:<12}: {count}"
        )

        displayed = True

    remaining_decisions = sorted(
        decision
        for decision in counts
        if decision not in display_order
    )

    for decision in remaining_decisions:

        print(
            f"{decision:<12}: "
            f"{counts[decision]}"
        )

        displayed = True

    if not displayed:

        print(
            "No decision data available."
        )

    print()
    print("Markets")
    print("-" * 60)

    for coin in coins:

        token = str(
            coin.get(
                "token",
                "UNKNOWN",
            )
        )

        if coin.get(
            "available",
            False,
        ) is not True:

            print(
                f"{token:<8} UNAVAILABLE"
            )

            continue

        decision = str(
            coin.get(
                "decision",
                "UNKNOWN",
            )
        )

        confidence = str(
            coin.get(
                "confidence",
                "UNKNOWN",
            )
        )

        print(
            f"{token:<8} "
            f"{decision:<10} "
            f"Confidence: {confidence}"
        )

    print()


# ==========================================================
# Founder Confirmation
# ==========================================================

def confirm_telegram_send(
    *,
    ask: Callable[[str], str] = input,
) -> bool:
    """
    Ask the founder whether to send the current snapshot.
    """

    answer = ask(
        "Send current snapshot to Telegram? [y/N]: "
    )

    normalized = str(
        answer,
    ).strip().lower()

    return normalized in {
        "y",
        "yes",
    }


# ==========================================================
# Daily Workflow
# ==========================================================

def run_founder_daily(
    *,
    generate_snapshot: Callable[
        [],
        dict[str, object],
    ] = generate_latest_snapshot,
    load_snapshot: Callable[
        [],
        dict[str, Any],
    ] = read_latest_snapshot,
    send_alert: Callable[
        ...,
        dict[str, object],
    ] = send_telegram_alert,
    ask: Callable[[str], str] = input,
) -> int:
    """
    Run the complete manual Founder Daily workflow.

    Returns
    -------
    int
        0 when completed successfully.
        1 when snapshot generation or Telegram sending fails.
    """

    print_heading()

    print("Generating latest 5-market snapshot...")
    print()

    try:

        generation_result = (
            generate_snapshot()
        )

        snapshot = load_snapshot()

        print_snapshot_summary(
            snapshot,
        )

    except Exception as error:

        print("Snapshot failed")
        print("-" * 60)
        print(
            str(
                error,
            )
        )
        print()

        return 1

    if not confirm_telegram_send(
        ask=ask,
    ):

        print()
        print(
            "Telegram skipped. "
            "Snapshot remains available for the dashboard."
        )
        print()

        return 0

    coins = snapshot.get(
        "coins",
    )

    if not isinstance(
        coins,
        list,
    ):

        print()
        print(
            "Telegram failed: "
            "snapshot coin data is invalid."
        )
        print()

        return 1

    print()
    print("Sending snapshot to Telegram...")

    try:

        telegram_result = send_alert(
            dashboard_data=coins,
        )

    except (
        RuntimeError,
        requests.RequestException,
    ) as error:

        print()
        print("Telegram failed")
        print("-" * 60)
        print(
            str(
                error,
            )
        )
        print()

        return 1

    print()
    print("Telegram sent")
    print("-" * 60)

    print(
        "Chat ID : "
        f"{telegram_result.get('chat_id', 'UNKNOWN')}"
    )

    print(
        "Coins   : "
        f"{telegram_result.get('coins', len(coins))}"
    )

    print(
        "Snapshot: "
        f"{generation_result.get('snapshot_file', 'saved')}"
    )

    print()

    return 0


def main() -> int:
    """
    Execute the DexSato Founder Daily command.
    """

    return run_founder_daily()


if __name__ == "__main__":

    raise SystemExit(
        main()
    )

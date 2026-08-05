"""
DexSato V1 Snapshot Command.

Run from the project root:

    python generate_snapshot.py

The command scans the active market universe and
replaces the latest shared snapshot.
"""

from __future__ import annotations

from application.founder_snapshot_service import (
    generate_latest_snapshot,
)


def main() -> int:
    """
    Generate and report the latest DexSato V1 snapshot.
    """

    print()

    print("=" * 60)
    print("DexSato — Market Snapshot")
    print("=" * 60)

    try:

        result = generate_latest_snapshot()

    except Exception as error:

        print()
        print(
            f"Snapshot failed: {error}"
        )
        print()

        return 1

    print()
    print(
        f"Total markets     : {result['total_coins']}"
    )
    print(
        f"Available markets : {result['available_coins']}"
    )
    print(
        f"Unavailable       : {result['unavailable_coins']}"
    )
    print(
        f"Generated at      : {result['generated_at']}"
    )
    print(
        f"Snapshot file     : {result['snapshot_file']}"
    )
    print()

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )

"""
DexSato Founder MVP Launcher.

Run from the project root:

    python main.py

Then open:

    http://127.0.0.1:8000
"""

from app.main import run


def main() -> None:
    """
    Start the DexSato Founder MVP web application.
    """

    run()


if __name__ == "__main__":
    main()
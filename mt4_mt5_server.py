"""Compatibility stub for the removed MT4-vs-MT5 comparator.

The v87 runtime uses :mod:`mt4_feed_server` as its only MT4 process.  Keeping
this tiny module avoids import errors for old user scripts without opening a
port or importing the signal engine.
"""


def main() -> int:
    """Explain the migration and exit without starting a background server."""
    print("Legacy MT4-MT5 comparator removed. Use mt4_feed_server.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

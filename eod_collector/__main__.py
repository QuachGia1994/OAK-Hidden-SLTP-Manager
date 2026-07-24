"""Main entry point allowing python -m eod_collector ... execution."""
import sys
from eod_collector.cli import main

if __name__ == "__main__":
    sys.exit(main())

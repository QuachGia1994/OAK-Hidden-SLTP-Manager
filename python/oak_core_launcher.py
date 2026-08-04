# -*- coding: utf-8 -*-
"""PyInstaller entry point for oak-core (absolute imports — no package context).

The real CLI lives in oak_core.__main__; this thin launcher avoids the
"relative import with no known parent package" error PyInstaller hits when
running a package __main__ directly.
"""
import sys


def main():
    from oak_core.__main__ import main as cli_main
    raise SystemExit(cli_main())


if __name__ == "__main__":
    main()

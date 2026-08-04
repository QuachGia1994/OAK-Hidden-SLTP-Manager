# -*- coding: utf-8 -*-
"""oak-core CLI entry point.

Usage:
    oak-core supervisor
    oak-core profile-worker --profile <name>   (later phases)
"""
import argparse
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="oak-core")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("supervisor", help="Run the supervisor sidecar (JSONL over stdio)")

    worker = sub.add_parser("profile-worker", help="Run one profile worker (later phases)")
    worker.add_argument("--profile", required=True, help="Profile name")

    args = parser.parse_args(argv)

    if args.command == "supervisor":
        from .supervisor import SupervisorApp

        app = SupervisorApp()
        app.run()
        return 0

    if args.command == "profile-worker":
        # Placeholder: profile workers land in Phase 2 (Edit prompt.txt §9).
        print(f"[oak-core] profile-worker not implemented yet (profile={args.profile})",
              file=sys.stderr)
        return 2

    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

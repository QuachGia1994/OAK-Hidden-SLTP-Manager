# -*- coding: utf-8 -*-
"""oak-core CLI entry point.

Usage:
    oak-core supervisor
    oak-core profile-worker --profile <name>
"""
import argparse
import sys
import time


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="oak-core")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("supervisor", help="Run the supervisor sidecar (JSONL over stdio)")

    worker = sub.add_parser("profile-worker", help="Run one MT5 profile worker")
    worker.add_argument("--profile", required=True, help="Profile name")
    worker.add_argument("--once", action="store_true",
                        help="Connect, verify, then exit (for tests/diagnostics)")

    args = parser.parse_args(argv)

    if args.command == "supervisor":
        from .supervisor import SupervisorApp

        app = SupervisorApp()
        app.run()
        return 0

    if args.command == "profile-worker":
        return _run_profile_worker(args.profile, once=args.once)

    parser.print_help(sys.stderr)
    return 2


def _run_profile_worker(profile_name: str, *, once: bool = False) -> int:
    """Connect one MT5 terminal for a profile and keep it alive.

    Each worker owns its MT5 connection (never shared across profiles — §2).
    Phase 2 scope: connect + verify account login/server, then report; the
    Hidden SL/TP / position-monitoring loops arrive in later phases.
    """
    from .worker import run_profile_worker

    return run_profile_worker(profile_name, once=once)


if __name__ == "__main__":
    raise SystemExit(main())

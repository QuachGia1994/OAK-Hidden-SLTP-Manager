#!/usr/bin/env python3
"""Generate dashboard/src/lib/generated-signal-rules.ts from canonical signal_rule_contract.json."""
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
CONTRACT_FILE = ROOT_DIR / "signal_rule_contract.json"
TARGET_FILE = ROOT_DIR / "dashboard" / "src" / "lib" / "generated-signal-rules.ts"
TARGET_FILE_JS = ROOT_DIR / "dashboard" / "src" / "lib" / "generated-signal-rules.js"


def generate_ts_content(contract: dict) -> str:
    version = contract["logic_version"]
    public_slots = json.dumps(contract["public_slots"])
    internal_slots = json.dumps(contract["internal_slots"])
    rules_json = json.dumps(contract["rules"], indent=2, ensure_ascii=False)
    startup_json = json.dumps(contract["startup_summary"], indent=2, ensure_ascii=False)

    return f"""// AUTO-GENERATED FILE BY scripts/generate_dashboard_signal_rules.py. DO NOT EDIT DIRECTLY.
export const ACTIVE_SIGNAL_LOGIC_VERSION = {version};
export const PUBLIC_SIGNAL_SLOTS = {public_slots} as const;
export const INTERNAL_SIGNAL_SLOTS = {internal_slots} as const;

export const RULES_BY_LOCALE = {rules_json} as const;

export const STARTUP_SUMMARY_BY_LOCALE = {startup_json} as const;
"""


def generate_js_content(contract: dict) -> str:
    version = contract["logic_version"]
    public_slots = json.dumps(contract["public_slots"])
    internal_slots = json.dumps(contract["internal_slots"])
    rules_json = json.dumps(contract["rules"], indent=2, ensure_ascii=False)
    startup_json = json.dumps(contract["startup_summary"], indent=2, ensure_ascii=False)

    return f"""// AUTO-GENERATED FILE BY scripts/generate_dashboard_signal_rules.py. DO NOT EDIT DIRECTLY.
export const ACTIVE_SIGNAL_LOGIC_VERSION = {version};
export const PUBLIC_SIGNAL_SLOTS = {public_slots};
export const INTERNAL_SIGNAL_SLOTS = {internal_slots};

export const RULES_BY_LOCALE = {rules_json};

export const STARTUP_SUMMARY_BY_LOCALE = {startup_json};
"""


def main() -> None:
    if not CONTRACT_FILE.exists():
        print(f"ERROR: Contract file missing: {CONTRACT_FILE}", file=sys.stderr)
        sys.exit(1)

    with open(CONTRACT_FILE, "r", encoding="utf-8") as f:
        contract = json.load(f)

    expected_content = generate_ts_content(contract)
    expected_js_content = generate_js_content(contract)

    if "--check" in sys.argv:
        if not TARGET_FILE.exists() or not TARGET_FILE_JS.exists():
            print(f"ERROR: Target files missing", file=sys.stderr)
            sys.exit(1)
        actual_content = TARGET_FILE.read_text(encoding="utf-8")
        actual_js_content = TARGET_FILE_JS.read_text(encoding="utf-8")
        if actual_content.strip() != expected_content.strip() or actual_js_content.strip() != expected_js_content.strip():
            print("ERROR: Generated signal rules drift detected!", file=sys.stderr)
            print("Run 'python scripts/generate_dashboard_signal_rules.py' to sync.", file=sys.stderr)
            sys.exit(1)
        print("OK: Generated signal rules are up to date with signal_rule_contract.json")
        sys.exit(0)

    TARGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    TARGET_FILE.write_text(expected_content, encoding="utf-8")
    TARGET_FILE_JS.write_text(expected_js_content, encoding="utf-8")
    print(f"SUCCESS: Generated {TARGET_FILE} and {TARGET_FILE_JS} from {CONTRACT_FILE}")


if __name__ == "__main__":
    main()

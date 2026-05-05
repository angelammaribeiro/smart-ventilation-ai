from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


VALID_STATES = {
    "open": True,
    "closed": False,
    "1": True,
    "0": False,
    "true": True,
    "false": False,
    "on": True,
    "off": False,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set manual window state for telemetry labeling")
    parser.add_argument("state", help="open|closed|on|off|true|false|1|0")
    parser.add_argument("--file", default="data/processed/manual_window_state.json")
    parser.add_argument("--note", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    state_key = args.state.strip().lower()

    if state_key not in VALID_STATES:
        raise SystemExit("Invalid state. Use one of: open, closed, on, off, true, false, 1, 0")

    out_path = Path(args.file)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "window_open": VALID_STATES[state_key],
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "note": args.note,
    }

    out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(f"Manual window state saved to {out_path}: {payload}")


if __name__ == "__main__":
    main()

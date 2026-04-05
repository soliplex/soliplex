#!/usr/bin/env python3
"""List available Hermes tools with availability status."""

import json
import os
import sys

try:
    import httpx
except ImportError:
    print("Requires: pip install httpx")
    sys.exit(1)

HERMES_URL = os.environ.get("HERMES_URL", "http://localhost:8642")


def main():
    r = httpx.get(f"{HERMES_URL}/v1/agent/tools", timeout=10.0)
    data = r.json()
    summary = data.get("summary", {})

    print(
        f"{summary.get('available_tools', 0)}/{summary.get('total_tools', 0)}"
        f" tools available\n"
    )

    print("Available toolsets:")
    for ts_name in summary.get("available_toolsets", []):
        ts = data["toolsets"][ts_name]
        tools = [t["name"] for t in ts["tools"]]
        print(f"  {ts_name:20s} ({len(tools)}) {', '.join(tools)}")

    gated = summary.get("gated_toolsets", [])
    if gated:
        print(f"\nGated toolsets (need API keys in .env):")
        for ts_name in gated:
            ts = data["toolsets"][ts_name]
            print(f"  {ts_name:20s} ({ts['tool_count']})")


if __name__ == "__main__":
    main()

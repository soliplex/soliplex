#!/usr/bin/env python3
"""
Visualize chat history threads and runs for a room.

Usage:
    python visualize_threads.py <room_id> [--base-url URL] [--token TOKEN]

Examples:
    python visualize_threads.py joker
    python visualize_threads.py genui --base-url http://localhost:8000/api/v1
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.request import Request
from urllib.request import urlopen


def fetch_json(url: str, token: str) -> dict:
    """Fetch JSON from URL with auth header."""
    req = Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")

    try:
        with urlopen(req) as response:
            return json.loads(response.read().decode())
    except HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        print(f"URL: {url}")
        sys.exit(1)
    except URLError as e:
        print(f"URL Error: {e.reason}")
        sys.exit(1)


def format_timestamp(ts: str | None) -> str:
    """Format ISO timestamp to readable format."""
    if not ts:
        return "?"

    ts_no_zulu = ts.replace("Z", "+00:00")

    try:
        dt = datetime.fromisoformat(ts_no_zulu)
    except ValueError:
        return ts[:19]

    return dt.strftime("%Y-%m-%d %H:%M:%S")


def truncate(text: str, max_len: int = 60) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def reconstruct_text_message(events: list, message_id: str) -> str:
    """Reconstruct full text from TEXT_MESSAGE_CONTENT events."""
    parts = []
    for event in events:
        if (
            event.get("type") == "TEXT_MESSAGE_CONTENT"
            and event.get("messageId") == message_id
        ):
            parts.append(event.get("delta", ""))
    return "".join(parts)


def get_user_message_from_run_input(run_input: dict) -> str | None:
    """Extract user message from run_input."""
    messages = run_input.get("messages", [])
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                # Handle content array format
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        return part.get("text", "")
                    elif isinstance(part, str):
                        return part
    return None


def visualize_thread(thread_data: dict, verbose: bool = False):
    """Print visualization of a single thread."""
    thread_id = thread_data.get("thread_id", "?")
    created = format_timestamp(thread_data.get("created"))
    metadata = thread_data.get("metadata")
    thread_name = metadata.get("name") if metadata else None

    # Thread header
    print(f"\n{'=' * 80}")
    if thread_name:
        print(f"📋 THREAD: {thread_name}")
        print(f"   ID: {thread_id}")
    else:
        print(f"📋 THREAD: {thread_id}")
    print(f"   Created: {created}")
    print(f"{'=' * 80}")

    runs = thread_data.get("runs", {})
    if not runs:
        print("   (no runs)")
        return

    # Sort runs by created timestamp
    sorted_runs = sorted(runs.items(), key=lambda x: x[1].get("created", ""))

    for run_idx, (run_id, run_data) in enumerate(sorted_runs, 1):
        run_created = format_timestamp(run_data.get("created"))
        run_input = run_data.get("run_input", {})
        events = run_data.get("events", [])

        print(
            f"\n  ┌─ Run {run_idx} ───────────────────────────────────────────"
        )
        print(f"  │ ID: {run_id}")
        print(f"  │ Created: {run_created}")

        # Show user message if present
        user_msg = get_user_message_from_run_input(run_input)
        if user_msg:
            print("  │")
            print(f"  │ 👤 USER: {truncate(user_msg, 65)}")

        # Process events
        if events:
            tool_calls = {}  # tool_call_id -> {name, args, result}
            text_messages = {}  # message_id -> role

            for event in events:
                event_type = event.get("type", "")

                if event_type == "TOOL_CALL_START":
                    tc_id = event.get("toolCallId")
                    tool_calls[tc_id] = {
                        "name": event.get("toolCallName"),
                        "args": "",
                        "result": None,
                    }
                elif event_type == "TOOL_CALL_ARGS":
                    tc_id = event.get("toolCallId")
                    if tc_id in tool_calls:
                        tool_calls[tc_id]["args"] += event.get("delta", "")
                elif event_type == "TOOL_CALL_RESULT":
                    tc_id = event.get("toolCallId")
                    if tc_id in tool_calls:
                        tool_calls[tc_id]["result"] = event.get("content")
                elif event_type == "TEXT_MESSAGE_START":
                    msg_id = event.get("messageId")
                    text_messages[msg_id] = event.get("role", "assistant")

            # Display tool calls
            if tool_calls:
                print("  │")
                for _tc_id, tc_data in tool_calls.items():
                    print(f"  │ 🔧 TOOL: {tc_data['name']}")
                    if tc_data["args"]:
                        args_display = truncate(tc_data["args"], 55)
                        print(f"  │    Args: {args_display}")
                    if tc_data["result"]:
                        result_display = truncate(tc_data["result"], 55)
                        print(f"  │    Result: {result_display}")

            # Display assistant messages
            for msg_id, role in text_messages.items():
                if role == "assistant":
                    full_text = reconstruct_text_message(events, msg_id)
                    if full_text:
                        print("  │")
                        print("  │ 🤖 ASSISTANT:")
                        # Show first few lines
                        lines = full_text.strip().split("\n")
                        for line in lines[:5]:
                            print(f"  │    {truncate(line, 65)}")
                        if len(lines) > 5:
                            print(f"  │    ... ({len(lines) - 5} more lines)")

            # Show event summary if verbose
            if verbose:
                event_types = {}
                for event in events:
                    t = event.get("type", "UNKNOWN")
                    event_types[t] = event_types.get(t, 0) + 1
                print("  │")
                print(f"  │ Events: {dict(event_types)}")
        else:
            print("  │ (no events)")

        print(f"  └{'─' * 60}")


def main():
    parser = argparse.ArgumentParser(
        description="Visualize chat history threads and runs for a room"
    )
    parser.add_argument("room_id", help="Room ID to visualize")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000/api/v1",
        help="Base URL for the API (default: http://localhost:8000/api/v1)",
    )
    parser.add_argument(
        "--token", default="test", help="Auth token (default: test)"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show verbose output including event counts",
    )
    parser.add_argument("--thread", help="Show only a specific thread ID")

    args = parser.parse_args()

    # Fetch thread list
    list_url = f"{args.base_url}/rooms/{args.room_id}/agui"
    print(f"Fetching threads from: {list_url}")

    threads_response = fetch_json(list_url, args.token)
    threads = threads_response.get("threads", [])

    if not threads:
        print(f"\nNo threads found in room '{args.room_id}'")
        return

    print(f"\nFound {len(threads)} thread(s) in room '{args.room_id}'")

    # Filter to specific thread if requested
    if args.thread:
        threads = [t for t in threads if t.get("thread_id") == args.thread]
        if not threads:
            print(f"Thread '{args.thread}' not found")
            return

    # Fetch and visualize each thread
    for thread_summary in threads:
        thread_id = thread_summary.get("thread_id")
        thread_url = f"{args.base_url}/rooms/{args.room_id}/agui/{thread_id}"

        thread_data = fetch_json(thread_url, args.token)
        visualize_thread(thread_data, verbose=args.verbose)

    print(f"\n{'=' * 80}")
    print(f"Total: {len(threads)} thread(s)")


if __name__ == "__main__":
    main()

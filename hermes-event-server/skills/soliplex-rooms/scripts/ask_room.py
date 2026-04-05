#!/usr/bin/env python3
"""
Send a message to another Soliplex room.

Usage:
  python3 ask_room.py <room_id> <message>
  python3 ask_room.py plain "What time is it?"
  python3 ask_room.py search "Find documents about authentication"
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from soliplex_client import SoliplexClient

if len(sys.argv) < 3:
    print(__doc__)
    sys.exit(1)

room_id = sys.argv[1]
message = " ".join(sys.argv[2:])

client = SoliplexClient()
print(f"Asking room '{room_id}': {message}")
print("-" * 40)
result = client.ask_room(room_id, message)
print(result)

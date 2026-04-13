---
name: soliplex-chat
description: Multi-turn chat with a Soliplex room using client-side shell-script tools
---

# Soliplex Chat

Run `soliplex_chat.py` (stdlib only, no pip) to hold a stateful conversation with a
Soliplex room.  Local shell scripts are registered as AG-UI tools; tool calls are handled
transparently and the user only sees the final text response.

## Usage

```bash
# Interactive
python3 soliplex_chat.py --url http://localhost:8000 --room chat \
    --tool secret_number:./secret_number.sh

# One-shot
python3 soliplex_chat.py -m "what is the secret number" \
    --tool secret_number:./secret_number.sh
```

## Auth

| Env var | CLI flag | Purpose |
|---|---|---|
| `SOLIPLEX_URL` | `--url` | Server base URL |
| `SOLIPLEX_ACCESS_TOKEN` | `--token` | Bearer token for OIDC servers |

## Tool scripts

`--tool name:./script.sh` (repeatable).  Script receives JSON args on stdin, writes
result to stdout, exits 0 on success.

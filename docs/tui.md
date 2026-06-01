# Terminal UI (TUI)

Soliplex ships a terminal client built with
[Textual](https://textual.textualize.io/) for interacting with rooms from the
command line -- a quick way to exercise a running backend without the Flutter
[client](client.md). Two entry points are provided:

- `soliplex-tui` -- the interactive terminal client.
- `soliplex-tui-serve` -- serves that same client as a web application (over
  [textual-serve](https://github.com/Textualize/textual-serve)) so it can be
  reached from a browser.

## Installation

The TUI's dependencies live in the `tui` dependency group (Textual,
textual-serve, textual-fspicker, and Typer):

```bash
uv sync --group tui
```

## Running the client

```bash
soliplex-tui
```

By default the client connects to a backend at <http://127.0.0.1:8000>. Point
it at a different server with `--url`:

```bash
soliplex-tui --url https://soliplex.example.com
```

Options:

- `--url URL` -- base URL of the Soliplex backend
  (default: `http://127.0.0.1:8000`)
- `-v` / `--verbose` -- enable verbose output
- `-V` / `--version` -- print the version and exit
- `-h` / `--help` -- show help and exit

### Authentication

On startup the TUI asks the backend which OIDC providers are configured
(`GET /api/login`):

- If the backend defines one or more providers, the TUI prompts you to pick
  one and enter your username and password, then uses the resulting token for
  all subsequent requests.
- If the backend exposes no providers -- for example, it was started with
  `--no-auth-mode` (see [Server Setup](server/index.md)) -- the TUI skips the
  login step and goes straight to the room list.

## Using the client

After authentication (if any), the TUI opens the room list; select a room to
open its chat view. The TUI is a thin client over the same `/api/v1`
endpoints the Flutter client uses, so the actions available mirror the REST
API. Most are reachable from the footer key bindings.

Global:

- `ctrl+n` -- view the installation configuration
- `ctrl+q` -- quit
- `ctrl+\` -- open the command palette

In a room:

- `ctrl+n` -- start a new thread
- `ctrl+t` -- list the room's threads
- `ctrl+r` -- list runs
- `ctrl+s` -- view the current AG-UI state
- `ctrl+z` -- edit thread metadata
- `ctrl+p` -- request an MCP token for the room
- `shift+ctrl+u` -- upload a file
- `esc` -- go back

Viewing a run:

- `ctrl+f` -- submit feedback on the run
- `ctrl+z` -- edit run metadata

## Serving the TUI over the web

`soliplex-tui-serve` wraps the client with
[textual-serve](https://github.com/Textualize/textual-serve), running it as a
web application you can open in a browser -- handy for demos, or for users who
cannot install the client locally:

```bash
soliplex-tui-serve
```

This serves at <http://127.0.0.1:8002> by default and connects to a backend
at <http://127.0.0.1:8000>. Options:

- `--backend-url URL` -- base URL of the Soliplex backend
  (default: `http://127.0.0.1:8000`)
- `--host HOST` -- interface to bind (default: `127.0.0.1`)
- `--port PORT` -- port to listen on (default: `8002`)
- `--public-url URL` -- publicly reachable URL of the served app
  (defaults to `http://{host}:{port}`)

For example, to serve on all interfaces behind a known public URL:

```bash
soliplex-tui-serve \
  --host 0.0.0.0 \
  --port 8002 \
  --backend-url https://soliplex.example.com \
  --public-url https://tui.example.com
```

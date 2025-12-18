# Server Setup

The Soliplex server is a FastAPI-based backend that forwards requests
to OpenAI and provides RAG functionality.

## Prerequisites

- Python 3.13+

- Access to LLM:

   - OpenAI - an API key is required to use OpenAI
   - Ollama  ([https://ollama.com/] https://ollama.com/)

- Logfire (optional):

  A token from logfire ([login here](https://logfire-us.pydantic.dev/login))
  allows for visibility into the application. (see the
  [docs on FastAPI integration](https://logfire.pydantic.dev/docs/integrations/web-frameworks/fastapi/)
  for more information).

## Installation

1. Clone the repository:
   ```bash
   git clone git@github.com:soliplex/soliplex.git
   cd soliplex/
   ```

2. Set up a Python3 virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install --upgrade setuptools pip
   ```

3. Install `soliplex` and its dependencies:
   ```bash
   pip install -e .
   ```

4. Set up environment variables:

   An environment file can be used to configure secrets.
   For logfire, create a `.env` file with:
   ```
   LOGFIRE_TOKEN=<your_token_here>
   ```
## Running the example

The example configuration provides an overview of how a soliplex
application is assembled.  It contains four top-level installation
configurations:

- `example/minimal.yaml` is a minimal example using Ollama:  it requires
  no secrets.

- `example/installation.yaml` is a more fleshed-out example using Ollama:
  it requires secrets for the exernal Model-Control Protocol (MCP) client
  toosets for the room `mcptest`.

- `example/minimal-openai.yaml` is a minimal example using OpenAI: 
  it requires no secrets beyond the `OPENAI_API_KEY`.

- `example/installation.yaml` is a more fleshed-out example using OpenAI:
  in addition tothe `OPENAI_API_KEY` secret, it requires secrets for the
  exernal Model-Control Protocol (MCP) client toosets for the room `mcptest`.

Each installation configuration includes a number of rooms that 

1. Configure resources:

   The example needs access to a model server using either openapi
   or ollama as well as access to example MCP services.

   The example uses [https://smithery.ai/](https://smithery.ai/) but others
   can be configured.

   a. OIDC configuration:
   TODO

2. Configure the LLM (Ollama / OpenAI):

   - For the Ollama veriants, export the URL of your model server as
     `OLLAMA_BASE_URL`.  This url should *not* contain the `/v1` suffix.
     E.g. if you are running Ollama on your own machine:

     ```bash
     export OLLAMA_BASE_URL=http://localhost:11434
     ```

   - The example configuration uses the `gpt-oss` model.  If using either
     Ollama variant, install that model via:
     ```bash
     ollama pull gpt-oss:latest
     ```

3. Check for missing secrets / environment variables:

   This command will check the server for any missing variables or
   invalid configuration files.
   ```bash
   soliplex-cli check-config example/<installation config>.yaml
   ```

   The secrets used in the your chosen configuration should be exported as
   environment variables, e.g.:
   ```
   SMITHERY_AI_API_KEY=<your key>
   SMITHERY_AI_PROFILE=<your profile>
   ```

   Note that the alternate installation configurations, `example/minimal.yaml`
   and `example/minimal-openai.yaml`, requires no additional secrets
   The `example/minimal.yaml` configuration still expects
   the `OLLAMA_BASE_URL` environment variable to be set (or present in
   an `.env` file):
   ```bash
   soliplex-cli check-config example/minimal.yaml
   ```

4. Configure any missing secrets, e.g. by sourcing a `.env` file, or
   by exporting them directly.

5. Configure any missing environment variables, e.g. by editing
   the installation YAML file, adding them to a `.env` file in the
   installation path, or exporting them directly.
   ```bash
   export OLLAMA_BASE_URL=http://<your-ollama-host>:11434
   soliplex-cli check-config example/
   ```

## Running the Server

Start the FastAPI server with auto-reload:

```bash
soliplex-cli serve example/installation.yaml -r both
```

The server will be available at `http://localhost:8000` by default.

For testing purposes, the server can be run with authentication disabled.
To run without authentication:
```bash
soliplex-cli serve example/no_auth.yaml -r both
```

To confirm your room configuration:
```bash
curl -X 'GET' \
  'http://127.0.0.1:8000/api/v1/rooms' \
  -H 'accept: application/json'
```

## API Endpoints

If the `soliplex-cli` server is running, you can browse the
[live OpenAPI documentation](http://localhost:8000/docs).

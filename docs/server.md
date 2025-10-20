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
application is assembled.  There are two installations provided as examples.  The example_ollama folder is configured to use ollama as its agent provider.  The example_openai uses OpenAI.

### OpenAI configuration
1. Configure OpenAI
    - Your API key needs to be added to the server environment either via a .env file or as part of the invoking environment as OPENAPI_API_KEY
    ```bash
    export OPENAPI_API_KEY=<your_key>
    ```

### OLLAMA Configuration
1. Configure Ollama:

   - Export the URL of your model server as `OLLAMA_BASE_URL`.  This
    url should *not* contain the `/v1` suffix: e.g. use
    `OLLAMA_BASE_URL=http://localhost:11434` if you are running Ollama
    on your own machine.

   - The example configuration uses the qwen3 model.  To install:
     ```bash
     ollama pull qwen3:latest
     ```
### Validate 
1. Check for missing secrets / environment variables:

   This command will check the server for any missing variables or
   invalid configuration files.
   ```bash
   soliplex-cli check-config example/installation.yaml
   ```
 
2. Configure any missing secrets, e.g. by sourcing a `.env` file, or
   by exporting them directly. Environment variables can also be added to the configuration YAML.


## Indexing Documents
The haiku room provides an example of using ([https://ggozad.github.io/haiku.rag/] haiku-rag) for querying documents For the haiku room to function, one or more documents must be indexed.  For example purposes, the Soliplex documentation can be used. The indexing will be dependent upon the agent and model selections in your installation folder so changes may require re-indexing. Currently, haiku-rag must be run independently so its configuration must be set as environment variables to match the installation.
For OpenAI installations the configration should be similar to below, using values from the installation yaml file.
```
OPENAI_API_KEY=<your-key>
QA_PROVIDER=openai
EMBEDDINGS_PROVIDER=openai
EMBEDDINGS_MODEL=text-embedding-3-small
EMBEDDINGS_VECTOR_DIM=1536
QA_MODEL=gpt-4o-mini
RERANK_PROVIDER=""
```
For Ollama:
```
EMBEDDINGS_PROVIDER="ollama"
EMBEDDINGS_MODEL="mxbai-embed-large"
EMBEDDINGS_VECTOR_DIM=1024
QA_PROVIDER="ollama"
QA_MODEL="qwen3:latest"
OLLAMA_BASE_URL="http://localhost:11434"
```
Once the enviroment variables are set,
```bash
cd <your install directory>
haiku-rag add-src ../docs/ --db .\db\rag\rag.lancedb
```

## Running the Server

Start the FastAPI server with auto-reload:

```bash
soliplex-cli serve <your install>/minimal.yaml -r both
```

The server will be available at `http://localhost:8000` by default.

For testing purposes, the server can be run with authentication disabled.
To run without authentication:
```bash
soliplex-cli serve --no-auth-mode <your install>/minimal.yaml -r both
```

To confirm your room configuration:
```bash
soliplex-cli list-rooms ./<your install>/minimal.yaml
or via the server:
```
```bash
curl -X 'GET' \
  'http://127.0.0.1:8000/api/v1/rooms' \
  -H 'accept: application/json'
```

## API Endpoints

If the `soliplex-cli` server is running, you can browse the
[live OpenAPI documentation](http://localhost:8000/docs).

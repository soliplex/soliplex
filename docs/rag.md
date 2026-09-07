# Retrieval-Augmented Generation (RAG) Database

Soliplex depends on the `haiku-rag`
[library](https://pypi.org/project/haiku-rag) to manage its
retrieval-augmented generation (RAG) searches.  That library stores its
extracted documents / chunks / embeddings in
[LanceDB](https://lancedb.com/) databases.

The example installation of Soliplex uses the Soliplex documentation as its
RAG corpus, and expects that database to be created at `db/rag/rag.lancedb`.

## Note on `haiku-rag` Versions

The `soliplex` code itself requires only the `haiku-rag-slim` project
(<https://pypi.org/project/haiku.rag-slim/>), which allows for queries
against an existing LanceDB database.

However, this dependency is not sufficient to perform the ingestion /
indexing of documents.  For that purpose, either:

- Run `docling-serve` as a container, which this repository's
  `docker-compose.yaml` provides. **Recommended:** it keeps the ingestion
  dependencies out of the environment the server runs in.

  ```bash
  docker compose up -d docling_serve
  ```

  It listens on port 5001, which is where `example/haiku.rag.yaml`
  already points `providers.docling_serve.base_url`, so no configuration
  change is needed.

- Or install the main `haiku-rag` project
  (<https://pypi.org/project/haiku.rag/>), which pulls in every
  dependency needed to ingest and index documents.

  Be aware of what that costs: it resolves to roughly 88 additional
  packages, including `torch`, `transformers`, `opencv` and the full
  NVIDIA CUDA stack, and it upgrades `click` out from under the CLI.
  It also leaves both `haiku.rag` and `haiku.rag-slim` installed, each
  providing the same import package.

See the `haiku.rag` documentation to determine:

- [Which installation do you need?](https://ggozad.github.io/haiku.rag/installation/)

- [What are the tradeoffs of local vs. remote processing?](https://ggozad.github.io/haiku.rag/configuration/processing/#local-vs-remote-processing)

- [How to configure `haiku-rag` to run in "remote processing" mode?](https://ggozad.github.io/haiku.rag/remote-processing/)

## Adding a single document

```bash
export OLLAMA_BASE_URL=<your Ollama server / port>
haiku-rag --config example/haiku.rag.yaml \
  add-src --db db/rag/rag.lancedb docs/index.md
...
Document <UUID> added successfully.
```

## Adding all documents in a directory

```bash
export OLLAMA_BASE_URL=<your Ollama server / port>
haiku-rag --config example/haiku.rag.yaml \
  add-src --db db/rag/rag.lancedb docs/
...
17 documents added successfully.
```

## Configuration of `haiku-rag` clients within Soliplex

Please see [this page](config/rag.md) for notes on configuring
the various `haiku-rag` clients used in a Soliplex installation.

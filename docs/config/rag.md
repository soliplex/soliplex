# `haiku-rag` Client Configuration

In order to use its RAG database(s) (see [this page](../rag.md) for how to
create them), Soliplex installation uses `haiku.rag` as a library, creating
instances of `haiku.rag.client.HaikuRag` client class as needed.

**NOTE**:  the `embeddings` configuration used to create the RAG database
           must match the client configuration used to read the database.

The configuration used to create these client instances can be defined in
two places:

## Global Configuration

The default `haiku-rag` configuration for an installation lives in a
seprate file, `haiku.rag.yaml`, which is located by default in the
installation directory (next to the main installation config file).

See the [`haiku-rag` docs](https://ggozad.github.io/haiku.rag/configuration/)
for the format and semantics of this file.

## Room-level and Completion-level Configuration

Rooms and completions which use the `soliplex.tools.search_documents`
tool can also define a `haiku.rag.yaml` file, next to their own
config files.  Soliplex overlays any configuration defined in such files
on top of the global configuration when using the tool.

E.g., to override only the reranking used by `haiku-rag` in a given room:

```yaml
reranking:
  model:
    name: "gpt-oss:20b"
    provider: "ollama"
```

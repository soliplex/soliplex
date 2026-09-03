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
separate file, `haiku.rag.yaml`, which is located by default in the
installation directory (next to the main installation config file).

See the [`haiku-rag` docs](https://ggozad.github.io/haiku.rag/configuration/)
for the format and semantics of this file.

## Room-level and Completion-level Configuration

Rooms and completions can also define a `haiku.rag.yaml` file, next to
their own config files.  Soliplex overlays any configuration defined in
such files on top of the global configuration.

E.g., to override only the reranking used by `haiku-rag` in a given room:

```yaml
reranking:
  model:
    name: "gpt-oss:20b"
    provider: "ollama"
```

## Searching Several Databases

A RAG skill or tool which configures `rag_databases` (see
[rooms](rooms.md)) reads them as one set.  Soliplex resolves the path of
every database a config names and writes them into the client
configuration's `lancedb.databases`, as a mapping of name to location,
then opens a single client over the set.  A config naming one database
this way is read as one database, not as a set of one.

A config written with `rag_lancedb_stem` or `rag_lancedb_override_path`
names one database the same way, taking its name from the file's stem, so
`papers.lancedb` is `papers`.  That name is what the room's endpoints
report as `database`.

A config naming no database of its own reads the ones this file places in
`lancedb.databases`, under the names it gives them:

```yaml
lancedb:
  databases:
    medic: "s3://bucket/lancedb/medic.lancedb"
```

This is the only way to read a database that is not a local directory.
`lancedb.databases` is where `haiku.rag` places every database; a
configuration carrying the older `lancedb.uri` fails to load.

Candidates from the covered databases are combined by the configured
reranker.  Without one, they are ordered by cosine similarity to the
query: the databases in a set share an embedding model, so similarity in
that one space compares across them, where each database's own retrieval
scores do not.  A full-text search, which has no query vector, orders by
retrieval score instead.  A result carries the name of the database it
came from, never its location.

Chunk IDs are unique within a database but repeat between copies of one,
so the room's chunk endpoint asks each covered database in turn and the
first one holding the ID answers.

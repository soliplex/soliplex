#!/usr/bin/env bash
set -e

RAG_DB="/app/db/rag/haiku.rag.lancedb"
DOCUMENTS_DIR="/app/documents"

# Initialize the RAG database if it doesn't exist
if [ ! -d "$RAG_DB" ]; then
    echo "Initializing RAG database at $RAG_DB..."
    haiku-rag init --db "$RAG_DB"
fi

# Index any PDF documents that haven't been indexed yet
if [ -d "$DOCUMENTS_DIR" ]; then
    for pdf in "$DOCUMENTS_DIR"/*.pdf; do
        [ -f "$pdf" ] || continue
        if [ ! -f "${pdf}.indexed" ]; then
            echo "Indexing $pdf..."
            if haiku-rag add-src --db "$RAG_DB" "$pdf"; then
                touch "${pdf}.indexed"
                echo "Indexed $pdf successfully."
            else
                echo "Failed to index $pdf, skipping."
            fi
        fi
    done
fi

# Run soliplex-cli with any arguments passed to the container
exec "$@"

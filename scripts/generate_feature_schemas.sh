#!/bin/sh

repo_root=$(git rev-parse --show-toplevel)

soliplex-cli agui-feature-schemas "$repo_root/example/installation.yaml" | jq '{
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
              "filter_documents": .filter_documents.json_schema,
              "ask_history": .ask_history.json_schema,
              "haiku.rag.chat": .["haiku.rag.chat"].json_schema
            }
          }' >"$repo_root/schemas/schema.json"

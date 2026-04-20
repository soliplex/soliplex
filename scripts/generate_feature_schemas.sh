#!/bin/sh

repo_root=$(git rev-parse --show-toplevel)

soliplex-cli agui-feature-schemas "$repo_root/example/installation.yaml" | jq '{
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
              "rag": .rag.json_schema,
              "analysis": .analysis.json_schema
            }
          }' >"$repo_root/schemas/schema.json"

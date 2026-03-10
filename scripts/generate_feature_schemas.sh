#!/bin/sh

repo_root=$(git rev-parse --show-toplevel)

soliplex-cli agui-feature-schemas "$repo_root/example/installation.yaml" | jq '{
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
              "image-generation": .["image-generation"].json_schema,
              "rag": .rag.json_schema,
              "rlm": .rlm.json_schema
            }
          }' >"$repo_root/schemas/schema.json"

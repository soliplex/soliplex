#!/usr/bin/env python3
"""Generate Monty-compatible Python validators from Pydantic models.

Emits pure-Python functions using only dicts, lists, and builtins —
no imports, no classes — so the output runs inside the Monty sandbox.

Usage:
    python scripts/generate_monty_schemas.py [--model MODEL_NAME]

Without --model, prints validators for all supported models.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, get_args, get_origin

import pydantic


def _monty_coercion(field_name: str, field_type: str, default: str) -> str:
    """Return a Monty-compatible coercion expression."""
    match field_type:
        case "string":
            return f"str(raw.get('{field_name}', {default}))"
        case "integer":
            return f"int(raw.get('{field_name}', {default}))"
        case "number":
            return f"float(raw.get('{field_name}', {default}))"
        case "boolean":
            return f"bool(raw.get('{field_name}', {default}))"
        case "array":
            return f"list(raw.get('{field_name}', {default}))"
        case "object":
            return f"dict(raw.get('{field_name}', {default}))"
        case _:
            return f"raw.get('{field_name}', {default})"


def _json_schema_default(prop: dict[str, Any]) -> str:
    """Extract a safe default value from a JSON schema property."""
    if "default" in prop:
        val = prop["default"]
        if isinstance(val, str):
            return repr(val)
        if isinstance(val, bool):
            return "True" if val else "False"
        return repr(val)

    schema_type = prop.get("type", "string")
    match schema_type:
        case "string":
            return "''"
        case "integer":
            return "0"
        case "number":
            return "0.0"
        case "boolean":
            return "False"
        case "array":
            return "[]"
        case "object":
            return "{}"
        case _:
            return "None"


def generate_monty_validator(
    model_class: type[pydantic.BaseModel],
    *,
    function_name: str | None = None,
) -> str:
    """Generate a Monty-compatible validator function for a Pydantic model.

    Args:
        model_class: The Pydantic model to generate a validator for.
        function_name: Override the generated function name.

    Returns:
        A string of Monty-compatible Python code.
    """
    schema = model_class.model_json_schema()
    name = function_name or f"validate_{_snake_case(model_class.__name__)}"
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    lines = [f"def {name}(raw):"]
    lines.append("    result = {}")

    for field_name, prop in properties.items():
        # Resolve $ref or anyOf to a simple type
        field_type = _resolve_type(prop, schema)
        default = _json_schema_default(prop)
        coercion = _monty_coercion(field_name, field_type, default)
        lines.append(f"    result['{field_name}'] = {coercion}")

    lines.append("    return result")
    lines.append("")

    return "\n".join(lines)


def _resolve_type(prop: dict[str, Any], root_schema: dict[str, Any]) -> str:
    """Resolve a JSON schema property to a simple type string."""
    if "type" in prop:
        return prop["type"]

    if "anyOf" in prop:
        for variant in prop["anyOf"]:
            if variant.get("type") != "null":
                return _resolve_type(variant, root_schema)

    if "$ref" in prop:
        ref_path = prop["$ref"]
        # Handle #/$defs/Name
        if ref_path.startswith("#/$defs/"):
            def_name = ref_path.split("/")[-1]
            defs = root_schema.get("$defs", {})
            if def_name in defs:
                ref_schema = defs[def_name]
                if "enum" in ref_schema:
                    return "string"  # Enums → strings in Monty
                return ref_schema.get("type", "string")

    if "allOf" in prop:
        for variant in prop["allOf"]:
            resolved = _resolve_type(variant, root_schema)
            if resolved != "string":
                return resolved
        return "string"

    return "string"


def _snake_case(name: str) -> str:
    """Convert CamelCase to snake_case."""
    result = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0:
            result.append("_")
        result.append(ch.lower())
    return "".join(result)


# ── Supported models ─────────────────────────────────────────────────────────

def _get_supported_models() -> dict[str, type[pydantic.BaseModel]]:
    """Return mapping of name → Pydantic model class."""
    from soliplex.models import Tool

    return {
        "tool": Tool,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        choices=list(_get_supported_models().keys()),
        help="Generate validator for a specific model (default: all)",
    )
    parser.add_argument(
        "--json-schema",
        action="store_true",
        help="Print the JSON schema instead of the Monty validator",
    )
    args = parser.parse_args()

    models = _get_supported_models()
    targets = {args.model: models[args.model]} if args.model else models

    for name, model_class in targets.items():
        if args.json_schema:
            print(json.dumps(model_class.model_json_schema(), indent=2))
        else:
            print(generate_monty_validator(model_class))


if __name__ == "__main__":
    main()

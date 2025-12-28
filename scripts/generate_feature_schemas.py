#!/usr/bin/env python3
"""Generate JSON schemas for AG-UI features

This script generates JSON schema files for all registered AG-UI features
without requiring the backend server to be running.

The schemas are written to the schemas/ directory in the repository root.

Usage:
    python scripts/generate_feature_schemas.py
"""

import json
import pathlib
import sys

# Add src to path to allow imports
repo_root = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

from soliplex import config


def generate_schemas() -> None:
    """Generate JSON schema files for all AG-UI features"""
    output_dir = repo_root / "schemas"
    output_dir.mkdir(parents=True, exist_ok=True)

    features = config.AGUI_FEATURES_BY_NAME.values()

    for feature in features:
        # Generate schema
        schema = feature.json_schema

        # Write to file
        schema_file = output_dir / f"{feature.name}.json"
        with schema_file.open("w") as f:
            json.dump(schema, f, indent=2)

        print(f"Generated schema for '{feature.name}' -> {schema_file}")


if __name__ == "__main__":
    generate_schemas()

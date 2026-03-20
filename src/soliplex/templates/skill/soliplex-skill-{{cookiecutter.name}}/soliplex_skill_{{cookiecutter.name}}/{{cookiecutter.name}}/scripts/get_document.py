# /// script
# requires-python = ">=3.12"
# dependencies = ["haiku.rag-slim >= 0.34.0, < 0.35"]
# ///
"""Retrieve a document by ID, title, or URI."""
import asyncio
import json
from pathlib import Path

_DB_PATH = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "{{ cookiecutter.name }}.lancedb"
)


def _get_config():
    config_path = (
        Path(__file__).resolve().parent.parent
        / "assets"
        / "haiku.rag.yaml"
    )
    if config_path.exists():
        from haiku.rag.config import AppConfig

        return AppConfig.from_yaml(config_path)
    return None


async def _get_document(query):
    from haiku.rag.client import HaikuRAG

    async with HaikuRAG(
        _DB_PATH, config=_get_config(), read_only=True
    ) as rag:
        document = await rag.resolve_document(query)
        if document is None:
            return None
        return {
            "id": document.id,
            "title": document.title,
            "uri": document.uri,
            "content": document.content,
        }


def main(query: str):
    """Retrieve a document by ID, title, or URI.

    Args:
        query: Document ID, title, or URI to look up.
    """
    result = asyncio.run(_get_document(query))
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Retrieve a document by ID, title, or URI."
    )
    parser.add_argument(
        "--query", required=True,
        help="Document ID, title, or URI to look up.",
    )
    args = parser.parse_args()
    main(args.query)

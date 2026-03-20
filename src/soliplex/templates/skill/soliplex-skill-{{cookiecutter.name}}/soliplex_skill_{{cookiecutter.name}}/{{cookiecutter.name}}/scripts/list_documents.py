# /// script
# requires-python = ">=3.12"
# dependencies = ["haiku.rag-slim >= 0.34.0, < 0.35"]
# ///
"""List documents in the knowledge base."""
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


async def _list_documents(limit, offset):
    from haiku.rag.client import HaikuRAG

    async with HaikuRAG(
        _DB_PATH, config=_get_config(), read_only=True
    ) as rag:
        documents = await rag.list_documents(limit, offset)
        return [
            {
                "id": doc.id,
                "title": doc.title,
                "uri": doc.uri,
            }
            for doc in documents
        ]


def main(limit: int = 20, offset: int = 0):
    """List documents in the knowledge base with optional pagination.

    Args:
        limit: Maximum number of documents to return.
        offset: Number of documents to skip.
    """
    result = asyncio.run(_list_documents(limit, offset))
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="List documents in the knowledge base."
    )
    parser.add_argument(
        "--limit", type=int, default=20,
        help="Maximum number of documents to return.",
    )
    parser.add_argument(
        "--offset", type=int, default=0,
        help="Number of documents to skip.",
    )
    args = parser.parse_args()
    main(args.limit, args.offset)

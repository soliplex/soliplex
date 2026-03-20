# /// script
# requires-python = ">=3.12"
# dependencies = ["haiku.rag-slim >= 0.34.0, < 0.35"]
# ///
"""Retrieve a document by ID, title, or URI."""
import asyncio
import json

from {{ cookiecutter.name }}._lib import DB_PATH
from {{ cookiecutter.name }}._lib import get_config


def main(query: str):
    """Retrieve a document by ID, title, or URI.

    Args:
        query: Document ID, title, or URI to look up.
    """

    async def _run():
        from haiku.rag.client import HaikuRAG

        async with HaikuRAG(
            DB_PATH, config=get_config(), read_only=True
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

    result = asyncio.run(_run())
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()

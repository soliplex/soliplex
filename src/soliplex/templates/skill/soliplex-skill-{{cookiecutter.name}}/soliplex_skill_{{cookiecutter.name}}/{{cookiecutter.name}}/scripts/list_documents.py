# /// script
# requires-python = ">=3.12"
# dependencies = ["haiku.rag-slim >= 0.34.0, < 0.35"]
# ///
"""List documents in the knowledge base."""
import asyncio
import json

from {{ cookiecutter.name }}._lib import DB_PATH
from {{ cookiecutter.name }}._lib import get_config


def main(limit: int = 20, offset: int = 0):
    """List documents in the knowledge base with optional pagination.

    Args:
        limit: Maximum number of documents to return.
        offset: Number of documents to skip.
    """

    async def _run():
        from haiku.rag.client import HaikuRAG

        async with HaikuRAG(
            DB_PATH, config=get_config(), read_only=True
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

    result = asyncio.run(_run())
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()

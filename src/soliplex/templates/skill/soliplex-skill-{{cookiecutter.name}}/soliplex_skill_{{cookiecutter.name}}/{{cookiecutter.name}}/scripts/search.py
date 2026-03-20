# /// script
# requires-python = ">=3.12"
# dependencies = ["haiku.rag-slim >= 0.34.0, < 0.35"]
# ///
"""Search the knowledge base."""
import asyncio

from {{ cookiecutter.name }}._lib import DB_PATH
from {{ cookiecutter.name }}._lib import get_config


def main(query: str, limit: int = 10):
    """Search the knowledge base using hybrid search.

    Args:
        query: The search query.
        limit: Maximum number of results.
    """

    async def _run():
        from haiku.rag.client import HaikuRAG

        async with HaikuRAG(
            DB_PATH, config=get_config(), read_only=True
        ) as rag:
            results = await rag.search(query, limit=limit)
            results = await rag.expand_context(results)

        return "\n\n---\n\n".join(
            r.format_for_agent(rank=i + 1, total=len(results))
            for i, r in enumerate(results)
        )

    print(asyncio.run(_run()))


if __name__ == "__main__":
    main()

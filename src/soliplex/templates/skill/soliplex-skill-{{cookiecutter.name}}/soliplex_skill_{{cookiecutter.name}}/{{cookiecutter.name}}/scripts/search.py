# /// script
# requires-python = ">=3.12"
# dependencies = ["haiku.rag-slim >= 0.34.0, < 0.35"]
# ///
"""Search the knowledge base."""
import asyncio
from pathlib import Path

_DB_PATH = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "{{ cookiecutter.name }}.lancedb"
)
_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "haiku.rag.yaml"
)


def _rag_kw():
    from haiku.rag.config import get_config

    if _CONFIG_PATH.exists():
        from haiku.rag.config import AppConfig

        config = AppConfig.from_yaml(_CONFIG_PATH)
    else:
        config = get_config()
    return {"db_path": _DB_PATH, "config": config, "read_only": True}


async def _search(query, limit):
    from haiku.rag.client import HaikuRAG

    async with HaikuRAG(**_rag_kw()) as rag:
        results = await rag.search(query, limit=limit)
        results = await rag.expand_context(results)

    return "\n\n---\n\n".join(
        r.format_for_agent(rank=i + 1, total=len(results))
        for i, r in enumerate(results)
    )


def main(query: str, limit: int = 10):
    """Search the knowledge base using hybrid search.

    Args:
        query: The search query.
        limit: Maximum number of results.
    """
    print(asyncio.run(_search(query, limit)))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Search the knowledge base."
    )
    parser.add_argument(
        "--query", required=True, help="The search query.",
    )
    parser.add_argument(
        "--limit", type=int, default=10,
        help="Maximum number of results.",
    )
    args = parser.parse_args()
    main(args.query, args.limit)

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


async def _search(query, limit):
    from haiku.rag.client import HaikuRAG

    async with HaikuRAG(
        _DB_PATH, config=_get_config(), read_only=True
    ) as rag:
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

"""Search the knowledge base."""
from pathlib import Path

_DB_PATH = (
    Path(__file__).resolve().parent
    / "assets"
    / "{{ cookiecutter.name }}.lancedb"
)
_CONFIG_PATH = (
    Path(__file__).resolve().parent
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



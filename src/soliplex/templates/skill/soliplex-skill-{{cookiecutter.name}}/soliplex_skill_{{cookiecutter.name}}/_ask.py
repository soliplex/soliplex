"""Ask a question and get an answer with citations."""
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


async def _ask(question):
    from haiku.rag.client import HaikuRAG
    from haiku.rag.utils import format_citations

    async with HaikuRAG(**_rag_kw()) as rag:
        answer, citations = await rag.ask(question)

    if citations:
        answer += "\n\n" + format_citations(citations)

    return answer



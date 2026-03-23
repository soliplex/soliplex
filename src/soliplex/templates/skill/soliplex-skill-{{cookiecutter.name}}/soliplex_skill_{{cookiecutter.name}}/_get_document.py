"""Retrieve a document by ID, title, or URI."""
import json
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


async def _get_document(query):
    from haiku.rag.client import HaikuRAG

    async with HaikuRAG(**_rag_kw()) as rag:
        document = await rag.resolve_document(query)
        if document is None:
            return None
        return {
            "id": document.id,
            "title": document.title,
            "uri": document.uri,
            "content": document.content,
        }



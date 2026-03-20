from pathlib import Path

from haiku.rag.skills.rag import RAGState
from haiku.skills.models import Skill, SkillSource
from haiku.skills.parser import parse_skill_md
from haiku.skills.state import SkillRunDeps
from pydantic_ai import RunContext

_TOOL_NAMES = {{ cookiecutter.tool_names.split()|tojson }}
_SKILL_DIR = Path(__file__).parent / "{{ cookiecutter.name }}"
_DB_PATH = _SKILL_DIR / "assets" / "{{ cookiecutter.name }}.lancedb"


def _get_config():
    config_path = _SKILL_DIR / "assets" / "haiku.rag.yaml"
    if config_path.exists():
        from haiku.rag.config import AppConfig

        return AppConfig.from_yaml(config_path)
    return None

{% if "list_documents" in cookiecutter.tool_names %}
async def list_documents(
    ctx: RunContext[SkillRunDeps],
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict]:
    """List documents in the knowledge base with optional pagination.

    Args:
        limit: Maximum number of documents to return.
        offset: Number of documents to skip.
    """
    from soliplex_skill_{{ cookiecutter.name }}.{{ cookiecutter.name }}.scripts.list_documents import (
        _list_documents,
    )

    return await _list_documents(limit, offset)
{% endif %}
{% if "get_document" in cookiecutter.tool_names %}
async def get_document(
    ctx: RunContext[SkillRunDeps], query: str
) -> dict | None:
    """Retrieve a document by ID, title, or URI.

    Args:
        query: Document ID, title, or URI to look up.
    """
    from soliplex_skill_{{ cookiecutter.name }}.{{ cookiecutter.name }}.scripts.get_document import (
        _get_document,
    )

    return await _get_document(query)
{% endif %}
{% if "search" in cookiecutter.tool_names %}
async def search(
    ctx: RunContext[SkillRunDeps], query: str, limit: int | None = None
) -> str:
    """Search the knowledge base using hybrid search.

    Args:
        query: The search query.
        limit: Maximum number of results.
    """
    from soliplex_skill_{{ cookiecutter.name }}.{{ cookiecutter.name }}.scripts.search import (
        _search,
    )

    return await _search(query, limit)
{% endif %}
{% if "ask" in cookiecutter.tool_names %}
async def ask(
    ctx: RunContext[SkillRunDeps], question: str
) -> str:
    """Ask a question and get an answer with citations from the knowledge base.

    Args:
        question: The question to ask.
    """
    from soliplex_skill_{{ cookiecutter.name }}.{{ cookiecutter.name }}.scripts.ask import (
        _ask,
    )

    return await _ask(question)
{% endif %}
{% if "research" in cookiecutter.tool_names %}
async def research(
    ctx: RunContext[SkillRunDeps], question: str
) -> str:
    """Conduct deep multi-agent research on a question.

    Args:
        question: The research question to investigate.
    """
    from soliplex_skill_{{ cookiecutter.name }}.{{ cookiecutter.name }}.scripts.research import (
        _research,
    )

    return await _research(question)
{% endif %}

def create_skill() -> Skill:
    metadata, instructions = parse_skill_md(
        _SKILL_DIR / "SKILL.md"
    )
    tools = [
        v for k, v in globals().items()
        if k in _TOOL_NAMES and callable(v)
    ]
    return Skill(
        metadata=metadata,
        source=SkillSource.ENTRYPOINT,
        path=_SKILL_DIR,
        instructions=instructions,
        tools=tools,
        state_type=RAGState,
        state_namespace="rag",
    )

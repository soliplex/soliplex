"""Tools based on 'haiku.rag'"""

import pydantic_ai
from haiku.rag import client as hr_client
from haiku.rag.store.models import chunk as rag_store_models_chunk

from soliplex import agents
from soliplex import rag_audit
from soliplex.config import tools as config_tools


async def search_documents(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
    query: str,
) -> list[rag_store_models_chunk.SearchResult]:
    """Search the document knowledge base

    Finds relevant information based on the user's query.

    Args:
        query (str): The search query derived from the user's question.

    Returns:
        list[rag_store_models_chunk.SearchResult]:
            A list of search results with content, scores, and citations.
    """
    tool_config = ctx.deps.tool_configs[config_tools.SDTC_TOOL_KIND]

    hr_config = tool_config.haiku_rag_config

    # Named databases reach haiku.rag through the config, which federates
    # them into one client.
    if tool_config.rag_databases:
        db_path = None
    else:
        db_path = tool_config.rag_lancedb_path

    with rag_audit.audit_tool_access(
        ctx.deps,
        audit_method="search",
        db_path=tool_config.rag_db_audit_path,
        selector=query,
    ) as access:
        async with hr_client.HaikuRAG(
            db_path=db_path,
            config=hr_config,
            read_only=True,
        ) as rag:
            results = await rag.search(
                query,
                limit=tool_config.search_documents_limit,
            )

        access.record_refs([result.chunk_id for result in results])

        return results

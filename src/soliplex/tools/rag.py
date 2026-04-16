"""Tools based on 'haiku.rag'"""

import pydantic_ai
from haiku.rag import client as hr_client
from haiku.rag.store.models import chunk as rag_store_models_chunk

from soliplex import agents
from soliplex.config import tools as config_tools


async def search_documents(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
    query: str,
) -> list[rag_store_models_chunk.SearchResult]:
    """
    Search the document knowledge base for relevant information based on the user's query.

    Args:
        query (str): The search query derived from the user's question.

    Returns:
        list[rag_store_models_chunk.SearchResult]:
            A list of search results with content, scores, and citations.
    """  # noqa: E501  The first line is important to the LLM.
    tool_config = ctx.deps.tool_configs[config_tools.SDTC_TOOL_KIND]

    hr_config = tool_config.haiku_rag_config

    async with hr_client.HaikuRAG(
        db_path=tool_config.rag_lancedb_path,
        config=hr_config,
        read_only=True,
    ) as rag:
        results = await rag.search(
            query,
            limit=tool_config.search_documents_limit,
        )

        return results

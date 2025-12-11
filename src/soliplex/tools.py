import datetime

import pydantic_ai
from haiku.rag import client as rag_client
from haiku.rag.graph import research as rag_research
from haiku.rag.graph.research import graph as rag_research_graph
from haiku.rag.graph.research import state as rag_research_state

from soliplex import agents
from soliplex import agui
from soliplex import config
from soliplex import models


class NoToolConfig(ValueError):
    """The tool should not be called "bare"

    We set the 'tool_config' argumentdefault to 'None' to defeat Pydantic AI's
    overweent desire to pass it, even when we have already curried it in.
    """

    def __init__(self):
        super().__init__("No tool config found")


async def get_current_datetime() -> str:
    """
    Get the current date and time in ISO format.

    Returns:
        str: Current datetime in ISO format with timezone information.
    """
    return datetime.datetime.now(datetime.UTC).isoformat()


async def get_current_user(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
) -> models.UserProfile:
    """Return information from the current user's profile."""
    return ctx.deps.user


async def search_documents(
    query: str,
    tool_config: config.SearchDocumentsToolConfig = None,
) -> list[models.SearchResult]:
    """
    Search the document knowledge base for relevant information based on the user's query.

    Args:
        query (str): The search query derived from the user's question.

    Returns:
        list[models.SearchResult]: A list of documents with their
        relevance scores, and, optionally, document URIs.
    """  # noqa: E501  The first line is important to the LLM.
    if tool_config is None:
        raise NoToolConfig()

    hr_config = tool_config.haiku_rag_config

    hr_client_kw = {
        "db_path": tool_config.rag_lancedb_path,
        "config": hr_config,
    }

    async with rag_client.HaikuRAG(**hr_client_kw) as rag:
        results = await rag.search(
            query,
            limit=tool_config.search_documents_limit,
        )

        if tool_config.expand_context_radius > 0:
            results = await rag.expand_context(
                results,
                radius=tool_config.expand_context_radius,
            )

        def _search_results(doc, score):
            if tool_config.return_citations:
                return models.SearchResult(
                    content=doc.content,
                    score=score,
                    document_uri=doc.document_uri,
                )
            else:
                return models.SearchResult(
                    content=doc.content,
                    score=score,
                )

        return [_search_results(doc, score) for doc, score in results]


async def research_report(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
    question: str,
) -> rag_research.ResearchReport:
    """
    Perform reseach against document knowledge base based on the user's question.

    Args:
        question (str): the user's question.

    Returns:
        (haiku.rag.graph.research.ResearchReport): the research report.
    """  # noqa: E501  The first line is important to the LLM.
    tool_configs = ctx.deps.tool_configs
    try:
        tool_config = tool_configs["research_report"]
    except KeyError as exc:
        raise NoToolConfig() from exc

    hr_config = tool_config.haiku_rag_config
    graph = rag_research_graph.build_research_graph(hr_config)

    hr_client_kw = {
        "db_path": tool_config.rag_lancedb_path,
        "config": hr_config,
    }

    async with rag_client.HaikuRAG(**hr_client_kw) as client:
        context = rag_research.ResearchContext(
            original_question=question,
        )
        state = rag_research_state.ResearchState.from_config(
            context=context,
            config=hr_config,
        )
        graph_deps = rag_research_state.ResearchDeps(
            client=client,
            agui_emitter=ctx.deps.agui_emitter,
        )
        return await graph.run(state=state, deps=graph_deps)


async def agui_state(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
) -> agui.AGUI_State:
    """Return the AGUI state."""
    return ctx.deps.state

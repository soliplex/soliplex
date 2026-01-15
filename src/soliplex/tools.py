import datetime

import jsonpatch
import pydantic
import pydantic_ai
from ag_ui import core as agui_core
from haiku.rag import client as rag_client
from haiku.rag.agents import research as rag_research
from haiku.rag.agents.research import graph as rag_research_graph
from haiku.rag.agents.research import state as rag_research_state
from haiku.rag.store.models import chunk as rag_store_models_chunk

from soliplex import agents
from soliplex import agui
from soliplex import config
from soliplex import models
from soliplex.agui import features as agui_features


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
) -> list[rag_store_models_chunk.SearchResult]:
    """
    Search the document knowledge base for relevant information based on the user's query.

    Args:
        query (str): The search query derived from the user's question.

    Returns:
        list[rag_store_models_chunk.SearchResult]:
            A list of search results with content, scores, and citations.
    """  # noqa: E501  The first line is important to the LLM.
    if tool_config is None:
        raise NoToolConfig()

    hr_config = tool_config.haiku_rag_config

    async with rag_client.HaikuRAG(
        db_path=tool_config.rag_lancedb_path,
        config=hr_config,
    ) as rag:
        results = await rag.search(
            query,
            limit=tool_config.search_documents_limit,
        )

        if hr_config.search.context_radius > 0:
            results = await rag.expand_context(results)

        return results


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
        )
        return await graph.run(state=state, deps=graph_deps)


async def agui_state(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
) -> agui.AGUI_State:
    """Return the AGUI state."""
    return ctx.deps.state


class AWRC_AGUI_State(pydantic.BaseModel):
    filter_documents: agui_features.FilterDocuments | None = None
    ask_history: agui_features.AskedAndAnswered | None = None


async def ask_with_rich_citations(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
    question: str,
) -> pydantic_ai.ToolReturn:
    """Use a document knowledge base to answer the user's question.

    Args:
        question (str): the user's question.

    Returns:
        The answer to the question, based on the knowledge base.
    """
    tool_configs = ctx.deps.tool_configs
    try:
        tool_config = tool_configs["ask_with_rich_citations"]
    except KeyError as exc:
        raise NoToolConfig() from exc

    agui_state = AWRC_AGUI_State.model_validate(ctx.deps.state)

    search_filter = None

    documents = agui_state.filter_documents
    document_ids = getattr(documents, "document_ids", ()) or ()
    quoted = [f"'{id}'" for id in document_ids]

    if quoted:
        search_filter = f"id IN ({', '.join(quoted)})"

    hr_config = tool_config.haiku_rag_config

    async with rag_client.HaikuRAG(
        db_path=tool_config.rag_lancedb_path,
        config=hr_config,
    ) as rag:
        response, citations = await rag.ask(question, filter=search_filter)

        if agui_state.ask_history is None:
            agui_state.ask_history = agui_features.AskedAndAnswered()

        agui_state.ask_history.questions.append(
            agui_features.QuestionResponseCitations(
                question=question,
                response=response,
                citations=citations,
            )
        )
        patch = jsonpatch.make_patch(
            ctx.deps.state,
            agui_state.model_dump(),
        )
        metadata = [
            agui_core.StateDeltaEvent(delta=list(patch)),
        ]
        return pydantic_ai.ToolReturn(
            return_value=response,
            metadata=metadata,
        )

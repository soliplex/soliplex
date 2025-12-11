import datetime
from unittest import mock

import pytest
from haiku.rag.graph import agui as rag_agui

from soliplex import agents
from soliplex import config
from soliplex import installation
from soliplex import tools

USER = {
    "full_name": "Phreddy Phlyntstone",
    "email": "phreddy@example.com",
}
QUESTION = "What are postal regulations regarding lithium batteries?"


@pytest.mark.anyio
@mock.patch("soliplex.tools.datetime")
async def test_get_current_datetime(dt_module):
    NOW = datetime.datetime(2025, 8, 7, 11, 32, 41, tzinfo=datetime.UTC)
    now = dt_module.datetime.now
    now.return_value = NOW

    found = await tools.get_current_datetime()

    assert found == NOW.isoformat()

    now.assert_called_once_with(dt_module.UTC)


@pytest.mark.anyio
async def test_get_current_user():
    deps = mock.create_autospec(agents.AgentDependencies, user=USER)
    ctx = mock.Mock(spec_set=(["deps"]), deps=deps)

    found = await tools.get_current_user(ctx)

    assert found is deps.user


@pytest.mark.anyio
async def test_search_documents_wo_tool_config():
    with pytest.raises(tools.NoToolConfig):
        await tools.search_documents(
            query=QUESTION,
        )


@pytest.mark.anyio
@pytest.mark.parametrize("w_limit", [None, 2])
@pytest.mark.parametrize("w_cites", [False, True])
@pytest.mark.parametrize("w_radius", [0, 2])
@pytest.mark.parametrize("n_docs", [0, 1, 10])
@mock.patch("soliplex.tools.rag_client")
async def test_search_documents(
    rag_client, n_docs, w_radius, w_cites, w_limit
):
    hr_class = rag_client.HaikuRAG = mock.MagicMock()
    hr = hr_class.return_value
    client = hr.__aenter__.return_value
    search = client.search
    expand_context = client.expand_context

    docs = [
        (
            mock.Mock(
                spec=["content", "document_uri"],
                content=f"Doc #{i_doc}",
                document_uri=f"https://example.com/docs/doc_{i_doc}.pdf",
            ),
            i_doc,
        )
        for i_doc in range(n_docs)
    ]

    search.return_value = expand_context.return_value = docs

    sdt_config = mock.create_autospec(config.SearchDocumentsToolConfig)
    sdt_config.expand_context_radius = w_radius
    sdt_config.return_citations = w_cites

    if w_limit is None:
        sdt_config.search_documents_limit = exp_limit = 5
    else:
        sdt_config.search_documents_limit = w_limit
        exp_limit = w_limit

    found = await tools.search_documents(
        query=QUESTION,
        tool_config=sdt_config,
    )

    for f_result, (doc, i_doc) in zip(found, docs, strict=True):
        assert f_result.score == i_doc
        assert f_result.content == doc.content

        if w_cites:
            assert f_result.document_uri == doc.document_uri
        else:
            assert f_result.document_uri is None

    search.assert_awaited_once_with(QUESTION, limit=exp_limit)

    if w_radius > 0:
        expand_context.assert_called_once_with(docs, radius=w_radius)
    else:
        expand_context.assert_not_called()

    hr_class.assert_called_once_with(
        db_path=sdt_config.rag_lancedb_path,
        config=sdt_config.haiku_rag_config,
    )


@pytest.mark.anyio
async def test_rag_research_wo_tool_config():
    agui_emitter = mock.create_autospec(rag_agui.AGUIEmitter)
    deps = mock.create_autospec(
        agents.AgentDependencies,
        user=USER,
        tool_configs={},
        agui_emitter=agui_emitter,
    )
    ctx = mock.Mock(spec_set=(["deps"]), deps=deps)
    with pytest.raises(tools.NoToolConfig):
        await tools.research_report(
            ctx=ctx,
            question=QUESTION,
        )


@pytest.mark.anyio
@mock.patch("soliplex.tools.rag_client")
@mock.patch("soliplex.tools.rag_research_state")
@mock.patch("soliplex.tools.rag_research_graph")
@mock.patch("soliplex.tools.rag_research")
async def test_rag_research(rr, rr_graph, rr_state, rag_client):
    rc_class = rr.ResearchContext

    brg_func = rr_graph.build_research_graph = mock.Mock()
    graph = brg_func.return_value
    graph.run = mock.AsyncMock()

    rs_class = rr_state.ResearchState
    rd_class = rr_state.ResearchDeps

    hr_class = rag_client.HaikuRAG = mock.MagicMock()
    hr = hr_class.return_value
    client = hr.__aenter__.return_value

    hr_config = mock.Mock(spec_set=())
    the_installation = mock.create_autospec(installation.Installation)
    rrt_config = mock.create_autospec(
        config.RAGResearchToolConfig,
        haiku_rag_config=hr_config,
    )
    tool_configs = {"research_report": rrt_config}

    agui_emitter = mock.create_autospec(rag_agui.AGUIEmitter)
    deps = mock.create_autospec(
        agents.AgentDependencies,
        the_installation=the_installation,
        user=USER,
        tool_configs=tool_configs,
        agui_emitter=agui_emitter,
    )
    ctx = mock.Mock(spec_set=(["deps"]), deps=deps)

    found = await tools.research_report(
        ctx=ctx,
        question=QUESTION,
    )

    assert found is graph.run.return_value

    graph.run.assert_awaited_once_with(
        state=rs_class.from_config.return_value,
        deps=rd_class.return_value,
    )

    rd_class.assert_called_once_with(
        client=client,
        agui_emitter=agui_emitter,
    )

    rs_class.from_config.assert_called_once_with(
        context=rc_class.return_value,
        config=hr_config,
    )

    rc_class.assert_called_once_with(
        original_question=QUESTION,
    )

    brg_func.assert_called_once_with(hr_config)

    hr_class.assert_called_once_with(
        db_path=rrt_config.rag_lancedb_path,
        config=hr_config,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("w_state", [False, True])
async def test_agui_state(w_state):
    state = {
        "foo": "Foo",
        "bar": {
            "baz": "Baz",
        },
    }
    if w_state:
        deps = mock.create_autospec(
            agents.AgentDependencies,
            user=USER,
            tool_configs={},
            state=state,
        )
        expected = state
    else:
        deps = mock.create_autospec(
            agents.AgentDependencies,
            user=USER,
            tool_configs={},
            state=None,
        )
        expected = None

    ctx = mock.Mock(spec_set=(["deps"]), deps=deps)

    found = await tools.agui_state(ctx=ctx)

    assert found == expected

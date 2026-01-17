import datetime
from unittest import mock

import pytest
from ag_ui import core as agui_core

from soliplex import agents
from soliplex import config
from soliplex import installation
from soliplex import tools

USER = {
    "full_name": "Phreddy Phlyntstone",
    "email": "phreddy@example.com",
}
QUESTION = "What are postal regulations regarding lithium batteries?"


@pytest.fixture
def the_installation():
    return mock.create_autospec(installation.Installation)


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
async def test_get_current_user(the_installation):
    deps = agents.AgentDependencies(
        the_installation=the_installation,
        user=USER,
    )
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
@pytest.mark.parametrize("w_radius", [0, 2])
@pytest.mark.parametrize("n_docs", [0, 1, 10])
@mock.patch("soliplex.tools.rag_client")
async def test_search_documents(rag_client, n_docs, w_radius, w_limit):
    hr_class = rag_client.HaikuRAG = mock.MagicMock()
    hr = hr_class.return_value
    client = hr.__aenter__.return_value
    search = client.search
    expand_context = client.expand_context

    search_results = [
        mock.Mock(
            spec=["content", "document_uri", "score"],
            content=f"Doc #{i_doc}",
            document_uri=f"https://example.com/docs/doc_{i_doc}.pdf",
            score=i_doc,
        )
        for i_doc in range(n_docs)
    ]

    search.return_value = expand_context.return_value = search_results

    sdt_config = mock.create_autospec(config.SearchDocumentsToolConfig)
    sdt_config.haiku_rag_config.search.context_radius = w_radius

    if w_limit is None:
        sdt_config.search_documents_limit = exp_limit = 5
    else:
        sdt_config.search_documents_limit = w_limit
        exp_limit = w_limit

    found = await tools.search_documents(
        query=QUESTION,
        tool_config=sdt_config,
    )

    if w_radius > 0:
        assert found is expand_context.return_value
    else:
        assert found is search_results

    search.assert_awaited_once_with(QUESTION, limit=exp_limit)

    if w_radius > 0:
        expand_context.assert_called_once_with(search_results)
    else:
        expand_context.assert_not_called()

    hr_class.assert_called_once_with(
        db_path=sdt_config.rag_lancedb_path,
        config=sdt_config.haiku_rag_config,
    )


@pytest.mark.anyio
async def test_rag_research_wo_tool_config(the_installation):
    deps = agents.AgentDependencies(
        the_installation=the_installation,
        user=USER,
        tool_configs={},
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
async def test_rag_research(
    rr,
    rr_graph,
    rr_state,
    rag_client,
    the_installation,
):
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
    rrt_config = mock.create_autospec(
        config.RAGResearchToolConfig,
        haiku_rag_config=hr_config,
    )
    tool_configs = {"research_report": rrt_config}

    deps = agents.AgentDependencies(
        the_installation=the_installation,
        user=USER,
        tool_configs=tool_configs,
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
async def test_agui_state(the_installation, w_state):
    state = {
        "foo": "Foo",
        "bar": {
            "baz": "Baz",
        },
    }
    if w_state:
        deps = agents.AgentDependencies(
            the_installation=the_installation,
            user=USER,
            tool_configs={},
            state=state,
        )
        expected = state
    else:
        deps = agents.AgentDependencies(
            the_installation=the_installation,
            user=USER,
            tool_configs={},
        )
        expected = {}

    ctx = mock.Mock(spec_set=(["deps"]), deps=deps)

    found = await tools.agui_state(ctx=ctx)

    assert found == expected


@pytest.mark.anyio
async def test_ask_with_rich_citations_wo_tool_config(the_installation):
    deps = agents.AgentDependencies(
        the_installation=the_installation,
        user=USER,
        tool_configs={},
    )
    ctx = mock.Mock(spec_set=(["deps"]), deps=deps)
    with pytest.raises(tools.NoToolConfig):
        await tools.ask_with_rich_citations(
            ctx=ctx,
            question=QUESTION,
        )


@pytest.mark.anyio
@pytest.mark.parametrize("w_history", [False, True])
@pytest.mark.parametrize("w_filter", [False, True])
@mock.patch("soliplex.tools.rag_client")
async def test_ask_with_rich_citations(
    rag_client,
    the_installation,
    w_filter,
    w_history,
):
    QUESTION = "Which way is up?"
    ANSWER = "The other way from down"

    hr_class = rag_client.HaikuRAG = mock.MagicMock()
    hr = hr_class.return_value
    client = hr.__aenter__.return_value
    ask = client.ask
    ask.return_value = ANSWER, []

    state = {}
    expected_delta = []

    if w_filter:
        state["filter_documents"] = {
            "document_ids": [
                "DOCID1",
                "DOCID2",
            ],
        }
        exp_filter = "id IN ('DOCID1', 'DOCID2')"
    else:
        exp_filter = None
        expected_delta.append(
            {"op": "add", "path": "/filter_documents", "value": None}
        )

    exp_question = {"question": QUESTION, "citations": [], "response": ANSWER}

    if w_history:
        state["ask_history"] = {
            "questions": [
                {
                    "question": "Why is the sky blue?",
                    "response": "Because it isn't orange",
                    "citations": [],
                }
            ],
        }
        expected_delta.append(
            {
                "op": "add",
                "path": "/ask_history/questions/1",
                "value": exp_question,
            }
        )
    else:
        expected_delta.append(
            {
                "op": "add",
                "path": "/ask_history",
                "value": {
                    "questions": [
                        exp_question,
                    ],
                },
            }
        )

    awrctc = mock.create_autospec(
        config.AskWithRichCitationsToolConfig,
    )

    deps = agents.AgentDependencies(
        the_installation=the_installation,
        user=USER,
        tool_configs={"ask_with_rich_citations": awrctc},
        state=state,
    )

    ctx = mock.Mock(spec_set=(["deps"]), deps=deps)

    found = await tools.ask_with_rich_citations(
        ctx=ctx,
        question=QUESTION,
    )

    assert found.return_value is ANSWER

    (sd_event,) = found.metadata
    assert isinstance(sd_event, agui_core.StateDeltaEvent)
    found_delta = sd_event.delta

    # jsonpatch.make_patch does not guarantee order of patches.
    assert len(found_delta) == len(expected_delta)

    for ed in expected_delta:
        assert ed in found_delta

    ask.assert_called_once_with(QUESTION, filter=exp_filter)

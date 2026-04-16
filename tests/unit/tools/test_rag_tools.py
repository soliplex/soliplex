from unittest import mock

import pydantic_ai
import pytest

from soliplex import agents
from soliplex.config import tools as config_tools
from soliplex.tools import rag as rag_tools

QUESTION = "What are postal regulations regarding lithium batteries?"


@pytest.fixture
def sd_tool_config():
    return mock.create_autospec(config_tools.SearchDocumentsToolConfig)


@pytest.fixture
def ctx_w_deps(sd_tool_config):
    ctx = mock.create_autospec(pydantic_ai.RunContext)
    ctx.deps = mock.create_autospec(agents.AgentDependencies)
    ctx.deps.tool_configs = {
        config_tools.SDTC_TOOL_KIND: sd_tool_config,
    }
    return ctx


@pytest.mark.anyio
@pytest.mark.parametrize("w_limit", [None, 2])
@pytest.mark.parametrize("n_docs", [0, 1, 10])
@mock.patch("soliplex.tools.rag.hr_client")
async def test_search_documents(
    hr_client, ctx_w_deps, sd_tool_config, n_docs, w_limit
):
    hr_class = hr_client.HaikuRAG = mock.MagicMock()
    hr = hr_class.return_value
    client = hr.__aenter__.return_value
    search = client.search

    search_results = [
        mock.Mock(
            spec=["content", "document_uri", "score"],
            content=f"Doc #{i_doc}",
            document_uri=f"https://example.com/docs/doc_{i_doc}.pdf",
            score=i_doc,
        )
        for i_doc in range(n_docs)
    ]

    search.return_value = search_results

    if w_limit is None:
        sd_tool_config.search_documents_limit = exp_limit = 5
    else:
        sd_tool_config.search_documents_limit = w_limit
        exp_limit = w_limit

    found = await rag_tools.search_documents(
        ctx_w_deps,
        query=QUESTION,
    )

    assert found is search_results

    search.assert_awaited_once_with(QUESTION, limit=exp_limit)

    hr_class.assert_called_once_with(
        db_path=sd_tool_config.rag_lancedb_path,
        config=sd_tool_config.haiku_rag_config,
        read_only=True,
    )

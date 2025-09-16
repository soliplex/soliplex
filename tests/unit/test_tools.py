import datetime
from unittest import mock

import pytest

from soliplex import config
from soliplex import tools


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

    with mock.patch.dict("os.environ", RAG_LANCE_DB_PATH="/tmp/rag/"):
        found = await tools.search_documents(
            "postal regulations", tool_config=sdt_config,
        )

    for f_result, (doc, i_doc) in zip(found, docs, strict=True):
        assert f_result.score == i_doc
        assert f_result.content == doc.content

        if w_cites:
            assert f_result.document_uri == doc.document_uri
        else:
            assert f_result.document_uri is None

    search.assert_awaited_once_with("postal regulations", limit=exp_limit)

    if w_radius > 0:
        expand_context.assert_called_once_with(docs, radius=w_radius)
    else:
        expand_context.assert_not_called()

    hr_class.assert_called_once_with(sdt_config.rag_lancedb_path)

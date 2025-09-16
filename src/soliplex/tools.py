import datetime

from haiku.rag import client as rag_client

from soliplex import config
from soliplex import models


async def get_current_datetime() -> str:
    """
    Get the current date and time in ISO format.

    Returns:
        str: Current datetime in ISO format with timezone information.
    """
    return datetime.datetime.now(datetime.UTC).isoformat()


async def search_documents(
    query: str,
    tool_config: config.SearchDocumentsToolConfig=None,
) -> list[models.SearchResult]:
    """
    Search the document knowledge base for relevant information based on the user's query.

    Args:
        query (str): The search query derived from the user's question.

    Returns:
        list[models.SearchResult]: A list of documents with their
        relevance scores, and, optionally, document URIs.
    """  # noqa: E501  The first line is important to the LLM.
    async with rag_client.HaikuRAG(tool_config.rag_lancedb_path) as rag:

        results = await rag.search(
            query, limit=tool_config.search_documents_limit,
        )

        if tool_config.expand_context_radius > 0:
            results = await rag.expand_context(
                results, radius=tool_config.expand_context_radius,
            )

        def _search_results(doc, score):
            if tool_config.return_citations:
                return models.SearchResult(
                    content=doc.content,
                    score=score,
                    document_uri=doc.document_uri
                )
            else:
                return models.SearchResult(
                    content=doc.content,
                    score=score,
                )

        return [_search_results(doc, score) for doc, score in results ]

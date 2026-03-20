# /// script
# requires-python = ">=3.12"
# dependencies = ["haiku.rag-slim >= 0.34.0, < 0.35"]
# ///
"""Ask a question and get an answer with citations."""
import asyncio

from {{ cookiecutter.name }}._lib import DB_PATH
from {{ cookiecutter.name }}._lib import get_config


def main(question: str):
    """Ask a question and get an answer with citations from the knowledge base.

    Args:
        question: The question to ask.
    """

    async def _run():
        from haiku.rag.client import HaikuRAG
        from haiku.rag.utils import format_citations

        async with HaikuRAG(
            DB_PATH, config=get_config(), read_only=True
        ) as rag:
            answer, citations = await rag.ask(question)

        if citations:
            answer += "\n\n" + format_citations(citations)

        return answer

    print(asyncio.run(_run()))


if __name__ == "__main__":
    main()

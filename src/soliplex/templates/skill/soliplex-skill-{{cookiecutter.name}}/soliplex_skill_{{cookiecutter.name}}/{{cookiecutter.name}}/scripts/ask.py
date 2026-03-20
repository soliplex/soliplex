# /// script
# requires-python = ">=3.12"
# dependencies = ["haiku.rag-slim >= 0.34.0, < 0.35"]
# ///
"""Ask a question and get an answer with citations."""
import asyncio
from pathlib import Path

_DB_PATH = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "{{ cookiecutter.name }}.lancedb"
)


def _get_config():
    config_path = (
        Path(__file__).resolve().parent.parent
        / "assets"
        / "haiku.rag.yaml"
    )
    if config_path.exists():
        from haiku.rag.config import AppConfig

        return AppConfig.from_yaml(config_path)
    return None


async def _ask(question):
    from haiku.rag.client import HaikuRAG
    from haiku.rag.utils import format_citations

    async with HaikuRAG(
        _DB_PATH, config=_get_config(), read_only=True
    ) as rag:
        answer, citations = await rag.ask(question)

    if citations:
        answer += "\n\n" + format_citations(citations)

    return answer


def main(question: str):
    """Ask a question and get an answer with citations from the knowledge base.

    Args:
        question: The question to ask.
    """
    print(asyncio.run(_ask(question)))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Ask a question and get an answer with citations."
    )
    parser.add_argument(
        "--question", required=True,
        help="The question to ask.",
    )
    args = parser.parse_args()
    main(args.question)

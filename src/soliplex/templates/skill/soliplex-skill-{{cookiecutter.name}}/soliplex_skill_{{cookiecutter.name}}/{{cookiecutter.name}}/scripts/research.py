# /// script
# requires-python = ">=3.12"
# dependencies = ["haiku.rag-slim >= 0.34.0, < 0.35"]
# ///
"""Conduct deep multi-agent research on a question."""
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


async def _research(question):
    from haiku.rag.client import HaikuRAG

    async with HaikuRAG(
        _DB_PATH, config=_get_config(), read_only=True
    ) as rag:
        report = await rag.research(question)

    parts = [
        f"# {report.title}",
        f"\n## Executive Summary\n{report.executive_summary}",
    ]
    if report.main_findings:
        parts.append("\n## Main Findings")
        for finding in report.main_findings:
            parts.append(f"- {finding}")
    if report.conclusions:
        parts.append("\n## Conclusions")
        for conclusion in report.conclusions:
            parts.append(f"- {conclusion}")
    if report.recommendations:
        parts.append("\n## Recommendations")
        for rec in report.recommendations:
            parts.append(f"- {rec}")
    parts.append(f"\n## Sources\n{report.sources_summary}")
    return "\n".join(parts)


def main(question: str):
    """Conduct deep multi-agent research on a question.

    Args:
        question: The research question to investigate.
    """
    print(asyncio.run(_research(question)))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Conduct deep multi-agent research."
    )
    parser.add_argument(
        "--question", required=True,
        help="The research question to investigate.",
    )
    args = parser.parse_args()
    main(args.question)

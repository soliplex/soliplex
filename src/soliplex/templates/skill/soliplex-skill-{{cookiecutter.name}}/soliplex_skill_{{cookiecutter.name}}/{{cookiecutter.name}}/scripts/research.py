# /// script
# requires-python = ">=3.12"
# dependencies = ["haiku.rag-slim >= 0.34.0, < 0.35"]
# ///
"""Conduct deep multi-agent research on a question."""
import asyncio

from {{ cookiecutter.name }}._lib import DB_PATH
from {{ cookiecutter.name }}._lib import get_config


def main(question: str):
    """Conduct deep multi-agent research on a question.

    Args:
        question: The research question to investigate.
    """

    async def _run():
        from haiku.rag.client import HaikuRAG

        async with HaikuRAG(
            DB_PATH, config=get_config(), read_only=True
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
        parts.append(
            f"\n## Sources\n{report.sources_summary}"
        )
        return "\n".join(parts)

    print(asyncio.run(_run()))


if __name__ == "__main__":
    main()

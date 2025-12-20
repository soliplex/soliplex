#!/usr/bin/env python3
"""LLM Documentation Comprehension Evaluation using pydantic-evals.

This script evaluates whether an LLM can effectively answer questions
using only the Soliplex documentation files.

Uses pydantic-evals for the evaluation framework and pydantic-ai for LLM integration.

Usage:
    # With OpenAI (default)
    OPENAI_API_KEY=sk-... uv run python scripts/eval_comprehension.py

    # With Ollama
    OLLAMA_BASE_URL=http://127.0.0.1:11434 uv run python scripts/eval_comprehension.py --provider ollama --model llama3.2

    # Single domain
    uv run python scripts/eval_comprehension.py --domain server

    # Dry run (no LLM calls)
    uv run python scripts/eval_comprehension.py --dry-run
"""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import pydantic_ai
import yaml
from pydantic_ai.models import openai as openai_models
from pydantic_ai.providers import ollama as ollama_providers
from pydantic_ai.providers import openai as openai_providers
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext


PROJECT_ROOT = Path(__file__).parent.parent
SITE_DIR = PROJECT_ROOT / "site"
EVALS_FILE = PROJECT_ROOT / "tests" / "evals" / "questions.yaml"

# Map domain names to their full content files
DOMAIN_FILES = {
    "project": "llms-project-full.txt",
    "server": "llms-server-full.txt",
    "client": "llms-client-full.txt",
}

# Default models
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OLLAMA_MODEL = "llama3.2"

# Global agent instance (set by main)
_agent: pydantic_ai.Agent | None = None
_docs_cache: dict[str, str] = {}


@dataclass
class QuestionInput:
    """Input for a documentation question."""

    question: str
    domain: str


@dataclass
class ExpectedTopics:
    """Expected topics that should appear in the answer."""

    topics: list[str]


class TopicCoverageEvaluator(Evaluator[str, ExpectedTopics]):
    """Evaluator that checks if expected topics appear in the output."""

    def evaluate(self, ctx: EvaluatorContext[str, ExpectedTopics]) -> float:
        """Return score based on topic coverage (0.0 to 1.0)."""
        if ctx.expected_output is None:
            return 1.0

        output_lower = ctx.output.lower()
        expected_topics = ctx.expected_output.topics
        found = 0

        for topic in expected_topics:
            # Case-insensitive check with underscore/space variants
            topic_variants = [
                topic.lower(),
                topic.lower().replace("_", " "),
                topic.lower().replace(" ", "_"),
            ]
            if any(variant in output_lower for variant in topic_variants):
                found += 1

        return found / len(expected_topics) if expected_topics else 1.0


def load_questions(evals_file: Path = EVALS_FILE) -> dict:
    """Load evaluation questions from YAML file."""
    if not evals_file.exists():
        raise FileNotFoundError(f"Evals file not found: {evals_file}")

    with open(evals_file) as f:
        return yaml.safe_load(f)


def load_docs(domain: str) -> str:
    """Load documentation content for a domain."""
    if domain in _docs_cache:
        return _docs_cache[domain]

    filename = DOMAIN_FILES.get(domain)
    if not filename:
        raise ValueError(f"Unknown domain: {domain}")

    filepath = SITE_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(
            f"Documentation file not found: {filepath}\n"
            "Run 'uv run mkdocs build' first to generate docs."
        )

    content = filepath.read_text()
    _docs_cache[domain] = content
    return content


def create_agent(
    provider_type: str = "openai",
    model_name: str | None = None,
    base_url: str | None = None,
) -> pydantic_ai.Agent:
    """Create a pydantic-ai agent for evaluation."""
    if provider_type == "ollama":
        model = model_name or DEFAULT_OLLAMA_MODEL
        ollama_url = base_url or os.environ.get("OLLAMA_BASE_URL")
        provider_kwargs = {}
        if ollama_url:
            provider_kwargs["base_url"] = ollama_url
        provider = ollama_providers.OllamaProvider(**provider_kwargs)
    else:
        model = model_name or DEFAULT_OPENAI_MODEL
        provider_kwargs = {}
        if base_url:
            provider_kwargs["base_url"] = base_url
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            provider_kwargs["api_key"] = api_key
        provider = openai_providers.OpenAIProvider(**provider_kwargs)

    return pydantic_ai.Agent(
        model=openai_models.OpenAIChatModel(
            model_name=model,
            provider=provider,
        ),
        instructions=(
            "You are a developer assistant. Answer questions using ONLY "
            "the documentation provided in the user message. Be specific "
            "and mention relevant classes, functions, or concepts by name."
        ),
    )


async def answer_question(inputs: QuestionInput) -> str:
    """Task function that answers a question using documentation."""
    if _agent is None:
        return "[DRY RUN] No agent configured"

    docs_content = load_docs(inputs.domain)

    prompt = f"""Answer the following question using ONLY the documentation below.
Be specific and mention relevant classes, functions, or concepts by name.

<documentation>
{docs_content}
</documentation>

Question: {inputs.question}

Answer concisely but thoroughly, referencing specific items from the documentation."""

    result = await _agent.run(prompt)
    return result.output


def build_dataset(domains: list[str] | None = None) -> Dataset[QuestionInput, str]:
    """Build a pydantic-evals Dataset from questions.yaml."""
    questions = load_questions()

    if domains is None:
        domains = list(DOMAIN_FILES.keys())

    cases = []
    for domain in domains:
        if domain not in questions:
            print(f"Warning: No questions for domain '{domain}'", file=sys.stderr)
            continue

        for q in questions[domain]:
            case = Case(
                name=f"{domain}:{q['question'][:40]}...",
                inputs=QuestionInput(
                    question=q["question"],
                    domain=domain,
                ),
                expected_output=ExpectedTopics(topics=q["expected_topics"]),
                metadata={
                    "domain": domain,
                    "difficulty": q.get("difficulty", "medium"),
                    "full_question": q["question"],
                },
            )
            cases.append(case)

    return Dataset(
        cases=cases,
        evaluators=[TopicCoverageEvaluator()],
    )


def main():
    global _agent

    parser = argparse.ArgumentParser(
        description="Evaluate LLM comprehension of Soliplex documentation"
    )
    parser.add_argument(
        "--domain",
        "-d",
        choices=list(DOMAIN_FILES.keys()),
        help="Evaluate only a specific domain",
    )
    parser.add_argument(
        "--provider",
        "-p",
        choices=["openai", "ollama"],
        default="openai",
        help="LLM provider to use (default: openai)",
    )
    parser.add_argument(
        "--model",
        "-m",
        help=f"Model name (default: {DEFAULT_OPENAI_MODEL} for openai, "
        f"{DEFAULT_OLLAMA_MODEL} for ollama)",
    )
    parser.add_argument(
        "--base-url",
        help="Custom base URL for the provider",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="List cases without calling LLM",
    )
    args = parser.parse_args()

    domains = [args.domain] if args.domain else None

    # Build dataset
    dataset = build_dataset(domains)
    print(f"Built dataset with {len(dataset.cases)} cases")

    if args.dry_run:
        print("\n=== DRY RUN - Cases ===")
        for case in dataset.cases:
            print(f"  [{case.metadata['domain']}] {case.metadata['full_question']}")
            print(f"    Expected topics: {case.expected_output.topics}")
        return

    # Create agent
    _agent = create_agent(
        provider_type=args.provider,
        model_name=args.model,
        base_url=args.base_url,
    )

    # Run evaluation
    print("\nRunning evaluation...")
    report = dataset.evaluate_sync(answer_question)

    # Print report
    print("\n" + "=" * 60)
    print("EVALUATION REPORT")
    print("=" * 60)
    report.print(include_input=True, include_output=False)

    # Calculate pass rate (score >= 0.6 is passing)
    scores = [
        r.scores.get("TopicCoverageEvaluator", 0)
        for r in report.results
        if r.scores
    ]
    if scores:
        avg_score = sum(scores) / len(scores)
        passing = sum(1 for s in scores if s >= 0.6)
        print(f"\nAverage score: {avg_score:.2f}")
        print(f"Passing (>=60%): {passing}/{len(scores)}")

        if avg_score < 0.8:
            sys.exit(1)


if __name__ == "__main__":
    main()

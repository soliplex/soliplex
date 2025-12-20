#!/usr/bin/env python3
"""LLM Documentation Comprehension Evaluation.

This script evaluates whether an LLM can effectively answer questions
using only the Soliplex documentation files.

Uses pydantic-ai for LLM integration, supporting OpenAI and Ollama.

Usage:
    # With OpenAI (default)
    OPENAI_API_KEY=sk-... uv run python scripts/eval_comprehension.py

    # With Ollama
    uv run python scripts/eval_comprehension.py --provider ollama --model llama3.2

    # Single domain
    uv run python scripts/eval_comprehension.py --domain server

    # Dry run (no LLM calls)
    uv run python scripts/eval_comprehension.py --dry-run
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import pydantic_ai
import yaml
from pydantic_ai.models import openai as openai_models
from pydantic_ai.providers import ollama as ollama_providers
from pydantic_ai.providers import openai as openai_providers


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


@dataclass
class EvalResult:
    """Result of a single evaluation question."""

    domain: str
    question: str
    expected_topics: list[str]
    found_topics: list[str]
    missing_topics: list[str]
    passed: bool
    response_preview: str
    difficulty: str


def load_questions(evals_file: Path = EVALS_FILE) -> dict:
    """Load evaluation questions from YAML file."""
    if not evals_file.exists():
        raise FileNotFoundError(f"Evals file not found: {evals_file}")

    with open(evals_file) as f:
        return yaml.safe_load(f)


def load_docs(domain: str) -> str:
    """Load documentation content for a domain."""
    filename = DOMAIN_FILES.get(domain)
    if not filename:
        raise ValueError(f"Unknown domain: {domain}")

    filepath = SITE_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(
            f"Documentation file not found: {filepath}\n"
            "Run 'uv run mkdocs build' first to generate docs."
        )

    return filepath.read_text()


def create_agent(
    provider_type: str = "openai",
    model_name: str | None = None,
    base_url: str | None = None,
) -> pydantic_ai.Agent:
    """Create a pydantic-ai agent for evaluation."""
    if provider_type == "ollama":
        model = model_name or DEFAULT_OLLAMA_MODEL
        provider_kwargs = {}
        if base_url:
            provider_kwargs["base_url"] = base_url
        provider = ollama_providers.OllamaProvider(**provider_kwargs)
        # Ollama needs a dummy api_key
        provider_kwargs["api_key"] = "dummy"
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


async def ask_llm(agent: pydantic_ai.Agent, question: str, context: str) -> str:
    """Ask the LLM a question with documentation context."""
    prompt = f"""Answer the following question using ONLY the documentation below.
Be specific and mention relevant classes, functions, or concepts by name.

<documentation>
{context}
</documentation>

Question: {question}

Answer concisely but thoroughly, referencing specific items from the documentation."""

    result = await agent.run(prompt)
    return result.output


def check_topics(response: str, expected_topics: list[str]) -> tuple[list, list]:
    """Check which expected topics appear in the response."""
    response_lower = response.lower()
    found = []
    missing = []

    for topic in expected_topics:
        # Case-insensitive check, also handle underscores vs spaces
        topic_variants = [
            topic.lower(),
            topic.lower().replace("_", " "),
            topic.lower().replace(" ", "_"),
        ]
        if any(variant in response_lower for variant in topic_variants):
            found.append(topic)
        else:
            missing.append(topic)

    return found, missing


async def evaluate_question(
    agent: pydantic_ai.Agent,
    domain: str,
    question_data: dict,
    docs_content: str,
    dry_run: bool = False,
) -> EvalResult:
    """Evaluate a single question."""
    question = question_data["question"]
    expected_topics = question_data["expected_topics"]
    difficulty = question_data.get("difficulty", "medium")

    if dry_run:
        # In dry run mode, simulate a response
        response = f"[DRY RUN] Would ask: {question}"
        found_topics = []
        missing_topics = expected_topics
    else:
        response = await ask_llm(agent, question, docs_content)
        found_topics, missing_topics = check_topics(response, expected_topics)

    # Pass if at least 60% of expected topics are found
    pass_threshold = 0.6
    passed = len(found_topics) >= len(expected_topics) * pass_threshold

    return EvalResult(
        domain=domain,
        question=question,
        expected_topics=expected_topics,
        found_topics=found_topics,
        missing_topics=missing_topics,
        passed=passed,
        response_preview=response[:200] + "..." if len(response) > 200 else response,
        difficulty=difficulty,
    )


async def run_evaluation(
    agent: pydantic_ai.Agent,
    domains: list[str] | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> list[EvalResult]:
    """Run evaluation for specified domains."""
    questions = load_questions()
    results = []

    if domains is None:
        domains = list(DOMAIN_FILES.keys())

    for domain in domains:
        if domain not in questions:
            print(f"Warning: No questions for domain '{domain}'", file=sys.stderr)
            continue

        if not dry_run:
            try:
                docs_content = load_docs(domain)
            except FileNotFoundError as e:
                print(f"Error: {e}", file=sys.stderr)
                continue
        else:
            docs_content = "[DRY RUN - no docs loaded]"

        domain_questions = questions[domain]
        print(
            f"\n=== Evaluating {domain.upper()} "
            f"({len(domain_questions)} questions) ==="
        )

        for i, q in enumerate(domain_questions, 1):
            if verbose:
                print(f"  [{i}/{len(domain_questions)}] {q['question'][:50]}...")

            result = await evaluate_question(
                agent, domain, q, docs_content, dry_run
            )
            results.append(result)

            status = "PASS" if result.passed else "FAIL"
            if verbose:
                found = len(result.found_topics)
                total = len(result.expected_topics)
                print(f"    {status}: {found}/{total} topics")
                if result.missing_topics:
                    print(f"    Missing: {', '.join(result.missing_topics)}")

    return results


def print_summary(results: list[EvalResult]) -> None:
    """Print evaluation summary."""
    if not results:
        print("\nNo results to summarize.")
        return

    # Overall stats
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    pass_rate = passed / total * 100

    print(f"\n{'=' * 60}")
    print("EVALUATION SUMMARY")
    print(f"{'=' * 60}")
    print(f"Total questions: {total}")
    print(f"Passed: {passed} ({pass_rate:.1f}%)")
    print(f"Failed: {total - passed} ({100 - pass_rate:.1f}%)")

    # Per-domain breakdown
    domains = set(r.domain for r in results)
    print(f"\n{'Domain':<12} {'Passed':<10} {'Total':<10} {'Rate':<10}")
    print("-" * 42)
    for domain in sorted(domains):
        domain_results = [r for r in results if r.domain == domain]
        domain_passed = sum(1 for r in domain_results if r.passed)
        domain_total = len(domain_results)
        domain_rate = domain_passed / domain_total * 100
        print(f"{domain:<12} {domain_passed:<10} {domain_total:<10} {domain_rate:.1f}%")

    # By difficulty
    difficulties = set(r.difficulty for r in results)
    if len(difficulties) > 1:
        print(f"\n{'Difficulty':<12} {'Passed':<10} {'Total':<10} {'Rate':<10}")
        print("-" * 42)
        for diff in ["easy", "medium", "hard"]:
            diff_results = [r for r in results if r.difficulty == diff]
            if diff_results:
                diff_passed = sum(1 for r in diff_results if r.passed)
                diff_total = len(diff_results)
                diff_rate = diff_passed / diff_total * 100
                print(f"{diff:<12} {diff_passed:<10} {diff_total:<10} {diff_rate:.1f}%")

    # Failed questions detail
    failed = [r for r in results if not r.passed]
    if failed:
        print(f"\n{'=' * 60}")
        print("FAILED QUESTIONS")
        print(f"{'=' * 60}")
        for r in failed:
            print(f"\n[{r.domain}] {r.question}")
            print(f"  Expected: {', '.join(r.expected_topics)}")
            print(f"  Found: {', '.join(r.found_topics) or '(none)'}")
            print(f"  Missing: {', '.join(r.missing_topics)}")


def print_json(results: list[EvalResult]) -> None:
    """Print results as JSON."""
    output = {
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "pass_rate": (
                sum(1 for r in results if r.passed) / len(results)
                if results
                else 0
            ),
        },
        "results": [
            {
                "domain": r.domain,
                "question": r.question,
                "passed": r.passed,
                "expected_topics": r.expected_topics,
                "found_topics": r.found_topics,
                "missing_topics": r.missing_topics,
                "difficulty": r.difficulty,
            }
            for r in results
        ],
    }
    print(json.dumps(output, indent=2))


async def main_async(args):
    """Async main function."""
    domains = [args.domain] if args.domain else None

    if not args.dry_run:
        agent = create_agent(
            provider_type=args.provider,
            model_name=args.model,
            base_url=args.base_url,
        )
    else:
        agent = None

    results = await run_evaluation(
        agent=agent,
        domains=domains,
        dry_run=args.dry_run,
        verbose=args.verbose or not args.json,
    )

    if args.json:
        print_json(results)
    else:
        print_summary(results)

    # Exit with error if pass rate < 80%
    if results:
        pass_rate = sum(1 for r in results if r.passed) / len(results)
        if pass_rate < 0.8:
            sys.exit(1)


def main():
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
        help="Custom base URL for the provider (e.g., Ollama URL)",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="List questions without calling LLM",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed progress",
    )
    args = parser.parse_args()

    import asyncio

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""LLM Documentation Comprehension Evaluation.

This script evaluates whether an LLM can effectively answer questions
using only the Soliplex documentation files.

Usage:
    uv run python scripts/eval_comprehension.py
    uv run python scripts/eval_comprehension.py --domain server
    uv run python scripts/eval_comprehension.py --json
    uv run python scripts/eval_comprehension.py --dry-run
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

# Optional: Use anthropic SDK if available
try:
    import anthropic

    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


PROJECT_ROOT = Path(__file__).parent.parent
SITE_DIR = PROJECT_ROOT / "site"
EVALS_FILE = PROJECT_ROOT / "tests" / "evals" / "questions.yaml"

# Map domain names to their full content files
DOMAIN_FILES = {
    "project": "llms-project-full.txt",
    "server": "llms-server-full.txt",
    "client": "llms-client-full.txt",
}


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


def ask_llm(question: str, context: str) -> str:
    """Ask the LLM a question with documentation context."""
    if not HAS_ANTHROPIC:
        raise RuntimeError(
            "anthropic package not installed. "
            "Install with: uv add anthropic"
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Set it to run evaluations."
        )

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are a developer assistant. Answer the following question
using ONLY the documentation provided below. Be specific and mention relevant
classes, functions, or concepts by name.

<documentation>
{context}
</documentation>

Question: {question}

Answer concisely but thoroughly, referencing specific items from the documentation."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


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


def evaluate_question(
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
        response = ask_llm(question, docs_content)
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


def run_evaluation(
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
        print(f"\n=== Evaluating {domain.upper()} ({len(domain_questions)} questions) ===")

        for i, q in enumerate(domain_questions, 1):
            if verbose:
                print(f"  [{i}/{len(domain_questions)}] {q['question'][:50]}...")

            result = evaluate_question(domain, q, docs_content, dry_run)
            results.append(result)

            status = "PASS" if result.passed else "FAIL"
            if verbose:
                print(f"    {status}: {len(result.found_topics)}/{len(result.expected_topics)} topics")
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
            "pass_rate": sum(1 for r in results if r.passed) / len(results) if results else 0,
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

    domains = [args.domain] if args.domain else None

    try:
        results = run_evaluation(
            domains=domains,
            dry_run=args.dry_run,
            verbose=args.verbose or not args.json,
        )
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print_json(results)
    else:
        print_summary(results)

    # Exit with error if pass rate < 80%
    if results:
        pass_rate = sum(1 for r in results if r.passed) / len(results)
        if pass_rate < 0.8:
            sys.exit(1)


if __name__ == "__main__":
    main()

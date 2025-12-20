#!/usr/bin/env python3
"""LLM Documentation Comprehension Evaluation using pydantic-evals.

This script evaluates whether an LLM can effectively use Soliplex
documentation - either navigating the index or comprehending full content.

Uses pydantic-evals for the evaluation framework and pydantic-ai
for LLM integration.

Usage:
    # Navigation mode - test if LLM can find right section from index
    uv run python scripts/eval_comprehension.py --mode navigation

    # Comprehension mode (default) - test if LLM can answer from full docs
    uv run python scripts/eval_comprehension.py --mode comprehension

    # With Ollama
    OLLAMA_URL=http://127.0.0.1:11434/v1 \\
        uv run python scripts/eval_comprehension.py \\
        --provider ollama --model llama3.2

    # With Logfire tracing
    LOGFIRE_TOKEN=... uv run python scripts/eval_comprehension.py

    # JSON output for CI integration
    uv run python scripts/eval_comprehension.py --json > results.json

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
from pydantic import BaseModel
from pydantic_ai.models import openai as openai_models
from pydantic_ai.providers import ollama as ollama_providers
from pydantic_ai.providers import openai as openai_providers
from pydantic_evals import Case
from pydantic_evals import Dataset
from pydantic_evals.evaluators import Evaluator
from pydantic_evals.evaluators import EvaluatorContext

PROJECT_ROOT = Path(__file__).parent.parent
SITE_DIR = PROJECT_ROOT / "site"
EVALS_FILE = PROJECT_ROOT / "tests" / "evals" / "questions.yaml"

# Expected marker in locally-built docs (not production URLs)
LOCAL_BUILD_MARKER = "127.0.0.1"
PROD_URL_MARKER = "soliplex.github.io"

# Map domain names to their files (map and full content)
DOMAIN_FILES = {
    "project": {
        "map": "llms-project.txt",
        "full": "llms-project-full.txt",
    },
    "server": {
        "map": "llms-server.txt",
        "full": "llms-server-full.txt",
    },
    "client": {
        "map": "llms-client.txt",
        "full": "llms-client-full.txt",
    },
}

# Default models
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OLLAMA_MODEL = "llama3.2"

# Global state (set by main)
_agent: pydantic_ai.Agent | None = None  # Type: Agent[None, StructuredAnswer]
_judge_agent: pydantic_ai.Agent | None = None  # Type: Agent[None, JudgeScore]
_docs_cache: dict[str, str] = {}
_eval_mode: str = "comprehension"


@dataclass
class QuestionInput:
    """Input for a documentation question."""

    question: str
    domain: str


@dataclass
class ExpectedTopics:
    """Expected topics that should appear in the answer."""

    topics: list[str]


class StructuredAnswer(BaseModel):
    """Structured response from the LLM."""

    topics_found: list[str]
    explanation: str


class JudgeScore(BaseModel):
    """Structured response from the LLM judge."""

    score: float  # 0.0 to 1.0
    reasoning: str


class TopicCoverageEvaluator(Evaluator[StructuredAnswer, ExpectedTopics]):
    """Evaluator that checks if expected topics appear in structured output."""

    def evaluate(
        self, ctx: EvaluatorContext[StructuredAnswer, ExpectedTopics]
    ) -> float:
        """Return score based on topic coverage (0.0 to 1.0)."""
        if ctx.expected_output is None:
            return 1.0

        expected_topics = ctx.expected_output.topics
        if not expected_topics:
            return 1.0

        # Get topics from structured output
        found_topics_lower = [t.lower() for t in ctx.output.topics_found]

        found = 0
        for topic in expected_topics:
            # Case-insensitive check with underscore/space variants
            topic_variants = [
                topic.lower(),
                topic.lower().replace("_", " "),
                topic.lower().replace(" ", "_"),
            ]
            if any(
                any(variant in found for found in found_topics_lower)
                for variant in topic_variants
            ):
                found += 1

        return found / len(expected_topics)


class LLMJudgeEvaluator(Evaluator[StructuredAnswer, ExpectedTopics]):
    """Evaluator that uses an LLM to judge semantic topic coverage."""

    def evaluate(
        self, ctx: EvaluatorContext[StructuredAnswer, ExpectedTopics]
    ) -> float:
        """Use LLM to judge if the answer semantically covers expected topics."""
        import asyncio

        if ctx.expected_output is None:
            return 1.0

        if _judge_agent is None:
            # Fall back to keyword matching if no judge configured
            return TopicCoverageEvaluator().evaluate(ctx)

        expected_topics = ctx.expected_output.topics
        if not expected_topics:
            return 1.0

        # Build prompt for judge
        prompt = f"""You are evaluating whether an LLM's answer covers the expected topics.

Expected topics that should be covered (directly or semantically):
{expected_topics}

LLM's identified topics:
{ctx.output.topics_found}

LLM's explanation:
{ctx.output.explanation}

Score from 0.0 to 1.0 based on how well the answer covers the expected topics.
- 1.0 = All topics covered (exact match or clear semantic equivalent)
- 0.5 = Half the topics covered
- 0.0 = No topics covered

Consider semantic equivalents:
- "Installation Steps" covers "pip install", "venv", "clone"
- "Environment Variables" covers "env", "secrets"
- "Prerequisites" may cover "Python", "requirements"

Be generous with semantic matches - if the concept is clearly addressed, count it."""

        try:
            # Run async judge in sync context
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context, create task
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run, _judge_agent.run(prompt)
                    )
                    result = future.result(timeout=30)
            else:
                result = asyncio.run(_judge_agent.run(prompt))

            # Clamp score to valid range
            score = max(0.0, min(1.0, result.output.score))
            return score
        except Exception as e:
            print(f"Judge error: {e}", file=sys.stderr)
            # Fall back to keyword matching
            return TopicCoverageEvaluator().evaluate(ctx)


def validate_docs_build() -> tuple[list[str], list[str]]:
    """Validate that mkdocs was built correctly.

    Returns:
        Tuple of (errors, warnings) - errors are fatal, warnings are not
    """
    errors = []
    warnings = []

    # Check site directory exists
    if not SITE_DIR.exists():
        errors.append(f"Site directory not found: {SITE_DIR}")
        errors.append("Run 'uv run mkdocs build' first")
        return errors, warnings

    # Check all required files exist and are not empty
    for _domain, config in DOMAIN_FILES.items():
        for file_type, filename in config.items():
            filepath = SITE_DIR / filename
            if not filepath.exists():
                errors.append(f"Missing {file_type} file: {filepath}")
            elif filepath.stat().st_size == 0:
                errors.append(f"Empty file: {filepath}")

    if errors:
        return errors, warnings

    # Check for production vs local URLs (warning only)
    sample_file = SITE_DIR / DOMAIN_FILES["project"]["map"]
    content = sample_file.read_text()

    if PROD_URL_MARKER in content:
        warnings.append(
            f"Docs contain production URLs ({PROD_URL_MARKER}). "
            "This is fine for eval, but URLs won't work locally."
        )

    # Check docs freshness - warn if older than source
    docs_mtime = sample_file.stat().st_mtime
    source_dir = PROJECT_ROOT / "docs"
    if source_dir.exists():
        # Find newest source file
        newest_source = max(
            (f.stat().st_mtime for f in source_dir.rglob("*.md")),
            default=0,
        )
        if newest_source > docs_mtime:
            warnings.append(
                "Docs may be stale (source files are newer). "
                "Consider running 'uv run mkdocs build'"
            )

    return errors, warnings


def load_questions(evals_file: Path = EVALS_FILE) -> dict:
    """Load evaluation questions from YAML file."""
    if not evals_file.exists():
        raise FileNotFoundError(f"Evals file not found: {evals_file}")  # noqa: TRY003

    with open(evals_file) as f:
        return yaml.safe_load(f)


def load_docs(domain: str, mode: str = "comprehension") -> str:
    """Load documentation content for a domain.

    Args:
        domain: The domain (project, server, client)
        mode: 'navigation' for map file, 'comprehension' for full content
    """
    cache_key = f"{domain}:{mode}"
    if cache_key in _docs_cache:
        return _docs_cache[cache_key]

    domain_config = DOMAIN_FILES.get(domain)
    if not domain_config:
        raise ValueError(f"Unknown domain: {domain}")  # noqa: TRY003

    file_key = "map" if mode == "navigation" else "full"
    filename = domain_config[file_key]

    filepath = SITE_DIR / filename
    if not filepath.exists():
        msg = (
            f"Documentation file not found: {filepath}\n"
            "Run 'uv run mkdocs build' first to generate docs."
        )
        raise FileNotFoundError(msg)

    content = filepath.read_text()
    _docs_cache[cache_key] = content
    return content


def create_agent(
    provider_type: str = "openai",
    model_name: str | None = None,
    base_url: str | None = None,
    mode: str = "comprehension",
) -> pydantic_ai.Agent[None, StructuredAnswer]:
    """Create a pydantic-ai agent for evaluation with structured output."""
    if provider_type == "ollama":
        model = model_name or DEFAULT_OLLAMA_MODEL
        # OLLAMA_URL includes /v1, OLLAMA_BASE_URL does not
        ollama_url = base_url or os.environ.get("OLLAMA_URL")
        if not ollama_url:
            base = os.environ.get("OLLAMA_BASE_URL")
            if base:
                ollama_url = f"{base.rstrip('/')}/v1"
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

    if mode == "navigation":
        instructions = (
            "You are a documentation navigator. Given a documentation "
            "index, identify which section(s) would contain the answer "
            "to a question. Return the relevant topics/sections found."
        )
    else:
        instructions = (
            "You are a developer assistant. Answer questions using ONLY "
            "the documentation provided. Identify the key topics, classes, "
            "functions, or concepts mentioned that answer the question."
        )

    return pydantic_ai.Agent(
        model=openai_models.OpenAIChatModel(
            model_name=model,
            provider=provider,
        ),
        instructions=instructions,
        output_type=StructuredAnswer,
    )


def create_judge_agent(
    provider_type: str = "openai",
    model_name: str | None = None,
    base_url: str | None = None,
) -> pydantic_ai.Agent[None, JudgeScore]:
    """Create a pydantic-ai agent for LLM-as-judge evaluation."""
    if provider_type == "ollama":
        model = model_name or DEFAULT_OLLAMA_MODEL
        ollama_url = base_url or os.environ.get("OLLAMA_URL")
        if not ollama_url:
            base = os.environ.get("OLLAMA_BASE_URL")
            if base:
                ollama_url = f"{base.rstrip('/')}/v1"
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
            "You are an evaluation judge. Score how well an LLM's answer "
            "covers expected topics, considering semantic equivalents."
        ),
        output_type=JudgeScore,
    )


async def answer_question(inputs: QuestionInput) -> StructuredAnswer:
    """Task function that answers a question using documentation."""
    if _agent is None:
        return StructuredAnswer(
            topics_found=["DRY_RUN"],
            explanation="No agent configured - dry run mode",
        )

    docs_content = load_docs(inputs.domain, _eval_mode)

    if _eval_mode == "navigation":
        prompt = f"""Based on the documentation index below, identify which \
section(s) would contain information to answer this question.

<documentation_index>
{docs_content}
</documentation_index>

Question: {inputs.question}

Return the relevant section names, file paths, or topic keywords."""
    else:
        prompt = f"""Answer the following question using ONLY the \
documentation below.

<documentation>
{docs_content}
</documentation>

Question: {inputs.question}

Identify the key topics, classes, functions, or concepts from the \
documentation that answer this question."""

    try:
        result = await _agent.run(prompt)
    except Exception as e:
        # If structured output fails, return error info
        return StructuredAnswer(
            topics_found=["ERROR"],
            explanation=f"Failed to get structured output: {e}",
        )
    else:
        return result.output


def slugify_question(question: str) -> str:
    """Create a short slug from a question for case naming."""
    # Remove common question words and punctuation
    skip_words = {
        "what",
        "how",
        "is",
        "are",
        "do",
        "does",
        "the",
        "a",
        "an",
        "in",
        "to",
        "and",
        "or",
        "for",
        "of",
        "i",
        "my",
        "soliplex",
    }
    words = question.lower().replace("?", "").split()
    keywords = [w for w in words if w not in skip_words][:4]
    return "-".join(keywords)


def build_dataset(
    domains: list[str] | None = None,
    limit: int | None = None,
    use_judge: bool = False,
) -> Dataset[QuestionInput, StructuredAnswer]:
    """Build a pydantic-evals Dataset from questions.yaml."""
    questions = load_questions()

    if domains is None:
        domains = list(DOMAIN_FILES.keys())

    cases = []
    for domain in domains:
        if domain not in questions:
            print(
                f"Warning: No questions for domain '{domain}'",
                file=sys.stderr,
            )
            continue

        for idx, q in enumerate(questions[domain], 1):
            slug = slugify_question(q["question"])
            case = Case(
                name=f"{domain}/{idx:02d}-{slug}",
                inputs=QuestionInput(
                    question=q["question"],
                    domain=domain,
                ),
                expected_output=ExpectedTopics(topics=q["expected_topics"]),
                metadata={
                    "difficulty": q.get("difficulty", "medium"),
                },
            )
            cases.append(case)
            if limit and len(cases) >= limit:
                break
        if limit and len(cases) >= limit:
            break

    # Select evaluator based on mode
    evaluator = LLMJudgeEvaluator() if use_judge else TopicCoverageEvaluator()

    return Dataset(
        cases=cases,
        evaluators=[evaluator],
    )


def setup_logfire() -> str | None:
    """Configure logfire if LOGFIRE_TOKEN is set. Returns dashboard URL."""
    token = os.environ.get("LOGFIRE_TOKEN")
    if not token:
        return None

    try:
        import logfire

        # Disable scrubbing to see full prompts/responses in traces
        logfire.configure(scrubbing=False)
        logfire.instrument_pydantic_ai()
    except ImportError:
        print("Warning: logfire not installed, skipping", file=sys.stderr)
        return None

    # Extract project info from token or use default
    # Logfire URLs are: https://logfire.pydantic.dev/{org}/{project}
    project = os.environ.get("LOGFIRE_PROJECT", "soliplex-evals")
    return f"https://logfire.pydantic.dev/{project}"


def main():
    global _agent, _eval_mode

    parser = argparse.ArgumentParser(
        description="Evaluate LLM comprehension of Soliplex documentation"
    )
    parser.add_argument(
        "--mode",
        choices=["navigation", "comprehension"],
        default="comprehension",
        help="Eval mode: 'navigation' tests index usage, "
        "'comprehension' tests full content (default: comprehension)",
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
    parser.add_argument(
        "--show-output",
        "-o",
        action="store_true",
        help="Show LLM output in report",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output (show progress during evaluation)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON (for CI integration)",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        help="Limit number of questions to evaluate",
    )
    parser.add_argument(
        "--judge",
        "-j",
        action="store_true",
        help="Use LLM-as-judge for semantic topic matching (slower but more accurate)",
    )
    parser.add_argument(
        "--concurrency",
        "-c",
        type=int,
        default=1,
        help="Number of concurrent evaluations (default: 1)",
    )
    args = parser.parse_args()

    # Auto-detect provider based on environment if using defaults
    if args.provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
        if os.environ.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_URL"):
            print(
                "Note: OLLAMA_BASE_URL/OLLAMA_URL detected without OPENAI_API_KEY. "
                "Switching provider to 'ollama'.",
                file=sys.stderr,
            )
            args.provider = "ollama"

    # Validate docs build
    validation_errors, validation_warnings = validate_docs_build()
    if validation_errors:
        print("ERROR: Documentation validation failed:", file=sys.stderr)
        for err in validation_errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)
    for warn in validation_warnings:
        print(f"Warning: {warn}", file=sys.stderr)

    _eval_mode = args.mode
    domains = [args.domain] if args.domain else None

    # Setup logfire if configured
    logfire_url = setup_logfire()
    if logfire_url:
        print(f"Logfire enabled: {logfire_url}")

    # Build dataset
    dataset = build_dataset(domains, limit=args.limit, use_judge=args.judge)
    print(f"Built dataset with {len(dataset.cases)} cases")
    print(f"Mode: {_eval_mode}")
    if args.judge:
        print("Evaluator: LLM-as-judge (semantic matching)")

    if args.dry_run:
        print("\n=== DRY RUN - Cases ===")
        for case in dataset.cases:
            print(f"  {case.name}")
            print(f"    Q: {case.inputs.question}")
            print(f"    Topics: {case.expected_output.topics}")
        return

    # Create agent
    _agent = create_agent(
        provider_type=args.provider,
        model_name=args.model,
        base_url=args.base_url,
        mode=_eval_mode,
    )

    # Create judge agent if using LLM-as-judge
    global _judge_agent
    if args.judge:
        _judge_agent = create_judge_agent(
            provider_type=args.provider,
            model_name=args.model,
            base_url=args.base_url,
        )

    # Run evaluation
    if not args.json:
        print("\nRunning evaluation...")
        if args.concurrency > 1:
            print(f"Concurrency: {args.concurrency}")
    report = dataset.evaluate_sync(answer_question, max_concurrency=args.concurrency)

    # Process results
    results = []
    scores = []
    for case in report.cases:
        score = 0.0
        if case.scores:
            for score_result in case.scores.values():
                score = score_result.value
                scores.append(score)

        # Calculate matched/missing topics
        found_topics_lower = [t.lower() for t in case.output.topics_found]
        matched = []
        missing = []
        for topic in case.expected_output.topics:
            topic_variants = [
                topic.lower(),
                topic.lower().replace("_", " "),
                topic.lower().replace(" ", "_"),
            ]
            if any(
                any(variant in found for found in found_topics_lower)
                for variant in topic_variants
            ):
                matched.append(topic)
            else:
                missing.append(topic)

        results.append(
            {
                "name": case.name,
                "question": case.inputs.question,
                "domain": case.inputs.domain,
                "score": score,
                "passed": score >= 0.6,
                "expected_topics": case.expected_output.topics,
                "found_topics": case.output.topics_found,
                "matched_topics": matched,
                "missing_topics": missing,
                "explanation": case.output.explanation,
            }
        )

    # Calculate summary
    avg_score = sum(scores) / len(scores) if scores else 0.0
    passing = sum(1 for s in scores if s >= 0.6)
    pass_rate = passing / len(scores) if scores else 0.0

    if args.json:
        # JSON output for CI
        output = {
            "mode": _eval_mode,
            "summary": {
                "total_cases": len(scores),
                "passing": passing,
                "pass_rate": pass_rate,
                "average_score": avg_score,
            },
            "cases": results,
        }
        print(json.dumps(output, indent=2))
    else:
        # Human-readable output
        print("\n" + "=" * 60)
        print(f"EVALUATION REPORT ({_eval_mode.upper()} MODE)")
        print("=" * 60)

        for r in results:
            status = "✓" if r["passed"] else "✗"
            print(f"\n{status} {r['name']} (score: {r['score']:.0%})")
            print(f"  Q: {r['question']}")
            print(f"  Expected: {r['expected_topics']}")
            print(f"  LLM found: {r['found_topics']}")
            if r["missing_topics"]:
                print(f"  Missing: {r['missing_topics']}")
            if args.show_output:
                print(f"  Explanation: {r['explanation'][:500]}")

        if scores:
            print(f"\nAverage score: {avg_score:.2f}")
            print(f"Passing (>=60%): {passing}/{len(scores)}")

            if logfire_url:
                print(f"\nView traces: {logfire_url}")

    # Exit with error if below threshold
    if avg_score < 0.8:
        sys.exit(1)


if __name__ == "__main__":
    main()

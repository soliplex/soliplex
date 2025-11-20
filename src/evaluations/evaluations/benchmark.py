import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import logfire
import typer
from dotenv import load_dotenv
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_evals import Dataset as EvalDataset
from pydantic_evals.evaluators import IsInstance, LLMJudge
from pydantic_evals.reporting import ReportCaseFailure
from rich.console import Console
from rich.progress import Progress

from evaluations.config import DatasetSpec
from evaluations.datasets import DATASETS
from evaluations.llm_judge import ANSWER_EQUIVALENCE_RUBRIC
from evaluations.prompts import WIX_SUPPORT_PROMPT
from haiku.rag.client import HaikuRAG
from haiku.rag.config import AppConfig, find_config_file, load_yaml_config
from haiku.rag.logging import configure_cli_logging
from haiku.rag.qa import get_qa_agent

load_dotenv()

QA_JUDGE_MODEL = "qwen3"

logfire.configure(send_to_logfire="if-token-present", service_name="evals")
logfire.instrument_pydantic_ai()
configure_cli_logging()
console = Console()


async def populate_db(spec: DatasetSpec, config: AppConfig) -> None:
    spec.db_path.parent.mkdir(parents=True, exist_ok=True)
    corpus = spec.document_loader()
    if spec.document_limit is not None:
        corpus = corpus.select(range(min(spec.document_limit, len(corpus))))

    with Progress() as progress:
        task = progress.add_task("[green]Populating database...", total=len(corpus))
        async with HaikuRAG(spec.db_path, config=config) as rag:
            for doc in corpus:
                doc_mapping = cast(Mapping[str, Any], doc)
                payload = spec.document_mapper(doc_mapping)
                if payload is None:
                    progress.advance(task)
                    continue

                existing = await rag.get_document_by_uri(payload.uri)
                if existing is not None:
                    assert existing.id
                    chunks = await rag.chunk_repository.get_by_document_id(existing.id)
                    if chunks:
                        progress.advance(task)
                        continue
                    await rag.document_repository.delete(existing.id)

                await rag.create_document(
                    content=payload.content,
                    uri=payload.uri,
                    title=payload.title,
                    metadata=payload.metadata,
                )
                progress.advance(task)


async def run_qa_benchmark(
    spec: DatasetSpec, config: AppConfig, qa_limit: int | None = None
) -> ReportCaseFailure[str, str, dict[str, str]] | None:
    corpus = spec.qa_loader()
    if qa_limit is not None:
        corpus = corpus.select(range(min(qa_limit, len(corpus))))

    cases = [
        spec.qa_case_builder(index, cast(Mapping[str, Any], doc))
        for index, doc in enumerate(corpus, start=1)
    ]

    judge_model = OpenAIChatModel(
        model_name=QA_JUDGE_MODEL,
        provider=OllamaProvider(base_url=f"{config.providers.ollama.base_url}/v1"),
    )

    evaluation_dataset = EvalDataset[str, str, dict[str, str]](
        cases=cases,
        evaluators=[
            IsInstance(type_name="str"),
            LLMJudge(
                rubric=ANSWER_EQUIVALENCE_RUBRIC,
                include_input=True,
                include_expected_output=True,
                model=judge_model,
                assertion={
                    "evaluation_name": "answer_equivalent",
                    "include_reason": True,
                },
            ),
        ],
    )

    async with HaikuRAG(spec.db_path, config=config) as rag:
        system_prompt = WIX_SUPPORT_PROMPT if spec.key == "wix" else None
        qa = get_qa_agent(rag, system_prompt=system_prompt)

        async def answer_question(question: str) -> str:
            return await qa.answer(question)

        report = await evaluation_dataset.evaluate(
            answer_question,
            name=f"{spec.key}_qa_evaluation",
            max_concurrency=1,
            progress=True,
        )

    passing_cases = sum(
        1
        for case in report.cases
        if case.assertions.get("answer_equivalent")
        and case.assertions["answer_equivalent"].value
    )
    total_processed = len(report.cases)
    failures = report.failures

    total_cases = total_processed
    accuracy = passing_cases / total_cases if total_cases > 0 else 0

    console.print("\n=== QA Benchmark Results ===", style="bold cyan")
    console.print(f"Total questions: {total_cases}")
    console.print(f"Correct answers: {passing_cases}")
    console.print(f"QA Accuracy: {accuracy:.4f} ({accuracy * 100:.2f}%)")

    if failures:
        console.print("[red]\nSummary of failures:[/red]")
        for failure in failures:
            console.print(f"Case: {failure.name}")
            console.print(f"Question: {failure.inputs}")
            console.print(f"Error: {failure.error_message}")
            console.print("")

    return failures[0] if failures else None


async def evaluate_dataset(
    spec: DatasetSpec,
    config: AppConfig,
    skip_db: bool,
    skip_qa: bool,
    qa_limit: int | None,
) -> None:
    if not skip_db:
        console.print(f"Using dataset: {spec.key}", style="bold magenta")
        await populate_db(spec, config)

    if not skip_qa:
        console.print("\nRunning QA benchmarks...", style="bold yellow")
        await run_qa_benchmark(spec, config, qa_limit=qa_limit)


app = typer.Typer(help="Run QA benchmarks for configured datasets.")


@app.command(name="run")
def run(
    dataset: str = typer.Argument(..., help="Dataset key to evaluate."),
    config: Path | None = typer.Option(
        None, "--config", help="Path to haiku.rag YAML config file."
    ),
    skip_db: bool = typer.Option(
        False, "--skip-db", help="Skip updateing the evaluation db."
    ),
    skip_qa: bool = typer.Option(False, "--skip-qa", help="Skip QA benchmark."),
    qa_limit: int | None = typer.Option(
        None, "--qa-limit", help="Limit number of QA cases."
    ),
) -> None:
    spec = DATASETS.get(dataset.lower())
    if spec is None:
        valid_datasets = ", ".join(sorted(DATASETS))
        raise typer.BadParameter(
            f"Unknown dataset '{dataset}'. Choose from: {valid_datasets}"
        )

    # Load config from file or use defaults
    if config:
        if not config.exists():
            raise typer.BadParameter(f"Config file not found: {config}")
        console.print(f"Loading config from: {config}", style="dim")
        yaml_data = load_yaml_config(config)
        app_config = AppConfig.model_validate(yaml_data)
    else:
        # Try to find config file using standard search path
        config_path = find_config_file(None)
        if config_path:
            console.print(f"Loading config from: {config_path}", style="dim")
            yaml_data = load_yaml_config(config_path)
            app_config = AppConfig.model_validate(yaml_data)
        else:
            console.print("No config file found, using defaults", style="dim")
            app_config = AppConfig()

    asyncio.run(
        evaluate_dataset(
            spec=spec,
            config=app_config,
            skip_db=skip_db,
            skip_qa=skip_qa,
            qa_limit=qa_limit,
        )
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()

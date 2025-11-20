# Soliplex - Evaluations

Internal benchmarking and evaluation scripts for Soliplex RAG system.

This package is not published to PyPI and is only used for development and testing purposes.

## Overview

Contains evaluation scripts for benchmarking RAG performance. The system evaluates both retrieval accuracy and question-answering quality using LLM judges.

### Available Datasets

#### WiX
- **Source**: [Wix/WixQA](https://huggingface.co/datasets/Wix/WixQA) from HuggingFace
- **Content**: Wix help center articles and support documentation
- **Structure**:
  - Corpus: ~1,300 help articles with titles, URLs, and content
  - QA pairs: Expert-written questions with verified answers
  - Evaluation: Tests retrieval of relevant articles and answer accuracy
- **Use case**: Technical support documentation retrieval

#### RepliQA
- **Source**: [ServiceNow/repliqa](https://huggingface.co/datasets/ServiceNow/repliqa) from HuggingFace
- **Content**: News stories with reading comprehension questions
- **Structure**:
  - Corpus: News articles (filtered to "News Stories" topic)
  - QA pairs: Questions that require understanding document context
  - Evaluation: Tests single-document retrieval and comprehension
- **Use case**: Long-form document understanding and retrieval

## Installation

Install the evaluations package using uv:

```bash
# Create virtual environment
uv venv
# Sync dependencies
uv sync
```

## Usage

After installation, you can run the evaluations using the `evaluations` command:

```bash
# Run evaluations for a specific dataset
evaluations wix --config path/to/haiku.rag.yaml
evaluations repliqa --config path/to/haiku.rag.yaml

# View available options
evaluations --help
```

### Available Options

- `--config`: Path to haiku.rag YAML config file (optional, will search for config if not provided)
- `--skip-db`: Skip updating the evaluation database
- `--skip-qa`: Skip QA benchmark
- `--qa-limit`: Limit number of QA cases to evaluate

### Examples

```bash
# Run full evaluation for WiX dataset
evaluations wix --config example/haiku.rag.yaml

# Run only QA benchmark (skip database population)
evaluations repliqa --skip-db --config example/haiku.rag.yaml

# Run with limited QA cases for faster testing
evaluations wix --qa-limit 10 --config example/haiku.rag.yaml
```

## Creating New Datasets

To add a new evaluation dataset, create a new Python module in `evaluations/datasets/` and define a `DatasetSpec`:

### Step 1: Create Dataset Module

Create a file like `evaluations/datasets/my_dataset.py`:

```python
from collections.abc import Mapping
from typing import Any, cast
from datasets import Dataset, load_dataset
from pydantic_evals import Case
from evaluations.config import DatasetSpec, DocumentPayload

def load_my_corpus() -> Dataset:
    """Load the document corpus from HuggingFace or local source."""
    dataset_dict = load_dataset("organization/dataset-name")
    return cast(Dataset, dataset_dict["train"])

def map_my_document(doc: Mapping[str, Any]) -> DocumentPayload:
    """Map dataset document to DocumentPayload format."""
    return DocumentPayload(
        uri=str(doc["id"]),           # Unique document identifier
        content=doc["text"],           # Document text content
        title=doc.get("title"),        # Optional title
        metadata={"source": "custom"}  # Optional metadata
    )

def load_my_qa() -> Dataset:
    """Load QA pairs for evaluation."""
    dataset_dict = load_dataset("organization/dataset-name", "qa_split")
    return cast(Dataset, dataset_dict["test"])

def build_my_case(
    index: int, doc: Mapping[str, Any]
) -> Case[str, str, dict[str, str]]:
    """Build evaluation case from QA pair."""
    return Case(
        name=f"case_{index}_{doc['id']}",
        inputs=doc["question"],
        expected_output=doc["answer"],
        metadata={"case_index": str(index)}
    )

MY_SPEC = DatasetSpec(
    key="my_dataset",                    # CLI argument name
    db_filename="my_dataset.lancedb",    # LanceDB filename
    document_loader=load_my_corpus,      # Document loader function
    document_mapper=map_my_document,     # Document mapper function
    qa_loader=load_my_qa,                # QA loader function
    qa_case_builder=build_my_case,       # Case builder function
    document_limit=None,                 # Optional corpus size limit
)
```

### Step 2: Register Dataset

Add your dataset to `evaluations/datasets/__init__.py`:

```python
from evaluations.config import DatasetSpec
from .repliqa import REPLIQ_SPEC
from .wix import WIX_SPEC
from .my_dataset import MY_SPEC  # Import your spec

DATASETS: dict[str, DatasetSpec] = {
    spec.key: spec for spec in (REPLIQ_SPEC, WIX_SPEC, MY_SPEC)
}
```

### Step 3: Run Evaluation

```bash
evaluations my_dataset --config example/haiku.rag.yaml
```

### Dataset Component Reference

- **document_loader**: Function that returns a HuggingFace `Dataset` containing documents to index
- **document_mapper**: Function that converts dataset rows to `DocumentPayload` (uri, content, title, metadata)
- **qa_loader**: Function that returns a `Dataset` containing question-answer pairs
- **qa_case_builder**: Function that converts QA rows to pydantic-evals `Case` objects
- **document_limit**: Optional integer to limit corpus size for faster testing

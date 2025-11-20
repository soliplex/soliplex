# Soliplex - Evaluations

Internal benchmarking and evaluation scripts for Soliplex RAG system.

This package is not published to PyPI and is only used for development and testing purposes.

## Overview

Contains evaluation scripts for benchmarking RAG performance using datasets like:
- RepliQA
- WiX

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

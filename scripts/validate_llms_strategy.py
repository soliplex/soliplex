#!/usr/bin/env python3
"""Validate the llms.txt federation strategy.

Checks:
1. Context efficiency - maps must be within domain-specific thresholds
2. Link integrity - all map links must resolve
3. File existence - all expected files must exist

Usage:
    uv run python scripts/validate_llms_strategy.py
    uv run python scripts/validate_llms_strategy.py --json  # JSON output
"""

import argparse
import json
import re
import sys
from pathlib import Path

from llms_constants import DOMAINS
from llms_constants import PATTERNS

SITE_DIR = Path(__file__).parent.parent / "site"
DEFAULT_THRESHOLD = 0.15  # Fallback for total calculation


def estimate_tokens(text: str) -> int:
    """Estimate token count (roughly chars/4)."""
    return len(text) // 4


def check_file_existence() -> tuple[list[str], list[str]]:
    """Check all expected llms files exist."""
    errors = []
    warnings = []

    # Check root entry point
    root = SITE_DIR / "llms.txt"
    if not root.exists():
        errors.append(f"Missing root entry point: {root}")

    # Check domain files
    for domain, config in DOMAINS.items():
        map_file = SITE_DIR / config["map"]
        content_file = SITE_DIR / config["content"]

        if not map_file.exists():
            errors.append(f"Missing {domain} map: {map_file}")
        if not content_file.exists():
            errors.append(f"Missing {domain} content: {content_file}")

    return errors, warnings


def check_context_efficiency() -> tuple[list[str], dict]:
    """Check that maps are significantly smaller than content."""
    errors = []
    metrics = {}

    for domain, config in DOMAINS.items():
        map_file = SITE_DIR / config["map"]
        content_file = SITE_DIR / config["content"]
        threshold = config.get("threshold", DEFAULT_THRESHOLD)

        if not map_file.exists() or not content_file.exists():
            continue

        map_size = map_file.stat().st_size
        content_size = content_file.stat().st_size
        ratio = map_size / content_size if content_size > 0 else 0

        map_tokens = estimate_tokens(map_file.read_text())
        content_tokens = estimate_tokens(content_file.read_text())

        metrics[domain] = {
            "map_bytes": map_size,
            "content_bytes": content_size,
            "ratio": round(ratio, 4),
            "threshold": threshold,
            "map_tokens": map_tokens,
            "content_tokens": content_tokens,
            "reduction_pct": round((1 - ratio) * 100, 1),
        }

        if ratio > threshold:
            errors.append(
                f"{domain}: map is {ratio:.1%} of content "
                f"(threshold: {threshold:.0%})"
            )

    # Calculate totals
    total_map = sum(m["map_bytes"] for m in metrics.values())
    total_content = sum(m["content_bytes"] for m in metrics.values())
    total_ratio = total_map / total_content if total_content > 0 else 0

    metrics["_total"] = {
        "map_bytes": total_map,
        "content_bytes": total_content,
        "ratio": round(total_ratio, 4),
        "reduction_pct": round((1 - total_ratio) * 100, 1),
    }

    return errors, metrics


def check_map_content() -> tuple[list[str], dict]:
    """Check that map files contain meaningful content (category headers).

    A map file with only a title header but no ## category sections
    is effectively empty and won't help an LLM navigate the documentation.

    Domains with require_categories=False skip this check.
    """
    errors = []
    metrics = {}

    for domain, config in DOMAINS.items():
        map_file = SITE_DIR / config["map"]
        if not map_file.exists():
            continue

        content = map_file.read_text()
        lines = content.splitlines()

        # Count category headers (## sections)
        category_count = sum(1 for line in lines if line.startswith("## "))

        metrics[domain] = {
            "category_count": category_count,
            "line_count": len(lines),
        }

        # Only require categories if domain config specifies it
        require_categories = config.get("require_categories", True)
        if require_categories and category_count == 0:
            errors.append(
                f"{domain} map has no category headers (##) - "
                f"map may be empty or malformed"
            )

    return errors, metrics


def check_link_integrity() -> tuple[list[str], int]:
    """Check that links in map files resolve to existing files."""
    errors = []
    link_count = 0

    # Pattern for markdown links: [text](url)
    link_pattern = re.compile(PATTERNS["markdown_link"])

    for domain, config in DOMAINS.items():
        map_file = SITE_DIR / config["map"]
        if not map_file.exists():
            continue

        content = map_file.read_text()
        links = link_pattern.findall(content)
        link_count += len(links)

        for text, url in links:
            # Handle different URL formats
            if url.startswith("http://") or url.startswith("https://"):
                # Remote URL - skip validation
                continue
            elif url.startswith("/"):
                # Absolute path
                target = Path(url)
            else:
                # Relative path
                target = map_file.parent / url

            if not target.exists():
                errors.append(f"{domain} map: broken link [{text}]({url})")

    # Also check root llms.txt
    root = SITE_DIR / "llms.txt"
    if root.exists():
        content = root.read_text()
        links = link_pattern.findall(content)
        link_count += len(links)

        for text, url in links:
            if url.startswith("http://") or url.startswith("https://"):
                continue
            elif url.startswith("/"):
                target = Path(url)
            else:
                target = root.parent / url

            if not target.exists():
                errors.append(f"root llms.txt: broken link [{text}]({url})")

    return errors, link_count


def run_validation(json_output: bool = False) -> int:
    """Run all validation checks."""
    results = {
        "passed": True,
        "errors": [],
        "warnings": [],
        "metrics": {},
    }

    # Check 1: File existence
    errors, warnings = check_file_existence()
    results["errors"].extend(errors)
    results["warnings"].extend(warnings)

    # Check 2: Context efficiency
    errors, metrics = check_context_efficiency()
    results["errors"].extend(errors)
    results["metrics"]["efficiency"] = metrics

    # Check 3: Map content (has category headers)
    errors, content_metrics = check_map_content()
    results["errors"].extend(errors)
    results["metrics"]["map_content"] = content_metrics

    # Check 4: Link integrity
    errors, link_count = check_link_integrity()
    results["errors"].extend(errors)
    results["metrics"]["link_count"] = link_count

    # Determine pass/fail
    results["passed"] = len(results["errors"]) == 0

    if json_output:
        print(json.dumps(results, indent=2))
    else:
        print_report(results)

    return 0 if results["passed"] else 1


def print_report(results: dict) -> None:
    """Print human-readable validation report."""
    print("=" * 60)
    print("LLMs.txt Federation Strategy Validation")
    print("=" * 60)
    print()

    # Efficiency metrics
    print("Context Efficiency:")
    print("-" * 60)
    metrics = results["metrics"].get("efficiency", {})
    for domain, data in metrics.items():
        if domain == "_total":
            continue
        threshold = data.get("threshold", DEFAULT_THRESHOLD)
        status = "OK" if data["ratio"] <= threshold else "FAIL"
        print(
            f"  {domain:8} | map: {data['map_bytes']:>7,} B | "
            f"content: {data['content_bytes']:>9,} B | "
            f"ratio: {data['ratio']:>5.1%} (max {threshold:.0%}) [{status}]"
        )

    if "_total" in metrics:
        total = metrics["_total"]
        print("-" * 40)
        print(
            f"  {'TOTAL':8} | map: {total['map_bytes']:>7,} B | "
            f"content: {total['content_bytes']:>9,} B | "
            f"reduction: {total['reduction_pct']:>5}%"
        )
    print()

    # Link count
    print(f"Links validated: {results['metrics'].get('link_count', 0)}")
    print()

    # Errors
    if results["errors"]:
        print("ERRORS:")
        for error in results["errors"]:
            print(f"  - {error}")
        print()

    # Warnings
    if results["warnings"]:
        print("WARNINGS:")
        for warning in results["warnings"]:
            print(f"  - {warning}")
        print()

    # Final status
    if results["passed"]:
        print("RESULT: PASSED")
    else:
        print("RESULT: FAILED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate llms.txt federation strategy"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    args = parser.parse_args()

    sys.exit(run_validation(json_output=args.json))

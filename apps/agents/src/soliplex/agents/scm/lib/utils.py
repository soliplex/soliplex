"""Shared utilities for SCM operations."""

import base64
import hashlib
from typing import Any


def flatten_list(nested_list: list[Any]) -> list[Any]:
    """
    Flatten a nested list structure into a single-level list.

    Args:
        nested_list: A list that may contain nested lists

    Returns:
        A flattened list with all nested elements at the top level
    """
    flat = []
    for item in nested_list:
        if isinstance(item, list):
            flat.extend(flatten_list(item))
        else:
            flat.append(item)
    return flat


def compute_file_hash(content: bytes) -> str:
    """
    Compute SHA3-256 hash of file content.

    Args:
        content: File content as bytes

    Returns:
        Hexadecimal hash string
    """
    return hashlib.sha3_256(content, usedforsecurity=False).hexdigest()


def decode_base64_if_needed(content: bytes | str) -> bytes:
    """
    Decode base64 content if it's a string, otherwise return as-is.

    Args:
        content: Content as bytes or base64-encoded string

    Returns:
        Decoded bytes
    """
    if isinstance(content, str):
        return base64.b64decode(content)
    return content

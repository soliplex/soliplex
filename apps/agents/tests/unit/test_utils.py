"""Tests for soliplex.agents.scm.lib.utils module."""

import base64

from soliplex.agents.scm.lib.utils import compute_file_hash
from soliplex.agents.scm.lib.utils import decode_base64_if_needed
from soliplex.agents.scm.lib.utils import flatten_list


def test_flatten_list_simple():
    """Test flatten_list with simple nested list."""
    nested = [[1, 2], [3, 4], [5]]
    result = flatten_list(nested)
    assert result == [1, 2, 3, 4, 5]


def test_flatten_list_deeply_nested():
    """Test flatten_list with deeply nested list."""
    nested = [[1, [2, 3]], [4, [5, [6, 7]]]]
    result = flatten_list(nested)
    assert result == [1, 2, 3, 4, 5, 6, 7]


def test_flatten_list_empty():
    """Test flatten_list with empty list."""
    result = flatten_list([])
    assert result == []


def test_flatten_list_no_nesting():
    """Test flatten_list with no nesting."""
    result = flatten_list([1, 2, 3])
    assert result == [1, 2, 3]


def test_flatten_list_mixed_types():
    """Test flatten_list with mixed types."""
    nested = [["a", "b"], ["c"], ["d", "e"]]
    result = flatten_list(nested)
    assert result == ["a", "b", "c", "d", "e"]


def test_compute_file_hash():
    """Test compute_file_hash produces consistent SHA3-256 hash."""
    content = b"test content"
    hash1 = compute_file_hash(content)
    hash2 = compute_file_hash(content)

    # Same content should produce same hash
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA3-256 produces 64 character hex string


def test_compute_file_hash_different_content():
    """Test compute_file_hash produces different hashes for different content."""
    content1 = b"test content 1"
    content2 = b"test content 2"

    hash1 = compute_file_hash(content1)
    hash2 = compute_file_hash(content2)

    assert hash1 != hash2


def test_compute_file_hash_empty():
    """Test compute_file_hash with empty content."""
    content = b""
    result = compute_file_hash(content)
    assert len(result) == 64


def test_decode_base64_if_needed_with_string():
    """Test decode_base64_if_needed with base64 string."""
    original = b"test content"
    encoded = base64.b64encode(original).decode()

    result = decode_base64_if_needed(encoded)
    assert result == original


def test_decode_base64_if_needed_with_bytes():
    """Test decode_base64_if_needed with bytes."""
    content = b"test content"
    result = decode_base64_if_needed(content)
    assert result == content


def test_decode_base64_if_needed_with_empty_string():
    """Test decode_base64_if_needed with empty string."""
    result = decode_base64_if_needed("")
    assert result == b""


def test_decode_base64_if_needed_with_empty_bytes():
    """Test decode_base64_if_needed with empty bytes."""
    result = decode_base64_if_needed(b"")
    assert result == b""

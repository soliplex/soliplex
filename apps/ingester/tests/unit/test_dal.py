import logging
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest
from common import do_monkeypatch

from soliplex.ingester.lib import dal
from soliplex.ingester.lib import models

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_recursive_listdir(tmp_path):
    """Test recursive_listdir function"""
    # Create test directory structure
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    (test_dir / "file1.txt").write_text("test1")
    subdir = test_dir / "subdir"
    subdir.mkdir()
    (subdir / "file2.txt").write_text("test2")

    files = await dal.recursive_listdir(test_dir)
    assert len(files) == 2
    file_names = [f.name for f in files]
    assert "file1.txt" in file_names
    assert "file2.txt" in file_names


@pytest.mark.asyncio
async def test_read_input_url_file():
    """Test read_input_url with file:// URL"""
    with patch("soliplex.ingester.lib.dal.read_file_url") as mock_read:
        mock_read.return_value = b"test content"
        result = await dal.read_input_url("file:///tmp/test.txt")
        assert result == b"test content"
        mock_read.assert_called_once()


@pytest.mark.asyncio
async def test_read_input_url_s3():
    """Test read_input_url with s3:// URL"""
    with patch("soliplex.ingester.lib.dal.read_s3_url") as mock_read:
        mock_read.return_value = b"test content"
        result = await dal.read_input_url("s3://bucket/key")
        assert result == b"test content"
        mock_read.assert_called_once_with("s3://bucket/key")


@pytest.mark.asyncio
async def test_read_input_url_unknown():
    """Test read_input_url with unknown URL scheme"""
    with pytest.raises(ValueError, match="Unknown uri"):
        await dal.read_input_url("http://example.com/file.txt")


@pytest.mark.asyncio
async def test_read_file_url(tmp_path):
    """Test read_file_url function"""
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(b"test content")
    file_url = test_file.as_uri()

    result = await dal.read_file_url(file_url)
    assert result == b"test content"


@pytest.mark.asyncio
async def test_read_s3_url():
    """Test read_s3_url function"""
    with patch("soliplex.ingester.lib.dal.get_settings") as mock_settings:
        with patch("soliplex.ingester.lib.dal.opendal.AsyncOperator") as mock_op_class:
            mock_settings.return_value = Mock(
                s3_input_endpoint_url="http://localhost:9000",
                s3_input_key="key",
                s3_input_secret="secret",
                s3_input_region="us-east-1",
            )
            mock_op = AsyncMock()
            mock_op.read.return_value = b"s3 content"
            mock_op_class.return_value = mock_op

            result = await dal.read_s3_url("s3://bucket/path/to/file.txt")
            assert result == b"s3 content"
            mock_op.read.assert_called_once_with("path/to/file.txt")


@pytest.mark.asyncio
async def test_db_storage_operator_read(monkeypatch, mock_engine):
    """Test DBStorageOperator read method"""
    do_monkeypatch(monkeypatch, mock_engine)
    op = dal.DBStorageOperator("doc", "test_root")

    # Write a document first
    test_bytes = b"test content"
    await op.write("test_hash", test_bytes)

    # Read it back
    result = await op.read("test_hash")
    assert result == test_bytes


@pytest.mark.asyncio
async def test_db_storage_operator_read_not_found(monkeypatch, mock_engine):  # noqa F811
    """Test DBStorageOperator read method with file not found"""
    do_monkeypatch(monkeypatch, mock_engine)
    op = dal.DBStorageOperator("doc", "test_root")

    with pytest.raises(FileNotFoundError):
        await op.read("nonexistent_hash")


@pytest.mark.asyncio
async def test_db_storage_operator_is_exist(monkeypatch, mock_engine):  # noqa F811
    """Test DBStorageOperator is_exist method"""
    do_monkeypatch(monkeypatch, mock_engine)
    op = dal.DBStorageOperator("doc", "test_root")

    # Should not exist initially
    exists = await op.is_exist("test_hash")
    assert not exists

    # Write a document
    await op.write("test_hash", b"test content")

    # Should exist now
    exists = await op.is_exist("test_hash")
    assert exists


@pytest.mark.asyncio
async def test_db_storage_operator_write(monkeypatch, mock_engine):
    """Test DBStorageOperator write method"""
    do_monkeypatch(monkeypatch, mock_engine)
    op = dal.DBStorageOperator("doc", "test_root")

    test_bytes = b"test content"
    await op.write("test_hash", test_bytes)

    # Verify it was written
    result = await op.read("test_hash")
    assert result == test_bytes


@pytest.mark.asyncio
async def test_db_storage_operator_list(monkeypatch, mock_engine):
    """Test DBStorageOperator list method"""
    do_monkeypatch(monkeypatch, mock_engine)
    op = dal.DBStorageOperator("doc", "test_root")

    # Write multiple documents
    await op.write("hash1", b"content1")
    await op.write("hash2", b"content2")

    # List them
    hashes = await op.list("")
    assert len(hashes) == 2
    assert "hash1" in hashes
    assert "hash2" in hashes


@pytest.mark.asyncio
async def test_db_storage_operator_get_uri():
    """Test DBStorageOperator get_uri method"""

    op = dal.DBStorageOperator("doc", "test_root")

    uri = op.get_uri("test_hash")
    assert uri == "bytes://test_hash"


@pytest.mark.asyncio
async def test_db_storage_operator_delete(monkeypatch, mock_engine):
    do_monkeypatch(monkeypatch, mock_engine)
    """Test DBStorageOperator delete method"""

    op = dal.DBStorageOperator("doc", "test_root")

    # Write a document
    await op.write("test_hash", b"test content")

    # Verify it exists
    exists = await op.is_exist("test_hash")
    assert exists

    # Delete it
    await op.delete("test_hash")

    # Verify it's gone
    exists = await op.is_exist("test_hash")
    assert not exists


@pytest.mark.asyncio
async def test_db_storage_operator_delete_missing(monkeypatch, mock_engine):
    do_monkeypatch(monkeypatch, mock_engine)
    """Test DBStorageOperator delete method"""

    op = dal.DBStorageOperator("doc", "test_root")

    # Delete a document that doesn't exist
    with pytest.raises(FileNotFoundError):
        await op.delete("test_hash")


@pytest.mark.asyncio
async def test_file_storage_operator_init_relative_path(tmp_path):
    """Test FileStorageOperator initialization with relative path"""
    with patch("os.getcwd", return_value=str(tmp_path)):
        op = dal.FileStorageOperator("relative/path")
        assert op.store_path.startswith(str(tmp_path))


@pytest.mark.asyncio
async def test_file_storage_operator_init_absolute_path(tmp_path):
    """Test FileStorageOperator initialization with absolute path"""
    test_path = tmp_path / "absolute"
    op = dal.FileStorageOperator(str(test_path))
    assert op.store_path == str(test_path)
    assert test_path.exists()


@pytest.mark.asyncio
async def test_file_storage_operator_read(tmp_path):
    """Test FileStorageOperator read method"""
    op = dal.FileStorageOperator(str(tmp_path))
    test_bytes = b"test content"
    await op.write("test_hash_abc", test_bytes)

    result = await op.read("test_hash_abc")
    assert result == test_bytes


@pytest.mark.asyncio
async def test_file_storage_operator_is_exist(tmp_path):
    """Test FileStorageOperator is_exist method"""
    op = dal.FileStorageOperator(str(tmp_path))

    # Should not exist initially
    exists = await op.is_exist("test_hash_xyz")
    assert not exists

    # Write a file
    await op.write("test_hash_xyz", b"test content")

    # Should exist now
    exists = await op.is_exist("test_hash_xyz")
    assert exists


@pytest.mark.asyncio
async def test_file_storage_operator_write(tmp_path):
    """Test FileStorageOperator write method"""
    op = dal.FileStorageOperator(str(tmp_path))
    test_bytes = b"test content"
    await op.write("test_hash_def", test_bytes)

    # Verify it was written
    result = await op.read("test_hash_def")
    assert result == test_bytes


@pytest.mark.asyncio
async def test_file_storage_operator_delete(tmp_path):
    """Test FileStorageOperator delete method"""
    op = dal.FileStorageOperator(str(tmp_path))

    # Write a file
    await op.write("test_hash_ghi", b"test content")

    # Verify it exists
    exists = await op.is_exist("test_hash_ghi")
    assert exists

    # Delete it
    await op.delete("test_hash_ghi")

    # Verify it's gone
    exists = await op.is_exist("test_hash_ghi")
    assert not exists


@pytest.mark.asyncio
async def test_file_storage_operator_list(tmp_path):
    """Test FileStorageOperator list method"""
    op = dal.FileStorageOperator(str(tmp_path))

    # Write multiple files
    await op.write("hash1_ab", b"content1")
    await op.write("hash2_cd", b"content2")

    # List them
    files = await op.list("")
    assert len(files) >= 2


@pytest.mark.asyncio
async def test_file_storage_operator_get_uri(tmp_path):
    """Test FileStorageOperator get_uri method"""
    op = dal.FileStorageOperator(str(tmp_path))
    uri = op.get_uri("test_hash_jkl")
    assert uri.startswith("file://")


def test_get_storage_operator_doc_artifact():
    """Test get_storage_operator with DOC artifact type"""
    with patch("soliplex.ingester.lib.dal.get_settings") as mock_settings:
        mock_settings.return_value = Mock(
            file_store_target="db",
            file_store_dir="/tmp",
            doc_store_dir="docs",
        )
        op = dal.get_storage_operator(models.ArtifactType.DOC)
        assert isinstance(op, dal.DBStorageOperator)


def test_get_storage_operator_fs_target(tmp_path):
    """Test get_storage_operator with fs target"""
    with patch("soliplex.ingester.lib.dal.get_settings") as mock_settings:
        mock_settings_obj = Mock()
        mock_settings_obj.file_store_target = "fs"
        mock_settings_obj.file_store_dir = str(tmp_path)
        mock_settings_obj.document_store_dir = "docs"
        mock_settings.return_value = mock_settings_obj

        op = dal.get_storage_operator(models.ArtifactType.DOC)
        assert isinstance(op, dal.FileStorageOperator)


def test_get_storage_operator_s3_target():
    """Test get_storage_operator with s3 target"""

    with patch("soliplex.ingester.lib.dal.get_settings") as mock_settings:
        with patch("soliplex.ingester.lib.dal.opendal.AsyncOperator") as mock_op:
            # Create mock S3 config
            mock_s3_config = Mock()
            mock_s3_config.bucket = "test-bucket"
            mock_s3_config.endpoint_url = "http://localhost:9000"
            mock_s3_config.access_key_id = "key"
            mock_s3_config.access_secret = "secret"
            mock_s3_config.region = "us-east-1"

            mock_settings_obj = Mock()
            mock_settings_obj.file_store_target = "s3"
            mock_settings_obj.s3_doc = mock_s3_config
            mock_settings.return_value = mock_settings_obj

            _ = dal.get_storage_operator(models.ArtifactType.DOC)
            mock_op.assert_called_once()


def test_get_storage_operator_unknown_target():
    """Test get_storage_operator with unknown target"""
    with patch("soliplex.ingester.lib.dal.get_settings") as mock_settings:
        mock_settings.return_value = Mock(file_store_target="unknown")
        with pytest.raises(ValueError, match="Unknown target"):
            dal.get_storage_operator(models.ArtifactType.DOC)


def test_get_storage_operator_requires_step_config():
    """Test get_storage_operator requires step_config for non-DOC artifacts"""
    with patch("soliplex.ingester.lib.dal.get_settings") as mock_settings:
        mock_settings.return_value = Mock(file_store_target="db")
        with pytest.raises(ValueError, match="step_config is required"):
            dal.get_storage_operator(models.ArtifactType.PARSED_MD)


def test_get_storage_operator_validates_artifact_type():
    """Test get_storage_operator validates artifact type against step type"""
    mock_step_config = Mock()
    mock_step_config.step_type = models.WorkflowStepType.INGEST
    mock_step_config.id = 1

    with patch("soliplex.ingester.lib.dal.get_settings") as mock_settings:
        mock_settings.return_value = Mock(
            file_store_target="db",
            file_store_dir="/tmp",
            parsed_md_store_dir="parsed",
        )
        # INGEST step should not produce PARSED_MD artifact
        with pytest.raises(ValueError, match="Artifact type .* is not expected"):
            dal.get_storage_operator(models.ArtifactType.PARSED_MD, step_config=mock_step_config)


def test_get_storage_operator_with_valid_step_config():
    """Test get_storage_operator with valid step config"""
    mock_step_config = Mock()
    mock_step_config.step_type = models.WorkflowStepType.PARSE
    mock_step_config.id = 1

    with patch("soliplex.ingester.lib.dal.get_settings") as mock_settings:
        mock_settings.return_value = Mock(
            file_store_target="db",
            file_store_dir="/tmp",
            parsed_md_store_dir="parsed",
        )
        op = dal.get_storage_operator(models.ArtifactType.PARSED_MD, step_config=mock_step_config)
        assert isinstance(op, dal.DBStorageOperator)


def test_file_operator_store_path():
    op = dal.FileStorageOperator("tmp")
    assert "tmp" in op.store_path

    op = dal.FileStorageOperator("/tmp")
    assert "tmp" in op.store_path

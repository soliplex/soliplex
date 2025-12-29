import pathlib
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from docling_core.types.doc.document import DoclingDocument
from haiku.rag.config import Config as HRConfig
from haiku.rag.store.models.chunk import Chunk

from soliplex.ingester.lib import models
from soliplex.ingester.lib import rag


@pytest.fixture
def mock_app_config():
    """Create a mock AppConfig object"""
    config = MagicMock()
    config.providers = MagicMock()
    config.providers.docling_serve = MagicMock()
    config.providers.docling_serve.base_url = "http://localhost:5004/v1"
    config.providers.docling_serve.timeout = 30
    config.embeddings = MagicMock()
    config.embeddings.model = MagicMock()
    config.embeddings.model.name = "default-model"
    config.embeddings.model.vector_dim = 768
    config.embeddings.model.provider = "ollama"
    config.processing = MagicMock()
    config.storage = MagicMock()
    config.storage.data_dir = "/tmp/lancedb"
    config.storage.auto_vacuum = True
    return config


@pytest.fixture
def mock_settings():
    """Create a mock settings object"""
    settings = MagicMock()
    settings.docling_server_url = "http://localhost:5004/v1"
    settings.docling_http_timeout = 60
    settings.lancedb_dir = "/tmp/lancedb"
    settings.embed_batch_size = 10
    return settings


def test_build_docling_config(mock_app_config, mock_settings):
    """Test build_docling_config function"""
    with patch("soliplex.ingester.lib.rag.get_settings", return_value=mock_settings):
        config_dict = {}
        result = rag.build_docling_config(mock_app_config, config_dict)

        # Verify the config is a copy
        assert result is not mock_app_config

        # Verify docling_serve configuration is updated
        assert result.providers.docling_serve.base_url == "http://localhost:5004"
        assert result.providers.docling_serve.timeout == 60


def test_build_embed_config(mock_app_config):
    """Test build_embed_config function"""
    config_dict = {
        "model": "test-model",
        "vector_dim": 1024,
        "provider": "test-provider",
    }
    result = rag.build_embed_config(mock_app_config, config_dict)

    # Verify the config is a copy
    assert result is not mock_app_config

    # Verify embeddings configuration is updated
    assert result.embeddings.model.name == "test-model"
    assert result.embeddings.model.vector_dim == 1024
    assert result.embeddings.model.provider == "test-provider"


def test_build_embed_config_missing_required_key(mock_app_config):
    """Test build_embed_config raises ValueError when required keys are missing"""
    config_dict = {"model": "test-model"}  # Missing vector_dim

    with pytest.raises(ValueError, match="Missing required key vector_dim"):
        rag.build_embed_config(mock_app_config, config_dict)


def test_build_chunk_config(mock_app_config, mock_settings):
    """Test build_chunk_config function"""
    with patch("soliplex.ingester.lib.rag.get_settings", return_value=mock_settings):
        config_dict = {
            "chunk_size": 512,
            "chunker": "hierarchical",
            "text_context_radius": 2,  # Should be removed
            "extra_param": "value",
        }
        result = rag.build_chunk_config(mock_app_config, config_dict)

        # Verify the config is a copy
        assert result is not mock_app_config

        # Verify docling config is also built
        assert result.providers.docling_serve.base_url == "http://localhost:5004"

        # Verify processing parameters are set (text_context_radius should be excluded)
        assert result.processing.chunk_size == 512
        assert result.processing.chunker == "hierarchical"
        assert result.processing.extra_param == "value"


def test_build_chunk_config_missing_required_key(mock_app_config, mock_settings):
    """Test build_chunk_config raises ValueError when required keys are missing"""
    with patch("soliplex.ingester.lib.rag.get_settings", return_value=mock_settings):
        config_dict = {"chunk_size": 512}  # Missing chunker

        with pytest.raises(ValueError, match="Missing required key chunker"):
            rag.build_chunk_config(mock_app_config, config_dict)


def test_build_storage_config(mock_app_config, mock_settings):
    """Test build_storage_config function"""
    with patch("soliplex.ingester.lib.rag.get_settings", return_value=mock_settings):
        config_dict = {
            "data_dir": "test-dir",
            "extra_param": "value",
        }
        result = rag.build_storage_config(mock_app_config, config_dict)

        # Verify the config is a copy
        assert result is not mock_app_config

        # Verify storage parameters are set
        expected_path = pathlib.Path("/tmp/lancedb") / pathlib.Path("test-dir")
        assert result.storage.data_dir == expected_path
        assert result.storage.auto_vacuum is False  # Hardcoded to False
        assert result.storage.extra_param == "value"


def test_build_storage_config_missing_required_key(mock_app_config, mock_settings):
    """Test build_storage_config raises ValueError when required keys are missing"""
    with patch("soliplex.ingester.lib.rag.get_settings", return_value=mock_settings):
        config_dict = {}  # Missing data_dir

        with pytest.raises(ValueError, match="Missing required key data_dir"):
            rag.build_storage_config(mock_app_config, config_dict)


def test_build_full_config(mock_app_config, mock_settings):
    """Test build_full_config function"""
    with patch("soliplex.ingester.lib.rag.get_settings", return_value=mock_settings):
        chunk_config = {"chunk_size": 512, "chunker": "hierarchical"}
        embed_config = {"model": "test-model", "vector_dim": 1024, "provider": "test-provider"}
        storage_config = {"data_dir": "test-dir"}

        result = rag.build_full_config(mock_app_config, chunk_config, embed_config, storage_config)

        # Verify the config is a copy
        assert result is not mock_app_config

        # Verify all configurations are applied
        assert result.processing.chunk_size == 512
        assert result.processing.chunker == "hierarchical"
        assert result.embeddings.model.name == "test-model"
        assert result.embeddings.model.vector_dim == 1024
        expected_path = pathlib.Path("/tmp/lancedb") / pathlib.Path("test-dir")
        assert result.storage.data_dir == expected_path


@pytest.mark.asyncio
async def test_get_chunk_objs():
    """Test get_chunk_objs function"""
    mock_docling_doc = MagicMock(spec=DoclingDocument)
    config_dict = {"chunk_size": 512, "chunker": "hierarchical"}

    mock_chunk1 = MagicMock(spec=Chunk)
    mock_chunk2 = MagicMock(spec=Chunk)
    expected_chunks = [mock_chunk1, mock_chunk2]

    with (
        patch("soliplex.ingester.lib.rag.build_chunk_config") as mock_build_config,
        patch("soliplex.ingester.lib.rag.get_chunker") as mock_get_chunker,
    ):
        mock_config = MagicMock()
        mock_build_config.return_value = mock_config

        mock_chunker = MagicMock()
        mock_chunker.chunk = AsyncMock(return_value=expected_chunks)
        mock_get_chunker.return_value = mock_chunker

        result = await rag.get_chunk_objs(mock_docling_doc, config_dict)

        # Verify the correct functions were called
        mock_build_config.assert_called_once_with(HRConfig, config_dict)
        mock_get_chunker.assert_called_once_with(mock_config)
        mock_chunker.chunk.assert_called_once_with(mock_docling_doc)

        # Verify the result
        assert result == expected_chunks


@pytest.mark.asyncio
async def test_embed(mock_settings):
    """Test embed function"""
    with patch("soliplex.ingester.lib.rag.get_settings", return_value=mock_settings):
        mock_chunk1 = MagicMock(spec=Chunk)
        mock_chunk2 = MagicMock(spec=Chunk)
        mock_chunk3 = MagicMock(spec=Chunk)
        chunks = [mock_chunk1, mock_chunk2, mock_chunk3]

        config_dict = {"model": "test-model", "vector_dim": 1024, "provider": "test-provider"}
        doc_hash = "test-hash-123"

        # Mock embedded chunks returned
        embedded_chunk1 = MagicMock(spec=Chunk)
        embedded_chunk2 = MagicMock(spec=Chunk)
        embedded_chunk3 = MagicMock(spec=Chunk)

        with (
            patch("soliplex.ingester.lib.rag.build_embed_config") as mock_build_config,
            patch("soliplex.ingester.lib.rag.embed_chunks") as mock_embed_chunks,
        ):
            mock_config = MagicMock()
            mock_build_config.return_value = mock_config

            # Mock embed_chunks to return batches
            mock_embed_chunks.side_effect = [
                [embedded_chunk1, embedded_chunk2],  # First batch
                [embedded_chunk3],  # Second batch
            ]

            # Set batch size to 2
            mock_settings.embed_batch_size = 2

            result = await rag.embed(chunks, config_dict, doc_hash)

            # Verify the correct functions were called
            mock_build_config.assert_called_once_with(HRConfig, config_dict)
            assert mock_embed_chunks.call_count == 2

            # Verify the result
            assert result == [embedded_chunk1, embedded_chunk2, embedded_chunk3]


@pytest.mark.asyncio
async def test_save_to_rag():
    """Test save_to_rag function"""
    # Create mock objects
    mock_doc = MagicMock(spec=models.Document)
    mock_doc.hash = "doc-hash-123"
    mock_doc.doc_meta = {"md5": "md5-hash-456", "extra": "metadata"}
    mock_doc.mime_type = "application/pdf"

    mock_chunk1 = MagicMock(spec=Chunk)
    mock_chunk2 = MagicMock(spec=Chunk)
    chunks = [mock_chunk1, mock_chunk2]

    docling_json = '{"document": "content"}'
    source_uri = "http://example.com/doc.pdf"

    step_config = MagicMock(spec=models.StepConfig)
    step_config.config_json = {"data_dir": "test-dir"}

    embed_config = MagicMock(spec=models.StepConfig)
    embed_config.config_json = {"model": "test-model", "vector_dim": 1024, "provider": "test-provider"}

    mock_docling_document = MagicMock(spec=DoclingDocument)

    mock_new_doc = MagicMock()
    mock_new_doc.id = "new-rag-doc-id"

    with (
        patch("soliplex.ingester.lib.rag.build_embed_config") as mock_build_embed_config,
        patch("soliplex.ingester.lib.rag.build_storage_config") as mock_build_storage_config,
        patch("soliplex.ingester.lib.rag.DoclingDocument") as mock_docling_class,
        patch("soliplex.ingester.lib.rag.HaikuRAG") as mock_haiku_rag,
    ):
        mock_config = MagicMock()
        mock_build_embed_config.return_value = mock_config
        mock_build_storage_config.return_value = mock_config

        mock_docling_class.model_validate_json.return_value = mock_docling_document

        # Setup the async context manager for HaikuRAG
        mock_client = MagicMock()
        mock_client.import_document = AsyncMock(return_value=mock_new_doc)
        mock_haiku_rag.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_haiku_rag.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await rag.save_to_rag(
            doc=mock_doc,
            chunks=chunks,
            docling_json=docling_json,
            source_uri=source_uri,
            step_config=step_config,
            embed_config=embed_config,
        )

        # Verify the correct functions were called
        mock_build_embed_config.assert_called_once_with(HRConfig, embed_config.config_json)
        mock_build_storage_config.assert_called_once()
        mock_docling_class.model_validate_json.assert_called_once_with(docling_json)

        # Verify HaikuRAG was initialized and import_document was called
        mock_haiku_rag.assert_called_once_with(config=mock_config, create=True)
        mock_client.import_document.assert_called_once()

        # Verify the metadata passed to import_document
        call_kwargs = mock_client.import_document.call_args.kwargs
        assert call_kwargs["chunks"] == chunks
        assert call_kwargs["title"] is None
        assert call_kwargs["uri"] == source_uri
        assert call_kwargs["docling_document"] == mock_docling_document
        assert call_kwargs["metadata"]["doc_id"] == "doc-hash-123"
        assert call_kwargs["metadata"]["md5"] == "md5-hash-456"
        assert call_kwargs["metadata"]["content_type"] == "application/pdf"
        assert call_kwargs["metadata"]["extra"] == "metadata"

        # Verify the result
        assert result == "new-rag-doc-id"


@pytest.mark.asyncio
async def test_save_to_rag_missing_data_dir():
    """Test save_to_rag raises ValueError when data_dir is missing"""
    mock_doc = MagicMock(spec=models.Document)
    mock_doc.hash = "doc-hash-123"
    mock_doc.doc_meta = {"md5": "md5-hash-456"}

    step_config = MagicMock(spec=models.StepConfig)
    step_config.config_json = {}  # Missing data_dir

    embed_config = MagicMock(spec=models.StepConfig)
    embed_config.config_json = {"model": "test-model", "vector_dim": 1024, "provider": "test-provider"}

    with pytest.raises(ValueError, match="Missing required key data_dir"):
        await rag.save_to_rag(
            doc=mock_doc,
            chunks=[],
            docling_json='{"test": "data"}',
            source_uri="http://example.com/doc.pdf",
            step_config=step_config,
            embed_config=embed_config,
        )

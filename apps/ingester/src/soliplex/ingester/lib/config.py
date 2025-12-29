from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class S3Settings(BaseSettings):
    bucket: str = "default"
    endpoint_url: str = "default"
    access_key: str = "default"
    access_secret: str = "default"
    region: str = "default"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__", env_nested_max_split=1)
    doc_db_url: str
    docling_server_url: str = "http://localhost:5001/v1"
    docling_http_timeout: int = 600
    log_level: str = "INFO"
    file_store_target: str = "fs"
    file_store_dir: str = "file_store"
    lancedb_dir: str = "lancedb"
    document_store_dir: str = "raw"
    parsed_markdown_store_dir: str = "markdown"
    parsed_json_store_dir: str = "json"
    chunks_store_dir: str = "chunks"
    embeddings_store_dir: str = "embeddings"

    ingest_queue_concurrency: int = 20
    ingest_worker_concurrency: int = 10
    docling_concurrency: int = 3
    # default_s3: S3Settings = S3Settings()
    # document_s3: S3Settings = S3Settings()
    # parsed_markdown_s3: S3Settings = S3Settings()
    # parsed_json_s3: S3Settings = S3Settings()
    # chunks_s3: S3Settings = S3Settings()
    # embeddings_s3: S3Settings = S3Settings()

    workflow_dir: str = "config/workflows"
    default_workflow_id: str = "batch_split"
    param_dir: str = "config/params"
    default_param_id: str = "default"
    worker_checkin_interval: int = 120
    worker_checkin_timeout: int = 600
    worker_task_count: int = 5
    embed_batch_size: int = 1000

    do_rag: bool = True  # used for testing to turn off haiku rag


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

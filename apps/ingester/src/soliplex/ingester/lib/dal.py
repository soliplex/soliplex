import logging
import os
import pathlib

import aiofiles
import opendal
from aiofiles import os as aos
from fsspec.core import url_to_fs
from sqlalchemy import func
from sqlmodel import select

from . import models
from .config import get_settings

logger = logging.getLogger(__name__)


async def recursive_listdir(file_dir: pathlib.Path):
    file_paths = []
    ls = await aos.listdir(file_dir)
    for entry in ls:
        ed = file_dir / entry
        isdir = await aos.path.isdir(ed)
        if isdir:
            ext = await recursive_listdir(ed)
            file_paths.extend(ext)
        else:
            file_paths.append(ed)
    return file_paths


async def read_input_url(input_url: str):
    if input_url.startswith("file://"):
        _, local_path = url_to_fs(input_url)
        return await read_file_url(input_url)
    elif input_url.startswith("s3://"):
        return await read_s3_url(input_url)
    else:
        raise ValueError(f"Unknown uri {input_url}")


async def read_file_url(input_url: str):
    """
    read a file from file uri as an input to ingester
    """
    _, local_path = url_to_fs(input_url)
    async with aiofiles.open(local_path, "rb") as f:
        return await f.read()


async def read_s3_url(input_url: str):
    """
    read a file from s3 as an input to ingester
    """
    parts = input_url.split("/")
    bucket = parts[2]
    key = "/".join(parts[3:])
    logger.info(f"reading s3 bucket={bucket} key={key}")
    settings = get_settings()
    op = opendal.AsyncOperator(
        "s3",
        bucket=bucket,
        endpoint=settings.s3_input_endpoint_url,
        access_key_id=settings.s3_input_key,
        secret_access_key=settings.s3_input_secret,
        region=settings.s3_input_region,
    )
    return await op.read(key)


class DBStorageOperator:
    def __init__(self, artifact_type: str, storage_root: str):
        self.artifact_type = artifact_type
        self.storage_root = storage_root

    async def read(self, path: str) -> bytes:
        async with models.get_session() as session:
            rs = await session.exec(
                select(models.DocumentBytes)
                .where(models.DocumentBytes.hash == path)
                .where(models.DocumentBytes.artifact_type == self.artifact_type)
                .where(models.DocumentBytes.storage_root == self.storage_root)
            )
            res = rs.first()
            if res:
                return res.file_bytes
            else:
                raise FileNotFoundError(path)

    async def is_exist(self, path: str) -> bool:
        async with models.get_session() as session:
            statement = (
                select(func.count())
                .select_from(models.DocumentBytes)
                .where(models.DocumentBytes.hash == path)
                .where(models.DocumentBytes.artifact_type == self.artifact_type)
                .where(models.DocumentBytes.storage_root == self.storage_root)
            )
            rs = await session.exec(statement)
            ct = rs.first()
            logger.debug(f"is_exist found {ct} for {path}")
            return ct > 0

    async def write(self, path: str, file_bytes: bytes):
        async with models.get_session() as session:
            docbytes = models.DocumentBytes(
                hash=path,
                file_size=len(file_bytes),
                file_bytes=file_bytes,
                artifact_type=self.artifact_type,
                storage_root=self.storage_root,
            )
            session.add(docbytes)
            await session.flush()
            await session.commit()

    async def list(self, path: str) -> list[str]:
        async with models.get_session() as session:
            rs = await session.exec(
                select(models.DocumentBytes)
                .where(models.DocumentBytes.artifact_type == self.artifact_type)
                .where(models.DocumentBytes.storage_root == self.storage_root)
            )
            res = rs.all()
            return [r.hash for r in res]

    def get_uri(self, path: str) -> str:
        return f"bytes://{path}"

    async def delete(self, path: str):
        async with models.get_session() as session:
            rs = await session.exec(
                select(models.DocumentBytes)
                .where(models.DocumentBytes.hash == path)
                .where(models.DocumentBytes.artifact_type == self.artifact_type)
                .where(models.DocumentBytes.storage_root == self.storage_root)
            )
            res = rs.first()
            if res:
                await session.delete(res)
                await session.flush()
                await session.commit()
            else:
                raise FileNotFoundError(path)


class FileStorageOperator:
    def __init__(self, store_path: str):
        if not store_path.startswith("/"):
            store_path = os.path.join(os.getcwd(), store_path)
        # self.op = opendal.AsyncOperator("fs", root=store_path)
        self.store_path = store_path
        if not os.path.exists(store_path):
            os.makedirs(store_path, exist_ok=True)

    def _get_normalized_path(self, path: str) -> pathlib.Path:
        subdir = path[-2:]
        norm_path = pathlib.Path(self.store_path) / subdir
        norm_path.mkdir(parents=True, exist_ok=True)
        norm_path = norm_path / path
        # store_url = norm_path.as_uri()
        return norm_path

    async def read(self, path: str) -> bytes:
        norm_path = self._get_normalized_path(path)
        async with aiofiles.open(norm_path, "rb") as f:
            return await f.read()

    async def is_exist(self, path: str) -> bool:
        norm_path = self._get_normalized_path(path)
        return await aos.path.exists(norm_path)

    async def write(self, path: str, file_bytes: bytes):
        norm_path = self._get_normalized_path(path)
        async with aiofiles.open(norm_path, "wb") as f:
            await f.write(file_bytes)

    async def delete(self, path: str):
        norm_path = self._get_normalized_path(path)
        await aos.unlink(norm_path)

    async def list(self, path: str) -> list[str]:
        files = await recursive_listdir(self._get_normalized_path(self.store_path))
        return [f.name for f in files]

    def get_uri(self, path: str) -> str:
        norm_path = self._get_normalized_path(path)
        return norm_path.as_uri()


def get_storage_operator(
    artifact_type: models.ArtifactType,
    step_config: models.StepConfig | None = None,
) -> opendal.AsyncOperator:
    if step_config is not None:
        expected_artifact_type = models.ARTIFACTS_FROM_STEPS[step_config.step_type]
        if artifact_type not in expected_artifact_type:
            raise ValueError(f"Artifact type {artifact_type} is not expected for step type {step_config.step_type}")
    if step_config is None and artifact_type != models.ArtifactType.DOC:
        raise ValueError("step_config is required for non-document artifacts")
    settings = get_settings()
    target = settings.file_store_target
    op = None
    st = artifact_type.value
    if artifact_type == models.ArtifactType.DOC:
        root = ""
    else:
        root = str(step_config.id)  # TODO: may need to make friendlier
    if target == "s3":
        cfg = getattr(settings, f"s3_{st}")
        op = opendal.AsyncOperator(
            "s3",
            bucket=cfg.bucket,
            endpoint=cfg.endpoint_url,
            access_key_id=cfg.access_key_id,
            secret_access_key=cfg.access_secret,
            region=cfg.region,
            root=root,
        )
    elif target == "fs":
        fs_root = settings.file_store_dir + "/" + getattr(settings, f"{st}_store_dir") + "/" + root
        op = FileStorageOperator(fs_root)
    elif target == "db":
        op = DBStorageOperator(st, root)

    else:
        raise ValueError(f"Unknown target {target}")
    return op

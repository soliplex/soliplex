import hashlib
import json
import logging
import mimetypes
import pathlib
from pathlib import Path

import aiofiles
import aiofiles.os as aos

from soliplex.agents import ValidationError
from soliplex.agents import client
from soliplex.agents.config import settings

logger = logging.getLogger(__name__)

MIME_OVERRIDES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",  # noqa: E501
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",  # noqa: E501
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",  # noqa: E501
}


async def validate_config(path: str):
    """
    Validate a configuration file and print out validation results

    Args:
        path: The path to the configuration file to validate

    Returns:
        None
    """
    config = await read_config(path)
    validate = check_config(config)
    invalid = [row for row in validate if "valid" in row and not row["valid"]]
    print(f"Validation  for {path}")
    print(f"Total files: {len(config)}")
    if invalid:
        print(f"Found {len(invalid)} Invalid files:")
        for row in invalid:
            print(row["path"], row["reason"], row["metadata"]["content-type"])


async def read_config(config_path: str) -> list[dict]:
    logger.debug(f"Reading config from {config_path}")
    async with aiofiles.open(config_path) as f:
        config = json.loads(await f.read())
        ret = config
        if isinstance(config, list):
            ret = config
        elif isinstance(config, dict) and "data" in config.keys():
            ret = config["data"]
        else:
            raise ValidationError(config_path)

        ret = sorted(ret, key=lambda x: int(x["metadata"]["size"]))

        return ret


async def build_config(source_dir) -> list[dict]:
    paths = await recursive_listdir(Path(source_dir))
    allowed_extensions = settings.extensions
    config = []
    for path in paths:
        ext = path.name.split(".")[-1]
        if ext not in allowed_extensions and not path.is_dir():
            logger.info(f"skipping {path}")
            continue
        adj_path = path.relative_to(Path(source_dir))
        mime_type = mimetypes.guess_type(str(adj_path))[0]
        if mime_type is None:
            mime_type = MIME_OVERRIDES.get(mime_type, "application/octet-stream")
        rec = {
            "path": str(adj_path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "metadata": {
                "size": path.stat().st_size,
                "content-type": mime_type,
            },
        }
        config.append(rec)
    return config


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


def check_config(config: list[dict], start: int = 0, end: int = None) -> list[dict]:
    for row in config:
        path = row["path"]
        ext = path.split(".")[-1]
        row["valid"] = True
        if "metadata" in row and "content-type" in row["metadata"]:
            content_type = row["metadata"]["content-type"]
            if content_type in [
                "application/zip",
                "application/x-zip-compressed",
                "application/octet-stream",
                "application/x-rar-compressed",
                "application/x-7z-compressed",
            ]:
                row["valid"] = False
                row["reason"] = "Unsupported content type"
        else:
            row["valid"] = False
            row["reason"] = "No content type"

        if len(ext) > 4:
            row["valid"] = False
            row["reason"] = f"Unsupported file extension {ext}"
    return config


async def load_inventory(
    path: str,
    source: str,
    start: int = 0,
    end: int = None,
    skip_invalid: bool = False,
    workflow_definition_id: str | None = None,
    start_workflows: bool = True,
    param_set_id: str | None = None,
    priority: int = 0,
):
    config = await read_config(path)
    if skip_invalid:
        filtered = check_config(config)
        config = [x for x in filtered if x["valid"]]

    logger.info(f"found {len(config)} files in {path}")
    data_path = Path(path).parent
    to_process = await client.check_status(config, source)
    logger.info(f"found {len(to_process)}  out of {len(config)} to process in {data_path}")
    if end is None:
        end = len(config)
        to_process = to_process[start:end]
    ret = {"inventory": config, "to_process": to_process}
    if len(to_process) == 0:
        logger.info("nothing to process. exiting")
        return ret

    found_batch_id = client.find_batch_for_source(source)
    if found_batch_id:
        logger.info(f"found batch {found_batch_id} for {source}")
        batch_id = found_batch_id
    else:
        logger.info(f"no batch found for {source}. creating")
        batch_id = await client.create_batch(
            source,
            source,
        )
    ret["batch_id"] = batch_id
    ingested = []
    errors = []
    for row in to_process:
        meta = row["metadata"].copy()
        for k in [
            "path",
            "sha256",
            "size",
            "source",
            "batch_id",
            "source_uri",
        ]:
            if k in meta:
                del meta[k]
        logger.info(f"starting ingest for {row['path']}")
        mime_type = None
        if "metadata" in row and "content-type" in row["metadata"]:
            mime_type = row["metadata"]["content-type"]
        res = await do_ingest(
            data_path,
            row["path"],
            meta,
            source,
            batch_id,
            mime_type,
        )
        if "error" in res:
            logger.error(f"Error ingesting {row['path']}: {res['error']}")
            res["uri"] = row["path"]
            res["source"] = source
            res["batch_id"] = batch_id
            res["batch_id"] = batch_id
            errors.append(res)
        else:
            ingested.append(res)
    wf_res = None
    if len(errors) == 0 and start_workflows:
        wf_res = await client.do_start_workflows(
            batch_id,
            workflow_definition_id,
            param_set_id,
            priority,
        )
    ret["ingested"] = ingested
    ret["errors"] = errors
    ret["workflow_result"] = wf_res
    return ret


async def do_ingest(
    data_path: Path,
    uri: str,
    meta: dict[str, str],
    source: str,
    batch_id: int,
    mime_type: str,
):
    logger.info(f"path={data_path / uri}")
    load_path = uri
    if not uri.startswith("/"):
        load_path = data_path / uri
    async with aiofiles.open(load_path, "rb") as f:
        doc_body = await f.read()

    return await client.do_ingest(
        doc_body,
        uri,
        meta,
        source,
        batch_id,
        mime_type,
    )


async def status_report(config_path: str, source: str, detail: bool = False):
    print(f"checking status for {config_path} source={source} ")
    config = await read_config(config_path)
    to_process = await client.check_status(config, source)
    print(f"Files to process: {len(to_process)}")
    print(f"Total files: {len(config)}")
    if detail and len(to_process) > 0:
        for row in to_process:
            print(row)

import asyncio
import http.cookiejar as cj
import json
import logging
import os
from io import BytesIO

import aiohttp
import httpx
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_exponential_jitter

from soliplex.ingester.lib.config import get_settings

logger = logging.getLogger(__name__)

DOCLING_PATH = os.getenv("DOCLING_PATH", ".venv/scripts/docling")
DOCLING_PARAMS = os.getenv("DOCLING_PARAMS", " --no-ocr --no-tables ")
SMALLEST_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
)

_http_sem = None


def do_repl(data):
    if isinstance(data, dict):
        return {do_repl(k): do_repl(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [do_repl(item) for item in data]
    elif isinstance(data, str) and "data:image" in data:
        return SMALLEST_PNG
    return data


@retry(stop=stop_after_attempt(4), wait=wait_exponential_jitter(), reraise=True)
async def docling_convert(
    file_bytes: bytes,
    mime_type: str,
    source_uri: str,
    config_dict: dict[str, str | int | bool],
    output_formats: list[str] = ("json", "md"),
) -> dict:
    global _http_sem
    env = get_settings()
    if _http_sem is None:
        _http_sem = asyncio.Semaphore(env.docling_concurrency)

    async with _http_sem:
        local_jar = cj.CookieJar()
        _async_client = httpx.AsyncClient(timeout=env.docling_http_timeout, cookies=local_jar)
        async_url = f"{env.docling_server_url}/convert/file/async"
        parameters = {
            "from_formats": [
                "docx",
                "pptx",
                "html",
                "image",
                "pdf",
                "asciidoc",
                "md",
                "xlsx",
            ],
            "to_formats": list(output_formats),
            "abort_on_error": True,
        }
        if "ocr_lang" in config_dict and isinstance(config_dict["ocr_lang"], str):
            config_dict = config_dict.copy()
            # this param needs to be a list
            config_dict["ocr_lang"] = [config_dict["ocr_lang"]]
        parameters.update(config_dict)

        file_name = source_uri.split("/")[-1]
        if mime_type and "markdown" in mime_type and not file_name.endswith(".md"):
            file_name = file_name + ".md"
        f = BytesIO(file_bytes)
        files = {
            "files": (file_name, f, mime_type),
        }
        logger.info(f"using {parameters} on {file_name}")
        response = await _async_client.post(async_url, files=files, data=parameters)
        async_res = response.json()
        logger.info(async_res)
        if "task_id" not in async_res:
            raise ValueError(f"no task_id in response: {async_res}")
        task_id = async_res["task_id"]
        async with aiohttp.ClientSession(cookies=response.cookies) as session:
            ws_url = f"{env.docling_server_url.replace('http', 'ws')}/status/ws/{task_id}"
            async with session.ws_connect(ws_url) as ws:
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        payload = msg.json()
                        if payload["message"] == "error":
                            break
                        if payload["message"] == "update" and payload["task"]["task_status"] in (
                            "success",
                            "failure",
                        ):
                            break
        if "task" in payload and "task_status" in payload["task"] and payload["task"]["task_status"] == "failure":
            if "errors" in payload["task"]:
                logger.error(f"errors: {payload['task']['errors']}")
            else:
                logger.error(f"no errors in response: {payload}")
        result_url = f"{env.docling_server_url}/result/{task_id}"
        response = await _async_client.get(result_url)
        res = response.json()
        if "status" not in res:
            raise ValueError(f"no status in response: {res}")
        logger.info(f"{task_id} result={res['status']} processing time={res['processing_time']}")

        if res["status"] == "success":
            parsed = {}
            for output_format in output_formats:
                output_content = res["document"][f"{output_format}_content"]
                if output_format == "json":
                    if "image_export_mode" in parameters and parameters["image_export_mode"] == "placeholder":
                        logger.info(f" doing placeholder replacement for {source_uri}")
                        output_content = do_repl(output_content)
                    parsed[output_format] = json.dumps(output_content).encode("utf-8")
                else:
                    parsed[output_format] = str(output_content).encode("utf-8")
            return parsed
        else:
            raise ValueError(str(res["errors"]))

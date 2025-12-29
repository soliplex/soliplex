import logging

import aiofiles
import pytest

import soliplex.ingester.lib.docling as docling

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def xtest_docling_cmd():
    input_file = "tests/files/complex.pdf"
    fmt = "json"
    async with aiofiles.open(input_file, "rb") as f:
        ba = await f.read()
    res = await docling.run_docling(ba, input_file, fmt)
    logger.info(res[:10])
    async with aiofiles.open(input_file.replace("pdf", fmt), "wb") as f:
        await f.write(res)


@pytest.mark.asyncio
async def test_docling_convert():
    input_file = "tests/files/basic_ocr.pdf"
    async with aiofiles.open(input_file, "rb") as f:
        ba = await f.read()
    test_config = {
        "do_ocr": True,
        "force_ocr": False,
        "ocr_engine": "easyocr",
        "ocr_lang": "en",
        "pdf_backend": "dlparse_v2",
        "table_mode": "accurate",
    }

    js = await docling.docling_convert(ba, input_file, "application/pdf", config_dict=test_config)
    assert js


@pytest.mark.asyncio
async def test_docling_convert_no_img():
    input_file = "tests/files/amt_handbook_sample.pdf"
    async with aiofiles.open(input_file, "rb") as f:
        ba = await f.read()
    test_config = {
        "do_ocr": False,
        "force_ocr": False,
        "ocr_engine": "easyocr",
        "ocr_lang": "en",
        "pdf_backend": "pypdfium2",
        "table_mode": "accurate",
        "image_export_mode": "placeholder",
    }

    js = await docling.docling_convert(ba, input_file, "application/pdf", config_dict=test_config)
    assert js

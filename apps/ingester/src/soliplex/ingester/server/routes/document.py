import json
import logging

from fastapi import APIRouter
from fastapi import Form
from fastapi import Response
from fastapi import UploadFile
from fastapi import status

from soliplex.ingester.lib import operations
from soliplex.ingester.lib import workflow as workflow

logger = logging.getLogger(__name__)

doc_router = APIRouter(prefix="/api/v1/document", tags=["document"])


@doc_router.get("/", status_code=status.HTTP_200_OK)
async def get_docs(response: Response, source: str = None, batch_id: int = None):
    if source:
        docs = await operations.get_uris_for_source(source)
        return docs
    elif batch_id:
        docs = await operations.get_uris_for_batch(batch_id)
        return docs
    else:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {
            "error": "No source or batch_id provided",
            "status_code": status.HTTP_400_BAD_REQUEST,
        }


@doc_router.post("/ingest-document", status_code=status.HTTP_201_CREATED)
async def ingest_document(
    response: Response,
    file: UploadFile = None,
    input_uri: str = Form(None),
    mime_type: str = Form(None),
    source_uri: str = Form(...),
    source: str = Form(...),
    batch_id: int = Form(...),
    doc_meta: str = Form("{}"),
    priority: int = Form(0),
):
    logger.info(f"Received file: {file} from {source}")
    if file:
        file_bytes = await file.read()
    else:
        file_bytes = None
    try:
        meta_dict = json.loads(doc_meta)
    except json.JSONDecodeError:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": "metadata should be valid JSON object"}
    if not isinstance(meta_dict, dict):
        raise TypeError("Metadata must be a dictionary")  # noqa: TRY003
    meta_dict["batch_id"] = str(batch_id)
    try:
        docuri, doc = await workflow.initial_load(
            source_uri=source_uri,
            source=source,
            batch_id=batch_id,
            doc_meta=meta_dict,
            file_bytes=file_bytes,
            input_uri=input_uri,
            mime_type=mime_type,
        )

        res = {
            "batch_id": batch_id,
            "document_uri": source_uri,
            "document_hash": doc.hash,
            "source": source,
            "uri_id": docuri.id,
        }

    except KeyError as e:
        logger.exception("Error ingesting document")
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": str(e)}
    except Exception as ex:
        logger.exception("Error ingesting document")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"error": str(ex)}
    else:
        return res

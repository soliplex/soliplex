import datetime
import hashlib
import logging
import mimetypes
import os

from sqlmodel import select
from sqlmodel import text

from . import dal
from . import models
from .config import get_settings

logger = logging.getLogger(__name__)
MIME_OVERRIDES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}

MIME_OVERRIDES_REV = {v: k for k, v in MIME_OVERRIDES.items()}


def log_context(
    batch_id: int | None = None,
    doc_hash: str | None = None,
    action: str | None = None,
    source: str | None = None,
    uri: str | None = None,
) -> dict[str, str]:
    return {
        "batch_id": str(batch_id),
        "doc_hash": doc_hash,
        "action": action,
        "source": source,
        "uri": uri,
    }


class DocumentNotFoundError(ValueError):
    def __init__(self, doc_hash):
        super().__init__(f"Document {doc_hash} not found")


class DocumentInvalidError(ValueError):
    def __init__(self, doc_hash):
        super().__init__(f"Document {doc_hash} not found")


class BatchNotFoundError(ValueError):
    def __init__(self, batch_id):
        super().__init__(f"Batch {batch_id} not found")


class BatchCompletedError(ValueError):
    def __init__(self, batch_id):
        super().__init__(f"Batch {batch_id} already complete")


def _guess_mime_type(uri: str) -> str:
    file_name = os.path.basename(uri)

    guess = mimetypes.guess_type(file_name)[0]
    if guess is None:
        ext = os.path.splitext(file_name)[1]
        return MIME_OVERRIDES_REV.get(ext, "application/octet-stream")
    return guess


def guess_extension(mime_type: str) -> str:
    guess = mimetypes.guess_extension(mime_type)
    if guess is None:
        return MIME_OVERRIDES.get(mime_type, ".bin")
    return guess


async def update_doc_meta(doc_hash: str, meta: dict[str, str]):
    async with models.get_session() as session:
        q = select(models.Document).where(models.Document.hash == doc_hash)
        exec_rs = await session.exec(q)
        res = exec_rs.first()
        if res:
            res.doc_meta = meta
            session.add(res)
            await session.commit()
        else:
            raise DocumentNotFoundError(doc_hash)


async def find_document_uri(uri: str, source: str) -> models.DocumentURI:
    logger.info(
        f"find document {uri} {source} ",
        extra=log_context(source=source, uri=uri, action="find_document_uri"),
    )
    async with models.get_session() as session:
        q = select(models.DocumentURI).where(models.DocumentURI.source == source).where(models.DocumentURI.uri == uri)
        exec_rs = await session.exec(q)
        res = exec_rs.first()
        if res:
            session.expunge(res)
        return res


async def get_document_uris_by_hash(doc_hash: str) -> list[models.DocumentURI]:
    logger.debug(
        f"get document {doc_hash}",
        extra=log_context(doc_hash=doc_hash, action="get_document_uris_by_hash"),
    )
    async with models.get_session() as session:
        q = select(models.DocumentURI).where(models.DocumentURI.doc_hash == doc_hash)
        rs = await session.exec(q)
        res = rs.all()
        if res:
            [session.expunge(x) for x in res]
        return res


async def add_history_for_hash(doc_hash: str, action: str, batch_id=None, hist_meta=None):
    """
    add history for all document uris with a given hash. useful for
    tracking operations that hit the document level
    """
    if hist_meta is None:
        hist_meta = {}
    doc_uris = await get_document_uris_by_hash(doc_hash)
    async with models.get_session() as session:
        for doc_uri in doc_uris:
            # use blank meta unless needed
            await add_history(doc_uri, hist_meta, action, session, batch_id=batch_id)
        await session.commit()


async def add_history(
    doc_uri: models.DocumentURI,
    doc_meta: dict[str, str],
    action: str,
    session,
    batch_id: int = None,
) -> models.DocumentURIHistory:
    """
    add history for a documenturi
    """
    histmeta = doc_meta.copy()
    hist = models.DocumentURIHistory(
        doc_uri_id=doc_uri.id,
        hash=doc_uri.doc_hash,
        action=action,
        version=doc_uri.version,
        histmeta=histmeta,
        process_date=datetime.datetime.now(),
        batch_id=batch_id,
    )
    session.add(hist)
    await session.flush()
    return hist


async def handle_file(session, input_uri: str = None, file_bytes=None) -> tuple[str, int, str]:
    settings = get_settings()
    if file_bytes is None:
        if input_uri is None:
            raise ValueError("input_uri or file_bytes must be provided")
        file_bytes = await dal.read_input_url(input_uri)

    if file_bytes:
        hash = models.doc_hash(file_bytes)
        md5_hash = hashlib.md5(file_bytes).hexdigest()
        logger.debug(
            f"handle file {input_uri} {hash}  to {settings.file_store_target}",
            extra=log_context(uri=input_uri, doc_hash=hash, action="handle_file"),
        )

        op = dal.get_storage_operator(models.ArtifactType.DOC)
        exists = await op.is_exist(hash)
        if not exists:
            await op.write(hash, file_bytes)
        return hash, len(file_bytes), md5_hash
    else:
        raise ValueError("file_bytes must be provided")


async def delete_file(doc_hash: str, session):
    q = text(f"""select cs.* from stepconfig cs
           inner join runstep rs on rs.step_config_id=cs.id
           inner join workflowrun r on r.id=rs.workflow_run_id
           where r.doc_id='{doc_hash}'""")
    res = await session.exec(q)
    for step_config in res.all():
        for st in models.ArtifactType:
            op = dal.get_storage_operator(st, step_config)
            try:
                await op.delete(doc_hash)
            except FileNotFoundError as fe:
                logger.debug(
                    f"file not found  {doc_hash} {fe}",
                    extra=log_context(doc_hash=doc_hash, action="delete_file"),
                )

    await add_history_for_hash(doc_hash, "file deleted", session)


async def read_doc_bytes(doc_hash: str, storage_type: models.ArtifactType):
    op = dal.get_storage_operator(storage_type)
    return await op.read(doc_hash)


async def create_document_from_uri(
    source_uri: str,  # uri in source system
    source: str,  # source system identifier
    mime_type: str = None,
    file_bytes: bytes = None,  # bytes from file if available
    input_uri: str = None,  # uri to read file from (e.g. s3 or file)
    doc_meta: dict = None,  # metadata
    batch_id: int = None,
) -> tuple[models.DocumentURI, models.Document]:
    if mime_type is None:
        mime_type = _guess_mime_type(source_uri)
    if batch_id is not None:
        batch = await get_batch(batch_id)
        if batch is None:
            raise BatchNotFoundError(batch_id)
        elif batch.completed_date is not None:
            raise BatchCompletedError(batch_id)
    # TODO:handle uris
    async with models.get_session() as session:
        # doc.hash = models.doc_hash(doc.file_bytes)
        doc_hash, file_size, md5_hash = await handle_file(session, input_uri=input_uri, file_bytes=file_bytes)
        if doc_meta is None:
            doc_meta = {}
        doc_meta.update({"md5": md5_hash})
        doc = models.Document(
            hash=doc_hash,
            uri=source_uri,
            source=source,
            mime_type=mime_type,
            file_bytes=file_bytes,
            doc_meta=doc_meta,
            batch_id=batch_id,
            file_size=file_size,
        )

        docuri = models.DocumentURI(uri=source_uri, source=source, doc_hash=doc.hash, batch_id=batch_id)

        # check if doc exists and create if needed
        docq = select(models.Document).where(models.Document.hash == doc.hash)
        docrs = await session.exec(docq)
        existdoc = docrs.first()
        if existdoc:
            logger.info(
                f"document {doc.hash} already exists",
                extra=log_context(
                    doc_hash=doc.hash,
                    action="create_document_from_uri",
                    uri=source_uri,
                    source=source,
                ),
            )
            doc = existdoc
        else:
            session.add(doc)
            await session.flush()
            await session.refresh(doc)
        # check if uri exists and create if needed
        uriq = (
            select(models.DocumentURI).where(models.DocumentURI.uri == source_uri).where(models.DocumentURI.source == source)
        )
        urirs = await session.exec(uriq)
        existdocuri = urirs.first()
        if existdocuri:
            logger.info(
                f"uri {source_uri}/{source} already exists",
                extra=log_context(
                    doc_hash=doc.hash,
                    action="create_document_from_uri",
                    uri=source_uri,
                    source=source,
                ),
            )
            docuri = existdocuri
            # refresh hash
            if existdocuri.doc_hash != doc.hash:
                existdocuri.doc_hash = doc.hash
                existdocuri.version += 1
                session.add(existdocuri)
                await session.flush()
                await session.refresh(existdocuri)
                await add_history(existdocuri, doc_meta, "update", session, batch_id=batch_id)
                docuri = existdocuri
        else:
            session.add(docuri)
            await session.flush()
            await session.refresh(docuri)
            await add_history(docuri, doc_meta, "create", session, batch_id=batch_id)
            logger.info(
                f"created {docuri.id} {docuri.uri} {docuri.source}",
                extra=log_context(
                    doc_hash=doc.hash,
                    action="create_document_from_uri",
                    uri=source_uri,
                    source=source,
                ),
            )
            await session.refresh(docuri)
        session.expunge(doc)
        session.expunge(docuri)
        await session.commit()

        return docuri, doc


async def get_document_uri_history(
    doc_uri_id: int,
) -> list[models.DocumentURIHistory]:
    logger.debug(f"get history for {doc_uri_id}")
    async with models.get_session() as session:
        q = (
            select(models.DocumentURIHistory)
            .where(models.DocumentURIHistory.doc_uri_id == doc_uri_id)
            .order_by(models.DocumentURIHistory.process_date.asc())
        )
        rs = await session.exec(q)
        res = rs.all()
        [session.expunge(x) for x in res]
        return res


async def update_doc_status(source: str, uri_hashes: dict[str, str]):
    """
    deletes document uri records that are not in the uri_hashes provided

    Args:
        source (str): The source of the documents.
        uri_hashes (dict[str, str]): A dictionary mapping URIs to their respective hashes.

    Returns:
        dict[str, Any]: A dictionary containing the status of the documents.
    """
    status, to_delete = await get_doc_status(source, uri_hashes)
    logger.info(
        f" found {len(to_delete)} to delete for {source}",
        extra=log_context(action="update_doc_status", source=source),
    )

    async with models.get_session() as session:
        for row in to_delete:
            logger.info(
                f"deleting {row['uri']}",
                extra=log_context(action="update_doc_status", source=source),
            )
            uri = await find_document_uri(row["uri"], source)
            if uri:
                await delete_document_uri(uri.id, session)
    return status


async def get_uris_for_source(source: str) -> list[models.DocumentURI]:
    logger.debug(
        f"get history for {source}",
        extra=log_context(action="get_uris_for_source", source=source),
    )
    async with models.get_session() as session:
        q = select(models.DocumentURI).where(models.DocumentURI.source == source)
        rs = await session.exec(q)
        res = rs.all()
        [session.expunge(x) for x in res]
        return res


async def get_doc_status(source: str, source_hashes: dict[str, str]):
    stored_uris = await get_uris_for_source(source)
    stored_dict = {x.uri: x.doc_hash for x in stored_uris}
    to_remove = []
    res = {}
    for source_uri, source_hash in source_hashes.items():
        if source_uri in stored_dict:
            if "-" in source_hash:
                source_hash = source_hash.split("-")[1]
            if ":" in source_hash:
                source_hash = source_hash.split(":")[1]
            stored_hash = stored_dict[source_uri].split("-")[1]
            if source_hash == stored_hash:
                res[source_uri] = {"hash": source_hash, "status": "matched"}
            else:
                res[source_uri] = {
                    "source_hash": source_hash,
                    "stored_hash": stored_hash,
                    "status": "mismatch",
                }
            del stored_dict[source_uri]
        else:
            res[source_uri] = {"hash": source_hash, "status": "new"}
    for uri, hash in stored_dict.items():
        if uri not in source_hashes:
            to_remove.append({"uri": uri, "hash": hash, "status": "deleted"})
    return res, to_remove


async def get_uris_for_batch(batch_id: int) -> list[models.DocumentURI]:
    async with models.get_session() as session:
        q = select(models.DocumentURI).where(models.DocumentURI.batch_id == batch_id)
        rs = await session.exec(q)
        res = rs.all()
        [session.expunge(x) for x in res]
        return res


async def new_batch(source: str, name: str = None) -> int:
    async with models.get_session() as session:
        batch = models.DocumentBatch(source=source, name=name, start_date=datetime.datetime.now())
        session.add(batch)
        await session.flush()
        await session.refresh(batch)
        batch_id = batch.id
        await session.commit()

        return batch_id


async def list_batches() -> list[models.DocumentBatch]:
    async with models.get_session() as session:
        q = select(models.DocumentBatch)
        rs = await session.exec(q)
        res = rs.all()
        [session.expunge(x) for x in res]
        return res


async def get_batch(id: int) -> models.DocumentBatch:
    async with models.get_session() as session:
        q = select(models.DocumentBatch).where(models.DocumentBatch.id == id)
        rs = await session.exec(q)
        res = rs.first()
        if res:
            session.expunge(res)
            return res
        return None


async def get_documents_in_batch(id: int) -> list[models.Document]:
    async with models.get_session() as session:
        q = select(models.Document).where(models.Document.batch_id == id)
        rs = await session.exec(q)
        res = rs.all()
        [session.expunge(x) for x in res]
        return res


async def delete_document(doc_hash: str, session, raise_on_error=True) -> models.Document:
    logger.debug(f"remove document {doc_hash}", extra=log_context(doc_hash=doc_hash))
    # make sure there aren't any uris pointing to it
    # not all backends actually enforce this
    u1 = select(models.DocumentURI).where(models.DocumentURI.doc_hash == doc_hash)
    urs = await session.exec(u1)
    found = urs.all()
    if found and len(found) != 0:
        if raise_on_error:
            raise ValueError(f"document {doc_hash} has existing uris. found {len(found)} ")
        else:
            logger.info(
                f"ignoring delete of document with existing uris {doc_hash}",
                extra=log_context(doc_hash=doc_hash),
            )
            return

    q = select(models.Document).where(models.Document.hash == doc_hash)
    rs = await session.exec(q)
    res = rs.first()
    if res:
        await session.delete(res)
        await session.flush()
        await delete_file(res.hash, session)
        # don't commit here  we're borowing the session from the caller
        # await session.commit()

    return res


async def delete_document_uri(doc_uri_id: int, session) -> models.DocumentURI:
    logger.debug(f"remove document uri {doc_uri_id}")
    q = select(models.DocumentURI).where(models.DocumentURI.id == doc_uri_id)
    rs = await session.exec(q)
    res = rs.first()
    if res:
        await session.delete(res)
        await delete_document(res.doc_hash, session, raise_on_error=False)
        await session.flush()
    else:
        raise DocumentNotFoundError(doc_uri_id)
    return res


async def get_document(doc_hash: str) -> models.Document:
    logger.debug(f"get document {doc_hash}", extra=log_context(doc_hash=doc_hash))
    async with models.get_session() as session:
        q = select(models.Document).where(models.Document.hash == doc_hash)
        rs = await session.exec(q)
        res = rs.first()
        if res:
            session.expunge(res)
            return res
        else:
            raise DocumentNotFoundError(doc_hash)


async def delete_orphaned_documents():
    """
    delete orphaned documents that have no uri pointing to them
    """
    async with models.get_session() as session:
        q1 = text("""delete from document where hash not in
            (select doc_hash from documenturi)""")
        q2 = text("""delete from documenturihistory where hash not in
            (select doc_hash from documenturi)""")

        await session.exec(q1)
        await session.exec(q2)
        await session.commit()


async def validate_storage():
    filesets = {}
    for st in models.ArtifactType:
        op = dal.get_storage_operator(st)
        files = await op.list("/")
        files = set(files)
        filesets[st] = files
    diffs = {}
    for s1 in models.ArtifactType:
        for s2 in models.ArtifactType:
            if s1 == s2:
                continue
            diff = set(filesets[s1]) - (set(filesets[s2]))
            diffs[(s1, s2)] = diff

    return diffs

import logging

from soliplex.ingester.lib.workflow import WorkflowException

logger = logging.getLogger(__name__)
_start_span_marker = None
_notif_slack_marker = None
_end_span_marker = None


async def start_span(span_id: str):
    global _start_span_marker
    _start_span_marker = span_id
    logger.info(f"starting span {span_id}")


async def end_span(span_id: str):
    global _end_span_marker
    _end_span_marker = span_id
    logger.info(f"end span {span_id}")


async def notify_slack(channel_id: str, msg: str):
    logger.info(f"notify slack {channel_id} {msg}")
    global _notif_slack_marker
    _notif_slack_marker = channel_id


async def validate_document(batch_id: int = None, doc_hash: str = None, source: str = None, fail: bool = False):
    logger.info(f"validate_document started  source={source} batch_id={batch_id} doc_hash={doc_hash}")
    if fail:
        raise WorkflowException("validation failed")

    logger.info(f"validate_document completed  source={source} batch_id={batch_id} doc_hash={doc_hash}")


async def parse_document(batch_id: int = None, doc_hash: str = None, source: str = None):
    logger.info(f"parse_document started  source={source} batch_id={batch_id} doc_hash={doc_hash}")


async def chunk_document(batch_id: int = None, doc_hash: str = None, source: str = None):
    logger.info(f"chunk_document started  source={source} batch_id={batch_id} doc_hash={doc_hash}")


async def embed_document(batch_id: int = None, doc_hash: str = None, source: str = None):
    logger.info(f"embed_document started  source={source} batch_id={batch_id} doc_hash={doc_hash}")


async def save_document(
    batch_id: int = None,
    doc_hash: str = None,
    uri: str = None,
    source: str = None,
):
    logger.info(f"save_document started  source={source} batch_id={batch_id} doc_hash={doc_hash}")

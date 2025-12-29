import json
import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi import FastAPI
from fastapi import Form
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from soliplex.ingester.lib import operations
from soliplex.ingester.lib.config import get_settings

from .routes.batch import batch_router
from .routes.document import doc_router
from .routes.stats import stats_router
from .routes.workflow import wf_router

logger = logging.getLogger(__name__)


async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    logger.info("Starting soliplex-ingester")
    import soliplex.ingester.lib.wf.runner as runner

    await runner.start_worker()
    yield
    logger.info("soliplex-ingester stopped")


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)
v1_router = APIRouter(prefix="/api/v1")


@v1_router.post(
    "/source-status", summary="Check which files need processing by comparing submitted hashes to existing hashes"
)
async def source_status(source: str = Form(...), hashes: str = Form(...)):
    hashes = json.loads(hashes)
    if not isinstance(hashes, dict):
        msg = "hashes must be a dictionary"
        raise TypeError(msg)
    status, to_delete = await operations.get_doc_status(source, hashes)
    return status


@v1_router.post("/source-cleanup", summary="Delete files that are not in the submitted hashes for this source")
async def source_cleanup(batch_id: int = Form(...), hashes: str = Form(...)):
    hashes = json.loads(hashes)
    if not isinstance(hashes, dict):
        msg = "hashes must be a dictionary"
        raise TypeError(msg)
    batch = operations.get_batch(batch_id)
    source = batch.source
    status, to_delete = await operations.get_doc_status(source, hashes)
    operations.update_doc_status(source, hashes)
    return status


app.include_router(v1_router)
app.include_router(batch_router)
app.include_router(doc_router)
app.include_router(wf_router)
app.include_router(stats_router)

# Serve UI static assets
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    # Mount static assets at /_app
    app.mount("/_app", StaticFiles(directory=static_dir / "_app"), name="static-assets")

    # Catch-all route for SPA - serves index.html for all non-API routes
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """Serve the SPA for all routes not caught by API or static assets."""
        # Serve static files from root if they exist (like favicon.ico)
        file_path = static_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        # Otherwise serve index.html for SPA routing
        return FileResponse(static_dir / "index.html")

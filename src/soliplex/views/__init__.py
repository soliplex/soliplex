import fastapi
from fastapi import responses

from soliplex import util

router = fastapi.APIRouter()


#   'process_control' canary
@util.logfire_span("GET /ok")
@router.get(
    "/ok", response_class=responses.PlainTextResponse, tags=["process"]
)
async def health_check() -> str:
    """Check that the server is up and running.

    Primarily for use within a process composer environment.
    """
    return "OK"


# testing and validation

CHECK_HEADERS_VALUE_TYPE = str | None | dict[str, str]


@util.logfire_span("GET /check-headers")
@router.get("/check-headers", tags=["debug"])
async def check_headers(
    request: fastapi.Request,
) -> dict[str, CHECK_HEADERS_VALUE_TYPE]:  # pragma: NO COVER
    """Dump request headers for debugging"""
    return_to = "https://google.com"
    redirect_uri = request.url_for("health_check")
    redirect_uri = redirect_uri.replace_query_params(return_to=return_to)
    # redirect_uri = redirect_uri.replace(netloc=redirect_uri.netloc + '/api')
    return {
        "X-Forwarded-For": request.headers.get("x-forwarded-for"),
        "X-Forwarded-Proto": request.headers.get("x-forwarded-proto"),
        "X-Forwarded-Host": request.headers.get("x-forwarded-host"),
        "X-Forwarded-Port": request.headers.get("x-forwarded-port"),
        "X-Real-IP": request.headers.get("x-real-ip"),
        "Host": request.headers.get("host"),
        "redirect_uri": str(redirect_uri),
        "headers": request.headers,
    }

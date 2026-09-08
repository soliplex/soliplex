"""Discover a model's context window by asking its provider.

An OpenAI-compatible ``/v1/models`` listing describes each served model
with a card. vLLM puts ``max_model_len`` on that card; the OpenAI API
itself and Ollama's compatibility surface do not. That absence is the
answer, not a failure: it means the provider does not say how large the
window is, and a client must show no percentage rather than invent a
denominator.

Guessing one is the specific failure this avoids. Ollama advertises
gpt-oss at 131072 while the loaded runner serves 32768, and a
denominator four times too large reads as *emptier* than reality --
which is the direction that lets someone walk into a truncated context
believing they had room.
"""

import httpx

from soliplex import loggers

#: Windows keyed by '(base_url, model_name)'.
#:
#: Only *positive* answers are kept. A window that exists does not
#: change under a running deployment, so remembering it saves a request
#: per reading. An absent one is not equally stable: a provider can be
#: unreachable, or reachable but not yet serving the model -- Ollama
#: reports no size for a model it has evicted. Caching that absence
#: would hide the gauge for the life of the process even once the
#: provider started answering, and the only way back would be a
#: restart.
_MAX_MODEL_LEN: dict[tuple[str, str], int] = {}

#: Short by design. This sits in a request the user is waiting on, and a
#: missing window degrades to a hidden gauge rather than an error.
TIMEOUT_SECONDS = 5.0

#: vLLM mounts its tokenizer router at the application root, not under
#: the OpenAI-compatible '/v1' prefix, so the base URL a provider is
#: configured with has to have that suffix removed to reach it.
_OPENAI_SUFFIX = "/v1"


def _find_max_model_len(payload, model_name):
    """Return the window from a '/v1/models' payload, or None.

    Matches the card whose id is 'model_name'. Falls back to the only
    card when the listing has exactly one, because a provider serving a
    single model may name it differently than the configuration does.
    """
    if not isinstance(payload, dict):
        return None

    cards = payload.get("data") or []

    for card in cards:
        if not isinstance(card, dict):
            continue

        if card.get("id") == model_name:
            return card.get("max_model_len")

    if len(cards) == 1 and isinstance(cards[0], dict):
        return cards[0].get("max_model_len")

    return None


async def get_max_model_len(
    *,
    base_url: str,
    model_name: str,
    api_key: str | None = None,
    the_logger: loggers.LogWrapper,
) -> int | None:
    """Return the model's context window, or None when unknown.

    None covers every way this can fail to produce a number -- the
    provider does not report one, does not serve the model, or cannot be
    reached. All of them mean the same thing to a caller: show no
    percentage.
    """
    key = (base_url, model_name)

    if key in _MAX_MODEL_LEN:
        return _MAX_MODEL_LEN[key]

    headers = {}

    if api_key is not None:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.get(
                f"{base_url}/models",
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        # A transport or status failure renders as the host and the
        # reason, both of which are the diagnosis, and neither of which
        # is user-supplied.
        the_logger.warning(
            loggers.CONTEXT_WINDOW_UNAVAILABLE,
            base_url,
            exc,
            base_url=base_url,
            model_name=model_name,
            reason=str(exc),
        )
        return None
    except ValueError:
        # A malformed body's exception carries a window of the body
        # itself, so only its type is safe to record.
        the_logger.warning(
            loggers.CONTEXT_WINDOW_UNREADABLE,
            base_url,
            base_url=base_url,
            model_name=model_name,
        )
        return None

    found = _find_max_model_len(payload, model_name)

    if found is not None:
        _MAX_MODEL_LEN[key] = found

    return found


def _tokenize_url(base_url: str) -> str:
    """Return the tokenizer endpoint for an OpenAI-compatible base URL."""
    root = base_url

    if root.endswith(_OPENAI_SUFFIX):
        root = root[: -len(_OPENAI_SUFFIX)]

    return f"{root.rstrip('/')}/tokenize"


async def count_tokens(
    *,
    base_url: str,
    model_name: str,
    texts: list[str],
    api_key: str | None = None,
    the_logger: loggers.LogWrapper,
) -> list[int] | None:
    """Return a token count per entry in 'texts', or None.

    Uses the completion form of the tokenizer endpoint, which takes a
    bare string, so each piece of a conversation can be counted on its
    own without re-sending the whole transcript. Special tokens are left
    off: these are fragments of a request, not requests, and the
    per-message scaffolding they lack is recovered as a residual against
    what the provider actually measured.

    None when the provider has no tokenizer endpoint -- which is every
    provider but vLLM -- or cannot be reached. A caller must then report
    no breakdown rather than a made-up one.
    """
    if not texts:
        return []

    headers = {}

    if api_key is not None:
        headers["Authorization"] = f"Bearer {api_key}"

    url = _tokenize_url(base_url)
    counts = []

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            for text in texts:
                response = await client.post(
                    url,
                    headers=headers,
                    json={
                        "model": model_name,
                        "prompt": text,
                        "add_special_tokens": False,
                    },
                )
                response.raise_for_status()
                # A body of the wrong shape raises 'TypeError' here,
                # and one missing the field raises 'KeyError'; both are
                # caught below as "could not be read".
                counts.append(response.json()["count"])
    except httpx.HTTPError as exc:
        the_logger.warning(
            loggers.CONTEXT_TOKENIZE_UNAVAILABLE,
            url,
            exc,
            base_url=base_url,
            model_name=model_name,
            reason=str(exc),
        )
        return None
    except (ValueError, KeyError, TypeError):
        # A malformed body's exception quotes the body, so only the fact
        # that it could not be read is safe to record.
        the_logger.warning(
            loggers.CONTEXT_TOKENIZE_UNREADABLE,
            url,
            base_url=base_url,
            model_name=model_name,
        )
        return None

    return counts

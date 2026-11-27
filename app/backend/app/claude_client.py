"""Shared Claude API settings and helpers.

The pinned SDK (anthropic 0.52) predates `fallbacks` and `output_config`, so
they are sent through extra_headers/extra_body.
"""

import logging

import anthropic
import httpx

from app.config import settings

log = logging.getLogger("resume.claude")

MODEL = "claude-opus-5-5"

# On a policy decline, the API re-runs the request on a fallback model it picks.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


# Per-call timeouts (the SDK client itself is shared). Chat replies are short; documents stream long.
CHAT_TIMEOUT = httpx.Timeout(300, connect=10)
DOC_TIMEOUT = httpx.Timeout(900, connect=10)


class ClaudeError(RuntimeError):
    """Base for every failure this module raises. Messages are safe to log, never to show."""


class ClaudeRefusal(ClaudeError):
    """Raised when the model (and its fallback) declined the request."""


class ClaudeUnavailable(ClaudeError):
    """Timeout, connection failure, 429, 5xx or overloaded. Retryable."""


class ClaudeConfigError(ClaudeError):
    """Auth/permission/model-not-found (401/403/404) or another non-retryable 4xx."""


class ClaudeTruncated(ClaudeError):
    """The reply hit max_tokens."""


class ClaudeEmpty(ClaudeError):
    """The reply had no text."""


_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    """The single module-level async client, built lazily (tests patch this)."""
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=2)
    return _client


def _extras(effort: str) -> dict:
    return {
        "extra_headers": {"anthropic-beta": _FALLBACK_BETA},
        "extra_body": {"fallbacks": "default", "output_config": {"effort": effort}},
    }


def _map_error(exc: Exception) -> ClaudeError:
    """SDK exception -> typed error. Logs class name and request id only: never the
    provider's message text, request content or key material."""
    request_id = getattr(exc, "request_id", None)
    name = type(exc).__name__
    if isinstance(exc, (anthropic.APITimeoutError, anthropic.APIConnectionError)):
        log.warning("provider unreachable: %s", name)
        return ClaudeUnavailable("provider unreachable")
    if isinstance(exc, anthropic.APIStatusError):
        status = exc.status_code
        if status == 429 or status >= 500:
            log.warning("provider unavailable: %s status=%s request_id=%s", name, status, request_id)
            return ClaudeUnavailable(f"provider status {status}")
        log.error("provider auth/config error: %s status=%s request_id=%s", name, status, request_id)
        return ClaudeConfigError(f"provider status {status}")
    log.error("unexpected provider failure: %s request_id=%s", name, request_id)
    return ClaudeUnavailable("provider failure")


async def _call(fn):
    """Run one SDK call and translate SDK exceptions. All mapping lives here."""
    try:
        return await fn()
    except ClaudeError:
        raise
    except anthropic.AnthropicError as exc:
        raise _map_error(exc) from None


async def create_message(*, effort: str = "medium", timeout=CHAT_TIMEOUT, **kwargs):
    """messages.create on MODEL with refusal fallbacks and an explicit effort level.

    Thinking is always on for this model and counts toward max_tokens, so callers
    should leave generous headroom.
    """
    client = get_client()
    return await _call(
        lambda: client.messages.create(model=MODEL, timeout=timeout, **_extras(effort), **kwargs)
    )


async def stream_message(*, effort: str = "medium", timeout=DOC_TIMEOUT, **kwargs):
    """Same as create_message but streamed (for long outputs); returns the final message."""
    client = get_client()

    async def run():
        async with client.messages.stream(
            model=MODEL, timeout=timeout, **_extras(effort), **kwargs
        ) as stream:
            return await stream.get_final_message()

    return await _call(run)


def response_text(response) -> str:
    """Join the text blocks of a response.

    content[0] is usually a thinking block on current models, so never index it.
    Raises ClaudeRefusal, ClaudeTruncated (max_tokens) or ClaudeEmpty (no text).
    """
    if response.stop_reason == "refusal":
        raise ClaudeRefusal("Claude declined this request.")
    if response.stop_reason == "max_tokens":
        raise ClaudeTruncated("The reply was cut off at max_tokens.")
    text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    if not text.strip():
        raise ClaudeEmpty("The reply had no text.")
    return text

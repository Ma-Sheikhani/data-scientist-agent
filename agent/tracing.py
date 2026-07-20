import logging
from contextlib import contextmanager
from typing import Any, Dict, Optional

from langfuse import Langfuse

from api.core.config import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Client initialisation
# ------------------------------------------------------------------
_langfuse_client: Optional[Langfuse] = None

if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
    try:
        _langfuse_client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
        _langfuse_client.auth_check()
        logger.info("Langfuse tracing enabled")
    except Exception as e:
        logger.warning("Langfuse init failed: %s", e)
        _langfuse_client = None
else:
    logger.info("Langfuse keys not set – tracing disabled")


# ------------------------------------------------------------------
# Adapter class
# ------------------------------------------------------------------
class _SpanAdapter:
    def __init__(self, span):
        self._span = span
        self._ended = False

    def end(self, output: Any = None, usage: Optional[Dict[str, int]] = None, **kwargs):
        """Update the span with final output/usage and end it."""
        if self._ended:
            return
        self._ended = True
        # Update the span with output and usage before the context manager ends it
        update_kwargs = {}
        if output is not None:
            update_kwargs["output"] = output
        if usage is not None:
            update_kwargs["usage"] = usage
        if update_kwargs:
            self._span.update(**update_kwargs)
        # The span will be ended automatically when the context manager exits


class _DummySpanAdapter:
    def end(self, **kwargs):
        pass


# ------------------------------------------------------------------
# Context manager
# ------------------------------------------------------------------
@contextmanager
def trace_llm_call(
    name: str,
    model: str,
    input_data: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    If Langfuse is enabled, starts a new observation (which becomes a trace
    because it has no parent) and yields an adapter whose .end() updates output/usage.
    Otherwise yields a no‑op adapter.
    """
    if _langfuse_client is None:
        yield _DummySpanAdapter()
        return

    with _langfuse_client.start_as_current_observation(
        name=name,
        input=input_data,
        metadata=metadata,
    ) as span:
        adapter = _SpanAdapter(span)
        yield adapter
        # Span is ended automatically after the with-block

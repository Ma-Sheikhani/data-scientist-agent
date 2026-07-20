import json
import logging
import re  # NEW: for comment stripping
from typing import Optional, Type, TypeVar, overload

from openai import OpenAI
from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from agent.tracing import trace_llm_call
from api.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# fmt: off

@overload
def call_llm(
    system_prompt: str,
    user_prompt: str,
    response_format: Optional[dict] = None,
    *,
    pydantic_model: None = None,
) -> str:
    ...


@overload
def call_llm(
    system_prompt: str,
    user_prompt: str,
    response_format: Optional[dict] = None,
    *,
    pydantic_model: Type[T],
) -> T:
    ...

# fmt: on


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def call_llm(
    system_prompt: str,
    user_prompt: str,
    response_format: Optional[dict] = None,
    pydantic_model: Optional[Type[T]] = None,
) -> "T | str":
    # ---- Backend selection ----
    model = getattr(settings, "active_llm_model", None) or settings.OPENROUTER_MODEL
    api_key = (
        getattr(settings, "active_llm_api_key", None) or settings.OPENROUTER_API_KEY
    )
    base_url = (
        getattr(settings, "active_llm_base_url", None) or settings.OPENROUTER_BASE_URL
    )

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=60.0)

    kwargs: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.0,
    }
    if response_format:
        kwargs["response_format"] = response_format

    with trace_llm_call(
        name="call_llm",
        model=model,
        input_data={
            "system": system_prompt,
            "user": user_prompt,
        },
    ) as generation:
        response = client.chat.completions.create(**kwargs)
        raw: Optional[str] = response.choices[0].message.content
        if raw is None:
            raw = ""

        # --- Strip comments and trailing commas ---
        raw = re.sub(r"//.*", "", raw)
        raw = re.sub(r"/\*.*?\*/", "", raw, flags=re.DOTALL)
        raw = re.sub(r",\s*}", "}", raw)
        raw = re.sub(r",\s*]", "]", raw)
        # -----------------------------------------

        usage = None
        if response.usage:
            usage = {
                "input": response.usage.prompt_tokens,
                "output": response.usage.completion_tokens,
            }

        generation.end(output=raw, usage=usage)

    # ---- Pydantic parsing ----
    if pydantic_model:
        try:
            data = json.loads(raw)
            return pydantic_model(**data)
        except (json.JSONDecodeError, ValidationError):
            if "```json" in raw:
                json_str = raw.split("```json")[1].split("```")[0].strip()
                data = json.loads(json_str)
                return pydantic_model(**data)
            elif "```" in raw:
                json_str = raw.split("```")[1].split("```")[0].strip()
                data = json.loads(json_str)
                return pydantic_model(**data)
            else:
                logger.error("Failed to parse JSON. Raw content: %s", raw[:500])
                raise
    return raw

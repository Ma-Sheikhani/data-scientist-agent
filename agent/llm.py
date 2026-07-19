import json
from typing import Optional, Type, TypeVar, overload

from openai import OpenAI
from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from api.core.config import settings

T = TypeVar("T", bound=BaseModel)


# Overloads: tell mypy exactly what the return type is based on arguments

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
    client = OpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
    )
    kwargs: dict = {
        "model": settings.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.0,
    }
    if response_format:
        kwargs["response_format"] = response_format

    # The OpenAI library's type hints are very strict; ignore the arg-type check here
    response = client.chat.completions.create(**kwargs)
    raw: Optional[str] = response.choices[0].message.content
    if raw is None:
        raw = ""  # never return None

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
                raise
    return raw

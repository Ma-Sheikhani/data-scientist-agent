from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from api.core.config import settings


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def call_llm(
    system_prompt: str,
    user_prompt: str,
    response_format: dict | None = None,
) -> str:
    # Select backend configuration
    if settings.LLM_BACKEND == "openrouter":
        base_url = settings.OPENROUTER_BASE_URL
        api_key = settings.OPENROUTER_API_KEY
        model = settings.OPENROUTER_MODEL
    else:  # default to local
        base_url = settings.LLM_BASE_URL_LOCAL
        api_key = settings.LLM_API_KEY_LOCAL
        model = settings.LLM_MODEL_LOCAL

    client = OpenAI(base_url=base_url, api_key=api_key)

    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.0,
    }
    # response_format only supported by some models; include if needed
    if response_format:
        kwargs["response_format"] = response_format

    response = client.chat.completions.create(**kwargs)  # type: ignore[call-overload]
    return response.choices[0].message.content  # type: ignore[no-any-return]

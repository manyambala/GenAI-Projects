import json

import httpx
from pydantic import BaseModel, ValidationError

from app.config import settings


async def ask_local(prompt, fallback):
    if not settings.ollama_model or settings.ollama_model.startswith("<"):
        return fallback
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=5.0)) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={"model": settings.ollama_model, "prompt": prompt, "stream": False, "format": "json"},
            )
            response.raise_for_status()
            parsed = json.loads(response.json().get("response", "{}"))
            return {**fallback, **parsed} if isinstance(parsed, dict) else fallback
    except (httpx.HTTPError, ValueError, TypeError, json.JSONDecodeError):
        return fallback


async def ask_structured(prompt: str, fallback: dict, schema: type[BaseModel]) -> tuple[dict, bool]:
    """Call Ollama and validate an agent's structured output.

    The deterministic fallback is validated through the same schema. The
    boolean indicates whether the final validated output came from Ollama.
    """

    candidate = await ask_local(prompt, fallback)
    try:
        validated = schema.model_validate(candidate).model_dump()
        return validated, candidate != fallback
    except ValidationError:
        return schema.model_validate(fallback).model_dump(), False

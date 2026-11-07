"""Gemini client (server-side only). Returns None whenever the key is missing or a call fails, so callers fall back to templates."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os

from dotenv import load_dotenv

load_dotenv()

_cache: dict = {}
_sem = {"loop": None, "sem": None}
TIMEOUT_SECONDS = 15
MAX_CONCURRENT = 3


def api_key():
    return os.getenv("GEMINI_API_KEY") or None


def model_name():
    return os.getenv("GEMINI_MODEL", "gemini-flash-latest")


def available() -> bool:
    return bool(api_key())


def _semaphore():
    loop = asyncio.get_running_loop()
    if _sem["loop"] is not loop:
        _sem["loop"], _sem["sem"] = loop, asyncio.Semaphore(MAX_CONCURRENT)
    return _sem["sem"]


def _call(prompt: str, schema, system: str | None):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key())
    resp = client.models.generate_content(
        model=model_name(), contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system, response_mime_type="application/json",
                                           response_schema=schema, temperature=0.2))
    return json.loads(resp.text)


async def generate_json(prompt: str, schema, system: str | None = None):
    """Call Gemini with a JSON schema. Cached by input hash. Returns a dict or None."""
    if not available():
        return None
    key = hashlib.sha256((model_name() + "|" + (system or "") + "|" + prompt).encode()).hexdigest()
    if key in _cache:
        return _cache[key]
    try:
        async with _semaphore():
            result = await asyncio.wait_for(asyncio.to_thread(_call, prompt, schema, system), TIMEOUT_SECONDS)
    except Exception:
        return None
    if isinstance(result, dict):
        _cache[key] = result
        return result
    return None

import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_CHAT_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"
EMBEDDING_MODEL = "nvidia/nemotron-3-embed-1b"
EMBEDDING_DIM = 2048


def _post(path: str, payload: dict, *, timeout: float = 60) -> dict:
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY is not set")

    request = Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"NVIDIA API returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"NVIDIA API connection failed: {exc.reason}") from exc


def complete(messages: list[dict], *, max_tokens: int = 1024, temperature: float = 0.7, timeout: float = 60) -> str:
    model = os.getenv("NVIDIA_CHAT_MODEL") or DEFAULT_CHAT_MODEL
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    if model == DEFAULT_CHAT_MODEL:
        # Keep the output budget for the answer, including short follow-up and JSON calls.
        payload["chat_template_kwargs"] = {"enable_thinking": False}
        payload["reasoning_budget"] = 0
    elif model == "nvidia/nemotron-3-super-120b-a12b":
        payload["reasoning_effort"] = "none"
    response = _post("/chat/completions", payload, timeout=timeout)
    try:
        content = response["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("empty response content")
        return content.strip()
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError("NVIDIA API returned no response text") from exc


def generate_response(system_prompt: str, message: str, history: list[dict] | None = None, max_tokens: int = 1024) -> str:
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend({"role": item["role"], "content": item["content"]} for item in (history or []))
    messages.append({"role": "user", "content": message})
    return complete(messages, max_tokens=max_tokens)


def generate_follow_up_questions(user_message: str, assistant_response: str) -> list[str]:
    prompt = (
        f'The user asked: "{user_message}"\n'
        f"The assistant replied:\n{assistant_response[:800]}\n\n"
        "Generate exactly 3 short follow-up questions the user might want to ask next. "
        "Each question on its own line. No numbering, no bullets, no extra text."
    )
    try:
        response = complete([
            {"role": "system", "content": "Generate follow-up questions."},
            {"role": "user", "content": prompt},
        ], max_tokens=300, timeout=10)
        lines = [line.strip().lstrip("-•*0123456789. ") for line in response.splitlines() if line.strip()]
        return lines[:3]
    except Exception as exc:
        logging.getLogger(__name__).warning("NVIDIA follow-up generation failed: %s", exc)
        return []


def embedding(text: str, input_type: str) -> list[float]:
    response = _post("/embeddings", {
        "model": EMBEDDING_MODEL,
        "input": [text],
        "input_type": input_type,
        "encoding_format": "float",
        "truncate": "END",
    })
    try:
        vector = response["data"][0]["embedding"]
        if len(vector) != EMBEDDING_DIM:
            raise ValueError(f"expected {EMBEDDING_DIM} dimensions, got {len(vector)}")
        return vector
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError(f"NVIDIA API returned an invalid {input_type} embedding") from exc

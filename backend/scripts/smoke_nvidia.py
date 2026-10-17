"""Live check of the NVIDIA setup: model IDs, JSON output, reasoning stripping, embedding dimension.

Run from backend/:  uv run python scripts/smoke_nvidia.py
Exits 0 only when every check passes. Never prints the API key.
"""

import asyncio
import json
import sys

import httpx

from covora.config import Settings, get_settings
from covora.gateway.nvidia import NvidiaBackend
from covora.gateway.output import extract_json, strip_reasoning
from covora.observability.redaction import redact

SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "integer"}},
    "required": ["answer"],
}
QUESTION = [{"role": "user", "content": 'What is 2 + 3? Reply only with JSON like {"answer": <integer>}.'}]
MODES = ["guided_json", "response_format", "none"]


def _safe(settings: Settings, value: str) -> str:
    return redact(value, settings.secret_values())


async def _check_models(settings: Settings) -> bool:
    key = settings.nvidia_api_key.get_secret_value()
    async with httpx.AsyncClient(timeout=30) as http:
        response = await http.get(f"{settings.nvidia_base_url}/models", headers={"Authorization": f"Bearer {key}"})
    response.raise_for_status()
    ids = {m["id"] for m in response.json().get("data", [])}
    wanted = [settings.nemotron_nano_model, settings.nemotron_super_model, settings.nemotron_embed_model]
    missing = [m for m in wanted if m not in ids]
    print("OK models" if not missing else f"FAIL models missing: {', '.join(missing)}")
    return not missing


async def _answer(backend: NvidiaBackend, model: str, reasoning: bool, timeout_s: float) -> tuple[int | None, str]:
    response = await backend.chat(
        model=model, messages=QUESTION, json_schema=SCHEMA, reasoning=reasoning, timeout_s=timeout_s
    )
    return json.loads(extract_json(response.text)).get("answer"), strip_reasoning(response.text)


async def main() -> int:
    settings = get_settings()
    if not settings.nvidia_api_key:
        print("FAIL NVIDIA_API_KEY is not set in .env")
        return 1

    ok = await _check_models(settings)

    working_mode = None
    ordered = [settings.nvidia_structured_mode] + [m for m in MODES if m != settings.nvidia_structured_mode]
    for mode in ordered:
        backend = NvidiaBackend(settings.model_copy(update={"nvidia_structured_mode": mode}))
        try:
            answer, _ = await _answer(backend, settings.nemotron_nano_model, reasoning=False, timeout_s=90)
        except Exception as exc:  # noqa: BLE001 - report and try the next mode
            print(f"  structured mode {mode} failed: {_safe(settings, str(exc))[:300]}")
            continue
        if answer == 5:
            working_mode = mode
            break
        print(f"  structured mode {mode} gave answer {answer!r}")
    if working_mode is None:
        print("FAIL nano-json")
        return 1
    print("OK nano-json")

    backend = NvidiaBackend(settings.model_copy(update={"nvidia_structured_mode": working_mode}))
    try:
        answer, text = await _answer(backend, settings.nemotron_super_model, reasoning=True, timeout_s=240)
        if answer == 5 and "<think>" not in text.lower():
            print("OK super-json")
        else:
            ok = False
            print(f"FAIL super-json (answer={answer!r})")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"FAIL super-json: {_safe(settings, str(exc))[:300]}")

    try:
        vectors = await backend.embed(
            model=settings.nemotron_embed_model, texts=["hello world"], input_type="passage", timeout_s=60
        )
        print(f"OK embed dim={len(vectors[0])}")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"FAIL embed: {_safe(settings, str(exc))[:300]}")

    print(f"OK structured-mode={working_mode}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

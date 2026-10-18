import json
from collections.abc import Callable
from typing import Any

from covora.agents.step import WorkingMemory
from covora.memory.prompts import render_prompt


def json_messages(prompt_body: str, inputs: dict[str, Any], **values: Any) -> Callable[[WorkingMemory], list[dict]]:
    """Build an agent's messages: the rendered prompt as system, the step's inputs as one JSON user message."""

    def build(wm: WorkingMemory) -> list[dict]:
        system = render_prompt(prompt_body, memories=wm.render_memories(), **values)
        user = json.dumps(inputs, ensure_ascii=False, default=str)
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    return build

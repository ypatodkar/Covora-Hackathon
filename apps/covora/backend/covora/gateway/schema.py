"""The JSON schema sent to the model to constrain its output.

Hosted structured decoding doesn't follow `$ref`s and lets the model skip optional
fields, so the schema is made self-contained and every property is required. Fields
that may be empty stay nullable or allow empty lists; Pydantic still validates the reply.
"""

from typing import Any

from pydantic import BaseModel

_MAX_DEPTH = 30


def output_schema(model: type[BaseModel]) -> dict[str, Any]:
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})

    def resolve(node: Any, depth: int) -> Any:
        if depth > _MAX_DEPTH:
            raise ValueError(f"schema for {model.__name__} is too deeply nested")
        if isinstance(node, list):
            return [resolve(item, depth + 1) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            target = resolve(defs[node["$ref"].split("/")[-1]], depth + 1)
            extras = {k: resolve(v, depth + 1) for k, v in node.items() if k != "$ref"}
            return {**target, **extras}
        out = {k: resolve(v, depth + 1) for k, v in node.items()}
        if "properties" in out:
            out["required"] = list(out["properties"])
        return out

    return resolve(raw, 0)

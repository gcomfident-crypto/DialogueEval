from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError


T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(ValueError):
    pass


def parse_json_object(raw_content: str) -> dict[str, Any]:
    text = raw_content.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end < start:
            raise StructuredOutputError("model output is not a JSON object")
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise StructuredOutputError(f"invalid JSON: {exc.msg}") from exc

    if not isinstance(data, dict):
        raise StructuredOutputError("model output top level must be a JSON object")
    return data


def parse_model(raw_content: str, model_type: type[T]) -> T:
    data = parse_json_object(raw_content)
    try:
        return model_type.model_validate(data)
    except ValidationError as exc:
        raise StructuredOutputError(str(exc)) from exc

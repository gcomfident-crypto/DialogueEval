from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_structured_file(path: str | Path) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    if not text.strip():
        return {}

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "PyYAML is required to read non-JSON YAML files. "
                "Install dependencies with `pip install -r requirements.txt`."
            ) from exc
        data = yaml.safe_load(text) or {}

    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping/object at the top level.")
    return data


def write_model(path: str | Path, model: BaseModel) -> None:
    write_structured_file(path, model.model_dump(mode="json"))


def write_structured_file(path: str | Path, data: dict[str, Any] | list[Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    output_path.write_text(text + "\n", encoding="utf-8")


def load_model(path: str | Path, model_type: type[T]) -> T:
    return model_type.model_validate(read_structured_file(path))

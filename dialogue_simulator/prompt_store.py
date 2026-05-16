from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from dialogue_simulator.prompt_registry import DEFAULT_PROMPT_SPECS, PromptSpec


@dataclass
class PromptSyncResult:
    name: str
    version_id: str | None
    status: str
    error: str = ""


_PROMPT_CACHE: dict[tuple[str, str, str], tuple[float, Any]] = {}


def render_prompt_text(spec: PromptSpec, variables: dict[str, Any] | None = None) -> str:
    prompt_variables = _string_variables(variables or {})
    if _use_phoenix_prompts():
        try:
            messages = _render_phoenix_messages(spec, prompt_variables)
            content = _first_message_content(messages, role=spec.role)
            if content:
                return content
        except Exception as exc:
            if _strict_phoenix_prompts():
                raise
            _log_prompt_fallback(spec.name, exc)
    return _render_mustache(spec.content, prompt_variables)


def sync_default_prompts(
    *,
    base_url: str | None = None,
    model_name: str = "deepseek-chat",
    dry_run: bool = False,
) -> list[PromptSyncResult]:
    results: list[PromptSyncResult] = []
    client = None if dry_run else _phoenix_client(base_url=base_url)
    for spec in DEFAULT_PROMPT_SPECS:
        if dry_run:
            results.append(PromptSyncResult(name=spec.name, version_id=None, status="dry_run"))
            continue
        try:
            version = _prompt_version(spec, model_name=model_name)
            created = client.prompts.create(
                version=version,
                name=spec.name,
                prompt_description=spec.description,
                prompt_metadata={
                    "source": "DialogueEval",
                    "managed_by": "dialogue_simulator.prompt_store.sync_default_prompts",
                    "variables": list(spec.variables),
                },
            )
            results.append(
                PromptSyncResult(name=spec.name, version_id=getattr(created, "id", None), status="created")
            )
        except Exception as exc:
            results.append(PromptSyncResult(name=spec.name, version_id=None, status="error", error=str(exc)))
    _PROMPT_CACHE.clear()
    return results


def prompt_status() -> dict[str, Any]:
    return {
        "provider": os.getenv("DIALOGUE_EVAL_PROMPTS_PROVIDER", ""),
        "enabled": _use_phoenix_prompts(),
        "strict": _strict_phoenix_prompts(),
        "phoenix_base_url": _phoenix_base_url(),
        "tag": os.getenv("DIALOGUE_EVAL_PROMPT_TAG", ""),
        "cache_seconds": _cache_seconds(),
        "prompt_count": len(DEFAULT_PROMPT_SPECS),
        "prompts": [
            {
                "name": spec.name,
                "role": spec.role,
                "description": spec.description,
                "variables": list(spec.variables),
            }
            for spec in DEFAULT_PROMPT_SPECS
        ],
    }


def _render_phoenix_messages(spec: PromptSpec, variables: dict[str, str]) -> list[dict[str, str]]:
    version = _get_prompt_version(spec.name)
    formatted = version.format(variables=variables, sdk="openai")
    messages = getattr(formatted, "messages", None)
    if not isinstance(messages, list):
        raise ValueError(f"Phoenix prompt {spec.name} did not return OpenAI messages.")
    return messages


def _get_prompt_version(name: str):
    base_url = _phoenix_base_url()
    tag = os.getenv("DIALOGUE_EVAL_PROMPT_TAG", "")
    key = (base_url, tag, name)
    now = time.monotonic()
    cached = _PROMPT_CACHE.get(key)
    if cached and cached[0] > now:
        return cached[1]

    client = _phoenix_client(base_url=base_url)
    version = (
        client.prompts.get(prompt_identifier=name, tag=tag)
        if tag
        else client.prompts.get(prompt_identifier=name)
    )
    _PROMPT_CACHE[key] = (now + _cache_seconds(), version)
    return version


def _phoenix_client(*, base_url: str | None = None):
    try:
        from phoenix.client import Client
    except Exception as exc:
        raise RuntimeError(
            "arize-phoenix-client is required for Phoenix prompt management. "
            "Install it with `pip install arize-phoenix-client`."
        ) from exc
    return Client(base_url=base_url or _phoenix_base_url())


def _prompt_version(spec: PromptSpec, *, model_name: str):
    from phoenix.client.types import PromptVersion

    return PromptVersion.from_openai(
        {
            "model": model_name,
            "messages": [{"role": spec.role, "content": spec.content}],
        },
        model_provider="DEEPSEEK",
        template_format="MUSTACHE",
        description=spec.description,
    )


def _first_message_content(messages: list[dict[str, Any]], *, role: str) -> str:
    for message in messages:
        if message.get("role") == role and isinstance(message.get("content"), str):
            return str(message["content"])
    for message in messages:
        if isinstance(message.get("content"), str):
            return str(message["content"])
    return ""


def _render_mustache(template: str, variables: dict[str, str]) -> str:
    rendered = template
    for key, value in variables.items():
        rendered = rendered.replace("{{ " + key + " }}", value)
        rendered = rendered.replace("{{" + key + "}}", value)
    return rendered


def _string_variables(variables: dict[str, Any]) -> dict[str, str]:
    return {key: str(value) for key, value in variables.items()}


def _use_phoenix_prompts() -> bool:
    provider = os.getenv("DIALOGUE_EVAL_PROMPTS_PROVIDER", "").strip().lower()
    if provider:
        return provider == "phoenix"
    return _truthy(os.getenv("DIALOGUE_EVAL_USE_PHOENIX_PROMPTS"))


def _strict_phoenix_prompts() -> bool:
    return _truthy(os.getenv("DIALOGUE_EVAL_PROMPTS_STRICT"))


def _phoenix_base_url() -> str:
    return os.getenv("PHOENIX_BASE_URL", "http://127.0.0.1:6006").rstrip("/")


def _cache_seconds() -> int:
    value = os.getenv("DIALOGUE_EVAL_PROMPT_CACHE_SECONDS", "30")
    try:
        return max(0, int(value))
    except ValueError:
        return 30


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _log_prompt_fallback(name: str, exc: Exception) -> None:
    if not _truthy(os.getenv("DIALOGUE_EVAL_PROMPT_FALLBACK_LOG", "true")):
        return
    print(f"[prompts] fallback to local prompt {name}: {exc}")

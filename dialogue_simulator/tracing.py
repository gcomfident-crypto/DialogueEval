from __future__ import annotations

import json
import os
import sys
from contextlib import ExitStack, contextmanager
from typing import Any, Iterator


_TRACER_PROVIDER: Any | None = None
_TRACER: Any | None = None
_CONFIGURED = False
_SETUP_ERROR = ""


def setup_tracing(service_name: str = "dialogue-eval") -> None:
    global _TRACER_PROVIDER, _TRACER, _CONFIGURED, _SETUP_ERROR

    if _CONFIGURED:
        return
    _CONFIGURED = True

    if not is_tracing_enabled():
        return

    try:
        from phoenix.otel import register
    except Exception as exc:
        _SETUP_ERROR = f"phoenix.otel is unavailable: {exc}"
        print(f"[tracing] {_SETUP_ERROR}", file=sys.stderr)
        return

    endpoint = _normalize_http_endpoint(
        os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces")
    )
    project_name = os.getenv("PHOENIX_PROJECT_NAME", "dialogue-eval")
    auto_instrument = _truthy(os.getenv("PHOENIX_AUTO_INSTRUMENT", "false"))

    try:
        _TRACER_PROVIDER = register(
            project_name=project_name,
            endpoint=endpoint,
            protocol="http/protobuf",
            batch=False,
            auto_instrument=auto_instrument,
        )
        _TRACER = _TRACER_PROVIDER.get_tracer(service_name)
    except Exception as exc:
        _SETUP_ERROR = str(exc)
        print(f"[tracing] failed to configure Phoenix tracing: {exc}", file=sys.stderr)


def shutdown_tracing() -> None:
    provider = _TRACER_PROVIDER
    if provider is None:
        return
    try:
        provider.shutdown()
    except Exception as exc:
        print(f"[tracing] failed to shutdown tracer provider: {exc}", file=sys.stderr)


def tracing_status() -> dict[str, Any]:
    return {
        "enabled": is_tracing_enabled(),
        "configured": _TRACER is not None,
        "project_name": os.getenv("PHOENIX_PROJECT_NAME", "dialogue-eval"),
        "collector_endpoint": os.getenv("PHOENIX_COLLECTOR_ENDPOINT", ""),
        "setup_error": _SETUP_ERROR,
    }


@contextmanager
def trace_span(
    name: str,
    *,
    kind: str = "chain",
    attributes: dict[str, Any] | None = None,
    input_data: Any | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> Iterator["SpanHandle"]:
    setup_tracing()
    if _TRACER is None:
        yield SpanHandle(None)
        return

    with ExitStack() as stack:
        _enter_context_helpers(
            stack,
            session_id=session_id,
            metadata=metadata,
            tags=tags,
        )
        span = stack.enter_context(_start_current_span(name, kind))
        handle = SpanHandle(span)
        handle.set_attributes(attributes or {})
        if input_data is not None:
            handle.set_input(input_data)
        try:
            yield handle
            handle.set_ok()
        except Exception as exc:
            handle.record_exception(exc)
            raise


class SpanHandle:
    def __init__(self, span: Any | None) -> None:
        self._span = span

    def set_input(self, value: Any) -> None:
        if self._span is None:
            return
        payload = _prepare_io(value)
        try:
            self._span.set_input(payload)
        except Exception:
            self.set_attribute("input.value", payload)

    def set_output(self, value: Any) -> None:
        if self._span is None:
            return
        payload = _prepare_io(value)
        try:
            self._span.set_output(payload)
        except Exception:
            self.set_attribute("output.value", payload)

    def set_attribute(self, key: str, value: Any) -> None:
        if self._span is None or value is None:
            return
        try:
            self._span.set_attribute(key, _attribute_value(value))
        except Exception:
            return

    def set_attributes(self, attributes: dict[str, Any]) -> None:
        for key, value in attributes.items():
            self.set_attribute(key, value)

    def record_exception(self, exc: Exception) -> None:
        if self._span is None:
            return
        try:
            self._span.record_exception(exc)
        except Exception:
            pass
        self.set_attribute("error", str(exc))
        try:
            from opentelemetry.trace import Status, StatusCode

            self._span.set_status(Status(StatusCode.ERROR, str(exc)))
        except Exception:
            pass

    def set_ok(self) -> None:
        if self._span is None:
            return
        try:
            from opentelemetry.trace import Status, StatusCode

            self._span.set_status(Status(StatusCode.OK))
        except Exception:
            pass


def is_tracing_enabled() -> bool:
    explicit = os.getenv("DIALOGUE_EVAL_TRACING_ENABLED") or os.getenv("PHOENIX_ENABLED")
    if explicit is not None:
        return _truthy(explicit)
    return bool(os.getenv("PHOENIX_COLLECTOR_ENDPOINT"))


def _start_current_span(name: str, kind: str):
    try:
        return _TRACER.start_as_current_span(name, openinference_span_kind=kind)
    except TypeError:
        return _TRACER.start_as_current_span(name)


def _enter_context_helpers(
    stack: ExitStack,
    *,
    session_id: str | None,
    metadata: dict[str, Any] | None,
    tags: list[str] | None,
) -> None:
    try:
        from phoenix.otel import using_metadata, using_session, using_tags
    except Exception:
        return
    if session_id:
        _enter_helper(stack, using_session, session_id)
    if metadata:
        _enter_helper(stack, using_metadata, metadata)
    if tags:
        _enter_helper(stack, using_tags, tags)


def _enter_helper(stack: ExitStack, helper: Any, value: Any) -> None:
    try:
        stack.enter_context(helper(value))
    except TypeError:
        try:
            stack.enter_context(helper(session_id=value))
        except TypeError:
            return


def _normalize_http_endpoint(endpoint: str) -> str:
    value = endpoint.strip()
    if not value:
        return "http://localhost:6006/v1/traces"
    if value.endswith("/v1/traces"):
        return value
    if value.endswith("/"):
        value = value.rstrip("/")
    return f"{value}/v1/traces"


def _prepare_io(value: Any) -> Any:
    if not _capture_content():
        return "<content capture disabled>"
    return _truncate_jsonable(_jsonable(value), _max_chars())


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _truncate_jsonable(value: Any, max_chars: int) -> Any:
    if isinstance(value, str):
        if len(value) <= max_chars:
            return value
        return value[:max_chars] + f"...<truncated {len(value) - max_chars} chars>"
    if isinstance(value, list):
        return [_truncate_jsonable(item, max_chars) for item in value]
    if isinstance(value, dict):
        return {key: _truncate_jsonable(item, max_chars) for key, item in value.items()}
    return value


def _attribute_value(value: Any) -> str | int | float | bool | list[str] | list[int] | list[float] | list[bool]:
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    if isinstance(value, list) and all(isinstance(item, int) for item in value):
        return value
    if isinstance(value, list) and all(isinstance(item, float) for item in value):
        return value
    if isinstance(value, list) and all(isinstance(item, bool) for item in value):
        return value
    return _json_dumps(_jsonable(value))


def _json_dumps(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        return str(value)


def _capture_content() -> bool:
    return _truthy(os.getenv("DIALOGUE_EVAL_TRACE_CONTENT", "true"))


def _max_chars() -> int:
    value = os.getenv("DIALOGUE_EVAL_TRACE_MAX_CHARS", "20000")
    try:
        return max(1000, int(value))
    except ValueError:
        return 20000


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}

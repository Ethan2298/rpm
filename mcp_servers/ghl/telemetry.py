from __future__ import annotations

import functools
import inspect
import json
import logging
import os
import time
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

import httpx
from mcp.server.fastmcp import FastMCP

LOGGER = logging.getLogger(__name__)

DEFAULT_EVENTS_TABLE = "mcp_events"
DEFAULT_INTEGRATION_CATEGORY = "GHL"
SENSITIVE_KEYWORDS = (
    "body",
    "content",
    "message",
    "notes",
    "subject",
    "email",
    "phone",
    "token",
    "secret",
    "password",
    "attachment",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso_z(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "t", "1", "yes", "y"}:
            return True
        if normalized in {"false", "f", "0", "no", "n"}:
            return False
    return bool(value)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(keyword in lowered for keyword in SENSITIVE_KEYWORDS)


def summarize_value(value: Any, *, key: str | None = None) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value

    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return ""
        if key and _is_sensitive_key(key):
            return {"redacted": True, "length": len(trimmed)}
        if len(trimmed) <= 96:
            return trimmed
        return {"preview": trimmed[:96], "length": len(trimmed)}

    if isinstance(value, dict):
        return {str(k): summarize_value(v, key=str(k)) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        items = list(value)
        return {
            "count": len(items),
            "items": [summarize_value(item) for item in items[:5]],
        }

    return str(value)


def summarize_invocation(tool_name: str, args: tuple[Any, ...], kwargs: dict[str, Any], signature: inspect.Signature | None = None) -> dict[str, Any]:
    if signature is not None:
        try:
            bound = signature.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            payload = {
                name: summarize_value(value, key=name)
                for name, value in bound.arguments.items()
            }
            return {
                "tool": tool_name,
                "arguments": payload,
            }
        except TypeError:
            pass

    fallback = {
        "args": [summarize_value(arg) for arg in args],
        "kwargs": {name: summarize_value(value, key=name) for name, value in kwargs.items()},
    }
    return {
        "tool": tool_name,
        "arguments": fallback,
    }


@dataclass(slots=True)
class MCPEvent:
    request_id: str
    timestamp: datetime
    actor: str
    session_id: str | None
    tool_name: str
    duration_ms: int
    success: bool
    error_code: str | None
    scope_required: str | None
    upstream_status: int | None
    payload_summary: dict[str, Any]
    integration_category: str = DEFAULT_INTEGRATION_CATEGORY

    def to_row(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "occurred_at": _to_iso_z(self.timestamp),
            "actor": self.actor,
            "session_id": self.session_id,
            "integration_category": self.integration_category,
            "tool_name": self.tool_name,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error_code": self.error_code,
            "scope_required": self.scope_required,
            "upstream_status": self.upstream_status,
            "payload_summary": self.payload_summary,
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "MCPEvent":
        occurred_at = row.get("occurred_at") or row.get("timestamp") or _to_iso_z(_utc_now())
        timestamp = _parse_iso_z(str(occurred_at))
        payload_summary = row.get("payload_summary") or {}
        if isinstance(payload_summary, str):
            try:
                payload_summary = json.loads(payload_summary)
            except json.JSONDecodeError:
                payload_summary = {"raw": payload_summary}
        return cls(
            request_id=str(row.get("request_id") or ""),
            timestamp=timestamp,
            actor=str(row.get("actor") or "unknown"),
            session_id=row.get("session_id"),
            integration_category=str(row.get("integration_category") or DEFAULT_INTEGRATION_CATEGORY),
            tool_name=str(row.get("tool_name") or ""),
            duration_ms=int(row.get("duration_ms") or 0),
            success=_coerce_bool(row.get("success")),
            error_code=row.get("error_code"),
            scope_required=row.get("scope_required"),
            upstream_status=_coerce_int(row.get("upstream_status")),
            payload_summary=payload_summary if isinstance(payload_summary, dict) else {},
        )


@dataclass(slots=True)
class MCPEventQuery:
    since: datetime | None = None
    until: datetime | None = None
    actor: str | None = None
    integration_category: str | None = None
    tool_name: str | None = None
    success: bool | None = None
    limit: int = 200


class MCPEventStore(Protocol):
    async def write_event(self, event: MCPEvent) -> None:
        ...

    async def fetch_events(self, query: MCPEventQuery | None = None) -> list[MCPEvent]:
        ...

    async def healthcheck(self) -> bool:
        ...


class NoopEventStore:
    enabled = False

    async def write_event(self, event: MCPEvent) -> None:
        return None

    async def fetch_events(self, query: MCPEventQuery | None = None) -> list[MCPEvent]:
        return []

    async def healthcheck(self) -> bool:
        return False


class MemoryEventStore:
    enabled = True

    def __init__(self) -> None:
        self.events: list[MCPEvent] = []

    async def write_event(self, event: MCPEvent) -> None:
        self.events.append(event)

    async def fetch_events(self, query: MCPEventQuery | None = None) -> list[MCPEvent]:
        query = query or MCPEventQuery()
        events = list(self.events)
        if query.since is not None:
            events = [event for event in events if event.timestamp >= query.since]
        if query.until is not None:
            events = [event for event in events if event.timestamp <= query.until]
        if query.actor:
            events = [event for event in events if event.actor == query.actor]
        if query.integration_category:
            events = [event for event in events if event.integration_category == query.integration_category]
        if query.tool_name:
            events = [event for event in events if event.tool_name == query.tool_name]
        if query.success is not None:
            events = [event for event in events if event.success == query.success]
        events.sort(key=lambda event: event.timestamp, reverse=True)
        return events[: query.limit]

    async def healthcheck(self) -> bool:
        return True


class SupabaseEventStore:
    enabled = True

    def __init__(self, url: str, service_role_key: str, *, table: str = DEFAULT_EVENTS_TABLE) -> None:
        self.url = url.rstrip("/")
        self.service_role_key = service_role_key.strip()
        self.table = table.strip() or DEFAULT_EVENTS_TABLE

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.service_role_key}",
            "apikey": self.service_role_key,
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }

    async def write_event(self, event: MCPEvent) -> None:
        async with httpx.AsyncClient(base_url=self.url, headers=self._headers(), timeout=15.0) as client:
            response = await client.post(f"/rest/v1/{self.table}", json=[event.to_row()])
            response.raise_for_status()

    async def fetch_events(self, query: MCPEventQuery | None = None) -> list[MCPEvent]:
        query = query or MCPEventQuery()
        params: list[tuple[str, str]] = [("select", "*"), ("order", "occurred_at.desc"), ("limit", str(query.limit))]

        if query.since is not None:
            params.append(("occurred_at", f"gte.{_to_iso_z(query.since)}"))
        if query.until is not None:
            params.append(("occurred_at", f"lte.{_to_iso_z(query.until)}"))
        if query.actor:
            params.append(("actor", f"eq.{query.actor}"))
        if query.integration_category:
            params.append(("integration_category", f"eq.{query.integration_category}"))
        if query.tool_name:
            params.append(("tool_name", f"eq.{query.tool_name}"))
        if query.success is not None:
            params.append(("success", f"eq.{str(query.success).lower()}"))

        async with httpx.AsyncClient(base_url=self.url, headers=self._headers(), timeout=15.0) as client:
            response = await client.get(f"/rest/v1/{self.table}", params=params)
            response.raise_for_status()
            rows = response.json()
            return [MCPEvent.from_row(row) for row in rows]

    async def healthcheck(self) -> bool:
        await self.fetch_events(MCPEventQuery(limit=1))
        return True


def create_event_store_from_env() -> MCPEventStore:
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    table = os.getenv("MCP_EVENTS_TABLE", DEFAULT_EVENTS_TABLE).strip() or DEFAULT_EVENTS_TABLE
    if not supabase_url or not service_role_key:
        return NoopEventStore()
    return SupabaseEventStore(supabase_url, service_role_key, table=table)


def resolve_actor() -> str:
    for env_name in ("MCP_ACTOR_ID", "MCP_CLIENT_NAME", "MCP_USER_ID", "USER"):
        value = os.getenv(env_name, "").strip()
        if value:
            return value
    return "unknown"


def resolve_session_id() -> str | None:
    for env_name in ("MCP_SESSION_ID", "MCP_CLIENT_SESSION_ID"):
        value = os.getenv(env_name, "").strip()
        if value:
            return value
    return None


def resolve_integration_category() -> str:
    for env_name in ("MCP_INTEGRATION_CATEGORY", "MCP_CATEGORY", "MCP_TOOL_CATEGORY"):
        value = os.getenv(env_name, "").strip()
        if value:
            return value
    return DEFAULT_INTEGRATION_CATEGORY


def classify_result(result: Any) -> tuple[bool, int | None, str | None, str | None]:
    parsed: dict[str, Any] | None = None
    if isinstance(result, str):
        try:
            candidate = json.loads(result)
        except json.JSONDecodeError:
            return True, None, None, None
        if isinstance(candidate, dict):
            parsed = candidate
    elif isinstance(result, dict):
        parsed = result

    if not parsed or "success" not in parsed:
        return True, None, None, None

    if parsed.get("success"):
        return True, None, None, None

    error = parsed.get("error", {})
    if not isinstance(error, dict):
        error = {}
    upstream_status = _coerce_int(error.get("status_code"))
    scope_required = error.get("required_scope")
    field = error.get("field")
    if upstream_status == 400 and field:
        error_code = f"validation:{field}"
    elif upstream_status is not None:
        error_code = f"http:{upstream_status}"
    else:
        error_code = "tool_error"
    return False, upstream_status, scope_required if isinstance(scope_required, str) else None, error_code


class InstrumentedFastMCP:
    def __init__(self, app: FastMCP, *, event_store: MCPEventStore | None = None) -> None:
        self._app = app
        self.event_store: MCPEventStore = event_store or create_event_store_from_env()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._app, name)

    def tool(self, *decorator_args: Any, **decorator_kwargs: Any):
        register = self._app.tool(*decorator_args, **decorator_kwargs)

        def decorator(fn):
            tool_name = decorator_kwargs.get("name") or fn.__name__
            signature = inspect.signature(fn)

            @functools.wraps(fn)
            async def wrapped(*args: Any, **kwargs: Any):
                request_id = uuid4().hex
                timestamp = _utc_now()
                started = time.perf_counter()
                success = True
                upstream_status: int | None = None
                scope_required: str | None = None
                error_code: str | None = None
                result: Any = None
                caught_exception: Exception | None = None

                try:
                    result = fn(*args, **kwargs)
                    if isinstance(result, Awaitable):
                        result = await result
                    success, upstream_status, scope_required, error_code = classify_result(result)
                    return result
                except Exception as exc:  # pragma: no cover - the tests assert behavior around this path
                    caught_exception = exc
                    success = False
                    upstream_status = _coerce_int(getattr(exc, "status_code", None))
                    if upstream_status is not None:
                        error_code = f"http:{upstream_status}"
                    else:
                        error_code = exc.__class__.__name__
                    raise
                finally:
                    duration_ms = max(0, int((time.perf_counter() - started) * 1000))
                    payload_summary = summarize_invocation(tool_name, args, kwargs, signature)
                    event = MCPEvent(
                        request_id=request_id,
                        timestamp=timestamp,
                        actor=resolve_actor(),
                        session_id=resolve_session_id(),
                        integration_category=resolve_integration_category(),
                        tool_name=tool_name,
                        duration_ms=duration_ms,
                        success=success,
                        error_code=error_code,
                        scope_required=scope_required,
                        upstream_status=upstream_status,
                        payload_summary=payload_summary,
                    )
                    try:
                        await self.event_store.write_event(event)
                    except Exception as logging_error:  # pragma: no cover - logging must not affect tool execution
                        LOGGER.warning(
                            "failed to persist MCP event",
                            extra={
                                "tool_name": tool_name,
                                "request_id": request_id,
                                "error": str(logging_error),
                                "caught_exception": caught_exception.__class__.__name__ if caught_exception else None,
                            },
                        )

            return register(wrapped)

        return decorator


def create_instrumented_mcp(name: str, *, instructions: str, event_store: MCPEventStore | None = None) -> InstrumentedFastMCP:
    return InstrumentedFastMCP(FastMCP(name, instructions=instructions), event_store=event_store)

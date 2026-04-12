import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from diagnostics.telemetry import MCPEvent, MCPEventQuery, MemoryEventStore, SupabaseEventStore, create_instrumented_mcp, summarize_value


def test_summarize_value_redacts_sensitive_fields():
    payload = summarize_value(
        {
            "body": "secret text",
            "email": "ethan@example.com",
            "phone": "+15551234567",
            "notes": "Bring cash and title",
            "title": "Follow up",
            "nested": {"message": "Call me later", "safe": "ok"},
        }
    )

    assert payload["body"]["redacted"] is True
    assert payload["email"]["redacted"] is True
    assert payload["phone"]["redacted"] is True
    assert payload["notes"]["redacted"] is True
    assert payload["title"] == "Follow up"
    assert payload["nested"]["message"]["redacted"] is True
    assert payload["nested"]["safe"] == "ok"


def test_instrumented_tool_records_success_event():
    store = MemoryEventStore()
    app = create_instrumented_mcp("Test", instructions="Test instructions", event_store=store)

    @app.tool()
    async def sample_tool(body: str, contact_id: str) -> str:
        return json.dumps({"success": True, "data": {"ok": True}})

    result = asyncio.run(sample_tool(body="secret payload", contact_id="contact-1"))

    assert json.loads(result)["success"] is True
    assert len(store.events) == 1
    event = store.events[0]
    assert event.tool_name == "sample_tool"
    assert event.success is True
    assert event.integration_category == "GHL"
    assert event.payload_summary["arguments"]["body"]["redacted"] is True
    assert event.payload_summary["arguments"]["contact_id"] == "contact-1"


def test_instrumented_tool_records_json_failure_event():
    store = MemoryEventStore()
    app = create_instrumented_mcp("Test", instructions="Test instructions", event_store=store)

    @app.tool()
    async def sample_tool(contact_id: str) -> str:
        return json.dumps(
            {
                "success": False,
                "error": {
                    "status_code": 400,
                    "message": "bad request",
                    "field": "contact_id",
                },
            }
        )

    result = asyncio.run(sample_tool(contact_id="contact-1"))

    assert json.loads(result)["success"] is False
    assert len(store.events) == 1
    event = store.events[0]
    assert event.success is False
    assert event.upstream_status == 400
    assert event.error_code == "validation:contact_id"
    assert event.integration_category == "GHL"


def test_instrumented_tool_records_exception_failure_event():
    store = MemoryEventStore()
    app = create_instrumented_mcp("Test", instructions="Test instructions", event_store=store)

    @app.tool()
    async def sample_tool() -> str:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        asyncio.run(sample_tool())

    assert len(store.events) == 1
    event = store.events[0]
    assert event.success is False
    assert event.error_code == "RuntimeError"
    assert event.upstream_status is None
    assert event.integration_category == "GHL"


def test_instrumented_tool_uses_custom_integration_category(monkeypatch):
    monkeypatch.setenv("MCP_INTEGRATION_CATEGORY", "Payments")
    store = MemoryEventStore()
    app = create_instrumented_mcp("Test", instructions="Test instructions", event_store=store)

    @app.tool()
    async def sample_tool() -> str:
        return json.dumps({"success": True, "data": {"ok": True}})

    asyncio.run(sample_tool())

    assert len(store.events) == 1
    assert store.events[0].integration_category == "Payments"


def test_instrumented_tool_logs_integration_category(caplog):
    store = MemoryEventStore()
    app = create_instrumented_mcp("Test", instructions="Test instructions", event_store=store)

    @app.tool()
    async def sample_tool() -> str:
        return json.dumps({"success": True, "data": {"ok": True}})

    with caplog.at_level(logging.INFO):
        asyncio.run(sample_tool())

    messages = [record for record in caplog.records if record.message.startswith("mcp tool invocation")]
    assert messages
    assert "integration=GHL" in messages[0].message


def test_memory_event_store_filters_by_request_id_and_integration():
    store = MemoryEventStore()
    first = MCPEvent(
        request_id="req-1",
        timestamp=datetime.now(timezone.utc),
        actor="ethan",
        session_id="session-1",
        integration_category="GHL",
        tool_name="search_contacts",
        duration_ms=50,
        success=True,
        error_code=None,
        scope_required=None,
        upstream_status=None,
        payload_summary={"tool": "search_contacts", "arguments": {}},
    )
    second = MCPEvent(
        request_id="req-2",
        timestamp=datetime.now(timezone.utc),
        actor="agent-1",
        session_id="session-2",
        integration_category="Payments",
        tool_name="capture_payment",
        duration_ms=75,
        success=True,
        error_code=None,
        scope_required=None,
        upstream_status=None,
        payload_summary={"tool": "capture_payment", "arguments": {}},
    )

    asyncio.run(store.write_event(first))
    asyncio.run(store.write_event(second))

    events = asyncio.run(
        store.fetch_events(MCPEventQuery(request_id="req-2", integration_category="Payments", limit=10))
    )

    assert len(events) == 1
    assert events[0].request_id == "req-2"
    assert events[0].integration_category == "Payments"


def test_supabase_event_store_includes_request_id_and_integration_filters(monkeypatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return []

    class FakeAsyncClient:
        def __init__(self, *, base_url, headers, timeout):
            captured["base_url"] = base_url
            captured["headers"] = headers
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, path, params=None):
            captured["path"] = path
            captured["params"] = params
            return FakeResponse()

    monkeypatch.setattr("diagnostics.telemetry.httpx.AsyncClient", FakeAsyncClient)

    store = SupabaseEventStore("https://example.supabase.co", "service-role", table="mcp_events")
    asyncio.run(
        store.fetch_events(
            MCPEventQuery(request_id="req-123", integration_category="GHL", limit=5)
        )
    )

    assert captured["path"] == "/rest/v1/mcp_events"
    params = captured["params"]
    assert ("request_id", "eq.req-123") in params
    assert ("integration_category", "eq.GHL") in params
    assert ("limit", "5") in params

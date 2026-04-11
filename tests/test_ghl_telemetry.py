import asyncio
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_servers.ghl.telemetry import MemoryEventStore, create_instrumented_mcp, summarize_value


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

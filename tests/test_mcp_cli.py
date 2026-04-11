import asyncio
from argparse import Namespace
from datetime import datetime, timezone
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_servers.ghl.cli import (
    build_failures_report,
    build_latency_report,
    build_status_report,
    build_usage_report,
    format_failures_report,
    format_latency_report,
    format_status_report,
    format_usage_report,
    run_command,
)
from mcp_servers.ghl.telemetry import MCPEvent, MemoryEventStore


def make_event(
    tool_name: str,
    *,
    actor: str = "ethan",
    integration_category: str = "GHL",
    success: bool = True,
    duration_ms: int = 100,
    timestamp: datetime | None = None,
    error_code: str | None = None,
    upstream_status: int | None = None,
    scope_required: str | None = None,
) -> MCPEvent:
    return MCPEvent(
        request_id=f"req-{tool_name}-{duration_ms}-{success}",
        timestamp=timestamp or datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc),
        actor=actor,
        session_id="session-1",
        integration_category=integration_category,
        tool_name=tool_name,
        duration_ms=duration_ms,
        success=success,
        error_code=error_code,
        scope_required=scope_required,
        upstream_status=upstream_status,
        payload_summary={"tool": tool_name, "arguments": {}},
    )


def test_status_report_uses_event_store_data():
    events = [
        make_event("search_contacts", duration_ms=80),
        make_event("send_message", success=False, duration_ms=220, error_code="http:403", upstream_status=403),
        make_event("search_contacts", duration_ms=120, actor="agent-1", integration_category="Payments"),
    ]

    report = build_status_report(events, store_configured=True, window_days=7)

    assert report["event_count"] == 3
    assert report["failure_count"] == 1
    assert report["top_tool"] == ("search_contacts", 2)
    assert report["top_actor"] == ("ethan", 2)
    assert report["top_integration"] == ("GHL", 2)
    assert "configured" in format_status_report(report)
    assert "top integration: GHL" in format_status_report(report)


def test_failure_report_formats_recent_failures():
    events = [
        make_event("search_contacts", duration_ms=80),
        make_event(
            "send_message",
            success=False,
            duration_ms=220,
            error_code="http:403",
            upstream_status=403,
            scope_required="conversations/message.write",
        ),
    ]

    report = build_failures_report(events, limit=10)

    assert report["failure_count"] == 1
    assert "http:403" in format_failures_report(report)
    assert "integration=GHL" in format_failures_report(report)


def test_latency_report_computes_tool_stats():
    events = [
        make_event("search_contacts", duration_ms=80),
        make_event("search_contacts", duration_ms=120),
        make_event(
            "send_message",
            success=False,
            duration_ms=220,
            error_code="http:403",
            upstream_status=403,
            integration_category="Payments",
        ),
    ]

    report = build_latency_report(events)

    assert report["event_count"] == 3
    assert report["tool_stats"]["search_contacts"]["count"] == 2
    assert report["tool_stats"]["search_contacts"]["p95_ms"] == 120
    assert report["integration_stats"]["GHL"]["count"] == 2
    assert "MCP latency" in format_latency_report(report)
    assert "integration" in format_latency_report(report)


def test_usage_report_counts_tools_and_actors():
    events = [
        make_event("search_contacts", actor="ethan"),
        make_event("search_contacts", actor="agent-1"),
        make_event(
            "send_message",
            actor="agent-1",
            success=False,
            error_code="http:403",
            upstream_status=403,
            integration_category="Payments",
        ),
    ]

    report = build_usage_report(events)

    assert report["event_count"] == 3
    assert report["tool_counts"]["search_contacts"] == 2
    assert report["actor_counts"]["agent-1"] == 2
    assert report["integration_counts"]["GHL"] == 2
    assert "MCP usage" in format_usage_report(report)
    assert "top integrations" in format_usage_report(report)


def test_cli_commands_read_from_store():
    store = MemoryEventStore()
    events = [
        make_event("search_contacts", duration_ms=80),
        make_event(
            "send_message",
            success=False,
            duration_ms=220,
            error_code="http:403",
            upstream_status=403,
            scope_required="conversations/message.write",
        ),
        make_event("search_contacts", actor="agent-1", duration_ms=120),
    ]

    async def seed_events():
        for event in events:
            await store.write_event(event)

    asyncio.run(seed_events())

    base_args = {"days": 7, "limit": 1000, "actor": None, "tool": None}

    status_output = asyncio.run(run_command(Namespace(command="status", **base_args), store=store))
    failures_output = asyncio.run(
        run_command(Namespace(command="failures", recent_limit=10, **base_args), store=store)
    )
    latency_output = asyncio.run(run_command(Namespace(command="latency", **base_args), store=store))
    usage_output = asyncio.run(run_command(Namespace(command="usage", **base_args), store=store))

    assert "events: 3" in status_output
    assert "failures: 1" in status_output
    assert "total failures: 1" in failures_output
    assert "MCP latency" in latency_output
    assert "MCP usage" in usage_output

import asyncio
from argparse import Namespace
from datetime import datetime, timezone
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from diagnostics import cli as cli_module
from diagnostics.cli import (
    CLICommandError,
    HealthCheckResult,
    build_failures_report,
    build_latency_report,
    build_parser,
    build_status_report,
    build_trace_report,
    build_usage_report,
    format_failures_report,
    format_latency_report,
    format_status_report,
    format_trace_report,
    format_usage_report,
    main,
    run_command,
)
from diagnostics.telemetry import MCPEvent, MemoryEventStore


def make_event(
    tool_name: str,
    *,
    actor: str = "ethan",
    integration_category: str = "GHL",
    success: bool = True,
    duration_ms: int = 100,
    request_id: str | None = None,
    timestamp: datetime | None = None,
    error_code: str | None = None,
    upstream_status: int | None = None,
    scope_required: str | None = None,
    payload_summary: dict | None = None,
) -> MCPEvent:
    return MCPEvent(
        request_id=request_id or f"req-{tool_name}-{duration_ms}-{success}",
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
        payload_summary=payload_summary or {"tool": tool_name, "arguments": {}},
    )


def test_parser_supports_health_trace_and_integration_filter():
    parser = build_parser()

    health_args = parser.parse_args(["health"])
    trace_args = parser.parse_args(["trace", "req-123", "--integration", "GHL"])
    status_args = parser.parse_args(["status", "--integration", "Payments"])

    assert health_args.command == "health"
    assert trace_args.command == "trace"
    assert trace_args.request_id == "req-123"
    assert trace_args.integration == "GHL"
    assert status_args.integration == "Payments"


def test_status_report_uses_event_store_data():
    events = [
        make_event("search_contacts", duration_ms=80),
        make_event("send_message", success=False, duration_ms=220, error_code="http:403", upstream_status=403),
        make_event("search_contacts", duration_ms=120, actor="agent-1", integration_category="Payments"),
    ]

    report = build_status_report(events, store_configured=True, window_days=7, integration=None)

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

    report = build_failures_report(events, limit=10, integration=None)

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

    report = build_latency_report(events, integration=None)

    assert report["event_count"] == 3
    assert report["tool_stats"]["search_contacts"]["count"] == 2
    assert report["tool_stats"]["search_contacts"]["p95_ms"] == 120
    assert report["integration_stats"]["GHL"]["count"] == 2
    assert "Jimmy latency" in format_latency_report(report)
    assert "integration" in format_latency_report(report)


def test_usage_report_counts_tools_actors_and_integrations():
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

    report = build_usage_report(events, integration=None)

    assert report["event_count"] == 3
    assert report["tool_counts"]["search_contacts"] == 2
    assert report["actor_counts"]["agent-1"] == 2
    assert report["integration_counts"]["GHL"] == 2
    assert "Jimmy usage" in format_usage_report(report)
    assert "top integrations" in format_usage_report(report)


def test_trace_report_formats_operator_detail():
    event = make_event(
        "send_message",
        request_id="req-trace-1",
        success=False,
        duration_ms=250,
        error_code="http:403",
        upstream_status=403,
        scope_required="conversations/message.write",
        payload_summary={
            "tool": "send_message",
            "arguments": {"body": {"redacted": True, "length": 12}},
        },
    )

    output = format_trace_report(build_trace_report(event))

    assert "request_id: req-trace-1" in output
    assert "integration: GHL" in output
    assert '"redacted": true' in output
    assert "secret payload" not in output


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

    base_args = {"days": 7, "limit": 1000, "actor": None, "integration": None, "tool": None}

    status_output = asyncio.run(run_command(Namespace(command="status", **base_args), store=store))
    failures_output = asyncio.run(
        run_command(Namespace(command="failures", recent_limit=10, **base_args), store=store)
    )
    latency_output = asyncio.run(run_command(Namespace(command="latency", **base_args), store=store))
    usage_output = asyncio.run(run_command(Namespace(command="usage", **base_args), store=store))

    assert "events: 3" in status_output
    assert "failures: 1" in status_output
    assert "total failures: 1" in failures_output
    assert "Jimmy latency" in latency_output
    assert "Jimmy usage" in usage_output


def test_integration_filter_applies_before_aggregation():
    store = MemoryEventStore()
    events = [
        make_event("search_contacts", integration_category="GHL"),
        make_event("send_message", integration_category="GHL", success=False, error_code="http:403", upstream_status=403),
        make_event("capture_payment", integration_category="Payments", actor="agent-1"),
    ]

    async def seed_events():
        for event in events:
            await store.write_event(event)

    asyncio.run(seed_events())

    output = asyncio.run(
        run_command(
            Namespace(command="usage", days=7, limit=1000, actor=None, integration="Payments", tool=None),
            store=store,
        )
    )

    assert "integration filter: Payments" in output
    assert "events: 1" in output
    assert "capture_payment: 1" in output
    assert "send_message" not in output


def test_trace_command_finds_event_by_request_id():
    store = MemoryEventStore()
    event = make_event(
        "send_message",
        request_id="req-find-me",
        payload_summary={
            "tool": "send_message",
            "arguments": {"body": {"redacted": True, "length": 9}},
        },
    )
    asyncio.run(store.write_event(event))

    output = asyncio.run(
        run_command(Namespace(command="trace", request_id="req-find-me", integration="GHL"), store=store)
    )

    assert "request_id: req-find-me" in output
    assert "integration: GHL" in output
    assert "payload_summary" in output
    assert "redacted" in output


def test_trace_command_returns_not_found_non_zero():
    store = MemoryEventStore()

    with pytest.raises(CLICommandError) as excinfo:
        asyncio.run(run_command(Namespace(command="trace", request_id="req-missing", integration=None), store=store))

    assert "status: not found" in excinfo.value.output
    assert "req-missing" in excinfo.value.output


def test_health_command_reports_all_healthy(monkeypatch):
    async def healthy(name: str, detail: str) -> HealthCheckResult:
        return HealthCheckResult(name, True, detail)

    monkeypatch.setattr(cli_module, "_check_required_env", lambda: healthy("config env", "all required env vars are present"))
    monkeypatch.setattr(cli_module, "_check_supabase_connectivity", lambda store: healthy("supabase connectivity", "reachable"))
    monkeypatch.setattr(cli_module, "_check_supabase_schema", lambda store: healthy("schema validation", "required columns are available"))
    monkeypatch.setattr(cli_module, "_check_ghl_probe", lambda: healthy("ghl live probe", "authenticated location read succeeded"))

    output = asyncio.run(run_command(Namespace(command="health", integration=None), store=MemoryEventStore()))

    assert "config env: ok" in output
    assert "supabase connectivity: ok" in output
    assert "schema validation: ok" in output
    assert "ghl live probe: ok" in output
    assert "overall: healthy" in output


@pytest.mark.parametrize(
    ("check_name", "detail"),
    [
        ("config env", "missing SUPABASE_URL"),
        ("supabase connectivity", "connection timed out"),
        ("schema validation", "integration_category column missing"),
        ("ghl live probe", "GHL API 403: unauthorized"),
    ],
)
def test_health_command_reports_unhealthy_cases(monkeypatch, check_name: str, detail: str):
    async def healthy(name: str) -> HealthCheckResult:
        return HealthCheckResult(name, True, "ok")

    async def maybe_fail(name: str) -> HealthCheckResult:
        if name == check_name:
            return HealthCheckResult(name, False, detail)
        return await healthy(name)

    monkeypatch.setattr(cli_module, "_check_required_env", lambda: maybe_fail("config env"))
    monkeypatch.setattr(cli_module, "_check_supabase_connectivity", lambda store: maybe_fail("supabase connectivity"))
    monkeypatch.setattr(cli_module, "_check_supabase_schema", lambda store: maybe_fail("schema validation"))
    monkeypatch.setattr(cli_module, "_check_ghl_probe", lambda: maybe_fail("ghl live probe"))

    with pytest.raises(CLICommandError) as excinfo:
        asyncio.run(run_command(Namespace(command="health", integration=None), store=MemoryEventStore()))

    assert check_name in excinfo.value.output
    assert detail in excinfo.value.output
    assert "overall: unhealthy" in excinfo.value.output


def test_main_returns_non_zero_for_unhealthy_health(monkeypatch, capsys):
    async def fake_run_command(args, *, store=None):
        raise CLICommandError("Jimmy health\n- overall: unhealthy")

    monkeypatch.setattr(cli_module, "run_command", fake_run_command)

    exit_code = main(["health"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "overall: unhealthy" in captured.out


def test_main_returns_zero_for_status(monkeypatch, capsys):
    async def fake_run_command(args, *, store=None):
        return "Jimmy status\n- overall: healthy"

    monkeypatch.setattr(cli_module, "run_command", fake_run_command)

    exit_code = main(["status"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Jimmy status" in captured.out

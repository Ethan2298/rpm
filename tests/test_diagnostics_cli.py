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
    build_anomalies_report,
    build_failures_report,
    build_inspect_report,
    build_latency_report,
    build_parser,
    build_reliability_report,
    build_session_report,
    build_status_report,
    build_trace_report,
    build_usage_report,
    format_anomalies_report,
    format_failures_report,
    format_inspect_report,
    format_latency_report,
    format_reliability_report,
    format_session_report,
    format_status_report,
    format_trace_report,
    format_usage_report,
    main,
    run_command,
    _tool_to_dict,
    _categorize_tools,
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


# --- reliability command ---


def test_reliability_report_shows_per_tool_success_rates():
    events = [
        make_event("search_contacts", duration_ms=80),
        make_event("search_contacts", duration_ms=90),
        make_event("search_contacts", success=False, duration_ms=200, error_code="http:500"),
        make_event("send_message", success=False, duration_ms=220, error_code="http:403"),
        make_event("send_message", success=False, duration_ms=180, error_code="http:403"),
        make_event("send_message", duration_ms=100),
    ]

    report = build_reliability_report(events, integration=None)

    assert report["event_count"] == 6
    assert report["overall_success_rate"] == 50.0
    assert report["tool_reliability"]["search_contacts"]["success_rate"] == 66.7
    assert report["tool_reliability"]["search_contacts"]["failure"] == 1
    assert report["tool_reliability"]["send_message"]["success_rate"] == 33.3
    assert report["tool_reliability"]["send_message"]["failure"] == 2


def test_reliability_report_shows_top_errors():
    events = [
        make_event("send_message", success=False, error_code="http:403"),
        make_event("send_message", success=False, error_code="http:403"),
        make_event("send_message", success=False, error_code="http:500"),
    ]

    report = build_reliability_report(events, integration=None)
    top_errors = report["tool_reliability"]["send_message"]["top_errors"]

    assert top_errors[0] == ("http:403", 2)
    assert top_errors[1] == ("http:500", 1)


def test_reliability_format_includes_error_breakdown():
    events = [
        make_event("search_contacts", duration_ms=80),
        make_event("search_contacts", success=False, error_code="http:500"),
    ]

    output = format_reliability_report(build_reliability_report(events, integration=None))

    assert "Jimmy reliability" in output
    assert "50.0%" in output
    assert "http:500" in output


def test_reliability_command_via_run_command():
    store = MemoryEventStore()

    async def seed():
        await store.write_event(make_event("search_contacts"))
        await store.write_event(make_event("search_contacts", success=False, error_code="http:500"))

    asyncio.run(seed())

    output = asyncio.run(
        run_command(
            Namespace(command="reliability", days=7, limit=1000, actor=None, integration=None, tool=None),
            store=store,
        )
    )

    assert "Jimmy reliability" in output
    assert "search_contacts" in output


# --- session command ---


def test_session_report_replays_events_in_order():
    events = [
        make_event("get_contact", timestamp=datetime(2026, 4, 11, 12, 2, tzinfo=timezone.utc), request_id="req-2"),
        make_event("search_contacts", timestamp=datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc), request_id="req-1"),
        make_event("send_message", timestamp=datetime(2026, 4, 11, 12, 5, tzinfo=timezone.utc), request_id="req-3",
                    success=False, error_code="http:403"),
    ]

    report = build_session_report(events, session_id="session-1")

    assert report["session_id"] == "session-1"
    assert report["event_count"] == 3
    assert report["success_count"] == 2
    assert report["failure_count"] == 1
    assert report["tool_sequence"] == ["search_contacts", "get_contact", "send_message"]


def test_session_format_shows_timeline():
    events = [
        make_event("search_contacts", timestamp=datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc), duration_ms=80),
        make_event("send_message", timestamp=datetime(2026, 4, 11, 12, 1, tzinfo=timezone.utc),
                    success=False, error_code="http:403", duration_ms=220),
    ]

    output = format_session_report(build_session_report(events, session_id="session-1"))

    assert "Jimmy session" in output
    assert "session_id: session-1" in output
    assert "timeline:" in output
    assert "search_contacts 80ms ok" in output
    assert "send_message 220ms FAIL http:403" in output


def test_session_command_via_run_command():
    store = MemoryEventStore()

    async def seed():
        await store.write_event(make_event("search_contacts", request_id="req-1"))
        await store.write_event(make_event("get_contact", request_id="req-2"))

    asyncio.run(seed())

    output = asyncio.run(
        run_command(Namespace(command="session", session_id="session-1"), store=store)
    )

    assert "session_id: session-1" in output
    assert "events: 2" in output


def test_session_command_not_found():
    store = MemoryEventStore()

    with pytest.raises(CLICommandError) as excinfo:
        asyncio.run(run_command(Namespace(command="session", session_id="nonexistent"), store=store))

    assert "no events found" in excinfo.value.output


# --- anomalies command ---


def test_anomalies_detects_failure_rate_spike():
    current = [
        make_event("search_contacts", success=False, error_code="http:500"),
        make_event("search_contacts", success=False, error_code="http:500"),
        make_event("search_contacts"),
    ]
    baseline = [
        make_event("search_contacts"),
        make_event("search_contacts"),
        make_event("search_contacts"),
        make_event("search_contacts"),
        make_event("search_contacts"),
        make_event("search_contacts", success=False, error_code="http:500"),
    ]

    report = build_anomalies_report(current, baseline, current_days=1, baseline_days=7, threshold=2.0)

    failure_alerts = [a for a in report["alerts"] if a["signal"] == "failure_rate"]
    assert len(failure_alerts) == 1
    assert "66.7%" in failure_alerts[0]["current"]


def test_anomalies_detects_new_error_codes():
    current = [
        make_event("send_message", success=False, error_code="http:429"),
    ]
    baseline = [
        make_event("send_message", success=False, error_code="http:403"),
        make_event("send_message"),
    ]

    report = build_anomalies_report(current, baseline, current_days=1, baseline_days=7, threshold=2.0)

    new_error_alerts = [a for a in report["alerts"] if a["signal"] == "new_error_code"]
    assert len(new_error_alerts) == 1
    assert "http:429" in new_error_alerts[0]["current"]


def test_anomalies_detects_latency_spike():
    current = [
        make_event("search_contacts", duration_ms=500),
        make_event("search_contacts", duration_ms=600),
    ]
    baseline = [
        make_event("search_contacts", duration_ms=100),
        make_event("search_contacts", duration_ms=120),
    ]

    report = build_anomalies_report(current, baseline, current_days=1, baseline_days=7, threshold=2.0)

    latency_alerts = [a for a in report["alerts"] if a["signal"] == "avg_latency"]
    assert len(latency_alerts) == 1


def test_anomalies_no_alerts_when_stable():
    events = [
        make_event("search_contacts", duration_ms=100),
        make_event("search_contacts", duration_ms=110),
    ]

    report = build_anomalies_report(events, events, current_days=1, baseline_days=7, threshold=2.0)

    assert len(report["alerts"]) == 0


def test_anomalies_detects_per_tool_failure_spike():
    current = [
        make_event("send_message", success=False, error_code="http:403"),
        make_event("send_message", success=False, error_code="http:403"),
        make_event("search_contacts"),
    ]
    baseline = [
        make_event("send_message"),
        make_event("send_message"),
        make_event("send_message"),
        make_event("send_message"),
        make_event("send_message"),
        make_event("send_message"),
        make_event("send_message", success=False, error_code="http:403"),
    ]

    report = build_anomalies_report(current, baseline, current_days=1, baseline_days=7, threshold=2.0)

    tool_alerts = [a for a in report["alerts"] if a["signal"] == "tool_failures:send_message"]
    assert len(tool_alerts) == 1


def test_anomalies_format_output():
    current = [make_event("search_contacts", success=False, error_code="http:500")]
    baseline = [make_event("search_contacts")]

    report = build_anomalies_report(current, baseline, current_days=1, baseline_days=7, threshold=2.0)
    output = format_anomalies_report(report)

    assert "Jimmy anomalies" in output
    assert "current window: 1d" in output
    assert "baseline window: 7d" in output
    assert "alerts" in output


def test_anomalies_command_via_run_command():
    store = MemoryEventStore()

    async def seed():
        await store.write_event(make_event("search_contacts", duration_ms=100))

    asyncio.run(seed())

    output = asyncio.run(
        run_command(
            Namespace(
                command="anomalies",
                current_days=1,
                baseline_days=7,
                threshold=2.0,
                limit=1000,
                actor=None,
                integration=None,
                tool=None,
            ),
            store=store,
        )
    )

    assert "Jimmy anomalies" in output


# --- inspect command ---


def _make_fake_tool(name, description="A tool", params=None):
    """Build a tool dict matching _tool_to_dict output."""
    params = params or []
    return {
        "name": name,
        "description": description,
        "full_description": description,
        "param_count": len(params),
        "params": params,
    }


def test_inspect_report_counts_tools():
    tools = [
        _make_fake_tool("search_contacts"),
        _make_fake_tool("get_contact"),
        _make_fake_tool("send_message"),
    ]

    report = build_inspect_report(tools, mode="local", show_schema=False)

    assert report["tool_count"] == 3
    assert report["mode"] == "local"
    assert "contacts" in report["categories"]
    assert "conversations" in report["categories"]


def test_inspect_report_classifies_read_write():
    tools = [
        _make_fake_tool("search_contacts"),
        _make_fake_tool("get_contact"),
        _make_fake_tool("send_message"),
        _make_fake_tool("create_opportunity"),
    ]

    report = build_inspect_report(tools, mode="local", show_schema=False)

    assert report["read_count"] == 2
    assert report["write_count"] == 2


def test_inspect_report_filters_by_tool_name():
    tools = [
        _make_fake_tool("search_contacts"),
        _make_fake_tool("get_contact"),
        _make_fake_tool("send_message"),
    ]

    report = build_inspect_report(tools, mode="local", show_schema=False, tool_filter="contact")

    assert report["tool_count"] == 2
    assert report["tool_filter"] == "contact"


def test_inspect_format_shows_categories():
    tools = [
        _make_fake_tool("search_contacts"),
        _make_fake_tool("kb_list"),
    ]

    output = format_inspect_report(build_inspect_report(tools, mode="local", show_schema=False))

    assert "Jimmy inspect" in output
    assert "[contacts]" in output
    assert "[knowledge base]" in output


def test_inspect_format_shows_schema_details():
    tools = [
        {
            "name": "search_contacts",
            "description": "Search contacts",
            "full_description": "Search contacts",
            "param_count": 2,
            "params": [
                {"name": "query", "type": "string", "required": True, "default": None, "has_default": False},
                {"name": "limit", "type": "integer", "required": False, "default": 20, "has_default": True},
            ],
        }
    ]

    output = format_inspect_report(build_inspect_report(tools, mode="local", show_schema=True))

    assert "query: string (required)" in output
    assert "limit: integer (optional, default=20)" in output


def test_inspect_categorize_puts_unknown_in_other():
    tools = [_make_fake_tool("custom_widget")]

    categories = _categorize_tools(tools)

    assert "other" in categories
    assert categories["other"][0]["name"] == "custom_widget"


def test_tool_to_dict_parses_mcp_tool():
    class FakeTool:
        name = "search_contacts"
        description = "Search contacts.\n\nMore detail here."
        inputSchema = {
            "properties": {
                "query": {"type": "string", "title": "Query"},
                "limit": {"type": "integer", "title": "Limit", "default": 20},
            },
            "required": ["query"],
            "type": "object",
        }

    result = _tool_to_dict(FakeTool())

    assert result["name"] == "search_contacts"
    assert result["description"] == "Search contacts."
    assert result["param_count"] == 2
    assert result["params"][0]["name"] == "query"
    assert result["params"][0]["required"] is True
    assert result["params"][1]["name"] == "limit"
    assert result["params"][1]["required"] is False
    assert result["params"][1]["default"] == 20


def test_inspect_command_local_via_run_command(monkeypatch):
    fake_tools = [
        {
            "name": "search_contacts",
            "description": "Search contacts",
            "full_description": "Search contacts",
            "param_count": 1,
            "params": [{"name": "query", "type": "string", "required": True, "default": None, "has_default": False}],
        }
    ]

    async def fake_load_local():
        return fake_tools

    monkeypatch.setattr(cli_module, "_load_local_tools", fake_load_local)

    output = asyncio.run(
        run_command(Namespace(command="inspect", remote=None, token=None, schema=False, tool=None))
    )

    assert "Jimmy inspect" in output
    assert "mode: local" in output
    assert "search_contacts" in output

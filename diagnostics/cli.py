from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any

import httpx

from mcp_servers.ghl.client import GHLAPIError, GHLClient
from diagnostics.telemetry import (
    MCPEvent,
    MCPEventQuery,
    MCPEventStore,
    SupabaseEventStore,
    create_event_store_from_env,
)

REQUIRED_HEALTH_ENV_VARS = (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "GHL_API_KEY",
    "GHL_LOCATION_ID",
)
REQUIRED_SCHEMA_COLUMNS = (
    "request_id",
    "occurred_at",
    "actor",
    "session_id",
    "integration_category",
    "tool_name",
    "duration_ms",
    "success",
    "error_code",
    "scope_required",
    "upstream_status",
    "payload_summary",
)


class CLICommandError(RuntimeError):
    def __init__(self, output: str):
        super().__init__(output)
        self.output = output


@dataclass(slots=True)
class HealthCheckResult:
    name: str
    healthy: bool
    detail: str


def _format_dt(value: datetime | None) -> str:
    if value is None:
        return "n/a"
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def _percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = int((len(ordered) * pct) + 0.999999)
    index = min(max(rank - 1, 0), len(ordered) - 1)
    return ordered[index]


def _top_rows(counter: Counter[str], limit: int = 5) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]


def _tool_stats(events: list[MCPEvent]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[int]] = defaultdict(list)
    for event in events:
        buckets[event.tool_name].append(event.duration_ms)

    stats: dict[str, dict[str, Any]] = {}
    for tool_name, durations in buckets.items():
        stats[tool_name] = {
            "count": len(durations),
            "avg_ms": int(round(mean(durations))) if durations else 0,
            "p95_ms": _percentile(durations, 0.95),
            "max_ms": max(durations) if durations else 0,
        }
    return dict(sorted(stats.items(), key=lambda item: (-item[1]["count"], item[0])))


def _integration_stats(events: list[MCPEvent]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[int]] = defaultdict(list)
    for event in events:
        buckets[event.integration_category].append(event.duration_ms)

    stats: dict[str, dict[str, Any]] = {}
    for category, durations in buckets.items():
        stats[category] = {
            "count": len(durations),
            "avg_ms": int(round(mean(durations))) if durations else 0,
            "p95_ms": _percentile(durations, 0.95),
            "max_ms": max(durations) if durations else 0,
        }
    return dict(sorted(stats.items(), key=lambda item: (-item[1]["count"], item[0])))


def build_status_report(events: list[MCPEvent], *, store_configured: bool, window_days: int, integration: str | None = None) -> dict[str, Any]:
    failures = [event for event in events if not event.success]
    latency_values = [event.duration_ms for event in events]
    tool_counts = Counter(event.tool_name for event in events)
    actor_counts = Counter(event.actor for event in events)
    integration_counts = Counter(event.integration_category for event in events)
    last_event_at = max((event.timestamp for event in events), default=None)
    return {
        "store_configured": store_configured,
        "window_days": window_days,
        "integration_filter": integration,
        "event_count": len(events),
        "failure_count": len(failures),
        "last_event_at": last_event_at,
        "p95_ms": _percentile(latency_values, 0.95),
        "top_tool": _top_rows(tool_counts, 1)[0] if tool_counts else None,
        "top_actor": _top_rows(actor_counts, 1)[0] if actor_counts else None,
        "top_integration": _top_rows(integration_counts, 1)[0] if integration_counts else None,
    }


def format_status_report(report: dict[str, Any]) -> str:
    lines = [
        "Jimmy status",
        f"- event store: {'configured' if report['store_configured'] else 'not configured'}",
        f"- window: {report['window_days']}d",
    ]
    if report["integration_filter"]:
        lines.append(f"- integration filter: {report['integration_filter']}")
    lines.extend(
        [
            f"- events: {report['event_count']}",
            f"- failures: {report['failure_count']}",
            f"- last event: {_format_dt(report['last_event_at'])}",
            f"- p95 latency: {report['p95_ms']} ms",
        ]
    )
    if report["top_tool"]:
        tool, count = report["top_tool"]
        lines.append(f"- top tool: {tool} ({count})")
    if report["top_actor"]:
        actor, count = report["top_actor"]
        lines.append(f"- top actor: {actor} ({count})")
    if report["top_integration"]:
        integration, count = report["top_integration"]
        lines.append(f"- top integration: {integration} ({count})")
    return "\n".join(lines)


def build_failures_report(events: list[MCPEvent], *, limit: int, integration: str | None = None) -> dict[str, Any]:
    failures = [event for event in events if not event.success]
    failure_codes = Counter(event.error_code or "unknown" for event in failures)
    failure_integrations = Counter(event.integration_category for event in failures)
    recent_failures = failures[:limit]
    return {
        "integration_filter": integration,
        "failure_count": len(failures),
        "failure_codes": failure_codes,
        "failure_integrations": failure_integrations,
        "recent_failures": recent_failures,
    }


def format_failures_report(report: dict[str, Any]) -> str:
    lines = [
        "Jimmy failures",
        f"- total failures: {report['failure_count']}",
    ]
    if report["integration_filter"]:
        lines.append(f"- integration filter: {report['integration_filter']}")
    if report["failure_codes"]:
        lines.append("- failure codes:")
        for code, count in _top_rows(report["failure_codes"], limit=10):
            lines.append(f"  - {code}: {count}")
    if report["failure_integrations"]:
        lines.append("- failure integrations:")
        for integration, count in _top_rows(report["failure_integrations"], limit=10):
            lines.append(f"  - {integration}: {count}")
    if report["recent_failures"]:
        lines.append("- recent failures:")
        for event in report["recent_failures"]:
            lines.append(
                f"  - {_format_dt(event.timestamp)} integration={event.integration_category} {event.tool_name} {event.error_code or 'unknown'} "
                f"status={event.upstream_status or 'n/a'} scope={event.scope_required or 'n/a'} "
                f"actor={event.actor} duration={event.duration_ms}ms request_id={event.request_id}"
            )
    return "\n".join(lines)


def build_latency_report(events: list[MCPEvent], *, integration: str | None = None) -> dict[str, Any]:
    stats = _tool_stats(events)
    integration_stats = _integration_stats(events)
    return {
        "integration_filter": integration,
        "event_count": len(events),
        "tool_stats": stats,
        "integration_stats": integration_stats,
        "overall_avg_ms": int(round(mean([event.duration_ms for event in events]))) if events else 0,
        "overall_p95_ms": _percentile([event.duration_ms for event in events], 0.95),
    }


def format_latency_report(report: dict[str, Any]) -> str:
    lines = [
        "Jimmy latency",
        f"- events: {report['event_count']}",
    ]
    if report["integration_filter"]:
        lines.append(f"- integration filter: {report['integration_filter']}")
    lines.extend(
        [
            f"- overall avg: {report['overall_avg_ms']} ms",
            f"- overall p95: {report['overall_p95_ms']} ms",
        ]
    )
    if report["tool_stats"]:
        lines.append("tool                     count   avg   p95   max")
        for tool_name, stats in report["tool_stats"].items():
            lines.append(
                f"{tool_name:<24} {stats['count']:>5} {stats['avg_ms']:>5} {stats['p95_ms']:>5} {stats['max_ms']:>5}"
            )
    if report["integration_stats"]:
        lines.append("integration              count   avg   p95   max")
        for integration, stats in report["integration_stats"].items():
            lines.append(
                f"{integration:<24} {stats['count']:>5} {stats['avg_ms']:>5} {stats['p95_ms']:>5} {stats['max_ms']:>5}"
            )
    return "\n".join(lines)


def build_usage_report(events: list[MCPEvent], *, integration: str | None = None) -> dict[str, Any]:
    tool_counts = Counter(event.tool_name for event in events)
    actor_counts = Counter(event.actor for event in events)
    integration_counts = Counter(event.integration_category for event in events)
    successful = sum(1 for event in events if event.success)
    return {
        "integration_filter": integration,
        "event_count": len(events),
        "successful_count": successful,
        "failure_count": len(events) - successful,
        "tool_counts": tool_counts,
        "actor_counts": actor_counts,
        "integration_counts": integration_counts,
    }


def format_usage_report(report: dict[str, Any]) -> str:
    lines = [
        "Jimmy usage",
        f"- events: {report['event_count']}",
    ]
    if report["integration_filter"]:
        lines.append(f"- integration filter: {report['integration_filter']}")
    lines.extend(
        [
            f"- successful: {report['successful_count']}",
            f"- failed: {report['failure_count']}",
        ]
    )
    if report["tool_counts"]:
        lines.append("- top tools:")
        for tool, count in _top_rows(report["tool_counts"], limit=10):
            lines.append(f"  - {tool}: {count}")
    if report["actor_counts"]:
        lines.append("- top actors:")
        for actor, count in _top_rows(report["actor_counts"], limit=10):
            lines.append(f"  - {actor}: {count}")
    if report["integration_counts"]:
        lines.append("- top integrations:")
        for integration, count in _top_rows(report["integration_counts"], limit=10):
            lines.append(f"  - {integration}: {count}")
    return "\n".join(lines)


def build_trace_report(event: MCPEvent) -> dict[str, Any]:
    return {
        "request_id": event.request_id,
        "timestamp": event.timestamp,
        "actor": event.actor,
        "session_id": event.session_id,
        "integration_category": event.integration_category,
        "tool_name": event.tool_name,
        "success": event.success,
        "duration_ms": event.duration_ms,
        "upstream_status": event.upstream_status,
        "scope_required": event.scope_required,
        "error_code": event.error_code,
        "payload_summary": event.payload_summary,
    }


def format_trace_report(report: dict[str, Any]) -> str:
    payload_json = json.dumps(report["payload_summary"], indent=2, sort_keys=True)
    lines = [
        "Jimmy trace",
        f"- request_id: {report['request_id']}",
        f"- timestamp: {_format_dt(report['timestamp'])}",
        f"- actor: {report['actor']}",
        f"- session_id: {report['session_id'] or 'n/a'}",
        f"- integration: {report['integration_category']}",
        f"- tool: {report['tool_name']}",
        f"- success: {str(report['success']).lower()}",
        f"- duration: {report['duration_ms']} ms",
        f"- upstream_status: {report['upstream_status'] if report['upstream_status'] is not None else 'n/a'}",
        f"- scope_required: {report['scope_required'] or 'n/a'}",
        f"- error_code: {report['error_code'] or 'n/a'}",
        "- payload_summary:",
    ]
    lines.extend(f"  {line}" for line in payload_json.splitlines())
    return "\n".join(lines)


def format_trace_not_found(request_id: str, integration: str | None = None) -> str:
    lines = [
        "Jimmy trace",
        f"- request_id: {request_id}",
        "- status: not found",
    ]
    if integration:
        lines.append(f"- integration filter: {integration}")
    return "\n".join(lines)


def _missing_env_vars(names: tuple[str, ...]) -> list[str]:
    return [name for name in names if not os.getenv(name, "").strip()]


def _format_health_report(results: list[HealthCheckResult]) -> str:
    overall_healthy = all(result.healthy for result in results)
    lines = ["Jimmy health"]
    for result in results:
        status = "ok" if result.healthy else "fail"
        lines.append(f"- {result.name}: {status} - {result.detail}")
    lines.append(f"- overall: {'healthy' if overall_healthy else 'unhealthy'}")
    return "\n".join(lines)


async def _check_required_env() -> HealthCheckResult:
    missing = _missing_env_vars(REQUIRED_HEALTH_ENV_VARS)
    if missing:
        return HealthCheckResult("config env", False, f"missing {', '.join(sorted(missing))}")
    return HealthCheckResult("config env", True, "all required env vars are present")


async def _check_supabase_connectivity(store: MCPEventStore) -> HealthCheckResult:
    if not isinstance(store, SupabaseEventStore):
        return HealthCheckResult("supabase connectivity", False, "event store is not configured")
    try:
        await store.fetch_events(MCPEventQuery(limit=1))
    except Exception as exc:
        return HealthCheckResult("supabase connectivity", False, str(exc))
    return HealthCheckResult("supabase connectivity", True, f"reachable table={store.table}")


async def _check_supabase_schema(store: MCPEventStore) -> HealthCheckResult:
    if not isinstance(store, SupabaseEventStore):
        return HealthCheckResult("schema validation", False, "event store is not configured")

    params = [("select", ",".join(REQUIRED_SCHEMA_COLUMNS)), ("limit", "1")]
    try:
        async with httpx.AsyncClient(base_url=store.url, headers=store._headers(), timeout=15.0) as client:
            response = await client.get(f"/rest/v1/{store.table}", params=params)
            response.raise_for_status()
    except Exception as exc:
        return HealthCheckResult("schema validation", False, str(exc))

    return HealthCheckResult("schema validation", True, "required columns are available")


async def _check_ghl_probe() -> HealthCheckResult:
    missing = _missing_env_vars(("GHL_API_KEY", "GHL_LOCATION_ID"))
    if missing:
        return HealthCheckResult("ghl live probe", False, f"missing {', '.join(sorted(missing))}")

    client: GHLClient | None = None
    try:
        client = GHLClient()
        await client.get(f"/locations/{client.location_id}", params={})
    except (ValueError, GHLAPIError, httpx.HTTPError) as exc:
        return HealthCheckResult("ghl live probe", False, str(exc))
    finally:
        if client is not None:
            await client.close()

    return HealthCheckResult("ghl live probe", True, "authenticated location read succeeded")


async def _load_events(
    store: MCPEventStore,
    *,
    days: int | None = None,
    limit: int,
    actor: str | None = None,
    integration: str | None = None,
    tool_name: str | None = None,
    success: bool | None = None,
    request_id: str | None = None,
) -> list[MCPEvent]:
    since = None
    if days is not None:
        since = datetime.now(timezone.utc) - timedelta(days=days)
    query = MCPEventQuery(
        request_id=request_id,
        since=since,
        actor=actor,
        integration_category=integration,
        tool_name=tool_name,
        success=success,
        limit=limit,
    )
    return await store.fetch_events(query)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jimmy-diag", description="Jimmy diagnostics CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common_arguments(command_parser: argparse.ArgumentParser, *, default_days: int, default_limit: int = 1000) -> None:
        command_parser.add_argument("--days", type=int, default=default_days, help="Lookback window in days")
        command_parser.add_argument("--limit", type=int, default=default_limit, help="Max rows to read")
        command_parser.add_argument("--actor", type=str, default=None, help="Filter by actor")
        command_parser.add_argument("--integration", type=str, default=None, help="Filter by integration category")
        command_parser.add_argument("--tool", type=str, default=None, help="Filter by tool")

    health_parser = subparsers.add_parser("health", help="Run live operator health checks")
    health_parser.add_argument("--integration", type=str, default=None, help="Reserved for future multi-integration health checks")

    status_parser = subparsers.add_parser("status", help="Show service health and recent activity")
    add_common_arguments(status_parser, default_days=1, default_limit=500)

    failures_parser = subparsers.add_parser("failures", help="Show recent failures")
    add_common_arguments(failures_parser, default_days=7, default_limit=1000)
    failures_parser.add_argument("--recent-limit", type=int, default=10, help="Max failures to print")

    latency_parser = subparsers.add_parser("latency", help="Show latency summary")
    add_common_arguments(latency_parser, default_days=7, default_limit=1000)

    usage_parser = subparsers.add_parser("usage", help="Show usage summary")
    add_common_arguments(usage_parser, default_days=7, default_limit=1000)

    trace_parser = subparsers.add_parser("trace", help="Trace a single request by request_id")
    trace_parser.add_argument("request_id", type=str, help="Exact request_id to inspect")
    trace_parser.add_argument("--integration", type=str, default=None, help="Filter by integration category")

    return parser


async def run_command(args: argparse.Namespace, *, store: MCPEventStore | None = None) -> str:
    resolved_store = store or create_event_store_from_env()
    store_configured = getattr(resolved_store, "enabled", True)

    if args.command == "health":
        results = [
            await _check_required_env(),
            await _check_supabase_connectivity(resolved_store),
            await _check_supabase_schema(resolved_store),
            await _check_ghl_probe(),
        ]
        output = _format_health_report(results)
        if not all(result.healthy for result in results):
            raise CLICommandError(output)
        return output

    if args.command == "trace":
        if not store_configured:
            raise RuntimeError("Supabase event store is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        events = await _load_events(
            resolved_store,
            limit=1,
            integration=args.integration,
            request_id=args.request_id,
        )
        if not events:
            raise CLICommandError(format_trace_not_found(args.request_id, integration=args.integration))
        return format_trace_report(build_trace_report(events[0]))

    events = await _load_events(
        resolved_store,
        days=args.days,
        limit=args.limit,
        actor=args.actor,
        integration=args.integration,
        tool_name=args.tool,
    )

    if args.command == "status":
        report = build_status_report(
            events,
            store_configured=store_configured,
            window_days=args.days,
            integration=args.integration,
        )
        return format_status_report(report)

    if not store_configured:
        raise RuntimeError("Supabase event store is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")

    if args.command == "failures":
        report = build_failures_report(events, limit=args.recent_limit, integration=args.integration)
        return format_failures_report(report)

    if args.command == "latency":
        report = build_latency_report(events, integration=args.integration)
        return format_latency_report(report)

    if args.command == "usage":
        report = build_usage_report(events, integration=args.integration)
        return format_usage_report(report)

    raise ValueError(f"Unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = asyncio.run(run_command(args))
    except CLICommandError as exc:
        print(exc.output)
        return 1
    except RuntimeError as exc:
        parser.exit(1, f"error: {exc}\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

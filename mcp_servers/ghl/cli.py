from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any

from mcp_servers.ghl.telemetry import (
    MCPEvent,
    MCPEventQuery,
    MCPEventStore,
    create_event_store_from_env,
)


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


def build_status_report(events: list[MCPEvent], *, store_configured: bool, window_days: int) -> dict[str, Any]:
    failures = [event for event in events if not event.success]
    latency_values = [event.duration_ms for event in events]
    tool_counts = Counter(event.tool_name for event in events)
    actor_counts = Counter(event.actor for event in events)
    last_event_at = max((event.timestamp for event in events), default=None)
    return {
        "store_configured": store_configured,
        "window_days": window_days,
        "event_count": len(events),
        "failure_count": len(failures),
        "last_event_at": last_event_at,
        "p95_ms": _percentile(latency_values, 0.95),
        "top_tool": _top_rows(tool_counts, 1)[0] if tool_counts else None,
        "top_actor": _top_rows(actor_counts, 1)[0] if actor_counts else None,
    }


def format_status_report(report: dict[str, Any]) -> str:
    lines = [
        "MCP status",
        f"- event store: {'configured' if report['store_configured'] else 'not configured'}",
        f"- window: {report['window_days']}d",
        f"- events: {report['event_count']}",
        f"- failures: {report['failure_count']}",
        f"- last event: {_format_dt(report['last_event_at'])}",
        f"- p95 latency: {report['p95_ms']} ms",
    ]
    if report["top_tool"]:
        tool, count = report["top_tool"]
        lines.append(f"- top tool: {tool} ({count})")
    if report["top_actor"]:
        actor, count = report["top_actor"]
        lines.append(f"- top actor: {actor} ({count})")
    return "\n".join(lines)


def build_failures_report(events: list[MCPEvent], *, limit: int) -> dict[str, Any]:
    failures = [event for event in events if not event.success]
    failure_codes = Counter(event.error_code or "unknown" for event in failures)
    recent_failures = failures[:limit]
    return {
        "failure_count": len(failures),
        "failure_codes": failure_codes,
        "recent_failures": recent_failures,
    }


def format_failures_report(report: dict[str, Any]) -> str:
    lines = [
        "MCP failures",
        f"- total failures: {report['failure_count']}",
    ]
    if report["failure_codes"]:
        lines.append("- failure codes:")
        for code, count in _top_rows(report["failure_codes"], limit=10):
            lines.append(f"  - {code}: {count}")
    if report["recent_failures"]:
        lines.append("- recent failures:")
        for event in report["recent_failures"]:
            lines.append(
                f"  - {_format_dt(event.timestamp)} {event.tool_name} {event.error_code or 'unknown'} "
                f"status={event.upstream_status or 'n/a'} scope={event.scope_required or 'n/a'} "
                f"actor={event.actor} duration={event.duration_ms}ms request_id={event.request_id}"
            )
    return "\n".join(lines)


def build_latency_report(events: list[MCPEvent]) -> dict[str, Any]:
    stats = _tool_stats(events)
    return {
        "event_count": len(events),
        "tool_stats": stats,
        "overall_avg_ms": int(round(mean([event.duration_ms for event in events]))) if events else 0,
        "overall_p95_ms": _percentile([event.duration_ms for event in events], 0.95),
    }


def format_latency_report(report: dict[str, Any]) -> str:
    lines = [
        "MCP latency",
        f"- events: {report['event_count']}",
        f"- overall avg: {report['overall_avg_ms']} ms",
        f"- overall p95: {report['overall_p95_ms']} ms",
    ]
    if report["tool_stats"]:
        lines.append("tool                     count   avg   p95   max")
        for tool_name, stats in report["tool_stats"].items():
            lines.append(
                f"{tool_name:<24} {stats['count']:>5} {stats['avg_ms']:>5} {stats['p95_ms']:>5} {stats['max_ms']:>5}"
            )
    return "\n".join(lines)


def build_usage_report(events: list[MCPEvent]) -> dict[str, Any]:
    tool_counts = Counter(event.tool_name for event in events)
    actor_counts = Counter(event.actor for event in events)
    successful = sum(1 for event in events if event.success)
    return {
        "event_count": len(events),
        "successful_count": successful,
        "failure_count": len(events) - successful,
        "tool_counts": tool_counts,
        "actor_counts": actor_counts,
    }


def format_usage_report(report: dict[str, Any]) -> str:
    lines = [
        "MCP usage",
        f"- events: {report['event_count']}",
        f"- successful: {report['successful_count']}",
        f"- failed: {report['failure_count']}",
    ]
    if report["tool_counts"]:
        lines.append("- top tools:")
        for tool, count in _top_rows(report["tool_counts"], limit=10):
            lines.append(f"  - {tool}: {count}")
    if report["actor_counts"]:
        lines.append("- top actors:")
        for actor, count in _top_rows(report["actor_counts"], limit=10):
            lines.append(f"  - {actor}: {count}")
    return "\n".join(lines)


async def _load_events(
    store: MCPEventStore,
    *,
    days: int,
    limit: int,
    actor: str | None = None,
    tool_name: str | None = None,
    success: bool | None = None,
) -> list[MCPEvent]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    query = MCPEventQuery(
        since=since,
        actor=actor,
        tool_name=tool_name,
        success=success,
        limit=limit,
    )
    return await store.fetch_events(query)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mcp", description="MCP observability CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common_arguments(command_parser: argparse.ArgumentParser, *, default_days: int, default_limit: int = 1000) -> None:
        command_parser.add_argument("--days", type=int, default=default_days, help="Lookback window in days")
        command_parser.add_argument("--limit", type=int, default=default_limit, help="Max rows to read")
        command_parser.add_argument("--actor", type=str, default=None, help="Filter by actor")
        command_parser.add_argument("--tool", type=str, default=None, help="Filter by tool")

    status_parser = subparsers.add_parser("status", help="Show service health and recent activity")
    add_common_arguments(status_parser, default_days=1, default_limit=500)

    failures_parser = subparsers.add_parser("failures", help="Show recent failures")
    add_common_arguments(failures_parser, default_days=7, default_limit=1000)
    failures_parser.add_argument("--recent-limit", type=int, default=10, help="Max failures to print")

    latency_parser = subparsers.add_parser("latency", help="Show latency summary")
    add_common_arguments(latency_parser, default_days=7, default_limit=1000)

    usage_parser = subparsers.add_parser("usage", help="Show usage summary")
    add_common_arguments(usage_parser, default_days=7, default_limit=1000)

    return parser


async def run_command(args: argparse.Namespace, *, store: MCPEventStore | None = None) -> str:
    resolved_store = store or create_event_store_from_env()
    store_configured = getattr(resolved_store, "enabled", True)
    events = await _load_events(
        resolved_store,
        days=args.days,
        limit=args.limit,
        actor=args.actor,
        tool_name=args.tool,
    )

    if args.command == "status":
        report = build_status_report(events, store_configured=store_configured, window_days=args.days)
        return format_status_report(report)

    if not store_configured:
        raise RuntimeError("Supabase event store is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")

    if args.command == "failures":
        report = build_failures_report(events, limit=args.recent_limit)
        return format_failures_report(report)

    if args.command == "latency":
        report = build_latency_report(events)
        return format_latency_report(report)

    if args.command == "usage":
        report = build_usage_report(events)
        return format_usage_report(report)

    raise ValueError(f"Unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = asyncio.run(run_command(args))
    except RuntimeError as exc:
        parser.exit(1, f"error: {exc}\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

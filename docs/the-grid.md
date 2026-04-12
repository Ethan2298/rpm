# The Grid — MCP Development Tracker

Development board for the Jimmy MCP server. Tools, skills, workflows, analytics, and hardening.

---

## Sections

### Programs (Tools)
Each MCP tool is a program. Track build status, test coverage, and edge cases.

#### Live Programs (46)
| Program | Zone | Status |
|---------|------|--------|
| `search_contacts` | contacts | live |
| `get_contact` | contacts | live |
| `create_or_update_contact` | contacts | live |
| `update_contact` | contacts | live |
| `delete_contact` | contacts | live |
| `add_contact_tags` | contacts | live |
| `remove_contact_tags` | contacts | live |
| `get_contact_notes` | contacts | live |
| `add_contact_note` | contacts | live |
| `get_contact_tasks` | contacts | live |
| `create_contact_task` | contacts | live |
| `search_conversations` | conversations | live |
| `get_conversation_messages` | conversations | live |
| `send_message` | conversations | live |
| `update_conversation` | conversations | live |
| `get_pipelines` | pipeline | live |
| `search_opportunities` | pipeline | live |
| `get_opportunity` | pipeline | live |
| `create_opportunity` | pipeline | live |
| `update_opportunity` | pipeline | live |
| `delete_opportunity` | pipeline | live |
| `list_calendars` | calendar | live |
| `get_calendar_events` | calendar | live |
| `get_calendar_free_slots` | calendar | live |
| `book_appointment` | calendar | live |
| `update_appointment` | calendar | live |
| `delete_appointment` | calendar | live |
| `get_location` | admin | live |
| `get_location_custom_fields` | admin | live |
| `get_location_tags` | admin | live |
| `get_users` | admin | live |
| `get_user` | admin | live |
| `get_dealer_context` | system | live |
| `kb_list` | knowledge | live |
| `kb_read` | knowledge | live |
| `kb_write` | knowledge | live |
| `kb_search` | knowledge | live |
| `kb_delete` | knowledge | live |
| `jimmy_skills` | skills | live |
| `jimmy_run_skill` | skills | live |
| `jimmy_settings` | skills | live |
| `jimmy_setup` | skills | live |
| `memory_write` | memory | live |
| `memory_read` | memory | live |
| `memory_search` | memory | live |
| `memory_list` | memory | live |
| `memory_delete` | memory | live |

#### Queued Programs
| Program | Zone | What it does | Priority |
|---------|------|-------------|----------|
| `analytics_status` | telemetry | Event count, failure count, p95 latency, top tool/actor | P1 |
| `analytics_failures` | telemetry | Recent failures, error codes, scope issues | P1 |
| `analytics_usage` | telemetry | Tool call counts, top tools, success rate | P1 |
| `analytics_latency` | telemetry | Per-tool avg/p95/max latency | P1 |
| `prepare_context` | system | Bundle contact + memory + recent messages in one call | P2 |
| `bulk_tag` | contacts | Tag multiple contacts in one call | P3 |
| `bulk_update_stage` | pipeline | Move multiple deals in one call | P3 |
| `scope_check` | admin | Test each endpoint category, report what works/doesn't | P3 |
| `log_outcome` | telemetry | Tag a conversation with result (booked/sold/lost/no-reply) | P3 |

---

### Routines (Skills)
Each skill is a workflow that chains multiple programs.

#### Live Routines (7)
| Routine | Mode | What it does |
|---------|------|-------------|
| `morning-brief` | review | Daily pipeline + inbox + calendar snapshot |
| `triage` | plan | Classify inbound leads HOT/WARM/COLD |
| `pipeline-audit` | review | Flag stale deals, missing data, health % |
| `contact` | plan | Full contact profile + history + actions |
| `deal` | plan | Deep-dive on a specific opportunity |
| `follow-ups` | plan | Overdue tasks + pending follow-ups |
| `template` | — | Skeleton for building new skills |

#### Queued Routines
| Routine | Mode | What it does | Priority |
|---------|------|-------------|----------|
| `inbox` | plan | Unread/unanswered messages ranked by urgency | P1 |
| `send` | execute | Context-aware message drafting + send with confirmation | P1 |
| `book` | execute | End-to-end appointment booking (free slots → book → confirm) | P2 |
| `new-lead` | execute | Intake: create contact, tag, create opportunity, log note | P2 |
| `weekly-review` | review | Won/lost this week, velocity, follow-up completion, patterns | P2 |
| `inventory-search` | plan | Search GHL products/custom objects for vehicles | P3 |
| `send-template` | execute | Load a message template, fill variables, send | P3 |
| `health-check` | review | Proactive error/scope failure check at session start | P3 |

---

### Cycles (Sprints)

#### Cycle 1 — Telemetry & Inbox
Goal: Make the MCP observable and handle the most common dealer question.

- [ ] Wire `analytics_status` tool (logic exists in cli.py)
- [ ] Wire `analytics_failures` tool
- [ ] Wire `analytics_usage` tool
- [ ] Wire `analytics_latency` tool
- [ ] Build `inbox` skill
- [ ] Build `send` skill
- [ ] Test all against live GHL data

#### Cycle 2 — Workflows & Context
Goal: Reduce tool-call overhead, streamline common actions.

- [ ] Build `prepare_context` tool
- [ ] Build `book` skill
- [ ] Build `new-lead` skill
- [ ] Add message templates to KB
- [ ] Build `send-template` skill

#### Cycle 3 — Intelligence & Hardening
Goal: Close the feedback loop, add bulk ops, harden edge cases.

- [ ] Build `weekly-review` skill
- [ ] Build `log_outcome` tool
- [ ] Build `scope_check` tool
- [ ] Build `bulk_tag` tool
- [ ] Build `bulk_update_stage` tool
- [ ] Build `health-check` skill
- [ ] Session-level analytics grouping
- [ ] Daily delta comparisons in morning-brief

---

### Diagnostics (Bugs & Edge Cases)
Track issues found during hardening.

| ID | Description | Zone | Status |
|----|-------------|------|--------|
| — | (empty — add as discovered) | — | — |

---

### Uplink (Integrations & Infra)
External dependencies and configuration.

| System | Status | Notes |
|--------|--------|-------|
| GHL API (read scopes) | live | contacts, conversations, opportunities, calendars |
| GHL API (write scopes) | needs setup | contacts.write, conversations/message.write, opportunities.write, calendars.write, calendars/events.write |
| Supabase Auth | live | Dealer login |
| Supabase mcp_events | live | Telemetry table |
| Supabase knowledge_base | live | KB storage |
| Supabase memory | needs verify | Memory table existence |
| OAuth 2.1 (MCP auth) | live | PIN-based + client_credentials |
| Vercel deployment | live | Next.js app |

---

### Lightcycle (Changelog)
What shipped, when.

| Date | What shipped |
|------|-------------|
| 2026-04-12 | Marcus → Jimmy rename (system prompt, UI, all docs) |
| 2026-04-12 | Codebase architecture audit + The Grid created |

---
description: Live MCP testing session — call Jimmy's tools, inspect responses, catch issues before they hit prod
---

# Test Jimmy — Live MCP Inspection

You are entering a live testing session for the Jimmy GHL MCP server.

## What this is

A hands-on session where you directly call the MCP tools registered on the live server and inspect the results. Think of it like a powerglove — you manipulate the MCP, poke at every tool, and verify things work before pushing to prod.

## How to run the session

### Step 1: Health Check
Call a lightweight read-only tool to confirm the MCP server is reachable and authenticated:
- Call `mcp__ghl__get_location` — this should return Mikalyzed Auto Boutique's location data
- If this fails, stop and diagnose (auth token expired? server down? deployment broken?)

### Step 2: Tool Inventory
List what's available:
- Report the total number of GHL MCP tools currently registered
- List them grouped by category (contacts, conversations, pipelines, calendars, tasks, notes, users, knowledge base)
- Flag any tools that look broken, duplicated, or missing descriptions

### Step 3: Targeted Testing
Based on what Ethan asks, or if no specific request, run through these core workflows:

**Contacts:**
- `search_contacts` with a real query
- `get_contact` on a result
- Verify the response shape is clean and useful

**Pipeline:**
- `get_pipelines` to see pipeline structure
- `search_opportunities` to pull live deals
- Verify monetary values, stages, and contact links resolve

**Conversations:**
- `search_conversations` to find recent threads
- `get_conversation_messages` on one
- Verify message history is readable

**Calendar:**
- `list_calendars` and `get_calendar_events` for upcoming
- Verify dates and appointment details

**Knowledge Base:**
- `kb_list` and `kb_search` if populated

### Step 4: Report
After testing, give a clear summary:
- What worked
- What broke or returned unexpected data
- What's missing or could be better
- Any tools returning 403s (scope not enabled yet — just note it, don't nag)

## Rules
- Only use **read-only** tools unless Ethan explicitly says to test writes
- Never modify real contact/deal/conversation data without explicit permission
- If a tool returns a 403 scope error, log it once and move on
- Keep responses tight — show the actual data, not just "it worked"
- If Ethan says "test [specific thing]" — focus there, skip the rest

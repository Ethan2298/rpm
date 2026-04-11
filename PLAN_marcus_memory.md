# Marcus Memory & Sales Intelligence — Implementation Plan

## Context

RPM is an AI-powered SMS sales agent ("Marcus") for a collector car dealership. The backend is FastAPI + SQLite + Anthropic Claude API. The frontend is Vite + React + TypeScript. Twilio handles real SMS via webhook.

The founder's business partner Andrej wrote a sales philosophy doc that the system prompt already reflects well — rapport, reciprocity, buyer type adaptation, conversation phases, 40-minute follow-ups, deadline-based urgency. The problem is the system prompt TELLS Marcus to do these things, but the backend doesn't ENABLE him to actually do them. Marcus is currently stateless across conversations and purely reactive (only responds when texted).

This plan closes that gap in 3 phases.

---

## Current Architecture (do not restructure — build on top of this)

```
backend/
  config.py          — Settings class, loads from env
  database.py        — SQLite connection + create_tables()
  models.py          — Pydantic models for all entities
  main.py            — FastAPI app, routers, seed logic, dashboard/appointment endpoints
  ai/
    system_prompt.py — SYSTEM_PROMPT string (Marcus's personality + instructions)
    engine.py        — get_ai_response() — Claude API call with tool-use loop
    tools.py         — TOOLS list + execute_tool() dispatcher
    humanizer.py     — typing delays, message splitting, emoji/repetition checks
  routes/
    sms.py           — /api/sms/inbound (simulator), conversation CRUD
    twilio_webhook.py — /api/sms/incoming (real Twilio), background thread processing
    cars.py          — inventory CRUD
    leads.py         — leads CRUD
    conversations.py — conversation list/detail
  services/
    inventory.py     — search_cars(), get_car_by_id()
    leads.py         — create_lead(), update_lead(), get_lead_by_phone(), calculate_lead_score()
    appointments.py  — appointment CRUD
```

**Database tables:** cars, leads, appointments, conversations  
**AI model:** claude-sonnet-4-6 (in engine.py)  
**Current tools Marcus has:** search_inventory, get_car_details, save_lead_info, check_availability, book_appointment

---

## Phase 1 — Lead Context & Memory (highest priority)

**Problem:** When someone texts Marcus, he has no idea if he's talked to them before. The `phone_number` param is passed to `get_ai_response()` but never used. If a lead texts back days later with a new conversation, Marcus starts from zero — violating Andrej's "continuity & personalization" principle entirely.

### 1A. Add `buyer_type` and `conversation_summary` to leads schema

**File: `backend/database.py`** — ALTER the leads table creation:
- Add `buyer_type TEXT` column (values: 'emotional', 'analytical', 'mixed', or NULL)
- Add `conversation_summary TEXT` column (AI-generated summary of past interactions)

**File: `backend/models.py`** — Add `buyer_type` and `conversation_summary` fields to LeadCreate, LeadUpdate, and Lead models.

**File: `backend/services/leads.py`** — Add both fields to the `fields` list in `create_lead()`. Update `calculate_lead_score()` to give +1 for having a buyer_type identified.

### 1B. Add `phase` to conversations

**File: `backend/database.py`** — Add `phase TEXT DEFAULT 'hook'` to conversations table. Valid values: 'hook', 'qualify', 'close', 'wrap', 'follow_up'.

**File: `backend/models.py`** — Add `phase` field to Conversation model.

### 1C. Build lead context injection

**File: `backend/ai/context.py`** (NEW) — Create a function `build_lead_context(phone_number: str) -> str` that:

1. Looks up the lead by phone number using `get_lead_by_phone()`
2. Looks up ALL past conversations for that phone number (including closed ones)
3. Returns a formatted context block like:

```
<lead_context>
Returning lead. Name: Mike. Phone: +13055551234.
Buyer type: emotional. Budget: 60-80k range. Timeline: this_month.
Interested in: 1967 Chevrolet Camaro SS (car #3).
Previous conversation summary: "Mike reached out about the '67 Camaro SS two weeks ago. He's an emotional buyer — talked about wanting to take it to cars & coffee. Got excited about the numbers-matching 396 engine. He asked about price flexibility, we moved toward a call but he went quiet. Never got his email."
Current conversation phase: qualify.
Notes: financing, not cash. Lives in Coral Gables.
</lead_context>
```

If no lead exists for this phone, return an empty string (new customer, no context).

### 1D. Inject context into the AI engine

**File: `backend/ai/engine.py`** — Modify `get_ai_response()`:

1. Import `build_lead_context` from `backend.ai.context`
2. Before calling the Anthropic API, call `build_lead_context(phone_number)`
3. If context exists, prepend it to the system prompt: `prompt = (system_prompt or SYSTEM_PROMPT) + "\n\n" + lead_context`

This way Marcus gets the full picture of who he's talking to on every single API call, without needing a tool call.

### 1E. Expand `save_lead_info` tool

**File: `backend/ai/tools.py`** — Add these fields to the `save_lead_info` tool schema:
- `buyer_type` (string, enum: 'emotional', 'analytical', 'mixed') — "The customer's buyer type based on conversation signals"
- `conversation_phase` (string, enum: 'hook', 'qualify', 'close', 'wrap') — "Current phase of this sales conversation"

Update `execute_tool()` for `save_lead_info`:
- When `buyer_type` is provided, save it to the lead
- When `conversation_phase` is provided, update the conversation's `phase` field (requires also passing conversation_id into the tool context — add it as a parameter or inject it)

### 1F. Generate conversation summary on close

**File: `backend/ai/summarizer.py`** (NEW) — Create a function `summarize_conversation(messages: list[dict]) -> str` that:

1. Takes the full message history
2. Calls Claude (use claude-haiku-4-5-20251001 to keep it cheap/fast) with a prompt like:

```
Summarize this sales conversation in 2-3 sentences from the salesperson's perspective. 
Focus on: what the customer wanted, their buyer type, where the deal stands, 
what objections came up, and what the next step should be. 
Write it as notes for yourself to pick up the conversation later.
```

3. Returns the summary string

**File: `backend/routes/twilio_webhook.py`** — In `_handle_clear()`, before closing the conversation:
1. Load the conversation messages
2. Call `summarize_conversation()` 
3. Save the summary to the lead's `conversation_summary` field

**File: `backend/routes/sms.py`** — Add similar logic if there's ever a way to close conversations from the simulator.

---

## Phase 2 — Proactive Follow-Up System

**Problem:** Andrej's most tactical insight — if a customer doesn't respond within ~40 minutes after Marcus sends something (especially a video, photos, or info), Marcus should proactively reach out with a qualifying question or reciprocity ask. Currently the system is 100% reactive.

### 2A. Add follow-up tracking to conversations

**File: `backend/database.py`** — Add to conversations table:
- `follow_up_status TEXT DEFAULT 'none'` — values: 'none', 'pending', 'sent', 'not_needed'
- `follow_up_at TEXT` — ISO timestamp of when follow-up should trigger
- `follow_up_count INTEGER DEFAULT 0` — how many follow-ups have been sent (cap at 2-3)

### 2B. Set follow-up timers automatically

**File: `backend/routes/twilio_webhook.py`** and **`backend/routes/sms.py`** — After Marcus sends a response:

1. Calculate follow-up time: `now + 40 minutes`
2. Update the conversation: `follow_up_status = 'pending'`, `follow_up_at = <timestamp>`
3. When a NEW inbound message arrives from the customer, reset: `follow_up_status = 'none'`, `follow_up_at = NULL`

### 2C. Follow-up cron endpoint

**File: `backend/routes/follow_ups.py`** (NEW) — Create a new router with:

`POST /api/cron/follow-ups` (protected by a secret header like `Authorization: Bearer <CRON_SECRET>`):

1. Query conversations where `follow_up_status = 'pending'` AND `follow_up_at <= now` AND `follow_up_count < 3`
2. For each conversation:
   a. Load the message history
   b. Build lead context
   c. Append a synthetic system message to the conversation: `"[SYSTEM: The customer has not responded in 40+ minutes. Send a follow-up using one of these strategies: (1) a qualifying question, (2) a reciprocity ask ('if I get you X, is that the last thing you need?'), or (3) a value-add with an ask ('I can send over the docs — what's a good email?'). Keep it natural, one message only.]"`
   d. Call `get_ai_response()` with the updated history
   e. Send the response via Twilio using `_send_sms()`
   f. Update: `follow_up_status = 'sent'`, `follow_up_count += 1`
   g. Set a new `follow_up_at` for the next follow-up (e.g., 24 hours later for follow-up #2)

**File: `backend/main.py`** — Register the new router.

**Deployment:** Add a Vercel cron job (or external cron) that hits this endpoint every 5 minutes:
```json
// vercel.json — add to crons array
{ "path": "/api/cron/follow-ups", "schedule": "*/5 * * * *" }
```

### 2D. Follow-up awareness in system prompt

**File: `backend/ai/system_prompt.py`** — The prompt already has `<follow_up_rules>`. No major changes needed, but add a note in `<tool_use>`:

```
- When you send a message that invites a response (a video, photos, detailed info, a question), 
  the system will automatically schedule a follow-up if the customer doesn't respond within 40 minutes. 
  You don't need to manage this yourself — just focus on writing great messages.
```

---

## Phase 3 — Deadline Tracking & Conversation Intelligence

### 3A. Deadline tracking tool

**File: `backend/database.py`** — New table:
```sql
CREATE TABLE IF NOT EXISTS deadlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    lead_id INTEGER,
    description TEXT NOT NULL,
    deadline_at TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id),
    FOREIGN KEY (lead_id) REFERENCES leads(id)
);
```

**File: `backend/ai/tools.py`** — Add a `set_deadline` tool:
```
name: set_deadline
description: "Set a deadline for a customer commitment or follow-up. Use when you tell a customer you'll hold a car, get back to them by a certain time, or when they say they'll do something by a date."
input_schema:
  description: string (what the deadline is for)
  deadline_at: string (ISO date or datetime)
```

Add to execute_tool() — insert into deadlines table.

### 3B. Deadline-aware follow-ups

Modify the cron endpoint from Phase 2 to also check for approaching/passed deadlines:
- If a deadline is approaching (within 2 hours) and the conversation is stale, trigger a follow-up referencing the deadline
- If a deadline has passed, update its status and trigger a "checking in" message

### 3C. Lead score auto-update

**File: `backend/ai/tools.py`** — After every `save_lead_info` call, automatically recalculate and update the lead score using `calculate_lead_score()`.

---

## Important Constraints

1. **Do not change the system prompt's voice, tone, or personality.** It's already well-calibrated to Andrej's notes. Only add structural/contextual blocks.
2. **Do not restructure the existing file layout.** Add new files where noted, modify existing ones in place.
3. **Keep SQLite.** This is a prototype. Don't introduce Postgres, Redis, or any other infra.
4. **Use claude-haiku-4-5-20251001 for summarization** (cheap, fast). Keep claude-sonnet-4-6 for the main agent.
5. **The frontend TextSimulator should continue working unchanged.** All changes are backend-only for Phase 1 and 2. If follow-up messages need to appear in the simulator, that's a future concern.
6. **Don't break the Twilio webhook flow.** The background-thread pattern in twilio_webhook.py works — keep it.
7. **Every schema change needs a migration path.** Use `ALTER TABLE ADD COLUMN` with defaults so existing data isn't lost. Put migration logic in `create_tables()` using try/except or `PRAGMA table_info` checks.

---

## Build Order

Start with Phase 1 in this exact order: 1A → 1B → 1C → 1D → 1E → 1F. Each step is testable independently.

Test after 1D by sending a message in the TextSimulator, saving lead info via tool use, then starting a new conversation with the same phone number — Marcus should know who he's talking to.

Then Phase 2: 2A → 2B → 2C → 2D. Test by sending a message, waiting 40+ minutes (or temporarily setting the timer to 2 minutes for testing), and verifying a follow-up is generated.

Phase 3 can wait until Phase 1 and 2 are solid.

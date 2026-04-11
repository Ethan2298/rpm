# Marcus Agent Design — Engineering Spec

**Project:** RPM (Response & Pipeline Machine)
**For:** Forward-deployed engineer + Andrej / sales team alignment
**Date:** 2026-04-10

---

## What This Doc Is

This is the build spec for turning Marcus from a stateless chatbot into a memory-equipped, proactive sales agent. Everything here traces back to Andrej's sales philosophy — the system prompt already captures the *voice*, but the backend doesn't give Marcus the *tools* to actually execute the playbook.

Three phases. Each one unlocks a specific capability gap.

---

## What Exists Today

**Stack:** FastAPI + SQLite + Anthropic Claude (sonnet) + Twilio SMS. React/Vite frontend with a text simulator.

**Marcus can currently:**
- Respond to inbound texts with personality, tool use, and Andrej's voice
- Search inventory, pull car details, check availability
- Save lead info (name, phone, email, budget, timeline, notes)
- Book appointments (call, visit, video)

**Marcus cannot currently:**
- Remember who he's talked to before (no cross-conversation memory)
- Identify or adapt to buyer types at a system level (prompt says to, backend doesn't track it)
- Track what phase a conversation is in
- Follow up proactively when a customer goes quiet
- Set or enforce deadlines he commits to

That's the gap. Here's how each phase closes it.

---

## Phase 1 — Lead Context & Memory

### The Problem

Marcus is stateless across conversations. A customer texts about a '67 Camaro on Monday, goes quiet, texts back Thursday — Marcus has zero idea who they are. The `phone_number` param exists in `get_ai_response()` but is never used for anything. This directly breaks Andrej's "continuity & personalization" principle.

### What Gets Built

**1A. Schema additions to `leads` table**

Two new columns:

| Column | Type | Purpose |
|---|---|---|
| `buyer_type` | TEXT (nullable) | `'emotional'`, `'analytical'`, `'mixed'`, or NULL | 
| `conversation_summary` | TEXT (nullable) | AI-generated summary of past interactions |

These are `ALTER TABLE ADD COLUMN` migrations inside `create_tables()` — no data loss on existing rows. Both default to NULL.

Lead score calculation gets a +1 bump when `buyer_type` is identified (signals Marcus has read the customer well enough to classify them).

**Why this matters to sales:** Andrej's playbook says emotional buyers need stories and experiences, analytical buyers need comps and numbers. Right now Marcus guesses fresh every conversation. With this, he *knows* from message one.

---

**1B. Conversation phase tracking**

New column on `conversations`:

| Column | Type | Default |
|---|---|---|
| `phase` | TEXT | `'hook'` |

Valid values map directly to Andrej's conversation flow: `hook` → `qualify` → `close` → `wrap` → `follow_up`

**Why this matters to sales:** The dashboard can eventually show "12 conversations in qualify phase, 3 approaching close" — pipeline visibility that doesn't exist today. For the agent, it prevents Marcus from jumping phases (trying to book an appointment in message 2).

---

**1C. Lead context builder — `backend/ai/context.py` (new file)**

A single function: `build_lead_context(phone_number: str) -> str`

What it does:
1. Looks up the lead by phone (`get_lead_by_phone()`)
2. Pulls ALL past conversations for that number (including closed ones)
3. Returns a structured context block that gets prepended to the system prompt

Example output:
```
<lead_context>
Returning lead. Name: Mike. Phone: +13055551234.
Buyer type: emotional. Budget: 60-80k range. Timeline: this_month.
Interested in: 1967 Chevrolet Camaro SS (car #3).
Previous conversation summary: "Mike reached out about the '67 Camaro SS two weeks ago. 
Emotional buyer — talked about taking it to cars & coffee. Got excited about the 
numbers-matching 396. Asked about price flexibility, we pushed toward a call but he went 
quiet. Never got his email."
Current conversation phase: qualify.
Notes: financing, not cash. Lives in Coral Gables.
</lead_context>
```

If no lead exists for this phone number → returns empty string. New customer, clean slate.

**Why this matters to sales:** This is the single highest-impact change. It's the difference between "hey what can I help you with" and "hey Mike, you still thinking about that Camaro?" — which is exactly how Andrej says follow-ups should feel.

---

**1D. Context injection into `engine.py`**

Minimal change. In `get_ai_response()`:

1. Call `build_lead_context(phone_number)`
2. If it returns content, append it to the system prompt: `prompt = base_prompt + "\n\n" + lead_context`

No tool call needed. Marcus just *has* the context on every API call — like a salesperson glancing at their CRM before picking up the phone.

**Design decision:** Context goes into the system prompt, not as a tool. Tools require Marcus to decide to look someone up. We don't want that decision point — he should always have the context, automatically.

---

**1E. Expanded `save_lead_info` tool**

Two new fields in the tool schema:

| Field | Type | Values |
|---|---|---|
| `buyer_type` | string (enum) | `'emotional'`, `'analytical'`, `'mixed'` |
| `conversation_phase` | string (enum) | `'hook'`, `'qualify'`, `'close'`, `'wrap'` |

When Marcus calls `save_lead_info` with `buyer_type`, it persists to the lead record. When he passes `conversation_phase`, the conversation's `phase` column updates.

Marcus already uses `save_lead_info` incrementally as he learns things (that's in the prompt). Now he can also tag buyer type and phase transitions as he detects them, without any new tool.

**Why this matters to sales:** Buyer type classification happens naturally inside the conversation — Marcus picks up on signals ("I just picture myself cruising PCH in that thing" = emotional). Persisting it means the *next* conversation starts calibrated correctly.

---

**1F. Conversation summarization on close**

New file: `backend/ai/summarizer.py`

A function `summarize_conversation(messages: list[dict]) -> str` that:
1. Takes the full message history
2. Calls Claude Haiku (cheap, fast) with a focused prompt:
   > "Summarize this sales conversation in 2-3 sentences from the salesperson's perspective. Focus on: what the customer wanted, their buyer type signals, where the deal stands, what objections came up, and what the next step should be. Write it as notes for yourself to pick up the conversation later."
3. Returns the summary string

This runs when a conversation closes — the summary saves to the lead's `conversation_summary` field.

**Why this matters to sales:** This is Andrej's "continuity" principle turned into infrastructure. A human salesperson jots notes after a call. This is Marcus doing the same thing — except he never forgets to.

---

### Phase 1 Build Order & Testing

Build sequence: 1A → 1B → 1C → 1D → 1E → 1F (each step testable independently)

**Smoke test after 1D:**
1. Open TextSimulator, text Marcus from +15551234567
2. Have a conversation where Marcus learns your name, budget, interests
3. Marcus should call `save_lead_info` naturally during the convo
4. Close the conversation, start a new one from the same number
5. **Marcus should reference what he knows** — name, interests, prior context

If he starts from scratch, context injection isn't working.

---

## Phase 2 — Proactive Follow-Up System

### The Problem

Andrej's most tactical insight: if a customer doesn't respond within ~40 minutes after Marcus sends something meaningful (video, photos, detailed info), Marcus should proactively reach out. Not with "just checking in" — with a specific move: a qualifying question, a reciprocity ask, or a value-add with an ask.

Currently Marcus is 100% reactive. He only speaks when spoken to.

### What Gets Built

**2A. Follow-up tracking columns on `conversations`**

| Column | Type | Default | Purpose |
|---|---|---|---|
| `follow_up_status` | TEXT | `'none'` | `'none'`, `'pending'`, `'sent'`, `'not_needed'` |
| `follow_up_at` | TEXT | NULL | ISO timestamp — when the follow-up should fire |
| `follow_up_count` | INTEGER | 0 | How many follow-ups sent (capped at 3) |

---

**2B. Automatic follow-up timer logic**

Two trigger points in the SMS handling code (both `twilio_webhook.py` and `sms.py`):

**After Marcus sends a response:**
- Set `follow_up_status = 'pending'`
- Set `follow_up_at = now + 40 minutes`

**When a new inbound message arrives from the customer:**
- Reset `follow_up_status = 'none'`
- Clear `follow_up_at`

The customer responding cancels the timer. Simple.

---

**2C. Follow-up cron endpoint — `backend/routes/follow_ups.py` (new file)**

`POST /api/cron/follow-ups` (protected by `Authorization: Bearer <CRON_SECRET>`)

Logic:
1. Query conversations where `follow_up_status = 'pending'` AND `follow_up_at <= now` AND `follow_up_count < 3`
2. For each one:
   - Load message history
   - Build lead context (from Phase 1)
   - Inject a system-level nudge into the conversation:
     > `"[SYSTEM: The customer has not responded in 40+ minutes. Send ONE follow-up using one of these strategies: (1) a qualifying question, (2) a reciprocity ask ('if I get you X, is that the last thing you need?'), (3) a value-add with an ask ('I can send over the docs — what's a good email?'). Keep it natural, one message only.]"`
   - Call `get_ai_response()` with the updated history
   - Send the response via Twilio
   - Update: `follow_up_status = 'sent'`, `follow_up_count += 1`
   - Schedule next follow-up: follow-up #2 fires 24 hours later, #3 fires 48 hours later

**Cron runs every 5 minutes** — checks for any pending follow-ups past their trigger time.

**Why this matters to sales:** This is the single biggest behavioral shift. Andrej's philosophy explicitly calls out the 40-minute window as where deals are won or lost. A customer going quiet after receiving photos isn't disinterested — they're thinking. A well-timed nudge from Marcus converts that silence into a next step. Without this, every quiet customer is a dead lead until they happen to text back.

---

**2D. System prompt awareness**

Small addition to the `<tool_use>` section of the system prompt:

> "When you send a message that invites a response (a video, photos, detailed info, a question), the system will automatically schedule a follow-up if the customer doesn't respond within 40 minutes. You don't need to manage this yourself — just focus on writing great messages."

Marcus doesn't need to know the mechanics. He just needs to know follow-ups are handled so he doesn't try to build his own timing logic through the conversation.

---

### Phase 2 Testing

**Smoke test:**
1. Set the follow-up timer to 2 minutes (temporarily, for testing)
2. Text Marcus, have a short convo where he sends info about a car
3. Stop responding
4. After 2 minutes, the cron should fire and Marcus sends a follow-up
5. Verify: the follow-up is natural, references the conversation, and uses one of the three strategies
6. Verify: responding to the follow-up resets the timer

---

## Phase 3 — Deadline Tracking & Conversation Intelligence

### The Problem

Marcus makes commitments during conversations: "I'll hold it for you till Friday," "let me get you those docs by tomorrow." Currently there's no mechanism to track or enforce these. A broken deadline destroys trust — Andrej calls this out explicitly.

### What Gets Built

**3A. Deadlines table**

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

**3B. `set_deadline` tool for Marcus**

```
name: set_deadline
description: "Set a deadline for a customer commitment or follow-up. Use when you 
  tell a customer you'll hold a car, get back to them by a certain time, or when 
  they say they'll do something by a date."
input:
  description: string — what the deadline is for
  deadline_at: string — ISO date or datetime
```

Marcus calls this naturally when he makes or hears a commitment. "I'll hold it till Friday" → `set_deadline("Holding '67 Camaro for Mike", "2026-04-12")`.

**3C. Deadline-aware follow-ups**

The cron from Phase 2 gets extended:
- If a deadline is approaching (within 2 hours) and the conversation is stale → trigger a follow-up referencing the deadline
- If a deadline has passed → update status, trigger a "checking in" message

**3D. Auto lead score recalculation**

After every `save_lead_info` call, automatically recalculate the lead score. This keeps the dashboard's lead scoring live and accurate without manual intervention.

---

## Constraints (Non-Negotiable)

1. **Don't touch Marcus's voice.** The system prompt personality is calibrated. Only add structural/contextual blocks.
2. **Don't restructure the file layout.** Add new files where noted. Modify existing ones in place.
3. **Keep SQLite.** This is a prototype. No Postgres, no Redis.
4. **Use Haiku for summarization.** Sonnet for the main agent. Cost discipline.
5. **TextSimulator keeps working.** All changes are backend-only for Phase 1 and 2.
6. **Don't break the Twilio webhook.** The background-thread pattern in `twilio_webhook.py` works — keep it.
7. **Migrations are additive.** `ALTER TABLE ADD COLUMN` with defaults. No data loss.

---

## Priority & Sequencing

| Phase | Impact | Effort | Ship Order |
|---|---|---|---|
| Phase 1 — Memory | Highest | Medium | First |
| Phase 2 — Follow-ups | High | Medium | Second |
| Phase 3 — Deadlines | Medium | Low | Third |

Phase 1 is the foundation. Phase 2 is the behavior change. Phase 3 is polish. Don't start Phase 2 until Phase 1's smoke test passes. Phase 3 can wait until both are solid.

---

## What This Enables for Sales

Once all three phases ship, Marcus goes from "chatbot that knows about cars" to "salesperson with a CRM and a follow-up system." Specifically:

- **Returning customers feel recognized.** "Hey Mike, still thinking about that Camaro?" instead of "Hey, how can I help you?"
- **Silent leads get worked.** The 40-minute follow-up is Andrej's highest-conviction tactic — now it's automated.
- **Buyer type adaptation is persistent.** Marcus doesn't re-learn that someone is analytical every conversation.
- **Commitments are tracked.** "I'll hold it till Friday" actually means something in the system.
- **Pipeline is visible.** Phase tracking gives the dashboard real sales funnel data.

None of this changes how Marcus talks. It changes what he knows and when he acts.

# GoHighLevel MCP & API Reference — RPM Integration

## Quick Reference

| Item | Value |
|---|---|
| **API Base URL** | `https://services.leadconnectorhq.com` |
| **Official MCP Endpoint** | `https://services.leadconnectorhq.com/mcp/` |
| **MCP Transport** | HTTP Streamable |
| **Auth Method** | Private Integration Token (PIT) — Bearer token |
| **API Version Header** | `Version: 2021-07-28` |
| **Location ID** | `1QB8GTp5uOImt305H61U` |
| **Token Rotation** | Every 90 days recommended, 7-day grace period option |

---

## Authentication

Every API request requires these headers:

```
Authorization: Bearer <PIT_TOKEN>
Content-Type: application/json
Version: 2021-07-28
```

For sub-account operations, `locationId` is required — either as a query param or header depending on the endpoint.

**Token Rotation:**
- "Rotate and expire later" — 7-day overlap where both old and new tokens work
- "Rotate and expire now" — immediate invalidation (use if compromised)

**Docs:** https://marketplace.gohighlevel.com/docs/Authorization/PrivateIntegrationsToken/

---

## Current PIT Scopes (Read-Only)

These are the scopes currently enabled on our PIT (`pit-87dc...`):

### Enabled (readonly)
- `businesses.readonly`
- `campaigns.readonly`
- `contacts.readonly`
- `conversations.readonly`
- `conversations/message.readonly`
- `conversations/reports.readonly`
- `objects/schema.readonly`
- `objects/record.readonly`
- `associations.readonly`
- `associations/relation.readonly`
- `links.readonly`
- `locations/customValues.readonly`
- `locations/customFields.readonly`
- `locations/tags.readonly`
- `locations/templates.readonly`
- `courses.readonly`
- `medias.readonly`
- `funnels/redirect.readonly`
- `funnels/page.readonly`
- `funnels/funnel.readonly`
- `funnels/pagecount.readonly`
- `opportunities.readonly`
- `products.readonly`
- `socialplanner/account.readonly`
- `socialplanner/oauth.readonly`
- `socialplanner/csv.readonly`
- `socialplanner/category.readonly`
- `socialplanner/tag.readonly`
- `users.readonly`
- `workflows.readonly`
- `emails/builder.readonly`

### NOT Enabled — Needed for Marcus
- `contacts.write` — create/update contacts, add tags, notes, tasks
- `conversations/message.write` — **send SMS/email as dealership**
- `opportunities.write` — move deals through pipeline stages
- `calendars.readonly` — read calendar availability
- `calendars.write` — create/manage calendars
- `calendars/events.readonly` — read appointments
- `calendars/events.write` — **book appointments**

**Docs:** https://marketplace.gohighlevel.com/docs/Authorization/Scopes/index.html

---

## API Endpoints Verified Working

### Contacts
```
GET /contacts/?locationId={locationId}&limit={n}
```
Returns: `{ contacts: [...], meta: { total, nextPageUrl, currentPage, nextPage } }`

- **8,273 contacts** in Mikalyzed's account
- Supports pagination via `startAfter` and `startAfterId`
- Contact fields: id, firstName, lastName, email, phone, tags, source, attributions, customFields, dateAdded

### Conversations
```
GET /conversations/search?locationId={locationId}&limit={n}
```
Returns: `{ conversations: [...], total }`

- **8,242 conversations** total
- Each conversation has: id, contactId, fullName, lastMessageBody, lastMessageType, lastMessageDirection, unreadCount, type, tags
- Message types: TYPE_SMS, TYPE_EMAIL, TYPE_INSTAGRAM, TYPE_CALL, TYPE_ACTIVITY_OPPORTUNITY

### Conversation Messages
```
GET /conversations/{conversationId}/messages
```
Returns: `{ messages: { messages: [...], lastMessageId, nextPage } }`

- Full message thread with direction (inbound/outbound), body, timestamps, source (workflow/app), attachments
- Includes activity messages (opportunity created/deleted, etc.)

### Pipelines
```
GET /opportunities/pipelines?locationId={locationId}
```
Returns: `{ pipelines: [...] }`

**4 pipelines in Mikalyzed:**

#### 1. Car Sales (`njOhZcOsp8QGIGN0DVmL`)
| Position | Stage | Stage ID |
|---|---|---|
| 0 | New Inquiry | `34de63e2-f95e-4bdf-ba32-d9b224320c52` |
| 1 | Contacted (No Answer) | `5e2276ff-ebdb-4e99-8d49-c9fae7f76bff` |
| 2 | Contacted (No Answer 2) | `5ffd814b-d8ec-475e-a6ee-1f5e14441797` |
| 3 | Contacted (No Answer 3) | `45861b9e-e357-4003-ab9d-e37c5c044705` |
| 4 | Follow Up | `7d44f87a-9409-4faa-a0c0-1ed3013717ed` |
| 5 | Follow Up (Active) | `50e094c0-b302-47b3-adee-eb83bc40d214` |
| 6 | Qualified Lead | `6fefaca3-18eb-4153-b3c2-cb2ee9402464` |
| 7 | Appointment Set | `086e5d03-9929-47a5-bdfb-de8038342428` |
| 8 | Sold | `a9b3c397-521a-4214-86dc-e15538b27f55` |
| 9 | Dead Deal | `25fa06a5-c867-4a4c-a998-d97d82f6c4c4` |
| 10 | Collector | `4526d5e7-6e1c-4328-99d9-1ed88d922209` |

#### 2. Sold Car Leads (`XdHSMRkxIGVYCIJBsA1b`)
| Position | Stage | Stage ID |
|---|---|---|
| 0 | GMC Syclone | `118b466b-3740-4132-838c-bf6c5f6abd19` |
| 1 | S2000 | `4ffd2d6b-ac20-405d-bacb-2c51523dd4ee` |
| 2 | Contacted | `eed7917f-fec1-484a-886d-ac14db9ec440` |
| 3 | Proposal Sent | `e5a11f40-f2f3-45a3-a9e1-cb2c46f94b9c` |
| 4 | Closed | `db89472a-0b9f-489a-83ac-18b6c494a821` |

#### 3. The Reserve (`8V9PoVnRjHN1jshJPkPo`)
| Position | Stage | Stage ID |
|---|---|---|
| 0 | New Lead | `58a1fb1a-0213-4930-a3a1-66e4f5f85cb4` |
| 1 | Contacted (No Answer) | `de4984c6-c893-48e6-affe-6440d24e7270` |
| 2 | Contacted (No Answer 2) | `c2604f99-a6a4-4a23-8b22-4b10fb97505d` |
| 3 | Contacted (No Answer 3) | `5b314d57-ff5b-4b13-82ca-5b462b390282` |
| 4 | Follow Up | `c7064860-5f5e-4e97-addb-5d1045e428b3` |
| 5 | Tour Scheduled | `ae370995-7a27-4b45-803a-abaece99f9e6` |
| 6 | Quote Sent | `d824f485-7036-45c3-826f-10b897b2b428` |
| 7 | Ready to Move In | `ad0804f8-f54b-4bf0-a810-d871bda5cb74` |
| 8 | Vehicle Stored | `ea86d178-f610-48f2-bf5a-37cdd2dbf8b7` |
| 9 | Cancelled/Not Interested | `ecf697cf-4540-4a9a-8e92-6d5a8bd98557` |

#### 4. Vehicle Acquisition (`BUg4isB3fSjzPUiHt7kn`)
| Position | Stage | Stage ID |
|---|---|---|
| 0 | New Lead | `fca5c414-e3bd-4c0c-b787-6f8189d5df1c` |
| 1 | Contacted | `8c24e545-9c35-47e6-bf58-b5318c5cb642` |
| 2 | Negotiating | `c290e467-8428-4e89-b711-197180ca42ce` |
| 3 | Vehicle Purchased | `045faceb-c7cd-4c35-81b8-158ab94071bd` |
| 4 | Lost / Dead Deal | `c5ce7e02-6297-4e8c-995b-419dc17ae5d1` |
| 5 | Collector | `1343da6b-4f9f-4f09-afea-9520ffd4e051` |

---

## GHL Official MCP Server

**Endpoint:** `https://services.leadconnectorhq.com/mcp/`
**Transport:** HTTP Streamable (not SSE, not stdio)

### Client Configuration
```json
{
  "mcpServers": {
    "ghl-mcp": {
      "url": "https://services.leadconnectorhq.com/mcp/",
      "headers": {
        "Authorization": "Bearer pit-a9f10e20-8cb5-4618-9a14-41704f1b61ca",
        "locationId": "1QB8GTp5uOImt305H61U"
      }
    }
  }
}
```

### Available Tools (36)

**Contacts (8)**
- `contacts_get-contact` — Get one contact by ID
- `contacts_create-contact` — Create contact
- `contacts_update-contact` — Update contact
- `contacts_upsert-contact` — Create or update (match by email/phone)
- `contacts_get-contacts` — Get multiple contacts (paginated)
- `contacts_add-tags` — Add tags to contact
- `contacts_remove-tags` — Remove tags from contact
- `contacts_get-all-tasks` — Get all tasks for a contact

**Calendars (2)**
- `calendars_get-calendar-events` — Get events (requires userId, groupId, or calendarId)
- `calendars_get-appointment-notes` — Get appointment notes

**Conversations (3)**
- `conversations_search-conversation` — Search/filter/sort conversations
- `conversations_get-messages` — Get messages by conversation ID
- `conversations_send-a-new-message` — Send message (SMS/email)

**Opportunities (4)**
- `opportunities_search-opportunity` — Search opportunities
- `opportunities_get-pipelines` — Get all pipelines
- `opportunities_get-opportunity` — Get by ID
- `opportunities_update-opportunity` — Update opportunity

**Payments (2)**
- `payments_get-order-by-id` — Get order
- `payments_list-transactions` — List transactions (paginated)

**Social Media (6)**
- `social-media-posting_create-post` — Create multi-platform post
- `social-media-posting_edit-post` — Edit post
- `social-media-posting_get-post` — Get post
- `social-media-posting_get-posts` — Get multiple posts
- `social-media-posting_get-account` — Get connected accounts
- `social-media-posting_get-social-media-statistics` — Get analytics

**Blogs (6)**
- `blogs_get-blog-post` — Get blog posts
- `blogs_get-all-categories-by-location` — Get categories
- `blogs_create-blog-post` — Create blog post
- `blogs_update-blog-post` — Update blog post
- `blogs_check-url-slug-exists` — Validate slug
- `blogs_get-all-blog-authors-by-location` — Get authors
- `blogs_get-blogs` — Get blog sites

**Emails (2)**
- `emails_fetch-template` — Get email templates
- `emails_create-template` — Create email template

**Locations (2)**
- `locations_get-location` — Get sub-account details
- `locations_get-custom-fields` — Get custom field definitions

**Note:** Claude Desktop doesn't support HTTP Streamable transport yet — NPX bridge package coming. Works with Cursor, Windsurf, n8n (v1.104+).

**Docs:** https://marketplace.gohighlevel.com/docs/other/mcp/index.html

---

## Webhooks

### Signature Verification
- **Current:** `X-GHL-Signature` header — Ed25519
- **Legacy:** `X-WH-Signature` header — RSA-SHA256 (**deprecated July 1, 2026**)

**Ed25519 Public Key:**
```
MCowBQYDK2VwAyEAi2HR1srL4o18O8BRa7gVJY7G7bupbN3H9AwJrHCDiOg=
```

### Payload Structure
```json
{
  "type": "ContactCreate",
  "timestamp": "2025-01-28T14:35:00.000Z",
  "webhookId": "test-123",
  "data": { ... }
}
```

### Retry Behavior
- Only retries on **HTTP 429** (rate limit)
- 10 min between attempts + random jitter
- Max 6 attempts (~1 hour 10 min total)
- **5xx errors are NOT retried** — treated as permanent failure

### Circuit Breaker
- Evaluated every 3 days
- Triggers if >10,000 webhooks in window AND >=90% failure
- First flag: email warning
- Second flag: **pauses webhook delivery**
- Recovery: manual re-enable in marketplace dashboard

### Key Rules
- Return `200 OK` immediately, process async
- Deduplicate using `webhookId`
- Scopes can only be changed while app is in **draft** status

**Docs:** https://marketplace.gohighlevel.com/docs/webhook/WebhookIntegrationGuide/index.html

---

## Existing Community MCP Servers

| Repo | Tools | Notes |
|---|---|---|
| `BusyBee3333/Go-High-Level-MCP-2026-Complete` | 520+ | Kitchen sink, 32 stars, over-engineered |
| `drausal/gohighlevel-mcp` | Full | npm: `@drausal/gohighlevel-mcp`, auto-generated from OpenAPI spec |
| `robbyDAninja/7fa-ghl-mcp` | 34 | Lightweight, agency-focused |
| `Snack-JPG/ghl-mcp` | 50 | Published on npm |

---

## Live Data Snapshot (April 10, 2026)

- **Contacts:** 8,273 (mostly Instagram leads, some website leads)
- **Conversations:** 8,242
- **Active pipelines:** 4 (Car Sales, Sold Car Leads, The Reserve, Vehicle Acquisition)
- **Dealership numbers in GHL:** `+13056147396` (customer-facing), `+17866103716` (internal notifications)
- **Key users:** Andrej Perez (owner, `ed97nQUXNdbmes5uJEaS`), another user (`vzx23kFHvsS8mdemS3qo`)

---

## Architecture Decision: Custom MCP vs Official MCP

**Decision: Build custom RPM MCP on top of GHL API**

**Reasons:**
1. GHL's official MCP has 36 generic tools — we need ~10-15 RPM-specific tools with business logic baked in
2. Marcus needs live inventory queries mid-conversation — GHL AI can't do this
3. Marcus needs Andrej's sales methodology as a multi-layered persona — GHL AI uses a single prompt field
4. Marcus needs CRM context awareness during conversations — GHL AI can't read its own CRM mid-chat
5. Custom MCP = less token overhead, faster responses, tighter control
6. GHL stays as the operational backbone (CRM, pipelines, phone numbers, workflows)

---

## Key Documentation Links

- **API Overview:** https://marketplace.gohighlevel.com/docs/
- **Private Integration Tokens:** https://marketplace.gohighlevel.com/docs/Authorization/PrivateIntegrationsToken/
- **OAuth 2.0:** https://marketplace.gohighlevel.com/docs/Authorization/OAuth2.0/index.html
- **All Scopes:** https://marketplace.gohighlevel.com/docs/Authorization/Scopes/index.html
- **Official MCP:** https://marketplace.gohighlevel.com/docs/other/mcp/index.html
- **Webhooks:** https://marketplace.gohighlevel.com/docs/webhook/WebhookIntegrationGuide/index.html
- **GitHub API Docs Repo:** https://github.com/GoHighLevel/highlevel-api-docs
- **Developer Community:** https://developers.gohighlevel.com/

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from mcp_servers.ghl.client import GHLAPIError, GHLClient
from mcp_servers.ghl.config import GHL_LOCATION_ID
from diagnostics.telemetry import create_instrumented_mcp

KB_DIR = Path(__file__).parent / "knowledge_base"
SKILL_PREFIX = "skill-"
SKILL_SETTINGS_SLUG = "skill-settings"
SKILL_TEMPLATE_SLUG = "skill-template"
COMMANDS_DIR = Path(__file__).parent / "commands"

mcp = create_instrumented_mcp(
    "Jimmy — Dealership Operations",
    instructions=(
        "You are Jimmy, an AI dealership operator. "
        "FIRST ACTION: Call get_dealer_context before doing anything else. "
        "It returns your voice rules, formatting requirements, and reasoning patterns — apply them to every response. "
        "Use GHL tools for contacts, conversations, pipelines, opportunities, calendars, tasks, notes, and team management. "
        "Use kb_read/kb_search to look up dealership knowledge before answering domain questions. "
        "Use memory_search before interacting with a contact to recall prior context. "
        "Use memory_write to store important facts you learn (contact preferences, dealer instructions, patterns). "
        "If a tool returns a scope error, move on silently. Never surface scope issues to the user. "
        "Never explain how you work. Never summarize what you just did. Just do the thing and report the result."
    ),
)
_client: GHLClient | None = None


def get_client() -> GHLClient:
    global _client
    if _client is None:
        _client = GHLClient()
    return _client


class _ClientProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(get_client(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        setattr(get_client(), name, value)


client = _ClientProxy()

VALID_OPPORTUNITY_STATUSES = {"open", "won", "lost", "abandoned", "all"}
VALID_WRITE_OPPORTUNITY_STATUSES = VALID_OPPORTUNITY_STATUSES - {"all"}
VALID_MESSAGE_TYPES = {"SMS", "Email"}
def _success(data: dict[str, Any]) -> str:
    return json.dumps({"success": True, "data": data})


def _error(e: GHLAPIError, required_scope: str | None = None) -> str:
    error_payload: dict[str, Any] = {"status_code": e.status_code, "message": e.message}
    if required_scope and e.status_code in {401, 403}:
        error_payload["required_scope"] = required_scope
    return json.dumps({"success": False, "error": error_payload})


def _validation_error(message: str, *, field: str | None = None, allowed_values: list[str] | None = None) -> str:
    payload: dict[str, Any] = {"status_code": 400, "message": message}
    if field:
        payload["field"] = field
    if allowed_values:
        payload["allowed_values"] = allowed_values
    return json.dumps({"success": False, "error": payload})


def _normalize_limit(limit: int) -> int:
    if limit < 1:
        raise ValueError("limit must be between 1 and 100")
    return min(limit, 100)


def _validate_opportunity_status(status: str, *, allow_all: bool) -> None:
    if not status:
        return

    valid_statuses = VALID_OPPORTUNITY_STATUSES if allow_all else VALID_WRITE_OPPORTUNITY_STATUSES
    if status not in valid_statuses:
        raise ValueError(f"status must be one of: {', '.join(sorted(valid_statuses))}")


def _validate_message_type(message_type: str) -> None:
    if message_type not in VALID_MESSAGE_TYPES:
        raise ValueError(f"message_type must be one of: {', '.join(sorted(VALID_MESSAGE_TYPES))}")


def _parse_skill_doc(content: str) -> dict[str, Any]:
    """Extract structured metadata from a skill KB doc."""
    lines = content.splitlines()
    meta: dict[str, Any] = {"title": "", "skill": "", "description": "", "mode": "plan", "instructions": ""}
    instructions_start = None
    for i, line in enumerate(lines):
        if line.startswith("# ") and not meta["title"]:
            meta["title"] = line[2:].strip()
        elif line.startswith("Skill:"):
            meta["skill"] = line.split(":", 1)[1].strip()
        elif line.startswith("Description:"):
            meta["description"] = line.split(":", 1)[1].strip()
        elif line.startswith("Mode:"):
            meta["mode"] = line.split(":", 1)[1].strip()
        elif line.strip().startswith("## Instructions"):
            instructions_start = i + 1
    if instructions_start is not None:
        meta["instructions"] = "\n".join(lines[instructions_start:]).strip()
    return meta


def _parse_iso8601_datetime(value: str, *, field: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO 8601 datetime string") from exc

    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone offset, for example 2026-04-11T15:00:00Z")

    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _serialize_opportunity_summary(opportunity: dict[str, Any]) -> dict[str, Any]:
    contact = opportunity.get("contact")
    created_at = opportunity.get("dateAdded") or opportunity.get("createdAt")
    return {
        "id": opportunity.get("id"),
        "name": opportunity.get("name"),
        "status": opportunity.get("status"),
        "pipelineId": opportunity.get("pipelineId"),
        "pipelineStageId": opportunity.get("pipelineStageId"),
        "monetaryValue": opportunity.get("monetaryValue"),
        "contactId": contact.get("id") if isinstance(contact, dict) else opportunity.get("contactId"),
        "contactName": contact.get("name") if isinstance(contact, dict) else None,
        "dateAdded": created_at,
    }


@mcp.tool()
async def search_contacts(query: str = "", tag: str = "", limit: int = 20) -> str:
    """Search dealership contacts by name, phone, email, or tag.

    TRIGGER: When the user mentions a person's name, asks "who is...", wants to look someone up,
    or references a lead/customer. Don't ask — just search.

    Args:
        query: Free-text search across contact name, phone, or email.
        tag: Optional tag keyword to search for when narrowing to tagged contacts.
        limit: Maximum contacts to return. Must be between 1 and 100.
    """
    try:
        params = {"limit": _normalize_limit(limit)}
        if query:
            params["query"] = query
        if tag:
            params["query"] = tag

        data = await get_client().get("/contacts/", params)
        contacts = []
        for contact in data.get("contacts", []):
            contacts.append(
                {
                    "id": contact.get("id"),
                    "name": contact.get("contactName"),
                    "firstName": contact.get("firstName"),
                    "lastName": contact.get("lastName"),
                    "phone": contact.get("phone"),
                    "email": contact.get("email"),
                    "tags": contact.get("tags", []),
                    "source": contact.get("source"),
                    "dateAdded": contact.get("dateAdded"),
                }
            )

        total = data.get("meta", {}).get("total", 0)
        return _success({"contacts": contacts, "total": total, "has_more": total > len(contacts)})
    except ValueError as e:
        return _validation_error(str(e), field="limit")
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def get_contact(contact_id: str) -> str:
    """Get full details for a specific contact by their GHL contact ID.

    TRIGGER: After finding a contact via search_contacts, always pull full details
    before answering questions about them. The search result is a summary — this is the truth.

    Args:
        contact_id: The GHL contact ID returned by search_contacts.
    """
    try:
        data = await get_client().get(f"/contacts/{contact_id}")
        contact = data.get("contact", data)
        return _success(
            {
                "contact": {
                    "id": contact.get("id"),
                    "name": contact.get("contactName"),
                    "firstName": contact.get("firstName"),
                    "lastName": contact.get("lastName"),
                    "phone": contact.get("phone"),
                    "email": contact.get("email"),
                    "tags": contact.get("tags", []),
                    "source": contact.get("source"),
                    "city": contact.get("city"),
                    "state": contact.get("state"),
                    "country": contact.get("country"),
                    "dateAdded": contact.get("dateAdded"),
                    "customFields": contact.get("customFields", []),
                    "attributions": contact.get("attributions", []),
                    "dnd": contact.get("dnd"),
                    "assignedTo": contact.get("assignedTo"),
                }
            }
        )
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def search_conversations(contact_id: str = "", limit: int = 20) -> str:
    """Search conversations, optionally filtered by contact ID.

    TRIGGER: When the user asks about messages, recent conversations, what a contact said,
    or before sending any message (you need the conversation_id).

    Args:
        contact_id: Optional GHL contact ID to scope conversations to one contact.
        limit: Maximum conversations to return. Must be between 1 and 100.
    """
    try:
        params = {"limit": _normalize_limit(limit)}
        if contact_id:
            params["contactId"] = contact_id

        data = await get_client().get("/conversations/search", params)
        conversations = []
        for conversation in data.get("conversations", []):
            conversations.append(
                {
                    "id": conversation.get("id"),
                    "contactId": conversation.get("contactId"),
                    "fullName": conversation.get("fullName"),
                    "lastMessageBody": (conversation.get("lastMessageBody") or "")[:200],
                    "lastMessageType": conversation.get("lastMessageType"),
                    "lastMessageDirection": conversation.get("lastMessageDirection"),
                    "lastMessageDate": conversation.get("lastMessageDate"),
                    "unreadCount": conversation.get("unreadCount", 0),
                    "type": conversation.get("type"),
                    "phone": conversation.get("phone"),
                    "email": conversation.get("email"),
                    "tags": conversation.get("tags", []),
                }
            )

        total = data.get("total", 0)
        return _success({"conversations": conversations, "total": total, "has_more": total > len(conversations)})
    except ValueError as e:
        return _validation_error(str(e), field="limit")
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def get_conversation_messages(conversation_id: str) -> str:
    """Get the full message thread for a conversation in chronological order.

    Args:
        conversation_id: The GHL conversation ID returned by search_conversations.
    """
    try:
        data = await get_client().get(f"/conversations/{conversation_id}/messages")
        raw_messages = data.get("messages", {}).get("messages", [])
        messages = []
        for message in reversed(raw_messages):
            messages.append(
                {
                    "direction": message.get("direction", "unknown"),
                    "body": (message.get("body") or "")[:500],
                    "messageType": message.get("messageType"),
                    "dateAdded": message.get("dateAdded"),
                    "source": message.get("source"),
                    "from": message.get("from"),
                    "to": message.get("to"),
                    "status": message.get("status"),
                    "attachments": message.get("attachments", []),
                }
            )

        has_more = data.get("messages", {}).get("nextPage", False)
        return _success({"messages": messages, "count": len(messages), "has_more": has_more})
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def get_pipelines() -> str:
    """Get all sales pipelines and their stages.

    Use this to look up valid pipeline and stage IDs before creating, searching, or updating opportunities.
    """
    try:
        data = await get_client().get("/opportunities/pipelines")
        pipelines = []
        for pipeline in data.get("pipelines", []):
            stages = []
            for stage in pipeline.get("stages", []):
                stages.append(
                    {
                        "id": stage.get("id"),
                        "name": stage.get("name"),
                        "position": stage.get("position"),
                    }
                )
            pipelines.append({"id": pipeline.get("id"), "name": pipeline.get("name"), "stages": stages})

        return _success({"pipelines": pipelines})
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def search_opportunities(
    pipeline_id: str = "",
    stage_id: str = "",
    status: str = "",
    contact_id: str = "",
    limit: int = 20,
) -> str:
    """Search deals/opportunities.

    Args:
        pipeline_id: Optional pipeline ID from get_pipelines.
        stage_id: Optional stage ID from get_pipelines.
        status: Optional deal status. Allowed values are open, won, lost, abandoned, or all.
        contact_id: Optional GHL contact ID to scope opportunities to one contact.
        limit: Maximum opportunities to return. Must be between 1 and 100.
    """
    try:
        _validate_opportunity_status(status, allow_all=True)
        params = {"limit": _normalize_limit(limit)}
        if pipeline_id:
            params["pipelineId"] = pipeline_id
        if stage_id:
            params["pipelineStageId"] = stage_id
        if status:
            params["status"] = status
        if contact_id:
            params["contactId"] = contact_id

        data = await get_client().get("/opportunities/search", params)
        opportunities = [_serialize_opportunity_summary(opportunity) for opportunity in data.get("opportunities", [])]
        total = data.get("meta", {}).get("total", len(opportunities))
        return _success({"opportunities": opportunities, "total": total, "has_more": total > len(opportunities)})
    except ValueError as e:
        field = "status" if "status" in str(e) else "limit"
        allowed_values = sorted(VALID_OPPORTUNITY_STATUSES) if field == "status" else None
        return _validation_error(str(e), field=field, allowed_values=allowed_values)
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def get_opportunity(opportunity_id: str) -> str:
    """Get full details for a specific opportunity/deal by its ID.

    Args:
        opportunity_id: The GHL opportunity ID returned by search_opportunities or create_opportunity.
    """
    try:
        data = await get_client().get(f"/opportunities/{opportunity_id}")
        opportunity = data.get("opportunity", data)
        return _success({"opportunity": opportunity})
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def list_calendars() -> str:
    """List available calendars for the current location.

    Use this before booking an appointment to discover valid calendar IDs.
    """
    try:
        data = await get_client().get("/calendars/")
        calendars = []
        for calendar in data.get("calendars", data.get("data", [])):
            calendars.append(
                {
                    "id": calendar.get("id"),
                    "name": calendar.get("name"),
                    "description": calendar.get("description"),
                    "isActive": calendar.get("isActive"),
                    "groupId": calendar.get("groupId"),
                }
            )
        return _success({"calendars": calendars, "count": len(calendars)})
    except GHLAPIError as e:
        return _error(e, required_scope="calendars.readonly")


@mcp.tool()
async def get_location() -> str:
    """Get the current sub-account (location) details configured for this MCP server."""
    try:
        data = await get_client().get(f"/locations/{get_client().location_id}", params={})
        location = data.get("location", data)
        return _success({"location": location})
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def get_location_custom_fields() -> str:
    """Get custom field definitions for the current location.

    Use this when a workflow needs to discover which custom fields exist before reading or writing field values.
    """
    try:
        data = await get_client().get(f"/locations/{get_client().location_id}/customFields", params={})
        custom_fields = data.get("customFields", data.get("fields", data))
        return _success({"customFields": custom_fields})
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def get_location_tags() -> str:
    """Get all tags configured for the current location.

    Use this to discover valid tag names before adding or removing tags from contacts.
    """
    try:
        data = await get_client().get(f"/locations/{get_client().location_id}/tags", params={})
        tags = data.get("tags", data.get("locationTags", data))
        return _success({"tags": tags})
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def create_or_update_contact(
    first_name: str = "",
    last_name: str = "",
    phone: str = "",
    email: str = "",
    tags: list[str] | None = None,
    source: str = "",
) -> str:
    """Create a new contact or update an existing one matched by phone or email.

    Args:
        first_name: Optional contact first name.
        last_name: Optional contact last name.
        phone: Optional phone number. Strongly recommended for upsert matching.
        email: Optional email address. Strongly recommended for upsert matching.
        tags: Optional list of tags to assign during the upsert.
        source: Optional lead source string to attach to the contact.
    """
    try:
        if not any([first_name, last_name, phone, email, tags, source]):
            return _validation_error(
                "At least one contact field must be provided. In practice, phone or email should be included so GHL can match an existing contact.",
                field="phone",
            )

        body: dict[str, Any] = {"locationId": get_client().location_id}
        if first_name:
            body["firstName"] = first_name
        if last_name:
            body["lastName"] = last_name
        if phone:
            body["phone"] = phone
        if email:
            body["email"] = email
        if tags:
            body["tags"] = tags
        if source:
            body["source"] = source

        data = await get_client().post("/contacts/upsert", json=body)
        return _success({"contact": data.get("contact", data)})
    except GHLAPIError as e:
        return _error(e, required_scope="contacts.write")


@mcp.tool()
async def add_contact_tags(contact_id: str, tags: list[str]) -> str:
    """Add one or more tags to a contact.

    Args:
        contact_id: The GHL contact ID to update.
        tags: The tags to add to the contact.
    """
    try:
        data = await get_client().post(f"/contacts/{contact_id}/tags", json={"tags": tags})
        return _success({"tags": data.get("tags", tags)})
    except GHLAPIError as e:
        return _error(e, required_scope="contacts.write")


@mcp.tool()
async def remove_contact_tags(contact_id: str, tags: list[str]) -> str:
    """Remove one or more tags from a contact.

    Args:
        contact_id: The GHL contact ID to update.
        tags: The tags to remove from the contact.
    """
    try:
        data = await get_client().delete(f"/contacts/{contact_id}/tags", json={"tags": tags})
        return _success({"tags": data.get("tags", tags)})
    except GHLAPIError as e:
        return _error(e, required_scope="contacts.write")


@mcp.tool()
async def send_message(conversation_id: str, message_type: str, body: str, subject: str = "") -> str:
    """Send an SMS or email through an existing conversation.

    TRIGGER: When the user says "text them", "send a message", "follow up", "reach out",
    or anything implying outbound communication to a contact.

    BEFORE SENDING: Check kb_search for relevant guidelines (follow-up practices, objection handling).
    Apply tone-and-voice rules to the message body — it should sound human, not templated.
    Keep SMS under 3 sentences. Always include a next step or question.

    Args:
        conversation_id: The conversation ID. Look this up via search_conversations first.
        message_type: Allowed values are SMS or Email.
        body: Message text.
        subject: Email subject line. Required when message_type is Email.
    """
    try:
        _validate_message_type(message_type)
        if not body.strip():
            return _validation_error("body cannot be empty", field="body")
        if message_type == "Email" and not subject.strip():
            return _validation_error("subject is required when message_type is Email", field="subject")

        payload: dict[str, Any] = {
            "type": message_type,
            "message": body,
            "conversationId": conversation_id,
        }
        if message_type == "Email":
            payload["subject"] = subject

        data = await get_client().post("/conversations/messages", json=payload)
        return _success({"messageId": data.get("messageId"), "message": data})
    except ValueError as e:
        return _validation_error(str(e), field="message_type", allowed_values=sorted(VALID_MESSAGE_TYPES))
    except GHLAPIError as e:
        return _error(e, required_scope="conversations/message.write")


@mcp.tool()
async def create_opportunity(
    contact_id: str,
    pipeline_id: str,
    stage_id: str,
    title: str,
    monetary_value: float | None = None,
    status: str = "open",
) -> str:
    """Create a new opportunity/deal for a contact.

    TRIGGER: When a lead is qualified and ready to track as a deal, or the user says
    "create a deal", "add to pipeline", "start tracking this one".
    Always call get_pipelines first to get valid pipeline_id and stage_id values.

    Args:
        contact_id: The GHL contact ID the deal belongs to.
        pipeline_id: The destination pipeline ID from get_pipelines.
        stage_id: The destination stage ID from get_pipelines.
        title: Human-readable deal name shown in GHL.
        monetary_value: Optional deal value.
        status: Initial deal status. Allowed values are open, won, lost, or abandoned.
    """
    try:
        if not title.strip():
            return _validation_error("title cannot be empty", field="title")
        _validate_opportunity_status(status, allow_all=False)

        body: dict[str, Any] = {
            "locationId": get_client().location_id,
            "contactId": contact_id,
            "pipelineId": pipeline_id,
            "pipelineStageId": stage_id,
            "name": title,
            "status": status,
        }
        if monetary_value is not None:
            body["monetaryValue"] = monetary_value

        data = await get_client().post("/opportunities", json=body)
        opportunity = data.get("opportunity", data)
        return _success({"opportunity": opportunity})
    except ValueError as e:
        return _validation_error(str(e), field="status", allowed_values=sorted(VALID_WRITE_OPPORTUNITY_STATUSES))
    except GHLAPIError as e:
        return _error(e, required_scope="opportunities.write")


@mcp.tool()
async def update_opportunity(
    opportunity_id: str,
    stage_id: str = "",
    status: str = "",
    monetary_value: float | None = None,
    title: str = "",
) -> str:
    """Update a deal by changing its stage, status, value, or title.

    Args:
        opportunity_id: The GHL opportunity ID to update.
        stage_id: Optional stage ID from get_pipelines.
        status: Optional deal status. Allowed values are open, won, lost, or abandoned.
        monetary_value: Optional updated deal value.
        title: Optional new deal title.
    """
    try:
        _validate_opportunity_status(status, allow_all=False)
        if not any([stage_id, status, monetary_value is not None, title]):
            return _validation_error(
                "At least one update field must be provided: stage_id, status, monetary_value, or title.",
                field="opportunity_id",
            )

        body: dict[str, Any] = {}
        if stage_id:
            body["pipelineStageId"] = stage_id
        if status:
            body["status"] = status
        if monetary_value is not None:
            body["monetaryValue"] = monetary_value
        if title:
            body["name"] = title

        data = await get_client().put(f"/opportunities/{opportunity_id}", json=body)
        return _success({"opportunity": data})
    except ValueError as e:
        return _validation_error(str(e), field="status", allowed_values=sorted(VALID_WRITE_OPPORTUNITY_STATUSES))
    except GHLAPIError as e:
        return _error(e, required_scope="opportunities.write")


@mcp.tool()
async def book_appointment(
    calendar_id: str,
    contact_id: str,
    start_time: str,
    end_time: str,
    title: str = "",
    notes: str = "",
) -> str:
    """Book an appointment on a GHL calendar.

    Args:
        calendar_id: The calendar ID from list_calendars.
        contact_id: The GHL contact ID attending the appointment.
        start_time: Appointment start in ISO 8601 format with timezone offset.
        end_time: Appointment end in ISO 8601 format with timezone offset.
        title: Optional appointment title visible in GHL.
        notes: Optional appointment notes.
    """
    try:
        normalized_start = _parse_iso8601_datetime(start_time, field="start_time")
        normalized_end = _parse_iso8601_datetime(end_time, field="end_time")
        if normalized_end <= normalized_start:
            return _validation_error("end_time must be after start_time", field="end_time")

        body: dict[str, Any] = {
            "calendarId": calendar_id,
            "locationId": get_client().location_id,
            "contactId": contact_id,
            "startTime": normalized_start,
            "endTime": normalized_end,
        }
        if title:
            body["title"] = title
        if notes:
            body["notes"] = notes

        data = await get_client().post("/calendars/events/appointments", json=body)
        return _success({"appointment": data})
    except ValueError as e:
        field = "end_time" if "end_time" in str(e) else "start_time"
        return _validation_error(str(e), field=field)
    except GHLAPIError as e:
        return _error(e, required_scope="calendars/events.write")


# ── Contact edits ────────────────────────────────────────────────────────────


@mcp.tool()
async def update_contact(
    contact_id: str,
    first_name: str = "",
    last_name: str = "",
    phone: str = "",
    email: str = "",
    city: str = "",
    state: str = "",
    address: str = "",
    postal_code: str = "",
    assigned_to: str = "",
    dnd: bool | None = None,
    custom_fields: list[dict[str, str]] | None = None,
) -> str:
    """Update specific fields on an existing contact.

    Args:
        contact_id: The GHL contact ID to update.
        first_name: Optional new first name.
        last_name: Optional new last name.
        phone: Optional new phone number.
        email: Optional new email address.
        city: Optional city.
        state: Optional state.
        address: Optional street address.
        postal_code: Optional zip/postal code.
        assigned_to: Optional user ID to assign the contact to.
        dnd: Optional Do Not Disturb flag.
        custom_fields: Optional list of custom field updates, each with 'id' and 'field_value' keys.
    """
    try:
        body: dict[str, Any] = {}
        if first_name:
            body["firstName"] = first_name
        if last_name:
            body["lastName"] = last_name
        if phone:
            body["phone"] = phone
        if email:
            body["email"] = email
        if city:
            body["city"] = city
        if state:
            body["state"] = state
        if address:
            body["address1"] = address
        if postal_code:
            body["postalCode"] = postal_code
        if assigned_to:
            body["assignedTo"] = assigned_to
        if dnd is not None:
            body["dnd"] = dnd
        if custom_fields:
            body["customFields"] = custom_fields

        if not body:
            return _validation_error("At least one field must be provided to update.", field="contact_id")

        data = await get_client().put(f"/contacts/{contact_id}", json=body)
        return _success({"contact": data.get("contact", data)})
    except GHLAPIError as e:
        return _error(e, required_scope="contacts.write")


@mcp.tool()
async def delete_contact(contact_id: str) -> str:
    """Permanently delete a contact from the CRM.

    Args:
        contact_id: The GHL contact ID to delete.
    """
    try:
        data = await get_client().delete(f"/contacts/{contact_id}")
        return _success({"deleted": True, "contactId": contact_id})
    except GHLAPIError as e:
        return _error(e, required_scope="contacts.write")


# ── Contact notes ────────────────────────────────────────────────────────────


@mcp.tool()
async def get_contact_notes(contact_id: str) -> str:
    """Get all notes attached to a contact.

    Args:
        contact_id: The GHL contact ID.
    """
    try:
        data = await get_client().get(f"/contacts/{contact_id}/notes")
        notes = data.get("notes", [])
        return _success({"notes": notes, "count": len(notes)})
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def add_contact_note(contact_id: str, body: str) -> str:
    """Add a note to a contact record.

    Args:
        contact_id: The GHL contact ID.
        body: The note text.
    """
    try:
        if not body.strip():
            return _validation_error("body cannot be empty", field="body")
        data = await get_client().post(f"/contacts/{contact_id}/notes", json={"body": body})
        return _success({"note": data})
    except GHLAPIError as e:
        return _error(e, required_scope="contacts.write")


# ── Contact tasks ────────────────────────────────────────────────────────────


@mcp.tool()
async def get_contact_tasks(contact_id: str) -> str:
    """Get all tasks (follow-ups, to-dos) for a contact.

    Args:
        contact_id: The GHL contact ID.
    """
    try:
        data = await get_client().get(f"/contacts/{contact_id}/tasks")
        tasks = data.get("tasks", [])
        return _success({"tasks": tasks, "count": len(tasks)})
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def create_contact_task(
    contact_id: str,
    title: str,
    due_date: str,
    description: str = "",
    assigned_to: str = "",
) -> str:
    """Create a follow-up task for a contact.

    Args:
        contact_id: The GHL contact ID.
        title: Task title.
        due_date: Due date in ISO 8601 format with timezone offset.
        description: Optional task description.
        assigned_to: Optional user ID to assign the task to.
    """
    try:
        if not title.strip():
            return _validation_error("title cannot be empty", field="title")
        normalized_due = _parse_iso8601_datetime(due_date, field="due_date")

        body: dict[str, Any] = {"title": title, "dueDate": normalized_due}
        if description:
            body["description"] = description
        if assigned_to:
            body["assignedTo"] = assigned_to

        data = await get_client().post(f"/contacts/{contact_id}/tasks", json=body)
        return _success({"task": data})
    except ValueError as e:
        return _validation_error(str(e), field="due_date")
    except GHLAPIError as e:
        return _error(e, required_scope="contacts.write")


# ── Conversation edits ───────────────────────────────────────────────────────


@mcp.tool()
async def update_conversation(
    conversation_id: str,
    starred: bool | None = None,
    unread_count: int | None = None,
) -> str:
    """Update a conversation's metadata — star it, or mark read/unread.

    Args:
        conversation_id: The GHL conversation ID.
        starred: Optional — set True to star, False to unstar.
        unread_count: Optional — set to 0 to mark as read, or a positive int to mark unread.
    """
    try:
        body: dict[str, Any] = {}
        if starred is not None:
            body["starred"] = starred
        if unread_count is not None:
            body["unreadCount"] = unread_count

        if not body:
            return _validation_error("At least one field must be provided: starred or unread_count.", field="conversation_id")

        data = await get_client().put(f"/conversations/{conversation_id}", json=body)
        return _success({"conversation": data})
    except GHLAPIError as e:
        return _error(e, required_scope="conversations.write")


# ── Calendar reads ───────────────────────────────────────────────────────────


@mcp.tool()
async def get_calendar_events(
    calendar_id: str = "",
    start_time: str = "",
    end_time: str = "",
    user_id: str = "",
    group_id: str = "",
) -> str:
    """Get calendar events/appointments.

    At least one of calendar_id, user_id, or group_id is required.

    Args:
        calendar_id: Optional calendar ID to scope events.
        start_time: Optional start of range in ISO 8601 format with timezone.
        end_time: Optional end of range in ISO 8601 format with timezone.
        user_id: Optional user ID to scope events to one team member.
        group_id: Optional calendar group ID.
    """
    try:
        if not any([calendar_id, user_id, group_id]):
            return _validation_error(
                "At least one of calendar_id, user_id, or group_id is required.",
                field="calendar_id",
            )

        params: dict[str, Any] = {}
        if calendar_id:
            params["calendarId"] = calendar_id
        if user_id:
            params["userId"] = user_id
        if group_id:
            params["groupId"] = group_id
        if start_time:
            params["startTime"] = _parse_iso8601_datetime(start_time, field="start_time")
        if end_time:
            params["endTime"] = _parse_iso8601_datetime(end_time, field="end_time")

        data = await get_client().get("/calendars/events", params)
        events = data.get("events", data.get("data", []))
        return _success({"events": events, "count": len(events)})
    except ValueError as e:
        field = "end_time" if "end_time" in str(e) else "start_time"
        return _validation_error(str(e), field=field)
    except GHLAPIError as e:
        return _error(e, required_scope="calendars/events.readonly")


@mcp.tool()
async def get_calendar_free_slots(
    calendar_id: str,
    start_date: str,
    end_date: str,
    timezone: str = "America/New_York",
) -> str:
    """Get available time slots for a calendar. Use before booking to find open times.

    Args:
        calendar_id: The calendar ID from list_calendars.
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        timezone: IANA timezone string. Defaults to America/New_York (Miami).
    """
    try:
        params: dict[str, Any] = {
            "startDate": start_date,
            "endDate": end_date,
            "timezone": timezone,
            "calendarId": calendar_id,
        }
        data = await get_client().get(f"/calendars/{calendar_id}/free-slots", params)
        slots = data.get("slots", data.get("data", data))
        return _success({"slots": slots})
    except GHLAPIError as e:
        return _error(e, required_scope="calendars.readonly")


# ── Calendar edits ───────────────────────────────────────────────────────────


@mcp.tool()
async def update_appointment(
    event_id: str,
    calendar_id: str,
    start_time: str = "",
    end_time: str = "",
    title: str = "",
    notes: str = "",
    status: str = "",
) -> str:
    """Reschedule or modify an existing appointment.

    Args:
        event_id: The GHL event/appointment ID.
        calendar_id: The calendar ID the appointment belongs to.
        start_time: Optional new start time in ISO 8601 with timezone.
        end_time: Optional new end time in ISO 8601 with timezone.
        title: Optional new appointment title.
        notes: Optional updated notes.
        status: Optional status update (confirmed, cancelled, showed, noshow).
    """
    try:
        body: dict[str, Any] = {"calendarId": calendar_id}
        if start_time:
            body["startTime"] = _parse_iso8601_datetime(start_time, field="start_time")
        if end_time:
            body["endTime"] = _parse_iso8601_datetime(end_time, field="end_time")
        if title:
            body["title"] = title
        if notes:
            body["notes"] = notes
        if status:
            body["status"] = status

        if len(body) <= 1:
            return _validation_error("At least one field must be provided to update.", field="event_id")

        data = await get_client().put(f"/calendars/events/appointments/{event_id}", json=body)
        return _success({"appointment": data})
    except ValueError as e:
        field = "end_time" if "end_time" in str(e) else "start_time"
        return _validation_error(str(e), field=field)
    except GHLAPIError as e:
        return _error(e, required_scope="calendars/events.write")


@mcp.tool()
async def delete_appointment(event_id: str) -> str:
    """Cancel and delete an appointment.

    Args:
        event_id: The GHL event/appointment ID to delete.
    """
    try:
        data = await get_client().delete(f"/calendars/events/appointments/{event_id}")
        return _success({"deleted": True, "eventId": event_id})
    except GHLAPIError as e:
        return _error(e, required_scope="calendars/events.write")


# ── Opportunity edits ────────────────────────────────────────────────────────


@mcp.tool()
async def delete_opportunity(opportunity_id: str) -> str:
    """Permanently delete an opportunity/deal.

    Args:
        opportunity_id: The GHL opportunity ID to delete.
    """
    try:
        data = await get_client().delete(f"/opportunities/{opportunity_id}")
        return _success({"deleted": True, "opportunityId": opportunity_id})
    except GHLAPIError as e:
        return _error(e, required_scope="opportunities.write")


# ── Users ────────────────────────────────────────────────────────────────────


@mcp.tool()
async def get_users() -> str:
    """Get all team members/users for the current location.

    Use this to look up user IDs for assigning contacts, tasks, or appointments.
    """
    try:
        data = await get_client().get("/users/")
        users = []
        for user in data.get("users", []):
            users.append(
                {
                    "id": user.get("id"),
                    "name": user.get("name"),
                    "firstName": user.get("firstName"),
                    "lastName": user.get("lastName"),
                    "email": user.get("email"),
                    "phone": user.get("phone"),
                    "role": user.get("role") or user.get("type"),
                }
            )
        return _success({"users": users, "count": len(users)})
    except GHLAPIError as e:
        return _error(e, required_scope="users.readonly")


@mcp.tool()
async def get_user(user_id: str) -> str:
    """Get details for a specific team member.

    Args:
        user_id: The GHL user ID.
    """
    try:
        data = await get_client().get(f"/users/{user_id}")
        return _success({"user": data})
    except GHLAPIError as e:
        return _error(e, required_scope="users.readonly")

# ---------------------------------------------------------------------------
# Knowledge Base tools — hybrid: Supabase for writes, bundled files as fallback
# ---------------------------------------------------------------------------


def _kb_slug(name: str) -> str:
    """Turn a human name into a filename slug, preserving '/' as folder separators."""
    parts = name.split("/")
    slugged = []
    for part in parts:
        s = re.sub(r"[^a-z0-9]+", "-", part.strip().lower()).strip("-")
        if s:
            slugged.append(s)
    if not slugged:
        raise ValueError("name must contain at least one alphanumeric character")
    return "/".join(slugged)


def _kb_doc_to_dict(path: Path) -> dict[str, Any]:
    """Read a KB markdown file into a dict with name, slug, and content."""
    content = path.read_text(encoding="utf-8")
    # Extract title from first H1 if present
    title = path.stem.replace("-", " ").title()
    for line in content.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    # Build slug as relative path from KB_DIR without .md extension
    rel = path.relative_to(KB_DIR).with_suffix("")
    slug = rel.as_posix()
    return {
        "slug": slug,
        "title": title,
        "content": content,
        "size_bytes": len(content.encode("utf-8")),
    }


def _kb_title_from_content(content: str, slug: str) -> str:
    """Extract title from first H1 heading, or derive from slug."""
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return slug.rsplit("/", 1)[-1].replace("-", " ").title()


_KB_TABLE = "knowledge_base"


def _kb_supabase_configured() -> bool:
    return bool(
        os.getenv("SUPABASE_URL", "").strip()
        and os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )


def _kb_headers() -> dict[str, str]:
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"].strip()
    return {
        "Authorization": f"Bearer {key}",
        "apikey": key,
        "Content-Type": "application/json",
    }


def _kb_base_url() -> str:
    return os.environ["SUPABASE_URL"].strip().rstrip("/")


def _kb_location_id() -> str:
    return GHL_LOCATION_ID or "default"


async def _kb_sb_list() -> list[dict[str, Any]]:
    params = [
        ("select", "slug,title,content,size_bytes"),
        ("location_id", f"eq.{_kb_location_id()}"),
        ("order", "slug.asc"),
    ]
    async with httpx.AsyncClient(base_url=_kb_base_url(), headers=_kb_headers(), timeout=15.0) as c:
        r = await c.get(f"/rest/v1/{_KB_TABLE}", params=params)
        r.raise_for_status()
        return r.json()


async def _kb_sb_read(slug: str) -> dict[str, Any] | None:
    params = [
        ("select", "slug,title,content,size_bytes"),
        ("location_id", f"eq.{_kb_location_id()}"),
        ("slug", f"eq.{slug}"),
        ("limit", "1"),
    ]
    async with httpx.AsyncClient(base_url=_kb_base_url(), headers=_kb_headers(), timeout=15.0) as c:
        r = await c.get(f"/rest/v1/{_KB_TABLE}", params=params)
        r.raise_for_status()
        rows = r.json()
        return rows[0] if rows else None


async def _kb_sb_upsert(slug: str, title: str, content: str) -> dict[str, Any]:
    row = {
        "location_id": _kb_location_id(),
        "slug": slug,
        "title": title,
        "content": content,
        "size_bytes": len(content.encode("utf-8")),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    headers = _kb_headers()
    headers["Prefer"] = "return=representation,resolution=merge-duplicates"
    async with httpx.AsyncClient(base_url=_kb_base_url(), headers=headers, timeout=15.0) as c:
        r = await c.post(f"/rest/v1/{_KB_TABLE}", json=row)
        r.raise_for_status()
        rows = r.json()
        return rows[0] if rows else row


async def _kb_sb_delete(slug: str) -> bool:
    params = [
        ("location_id", f"eq.{_kb_location_id()}"),
        ("slug", f"eq.{slug}"),
    ]
    headers = _kb_headers()
    headers["Prefer"] = "return=representation"
    async with httpx.AsyncClient(base_url=_kb_base_url(), headers=headers, timeout=15.0) as c:
        r = await c.delete(f"/rest/v1/{_KB_TABLE}", params=params)
        r.raise_for_status()
        return len(r.json()) > 0


def _bundled_kb_docs() -> dict[str, dict[str, Any]]:
    docs: dict[str, dict[str, Any]] = {}
    if KB_DIR.exists():
        for path in sorted(KB_DIR.rglob("*.md")):
            doc = _kb_doc_to_dict(path)
            docs[doc["slug"]] = doc
    return docs


def _merge_kb(bundled: dict[str, dict[str, Any]], sb_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = dict(bundled)
    for row in sb_rows:
        merged[row["slug"]] = {
            "slug": row["slug"],
            "title": row["title"],
            "content": row["content"],
            "size_bytes": row["size_bytes"],
        }
    return sorted(merged.values(), key=lambda d: d["slug"])


async def _kb_all_docs() -> list[dict[str, Any]]:
    bundled = _bundled_kb_docs()
    sb_rows = await _kb_sb_list() if _kb_supabase_configured() else []
    return _merge_kb(bundled, sb_rows)


async def _kb_read_one(slug: str) -> dict[str, Any] | None:
    if _kb_supabase_configured():
        row = await _kb_sb_read(slug)
        if row:
            return row
    path = (KB_DIR / f"{slug}.md").resolve()
    if path.is_relative_to(KB_DIR.resolve()) and path.exists():
        return _kb_doc_to_dict(path)
    return None


TONE_SLUG = "tone-and-voice"


@mcp.tool()
async def get_dealer_context() -> str:
    """Load Jimmy's tone, formatting rules, and reasoning patterns for this dealer.

    **CALL THIS BEFORE YOUR FIRST RESPONSE IN EVERY CONVERSATION.**

    Returns:
    - Voice and formatting rules you MUST follow in all responses
    - Reasoning patterns for how to think about dealership tasks
    - A summary of available knowledge base documents so you know what reference material exists

    After calling this tool, apply the returned rules to every subsequent message.
    Do not summarize or repeat the rules back — just absorb and follow them.
    """
    # Load tone document (Supabase first, bundled fallback)
    tone_doc = await _kb_read_one(TONE_SLUG)
    if tone_doc:
        tone_content = tone_doc["content"]
    else:
        tone_content = (
            "No tone document found. Defaults: be direct, concise, and helpful. "
            "Avoid corporate filler. Lead with answers."
        )

    # Build KB index
    all_docs = await _kb_all_docs()
    available_docs = [
        {"slug": d["slug"], "title": d["title"]}
        for d in all_docs
        if d["slug"] != TONE_SLUG
    ]

    return _success({
        "tone_and_voice": tone_content,
        "available_knowledge": available_docs,
        "knowledge_count": len(available_docs),
        "instructions": (
            "Apply the tone_and_voice rules to ALL responses in this conversation. "
            "These are not suggestions — they are requirements. "
            "When a question touches a topic covered by available_knowledge, "
            "use kb_read to load the relevant doc before answering. "
            "Never guess when you can look it up."
        ),
    })


@mcp.tool()
async def kb_list(folder: str = "") -> str:
    """List all knowledge base documents.

    Returns titles, slugs, and sizes of all docs in the dealership knowledge base.
    Use slugs with kb_read to fetch full content.
    """
    all_docs = await _kb_all_docs()

    if folder:
        prefix = folder.rstrip("/") + "/"
        all_docs = [d for d in all_docs if d["slug"].startswith(prefix) or d["slug"] == folder.rstrip("/")]

    docs = [{"slug": d["slug"], "title": d["title"], "size_bytes": d["size_bytes"]} for d in all_docs]
    child_folders: set[str] = set()
    folder_prefix = (folder.rstrip("/") + "/") if folder else ""
    for d in all_docs:
        slug = d["slug"]
        if "/" in slug:
            parts = slug.split("/")
            if folder:
                remaining = slug[len(folder_prefix):] if slug.startswith(folder_prefix) else None
                if remaining and "/" in remaining:
                    child_folders.add(folder_prefix + remaining.split("/")[0])
            else:
                child_folders.add(parts[0])

    return _success({
        "documents": docs,
        "folders": sorted(child_folders),
        "count": len(docs),
        "folder": folder or "/",
    })


@mcp.tool()
async def kb_read(slug: str) -> str:
    """Read a knowledge base document by its slug.

    Args:
        slug: The document slug from kb_list (e.g. "lead-qualification", "follow-up-practices").
    """
    doc = await _kb_read_one(slug)
    if doc:
        return _success({"document": doc})
    return _validation_error(f"Document '{slug}' not found. Use kb_list to see available documents.", field="slug")


@mcp.tool()
async def kb_write(name: str, content: str) -> str:
    """Create or update a knowledge base document.

    Use this to capture dealership knowledge — sales practices, inventory notes,
    customer personas, objection handling, or anything the team wants the agent to know.

    Args:
        name: Human-readable document name (e.g. "Classic Car Buyers"). Gets slugified for the filename.
        content: Full markdown content for the document. Start with a # heading matching the name.
    """
    if not content.strip():
        return _validation_error("content cannot be empty", field="content")
    if not _kb_supabase_configured():
        return _validation_error("Knowledge base storage is not configured.", field="name")
    try:
        slug = _kb_slug(name)
    except ValueError as e:
        return _validation_error(str(e), field="name")

    title = _kb_title_from_content(content, slug)
    existing = await _kb_read_one(slug)
    row = await _kb_sb_upsert(slug, title, content)
    doc = {
        "slug": row.get("slug", slug),
        "title": row.get("title", title),
        "content": row.get("content", content),
        "size_bytes": row.get("size_bytes", len(content.encode("utf-8"))),
    }
    return _success({
        "document": doc,
        "action": "updated" if existing else "created",
    })


@mcp.tool()
async def kb_search(query: str, folder: str = "") -> str:
    """Search knowledge base documents by keyword.

    Searches document titles and content for the query string. Case-insensitive.

    Args:
        query: Search term to find across all knowledge base documents.
    """
    if not query.strip():
        return _validation_error("query cannot be empty", field="query")

    all_docs = await _kb_all_docs()
    if folder:
        prefix = folder.rstrip("/") + "/"
        all_docs = [d for d in all_docs if d["slug"].startswith(prefix)]

    query_lower = query.lower()
    results = []
    for doc in all_docs:
        if query_lower in doc["content"].lower() or query_lower in doc["title"].lower() or query_lower in doc["slug"].lower():
            snippets = []
            for line in doc["content"].splitlines():
                if query_lower in line.lower() and line.strip():
                    snippets.append(line.strip()[:200])
                    if len(snippets) >= 3:
                        break
            results.append({"slug": doc["slug"], "title": doc["title"], "snippets": snippets})

    return _success({"results": results, "count": len(results), "query": query})


@mcp.tool()
async def kb_delete(slug: str) -> str:
    """Delete a knowledge base document.

    Args:
        slug: The document slug from kb_list.
    """
    if not _kb_supabase_configured():
        return _validation_error("Knowledge base storage is not configured.", field="slug")

    deleted = await _kb_sb_delete(slug)
    if deleted:
        return _success({"deleted": slug, "title": slug.rsplit("/", 1)[-1].replace("-", " ").title()})

    # Bundled files can't be deleted
    path = (KB_DIR / f"{slug}.md").resolve()
    if path.is_relative_to(KB_DIR.resolve()) and path.exists():
        return _validation_error(f"'{slug}' is a default document and cannot be deleted.", field="slug")

    return _validation_error(f"Document '{slug}' not found. Use kb_list to see available documents.", field="slug")


# ── Jimmy skill system ──────────────────────────────────────────────────────


@mcp.tool()
async def jimmy_skills() -> str:
    """List all available Jimmy skills with descriptions and modes.

    Returns skill names, slugs, descriptions, and interaction modes.
    Use jimmy_run_skill with a skill slug to execute one.
    """
    KB_DIR.mkdir(parents=True, exist_ok=True)
    skills = []
    for path in sorted(KB_DIR.glob(f"{SKILL_PREFIX}*.md")):
        slug = path.stem
        if slug in (SKILL_SETTINGS_SLUG, SKILL_TEMPLATE_SLUG):
            continue
        content = path.read_text(encoding="utf-8")
        meta = _parse_skill_doc(content)
        skills.append({
            "slug": slug,
            "name": meta["title"],
            "skill_id": meta["skill"],
            "description": meta["description"],
            "mode": meta["mode"],
        })
    return _success({"skills": skills, "count": len(skills)})


@mcp.tool()
async def jimmy_run_skill(skill_slug: str) -> str:
    """Load a skill's full instructions for execution.

    Call this to run a specific skill. The response contains instructions
    to follow step-by-step using the available MCP tools.

    Args:
        skill_slug: The skill slug (e.g. "skill-triage" or just "triage").
    """
    path = KB_DIR / f"{skill_slug}.md"
    if not path.exists():
        prefixed = KB_DIR / f"{SKILL_PREFIX}{skill_slug}.md"
        if prefixed.exists():
            path = prefixed
            skill_slug = f"{SKILL_PREFIX}{skill_slug}"
        else:
            return _validation_error(
                f"Skill '{skill_slug}' not found. Use jimmy_skills to see available skills.",
                field="skill_slug",
            )
    content = path.read_text(encoding="utf-8")
    meta = _parse_skill_doc(content)
    return _success({
        "slug": skill_slug,
        "name": meta["title"],
        "skill_id": meta["skill"],
        "description": meta["description"],
        "mode": meta["mode"],
        "instructions": meta["instructions"],
        "mode_hint": {
            "plan": "Present findings and ask before taking actions.",
            "execute": "Act on each step directly, report results.",
            "review": "Read-only analysis. Do not modify any data.",
        }.get(meta["mode"], "Follow the instructions as written."),
    })


@mcp.tool()
async def jimmy_settings(action: str = "read", content: str = "") -> str:
    """Read or write Jimmy user settings.

    Settings include default modes, pinned skills, and mode overrides.

    Args:
        action: "read" to get current settings, "write" to update them.
        content: Full markdown content for settings (only used with action="write").
    """
    if action not in ("read", "write"):
        return _validation_error("action must be 'read' or 'write'", field="action")

    KB_DIR.mkdir(parents=True, exist_ok=True)
    path = KB_DIR / f"{SKILL_SETTINGS_SLUG}.md"

    if action == "read":
        if not path.exists():
            return _success({"exists": False, "settings": None, "hint": "Run jimmy_setup to initialize default settings."})
        doc = _kb_doc_to_dict(path)
        return _success({"exists": True, "settings": doc})

    if not content.strip():
        return _validation_error("content cannot be empty for write action", field="content")
    path.write_text(content, encoding="utf-8")
    doc = _kb_doc_to_dict(path)
    return _success({"settings": doc, "action": "updated"})


@mcp.tool()
async def jimmy_setup() -> str:
    """Run the Jimmy guided setup flow.

    Verifies GHL connection, confirms default skills are installed,
    and returns local command files for Claude to write to .claude/commands/.

    Call this when first setting up Jimmy or to check current state.
    """
    # Step 1: Verify connection
    connection: dict[str, Any] = {"connected": False, "location_name": None, "error": None}
    try:
        data = await get_client().get(
            f"/locations/{get_client().location_id}", params={}
        )
        location = data.get("location", data)
        connection["connected"] = True
        connection["location_name"] = location.get("name")
    except GHLAPIError as e:
        connection["error"] = e.message
    except Exception as e:
        connection["error"] = str(e)

    # Step 2: Check which skills exist
    KB_DIR.mkdir(parents=True, exist_ok=True)
    installed_skills = []
    missing_skills = []
    for path in sorted(KB_DIR.glob(f"{SKILL_PREFIX}*.md")):
        slug = path.stem
        if slug in (SKILL_SETTINGS_SLUG, SKILL_TEMPLATE_SLUG):
            continue
        content = path.read_text(encoding="utf-8")
        meta = _parse_skill_doc(content)
        installed_skills.append({
            "slug": slug,
            "name": meta["title"],
            "description": meta["description"],
            "mode": meta["mode"],
        })

    # Step 3: Check settings and template
    settings_exists = (KB_DIR / f"{SKILL_SETTINGS_SLUG}.md").exists()
    template_exists = (KB_DIR / f"{SKILL_TEMPLATE_SLUG}.md").exists()

    # Step 4: Load command files to return
    commands = []
    if COMMANDS_DIR.exists():
        for cmd_path in sorted(COMMANDS_DIR.glob("*.md")):
            commands.append({
                "filename": cmd_path.name,
                "content": cmd_path.read_text(encoding="utf-8"),
            })

    return _success({
        "connection": connection,
        "skills": installed_skills,
        "skills_count": len(installed_skills),
        "settings_exists": settings_exists,
        "template_exists": template_exists,
        "commands": commands,
        "instructions": (
            "Setup complete. For each item in the 'commands' array, "
            "write the file to .claude/commands/<filename>. "
            "Then tell the user what was installed and how to use /jimmy."
        ),
    })


# ── Memory — persistent facts across sessions ──────────────────────────────

_MEMORY_TABLE = "memory"


def _mem_headers() -> dict[str, str]:
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"].strip()
    return {
        "Authorization": f"Bearer {key}",
        "apikey": key,
        "Content-Type": "application/json",
    }


def _mem_base_url() -> str:
    return os.environ["SUPABASE_URL"].strip().rstrip("/")


def _mem_configured() -> bool:
    return bool(
        os.getenv("SUPABASE_URL", "").strip()
        and os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )


@mcp.tool()
async def memory_write(
    key: str,
    content: str,
    category: str = "fact",
    related_contact_id: str = "",
) -> str:
    """Store a persistent memory that Jimmy can recall in future sessions.

    Use this when you learn something worth remembering:
    - A contact's preferences ("prefers text over email", "interested in F-150s")
    - Dealer instructions ("always check inventory before quoting")
    - Patterns you notice ("leads from Instagram rarely have phone numbers")
    - Session context that should persist ("Andrej is on vacation until April 18")

    Keys should be descriptive and unique — they act as the memory's identity.
    Writing to an existing key updates it.

    Args:
        key: Descriptive identifier for the memory (e.g. "contact:john-smith:vehicle-preference").
        content: The fact, preference, or context to remember.
        category: One of: contact, preference, fact, session, dealer.
        related_contact_id: Optional GHL contact ID if this memory is about a specific person.
    """
    if not _mem_configured():
        return _validation_error("Memory storage is not configured.", field="key")
    if not key.strip():
        return _validation_error("key cannot be empty", field="key")
    if not content.strip():
        return _validation_error("content cannot be empty", field="content")
    valid_categories = {"contact", "preference", "fact", "session", "dealer"}
    if category not in valid_categories:
        return _validation_error(
            f"category must be one of: {', '.join(sorted(valid_categories))}",
            field="category",
            allowed_values=sorted(valid_categories),
        )

    row: dict[str, Any] = {
        "location_id": _kb_location_id(),
        "key": key.strip(),
        "content": content.strip(),
        "category": category,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if related_contact_id:
        row["related_contact_id"] = related_contact_id

    headers = _mem_headers()
    headers["Prefer"] = "return=representation,resolution=merge-duplicates"
    try:
        async with httpx.AsyncClient(base_url=_mem_base_url(), headers=headers, timeout=15.0) as c:
            r = await c.post(f"/rest/v1/{_MEMORY_TABLE}", json=row)
            r.raise_for_status()
            rows = r.json()
            saved = rows[0] if rows else row
        return _success({
            "memory": {
                "key": saved.get("key", key),
                "content": saved.get("content", content),
                "category": saved.get("category", category),
                "related_contact_id": saved.get("related_contact_id"),
            },
            "action": "saved",
        })
    except httpx.HTTPStatusError as e:
        return _validation_error(f"Failed to write memory: {e.response.text}", field="key")


@mcp.tool()
async def memory_read(key: str) -> str:
    """Read a specific memory by its key.

    Args:
        key: The memory key to retrieve.
    """
    if not _mem_configured():
        return _validation_error("Memory storage is not configured.", field="key")

    params = [
        ("select", "key,content,category,related_contact_id,created_at,updated_at"),
        ("location_id", f"eq.{_kb_location_id()}"),
        ("key", f"eq.{key}"),
        ("limit", "1"),
    ]
    try:
        async with httpx.AsyncClient(base_url=_mem_base_url(), headers=_mem_headers(), timeout=15.0) as c:
            r = await c.get(f"/rest/v1/{_MEMORY_TABLE}", params=params)
            r.raise_for_status()
            rows = r.json()
        if not rows:
            return _validation_error(f"Memory '{key}' not found.", field="key")
        return _success({"memory": rows[0]})
    except httpx.HTTPStatusError as e:
        return _validation_error(f"Failed to read memory: {e.response.text}", field="key")


@mcp.tool()
async def memory_search(
    query: str = "",
    category: str = "",
    related_contact_id: str = "",
    limit: int = 20,
) -> str:
    """Search Jimmy's memories by keyword, category, or contact.

    TRIGGER: Before interacting with a contact, search their memories.
    Before answering domain questions, check for relevant dealer/preference memories.

    Args:
        query: Free-text search across memory keys and content.
        category: Optional filter by category (contact, preference, fact, session, dealer).
        related_contact_id: Optional GHL contact ID to find memories about a specific person.
        limit: Maximum memories to return (1-100).
    """
    if not _mem_configured():
        return _validation_error("Memory storage is not configured.", field="query")
    if not any([query, category, related_contact_id]):
        return _validation_error("At least one of query, category, or related_contact_id is required.", field="query")

    params: list[tuple[str, str]] = [
        ("select", "key,content,category,related_contact_id,created_at,updated_at"),
        ("location_id", f"eq.{_kb_location_id()}"),
        ("order", "updated_at.desc"),
        ("limit", str(min(max(limit, 1), 100))),
    ]
    if category:
        params.append(("category", f"eq.{category}"))
    if related_contact_id:
        params.append(("related_contact_id", f"eq.{related_contact_id}"))
    if query:
        # Use Postgres full-text search
        params.append(("search_vector", f"fts.{query}"))

    try:
        async with httpx.AsyncClient(base_url=_mem_base_url(), headers=_mem_headers(), timeout=15.0) as c:
            r = await c.get(f"/rest/v1/{_MEMORY_TABLE}", params=params)
            r.raise_for_status()
            rows = r.json()
        return _success({"memories": rows, "count": len(rows), "query": query or None})
    except httpx.HTTPStatusError as e:
        return _validation_error(f"Failed to search memories: {e.response.text}", field="query")


@mcp.tool()
async def memory_list(category: str = "", limit: int = 50) -> str:
    """List all memories, optionally filtered by category.

    Args:
        category: Optional filter by category (contact, preference, fact, session, dealer).
        limit: Maximum memories to return (1-100).
    """
    if not _mem_configured():
        return _validation_error("Memory storage is not configured.", field="category")

    params: list[tuple[str, str]] = [
        ("select", "key,content,category,related_contact_id,updated_at"),
        ("location_id", f"eq.{_kb_location_id()}"),
        ("order", "updated_at.desc"),
        ("limit", str(min(max(limit, 1), 100))),
    ]
    if category:
        params.append(("category", f"eq.{category}"))

    try:
        async with httpx.AsyncClient(base_url=_mem_base_url(), headers=_mem_headers(), timeout=15.0) as c:
            r = await c.get(f"/rest/v1/{_MEMORY_TABLE}", params=params)
            r.raise_for_status()
            rows = r.json()
        return _success({"memories": rows, "count": len(rows)})
    except httpx.HTTPStatusError as e:
        return _validation_error(f"Failed to list memories: {e.response.text}", field="category")


@mcp.tool()
async def memory_delete(key: str) -> str:
    """Delete a specific memory by its key.

    Args:
        key: The memory key to delete.
    """
    if not _mem_configured():
        return _validation_error("Memory storage is not configured.", field="key")

    params = [
        ("location_id", f"eq.{_kb_location_id()}"),
        ("key", f"eq.{key}"),
    ]
    headers = _mem_headers()
    headers["Prefer"] = "return=representation"
    try:
        async with httpx.AsyncClient(base_url=_mem_base_url(), headers=headers, timeout=15.0) as c:
            r = await c.delete(f"/rest/v1/{_MEMORY_TABLE}", params=params)
            r.raise_for_status()
            rows = r.json()
        if not rows:
            return _validation_error(f"Memory '{key}' not found.", field="key")
        return _success({"deleted": key})
    except httpx.HTTPStatusError as e:
        return _validation_error(f"Failed to delete memory: {e.response.text}", field="key")


if __name__ == "__main__":
    mcp.run(transport="stdio")

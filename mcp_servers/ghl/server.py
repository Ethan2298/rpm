import json
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_servers.ghl.client import GHLAPIError, GHLClient

mcp = FastMCP(
    "GoHighLevel CRM",
    instructions="MCP server for GoHighLevel CRM - contacts, conversations, pipelines, opportunities, calendars, tasks, notes, and team management for Mikalyzed Auto Boutique. NOTE: Some write scopes are not yet enabled on the PIT token. If a tool returns a 403 with a required_scope hint, silently note it and move on — do NOT repeatedly warn the user or suggest they enable scopes. They already know and will enable them when ready.",
)
client = GHLClient()

VALID_OPPORTUNITY_STATUSES = {"open", "won", "lost", "abandoned", "all"}
VALID_WRITE_OPPORTUNITY_STATUSES = VALID_OPPORTUNITY_STATUSES - {"all"}
VALID_MESSAGE_TYPES = {"SMS", "Email"}
SCOPE_HINTS = {
    "contacts.write": "Enable the contacts.write scope on the GHL Private Integration token.",
    "conversations.write": "Enable the conversations.write scope on the GHL Private Integration token.",
    "conversations/message.write": "Enable the conversations/message.write scope on the GHL Private Integration token.",
    "opportunities.write": "Enable the opportunities.write scope on the GHL Private Integration token.",
    "calendars.readonly": "Enable the calendars.readonly scope on the GHL Private Integration token.",
    "calendars/events.readonly": "Enable the calendars/events.readonly scope on the GHL Private Integration token.",
    "calendars/events.write": "Enable the calendars/events.write scope on the GHL Private Integration token.",
    "users.readonly": "Enable the users.readonly scope on the GHL Private Integration token.",
    "workflows.readonly": "Enable the workflows.readonly scope on the GHL Private Integration token.",
}


def _success(data: dict[str, Any]) -> str:
    return json.dumps({"success": True, "data": data})


def _error(e: GHLAPIError, required_scope: str | None = None) -> str:
    error_payload: dict[str, Any] = {"status_code": e.status_code, "message": e.message}
    if required_scope and e.status_code in {401, 403}:
        error_payload["required_scope"] = required_scope
        error_payload["resolution"] = SCOPE_HINTS.get(required_scope, f"Enable the {required_scope} scope on the GHL Private Integration token.")
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

        data = await client.get("/contacts/", params)
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

    Args:
        contact_id: The GHL contact ID returned by search_contacts.
    """
    try:
        data = await client.get(f"/contacts/{contact_id}")
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

    Args:
        contact_id: Optional GHL contact ID to scope conversations to one contact.
        limit: Maximum conversations to return. Must be between 1 and 100.
    """
    try:
        params = {"limit": _normalize_limit(limit)}
        if contact_id:
            params["contactId"] = contact_id

        data = await client.get("/conversations/search", params)
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
        data = await client.get(f"/conversations/{conversation_id}/messages")
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
        data = await client.get("/opportunities/pipelines")
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

        data = await client.get("/opportunities/search", params)
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
        data = await client.get(f"/opportunities/{opportunity_id}")
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
        data = await client.get("/calendars/")
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
        data = await client.get(f"/locations/{client.location_id}", params={})
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
        data = await client.get(f"/locations/{client.location_id}/customFields", params={})
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
        data = await client.get(f"/locations/{client.location_id}/tags", params={})
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

        body: dict[str, Any] = {"locationId": client.location_id}
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

        data = await client.post("/contacts/upsert", json=body)
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
        data = await client.post(f"/contacts/{contact_id}/tags", json={"tags": tags})
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
        data = await client.delete(f"/contacts/{contact_id}/tags", json={"tags": tags})
        return _success({"tags": data.get("tags", tags)})
    except GHLAPIError as e:
        return _error(e, required_scope="contacts.write")


@mcp.tool()
async def send_message(conversation_id: str, message_type: str, body: str, subject: str = "") -> str:
    """Send an SMS or email through an existing conversation.

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

        data = await client.post("/conversations/messages", json=payload)
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
            "locationId": client.location_id,
            "contactId": contact_id,
            "pipelineId": pipeline_id,
            "pipelineStageId": stage_id,
            "name": title,
            "status": status,
        }
        if monetary_value is not None:
            body["monetaryValue"] = monetary_value

        data = await client.post("/opportunities", json=body)
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

        data = await client.put(f"/opportunities/{opportunity_id}", json=body)
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
            "locationId": client.location_id,
            "contactId": contact_id,
            "startTime": normalized_start,
            "endTime": normalized_end,
        }
        if title:
            body["title"] = title
        if notes:
            body["notes"] = notes

        data = await client.post("/calendars/events/appointments", json=body)
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

        data = await client.put(f"/contacts/{contact_id}", json=body)
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
        data = await client.delete(f"/contacts/{contact_id}")
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
        data = await client.get(f"/contacts/{contact_id}/notes")
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
        data = await client.post(f"/contacts/{contact_id}/notes", json={"body": body})
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
        data = await client.get(f"/contacts/{contact_id}/tasks")
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

        data = await client.post(f"/contacts/{contact_id}/tasks", json=body)
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

        data = await client.put(f"/conversations/{conversation_id}", json=body)
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

        data = await client.get("/calendars/events", params)
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
        data = await client.get(f"/calendars/{calendar_id}/free-slots", params)
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

        data = await client.put(f"/calendars/events/appointments/{event_id}", json=body)
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
        data = await client.delete(f"/calendars/events/appointments/{event_id}")
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
        data = await client.delete(f"/opportunities/{opportunity_id}")
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
        data = await client.get("/users/")
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
        data = await client.get(f"/users/{user_id}")
        return _success({"user": data})
    except GHLAPIError as e:
        return _error(e, required_scope="users.readonly")


if __name__ == "__main__":
    mcp.run(transport="stdio")

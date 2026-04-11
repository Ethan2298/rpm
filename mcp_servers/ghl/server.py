import json

from mcp.server.fastmcp import FastMCP

from mcp_servers.ghl.client import GHLClient, GHLAPIError

mcp = FastMCP("GoHighLevel CRM", instructions="MCP server for GoHighLevel CRM — contacts, conversations, pipelines, opportunities, and appointments for Mikalyzed Auto Boutique.")
client = GHLClient()


def _error(e: GHLAPIError) -> str:
    return json.dumps({"error": True, "status_code": e.status_code, "message": e.message})


# ─── READ TOOLS ──────────────────────────────────────────────────────────────


@mcp.tool()
async def search_contacts(query: str = "", tag: str = "", limit: int = 20) -> str:
    """Search dealership contacts by name, phone, email, or tag. Returns up to 20 contacts by default."""
    try:
        params = {"limit": min(limit, 100)}
        if query:
            params["query"] = query
        if tag:
            params["query"] = tag  # GHL's search endpoint handles tag filtering via query
        data = await client.get("/contacts/", params)
        contacts = []
        for c in data.get("contacts", []):
            contacts.append({
                "id": c.get("id"),
                "name": c.get("contactName"),
                "firstName": c.get("firstName"),
                "lastName": c.get("lastName"),
                "phone": c.get("phone"),
                "email": c.get("email"),
                "tags": c.get("tags", []),
                "source": c.get("source"),
                "dateAdded": c.get("dateAdded"),
            })
        total = data.get("meta", {}).get("total", 0)
        return json.dumps({"contacts": contacts, "total": total, "has_more": total > len(contacts)})
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def get_contact(contact_id: str) -> str:
    """Get full details for a specific contact by their GHL contact ID."""
    try:
        data = await client.get(f"/contacts/{contact_id}")
        c = data.get("contact", data)
        return json.dumps({
            "id": c.get("id"),
            "name": c.get("contactName"),
            "firstName": c.get("firstName"),
            "lastName": c.get("lastName"),
            "phone": c.get("phone"),
            "email": c.get("email"),
            "tags": c.get("tags", []),
            "source": c.get("source"),
            "city": c.get("city"),
            "state": c.get("state"),
            "country": c.get("country"),
            "dateAdded": c.get("dateAdded"),
            "customFields": c.get("customFields", []),
            "attributions": c.get("attributions", []),
            "dnd": c.get("dnd"),
            "assignedTo": c.get("assignedTo"),
        })
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def search_conversations(contact_id: str = "", limit: int = 20) -> str:
    """Search conversations. Optionally filter by contact ID. Returns recent conversations with last message preview."""
    try:
        params = {"limit": min(limit, 100)}
        if contact_id:
            params["contactId"] = contact_id
        data = await client.get("/conversations/search", params)
        convos = []
        for c in data.get("conversations", []):
            convos.append({
                "id": c.get("id"),
                "contactId": c.get("contactId"),
                "fullName": c.get("fullName"),
                "lastMessageBody": (c.get("lastMessageBody") or "")[:200],
                "lastMessageType": c.get("lastMessageType"),
                "lastMessageDirection": c.get("lastMessageDirection"),
                "lastMessageDate": c.get("lastMessageDate"),
                "unreadCount": c.get("unreadCount", 0),
                "type": c.get("type"),
                "phone": c.get("phone"),
                "email": c.get("email"),
                "tags": c.get("tags", []),
            })
        total = data.get("total", 0)
        return json.dumps({"conversations": convos, "total": total, "has_more": total > len(convos)})
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def get_conversation_messages(conversation_id: str) -> str:
    """Get the full message thread for a conversation. Returns messages in chronological order."""
    try:
        data = await client.get(f"/conversations/{conversation_id}/messages")
        raw_msgs = data.get("messages", {}).get("messages", [])
        messages = []
        for m in reversed(raw_msgs):  # API returns newest first, we want chronological
            messages.append({
                "direction": m.get("direction", "unknown"),
                "body": (m.get("body") or "")[:500],
                "messageType": m.get("messageType"),
                "dateAdded": m.get("dateAdded"),
                "source": m.get("source"),
                "from": m.get("from"),
                "to": m.get("to"),
                "status": m.get("status"),
                "attachments": m.get("attachments", []),
            })
        has_more = data.get("messages", {}).get("nextPage", False)
        return json.dumps({"messages": messages, "count": len(messages), "has_more": has_more})
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def get_pipelines() -> str:
    """Get all sales pipelines and their stages. Use this to look up pipeline/stage IDs before searching or updating opportunities."""
    try:
        data = await client.get("/opportunities/pipelines")
        pipelines = []
        for p in data.get("pipelines", []):
            stages = []
            for s in p.get("stages", []):
                stages.append({
                    "id": s.get("id"),
                    "name": s.get("name"),
                    "position": s.get("position"),
                })
            pipelines.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "stages": stages,
            })
        return json.dumps({"pipelines": pipelines})
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def search_opportunities(pipeline_id: str = "", stage_id: str = "", status: str = "", contact_id: str = "", limit: int = 20) -> str:
    """Search deals/opportunities. Filter by pipeline, stage, contact, or status (open/won/lost/abandoned)."""
    try:
        params = {"limit": min(limit, 100)}
        if pipeline_id:
            params["pipelineId"] = pipeline_id
        if stage_id:
            params["pipelineStageId"] = stage_id
        if status:
            params["status"] = status
        if contact_id:
            params["contactId"] = contact_id
        data = await client.get("/opportunities/search", params)
        opps = []
        for o in data.get("opportunities", []):
            opps.append({
                "id": o.get("id"),
                "name": o.get("name"),
                "status": o.get("status"),
                "pipelineId": o.get("pipelineId"),
                "pipelineStageId": o.get("pipelineStageId"),
                "monetaryValue": o.get("monetaryValue"),
                "contactId": o.get("contact", {}).get("id") if isinstance(o.get("contact"), dict) else o.get("contactId"),
                "contactName": o.get("contact", {}).get("name") if isinstance(o.get("contact"), dict) else None,
                "dateAdded": o.get("dateAdded"),
            })
        total = data.get("meta", {}).get("total", len(opps))
        return json.dumps({"opportunities": opps, "total": total, "has_more": total > len(opps)})
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def get_opportunity(opportunity_id: str) -> str:
    """Get full details for a specific opportunity/deal by its ID."""
    try:
        data = await client.get(f"/opportunities/{opportunity_id}")
        return json.dumps(data)
    except GHLAPIError as e:
        return _error(e)


# ─── WRITE TOOLS ─────────────────────────────────────────────────────────────


@mcp.tool()
async def create_or_update_contact(first_name: str = "", last_name: str = "", phone: str = "", email: str = "", tags: list[str] | None = None, source: str = "") -> str:
    """Create a new contact or update existing (matches on phone/email). Requires contacts.write scope."""
    try:
        body: dict = {"locationId": client.location_id}
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
        return json.dumps({"success": True, "contact": data.get("contact", data)})
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def add_contact_tags(contact_id: str, tags: list[str]) -> str:
    """Add one or more tags to a contact. Requires contacts.write scope."""
    try:
        data = await client.post(f"/contacts/{contact_id}/tags", json={"tags": tags})
        return json.dumps({"success": True, "tags": data.get("tags", tags)})
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def remove_contact_tags(contact_id: str, tags: list[str]) -> str:
    """Remove one or more tags from a contact. Requires contacts.write scope."""
    try:
        data = await client.delete(f"/contacts/{contact_id}/tags", json={"tags": tags})
        return json.dumps({"success": True, "tags": data.get("tags", tags)})
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def send_message(conversation_id: str, message_type: str, body: str, subject: str = "") -> str:
    """Send an SMS or email through an existing conversation. Message goes from the dealership's GHL number/address. Requires conversations/message.write scope.

    Args:
        conversation_id: The conversation ID (look up via search_conversations first)
        message_type: 'SMS' or 'Email'
        body: Message text
        subject: Email subject line (required for Email type)
    """
    try:
        payload: dict = {
            "type": message_type,
            "message": body,
            "conversationId": conversation_id,
        }
        if message_type == "Email" and subject:
            payload["subject"] = subject
        data = await client.post("/conversations/messages", json=payload)
        return json.dumps({"success": True, "messageId": data.get("messageId"), "message": data})
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def update_opportunity(opportunity_id: str, stage_id: str = "", status: str = "", monetary_value: float | None = None, title: str = "") -> str:
    """Update a deal — move pipeline stage, change status (open/won/lost/abandoned), or update value. Requires opportunities.write scope."""
    try:
        body: dict = {}
        if stage_id:
            body["pipelineStageId"] = stage_id
        if status:
            body["status"] = status
        if monetary_value is not None:
            body["monetaryValue"] = monetary_value
        if title:
            body["name"] = title
        data = await client.put(f"/opportunities/{opportunity_id}", json=body)
        return json.dumps({"success": True, "opportunity": data})
    except GHLAPIError as e:
        return _error(e)


@mcp.tool()
async def book_appointment(calendar_id: str, contact_id: str, start_time: str, end_time: str, title: str = "", notes: str = "") -> str:
    """Book an appointment on a GHL calendar. Times must be ISO 8601 format. Requires calendars/events.write scope."""
    try:
        body: dict = {
            "calendarId": calendar_id,
            "locationId": client.location_id,
            "contactId": contact_id,
            "startTime": start_time,
            "endTime": end_time,
        }
        if title:
            body["title"] = title
        if notes:
            body["notes"] = notes
        data = await client.post("/calendars/events/appointments", json=body)
        return json.dumps({"success": True, "appointment": data})
    except GHLAPIError as e:
        return _error(e)


if __name__ == "__main__":
    mcp.run(transport="stdio")

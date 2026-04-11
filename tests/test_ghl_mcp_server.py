import asyncio
import importlib
import json
import os
import sys
from pathlib import Path

import pytest

from mcp_servers.ghl.telemetry import MemoryEventStore

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def load_server_module():
    os.environ.setdefault("GHL_API_KEY", "test-api-key")
    os.environ.setdefault("GHL_LOCATION_ID", "test-location-id")

    for name in ["mcp_servers.ghl.config", "mcp_servers.ghl.client", "mcp_servers.ghl.server"]:
        sys.modules.pop(name, None)

    return importlib.import_module("mcp_servers.ghl.server")


@pytest.fixture()
def server_module():
    return load_server_module()


def parse_json(result: str) -> dict:
    return json.loads(result)


def get_error(result: dict) -> dict:
    assert result["success"] is False
    return result["error"]


def get_data(result: dict) -> dict:
    assert result["success"] is True
    return result["data"]


def test_search_contacts_rejects_invalid_limit(server_module):
    result = parse_json(asyncio.run(server_module.search_contacts(limit=0)))
    error = get_error(result)

    assert error["field"] == "limit"
    assert "between 1 and 100" in error["message"]


def test_search_opportunities_rejects_invalid_status(server_module):
    result = parse_json(asyncio.run(server_module.search_opportunities(status="pending")))
    error = get_error(result)

    assert error["field"] == "status"
    assert error["allowed_values"] == ["abandoned", "all", "lost", "open", "won"]


def test_search_opportunities_normalizes_created_at(monkeypatch, server_module):
    async def fake_get(path, params=None):
        assert path == "/opportunities/search"
        assert params["pipelineId"] == "pipe-1"
        return {
            "opportunities": [
                {
                    "id": "opp-1",
                    "name": "Deal 1",
                    "status": "open",
                    "pipelineId": "pipe-1",
                    "pipelineStageId": "stage-1",
                    "monetaryValue": 15000,
                    "createdAt": "2026-04-11T12:00:00Z",
                    "contact": {"id": "contact-1", "name": "Ethan"},
                }
            ],
            "meta": {"total": 1},
        }

    monkeypatch.setattr(server_module.client, "get", fake_get)

    result = parse_json(asyncio.run(server_module.search_opportunities(pipeline_id="pipe-1", status="open", limit=5)))
    data = get_data(result)

    assert data["total"] == 1
    assert data["opportunities"][0]["dateAdded"] == "2026-04-11T12:00:00Z"
    assert data["opportunities"][0]["contactId"] == "contact-1"
    assert data["opportunities"][0]["contactName"] == "Ethan"


def test_search_contacts_uses_shared_success_envelope(monkeypatch, server_module):
    async def fake_get(path, params=None):
        assert path == "/contacts/"
        assert params["query"] == "Ethan"
        return {
            "contacts": [
                {
                    "id": "contact-1",
                    "contactName": "Ethan Smith",
                    "firstName": "Ethan",
                    "lastName": "Smith",
                    "phone": "+15551234567",
                    "email": "ethan@example.com",
                    "tags": ["VIP"],
                    "source": "website",
                    "dateAdded": "2026-04-11T12:00:00Z",
                }
            ],
            "meta": {"total": 1},
        }

    monkeypatch.setattr(server_module.client, "get", fake_get)

    result = parse_json(asyncio.run(server_module.search_contacts(query="Ethan", limit=5)))
    data = get_data(result)

    assert data["total"] == 1
    assert data["contacts"][0]["id"] == "contact-1"
    assert data["contacts"][0]["name"] == "Ethan Smith"


def test_get_contact_uses_shared_success_envelope(monkeypatch, server_module):
    async def fake_get(path, params=None):
        assert path == "/contacts/contact-1"
        return {
            "contact": {
                "id": "contact-1",
                "contactName": "Ethan Smith",
                "firstName": "Ethan",
                "lastName": "Smith",
                "phone": "+15551234567",
                "email": "ethan@example.com",
                "tags": ["VIP"],
                "source": "website",
                "city": "Miami",
                "state": "FL",
                "country": "US",
                "dateAdded": "2026-04-11T12:00:00Z",
                "customFields": [],
                "attributions": [],
                "dnd": False,
                "assignedTo": "user-1",
            }
        }

    monkeypatch.setattr(server_module.client, "get", fake_get)

    result = parse_json(asyncio.run(server_module.get_contact("contact-1")))
    data = get_data(result)

    assert data["contact"]["id"] == "contact-1"
    assert data["contact"]["city"] == "Miami"


def test_search_conversations_uses_shared_success_envelope(monkeypatch, server_module):
    async def fake_get(path, params=None):
        assert path == "/conversations/search"
        assert params["contactId"] == "contact-1"
        return {
            "conversations": [
                {
                    "id": "conv-1",
                    "contactId": "contact-1",
                    "fullName": "Ethan Smith",
                    "lastMessageBody": "Interested in the GT500",
                    "lastMessageType": "SMS",
                    "lastMessageDirection": "inbound",
                    "lastMessageDate": "2026-04-11T13:00:00Z",
                    "unreadCount": 1,
                    "type": "sms",
                    "phone": "+15551234567",
                    "email": "ethan@example.com",
                    "tags": ["VIP"],
                }
            ],
            "total": 1,
        }

    monkeypatch.setattr(server_module.client, "get", fake_get)

    result = parse_json(asyncio.run(server_module.search_conversations(contact_id="contact-1", limit=3)))
    data = get_data(result)

    assert data["total"] == 1
    assert data["conversations"][0]["id"] == "conv-1"
    assert data["conversations"][0]["unreadCount"] == 1


def test_get_conversation_messages_uses_shared_success_envelope(monkeypatch, server_module):
    async def fake_get(path, params=None):
        assert path == "/conversations/conv-1/messages"
        return {
            "messages": {
                "messages": [
                    {
                        "direction": "outbound",
                        "body": "See you tomorrow",
                        "messageType": "SMS",
                        "dateAdded": "2026-04-11T13:05:00Z",
                        "source": "app",
                        "from": "+15550000000",
                        "to": "+15551234567",
                        "status": "sent",
                        "attachments": [],
                    },
                    {
                        "direction": "inbound",
                        "body": "Sounds good",
                        "messageType": "SMS",
                        "dateAdded": "2026-04-11T13:06:00Z",
                        "source": "sms",
                        "from": "+15551234567",
                        "to": "+15550000000",
                        "status": "received",
                        "attachments": [],
                    },
                ],
                "nextPage": False,
            }
        }

    monkeypatch.setattr(server_module.client, "get", fake_get)

    result = parse_json(asyncio.run(server_module.get_conversation_messages("conv-1")))
    data = get_data(result)

    assert data["count"] == 2
    assert data["messages"][0]["body"] == "Sounds good"
    assert data["messages"][1]["body"] == "See you tomorrow"


def test_get_opportunity_uses_shared_success_envelope(monkeypatch, server_module):
    async def fake_get(path, params=None):
        assert path == "/opportunities/opp-1"
        return {
            "opportunity": {
                "id": "opp-1",
                "name": "Deal 1",
                "status": "open",
                "pipelineId": "pipeline-1",
            }
        }

    monkeypatch.setattr(server_module.client, "get", fake_get)

    result = parse_json(asyncio.run(server_module.get_opportunity("opp-1")))
    data = get_data(result)

    assert data["opportunity"]["id"] == "opp-1"
    assert data["opportunity"]["status"] == "open"


def test_create_or_update_contact_uses_shared_success_envelope(monkeypatch, server_module):
    async def fake_post(path, json=None, params=None):
        assert path == "/contacts/upsert"
        assert json["locationId"] == "test-location-id"
        assert json["phone"] == "+15551234567"
        return {"contact": {"id": "contact-1", "phone": "+15551234567"}}

    monkeypatch.setattr(server_module.client, "post", fake_post)

    result = parse_json(asyncio.run(server_module.create_or_update_contact(phone="+15551234567")))
    data = get_data(result)

    assert data["contact"]["id"] == "contact-1"


def test_add_contact_tags_uses_shared_success_envelope(monkeypatch, server_module):
    async def fake_post(path, json=None, params=None):
        assert path == "/contacts/contact-1/tags"
        return {"tags": ["VIP", "buyer"]}

    monkeypatch.setattr(server_module.client, "post", fake_post)

    result = parse_json(asyncio.run(server_module.add_contact_tags("contact-1", ["VIP", "buyer"])))
    data = get_data(result)

    assert data["tags"] == ["VIP", "buyer"]


def test_remove_contact_tags_uses_shared_success_envelope(monkeypatch, server_module):
    async def fake_delete(path, json=None, params=None):
        assert path == "/contacts/contact-1/tags"
        return {"tags": ["buyer"]}

    monkeypatch.setattr(server_module.client, "delete", fake_delete)

    result = parse_json(asyncio.run(server_module.remove_contact_tags("contact-1", ["VIP"])))
    data = get_data(result)

    assert data["tags"] == ["buyer"]


def test_send_message_requires_subject_for_email(server_module):
    result = parse_json(asyncio.run(server_module.send_message("conv-1", "Email", "Hello", subject="")))
    error = get_error(result)

    assert error["field"] == "subject"
    assert "required" in error["message"]


def test_send_message_rejects_invalid_message_type(server_module):
    result = parse_json(asyncio.run(server_module.send_message("conv-1", "TELEGRAM", "Hello")))
    error = get_error(result)

    assert error["field"] == "message_type"
    assert error["allowed_values"] == ["Email", "SMS"]


def test_send_message_adds_scope_guidance_on_auth_error(monkeypatch, server_module):
    async def fake_post(path, json=None, params=None):
        raise server_module.GHLAPIError(403, "The token is not authorized for this scope")

    monkeypatch.setattr(server_module.client, "post", fake_post)

    result = parse_json(asyncio.run(server_module.send_message("conv-1", "SMS", "Hello")))
    error = get_error(result)

    assert error["status_code"] == 403
    assert error["required_scope"] == "conversations/message.write"
    assert "conversations/message.write" in error["resolution"]


def test_create_opportunity_builds_expected_payload(monkeypatch, server_module):
    async def fake_post(path, json=None, params=None):
        assert path == "/opportunities"
        assert json["locationId"] == "test-location-id"
        assert json["contactId"] == "contact-1"
        assert json["pipelineId"] == "pipeline-1"
        assert json["pipelineStageId"] == "stage-1"
        assert json["name"] == "New Deal"
        assert json["status"] == "open"
        assert json["monetaryValue"] == 25000
        return {"opportunity": {"id": "opp-123", **json}}

    monkeypatch.setattr(server_module.client, "post", fake_post)

    result = parse_json(
        asyncio.run(
            server_module.create_opportunity(
                contact_id="contact-1",
                pipeline_id="pipeline-1",
                stage_id="stage-1",
                title="New Deal",
                monetary_value=25000,
            )
        )
    )
    data = get_data(result)

    assert data["opportunity"]["id"] == "opp-123"


def test_send_message_uses_shared_success_envelope(monkeypatch, server_module):
    async def fake_post(path, json=None, params=None):
        assert path == "/conversations/messages"
        return {"messageId": "msg-1", "status": "queued"}

    monkeypatch.setattr(server_module.client, "post", fake_post)

    result = parse_json(asyncio.run(server_module.send_message("conv-1", "SMS", "Hello")))
    data = get_data(result)

    assert data["messageId"] == "msg-1"
    assert data["message"]["status"] == "queued"


def test_list_calendars_returns_simplified_shape(monkeypatch, server_module):
    async def fake_get(path, params=None):
        assert path == "/calendars/"
        return {
            "calendars": [
                {
                    "id": "cal-1",
                    "name": "Main Calendar",
                    "description": "Primary showroom calendar",
                    "isActive": True,
                    "groupId": "group-1",
                }
            ]
        }

    monkeypatch.setattr(server_module.client, "get", fake_get)

    result = parse_json(asyncio.run(server_module.list_calendars()))
    data = get_data(result)

    assert data["count"] == 1
    assert data["calendars"][0]["id"] == "cal-1"
    assert data["calendars"][0]["name"] == "Main Calendar"


def test_get_location_uses_shared_success_envelope(monkeypatch, server_module):
    async def fake_get(path, params=None):
        assert path == "/locations/test-location-id"
        return {"location": {"id": "test-location-id", "name": "Jimmy Showroom"}}

    monkeypatch.setattr(server_module.client, "get", fake_get)

    result = parse_json(asyncio.run(server_module.get_location()))
    data = get_data(result)

    assert data["location"]["id"] == "test-location-id"
    assert data["location"]["name"] == "Jimmy Showroom"


def test_get_location_custom_fields_uses_shared_success_envelope(monkeypatch, server_module):
    async def fake_get(path, params=None):
        assert path == "/locations/test-location-id/customFields"
        return {"customFields": [{"id": "field-1", "name": "Budget"}]}

    monkeypatch.setattr(server_module.client, "get", fake_get)

    result = parse_json(asyncio.run(server_module.get_location_custom_fields()))
    data = get_data(result)

    assert data["customFields"][0]["id"] == "field-1"
    assert data["customFields"][0]["name"] == "Budget"


def test_get_location_tags_uses_shared_success_envelope(monkeypatch, server_module):
    async def fake_get(path, params=None):
        assert path == "/locations/test-location-id/tags"
        return {"tags": [{"id": "tag-1", "name": "VIP"}]}

    monkeypatch.setattr(server_module.client, "get", fake_get)

    result = parse_json(asyncio.run(server_module.get_location_tags()))
    data = get_data(result)

    assert data["tags"][0]["id"] == "tag-1"
    assert data["tags"][0]["name"] == "VIP"


def test_update_opportunity_uses_shared_success_envelope(monkeypatch, server_module):
    async def fake_put(path, json=None, params=None):
        assert path == "/opportunities/opp-1"
        assert json["name"] == "Updated Deal"
        return {"id": "opp-1", "name": "Updated Deal"}

    monkeypatch.setattr(server_module.client, "put", fake_put)

    result = parse_json(asyncio.run(server_module.update_opportunity("opp-1", title="Updated Deal")))
    data = get_data(result)

    assert data["opportunity"]["id"] == "opp-1"
    assert data["opportunity"]["name"] == "Updated Deal"


def test_book_appointment_requires_iso8601_with_timezone(server_module):
    result = parse_json(
        asyncio.run(
            server_module.book_appointment(
                calendar_id="cal-1",
                contact_id="contact-1",
                start_time="2026-04-11 15:00",
                end_time="2026-04-11T16:00:00Z",
            )
        )
    )
    error = get_error(result)

    assert error["field"] == "start_time"
    assert "timezone offset" in error["message"]


def test_book_appointment_rejects_end_before_start(server_module):
    result = parse_json(
        asyncio.run(
            server_module.book_appointment(
                calendar_id="cal-1",
                contact_id="contact-1",
                start_time="2026-04-11T16:00:00Z",
                end_time="2026-04-11T15:00:00Z",
            )
        )
    )
    error = get_error(result)

    assert error["field"] == "end_time"
    assert "after start_time" in error["message"]


def test_book_appointment_uses_shared_success_envelope(monkeypatch, server_module):
    async def fake_post(path, json=None, params=None):
        assert path == "/calendars/events/appointments"
        assert json["startTime"] == "2026-04-11T15:00:00Z"
        assert json["endTime"] == "2026-04-11T16:00:00Z"
        return {"id": "appt-1", "status": "confirmed"}

    monkeypatch.setattr(server_module.client, "post", fake_post)

    result = parse_json(
        asyncio.run(
            server_module.book_appointment(
                calendar_id="cal-1",
                contact_id="contact-1",
                start_time="2026-04-11T15:00:00Z",
                end_time="2026-04-11T16:00:00Z",
            )
        )
    )
    data = get_data(result)

    assert data["appointment"]["id"] == "appt-1"
    assert data["appointment"]["status"] == "confirmed"


def test_success_responses_use_shared_data_envelope(monkeypatch, server_module):
    async def fake_get(path, params=None):
        return {"pipelines": [{"id": "pipe-1", "name": "Main", "stages": []}]}

    monkeypatch.setattr(server_module.client, "get", fake_get)

    result = parse_json(asyncio.run(server_module.get_pipelines()))

    assert result == {
        "success": True,
        "data": {"pipelines": [{"id": "pipe-1", "name": "Main", "stages": []}]},
    }


def test_validation_errors_use_shared_error_envelope(server_module):
    result = parse_json(asyncio.run(server_module.update_opportunity("opp-1", status="all")))

    assert result == {
        "success": False,
        "error": {
            "status_code": 400,
            "message": "status must be one of: abandoned, lost, open, won",
            "field": "status",
            "allowed_values": ["abandoned", "lost", "open", "won"],
        },
    }


def test_auth_errors_use_shared_error_envelope(monkeypatch, server_module):
    async def fake_post(path, json=None, params=None):
        raise server_module.GHLAPIError(401, "The token is not authorized for this scope")

    monkeypatch.setattr(server_module.client, "post", fake_post)

    result = parse_json(asyncio.run(server_module.create_or_update_contact(phone="+15551234567")))

    assert result == {
        "success": False,
        "error": {
            "status_code": 401,
            "message": "The token is not authorized for this scope",
            "required_scope": "contacts.write",
            "resolution": "Enable the contacts.write scope on the GHL Private Integration token.",
        },
    }


# ---------------------------------------------------------------------------
# Telemetry integration tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def telemetry_store(server_module):
    original_store = server_module.mcp.event_store
    store = MemoryEventStore()
    server_module.mcp.event_store = store
    yield store
    server_module.mcp.event_store = original_store


def test_search_contacts_emits_telemetry_event(monkeypatch, server_module, telemetry_store):
    async def fake_get(path, params=None):
        assert path == "/contacts/"
        return {
            "contacts": [
                {
                    "id": "contact-1",
                    "contactName": "Ethan Smith",
                    "firstName": "Ethan",
                    "lastName": "Smith",
                    "phone": "+15551234567",
                    "email": "ethan@example.com",
                    "tags": ["VIP"],
                    "source": "website",
                    "dateAdded": "2026-04-11T12:00:00Z",
                }
            ],
            "meta": {"total": 1},
        }

    monkeypatch.setattr(server_module.client, "get", fake_get)

    result = parse_json(asyncio.run(server_module.search_contacts(query="Ethan", limit=5)))
    data = get_data(result)

    assert data["total"] == 1
    assert len(telemetry_store.events) == 1
    event = telemetry_store.events[0]
    assert event.tool_name == "search_contacts"
    assert event.success is True
    assert event.payload_summary["arguments"]["query"] == "Ethan"


def test_failed_upstream_call_still_records_telemetry(monkeypatch, server_module, telemetry_store):
    async def fake_post(path, json=None, params=None):
        raise server_module.GHLAPIError(403, "The token is not authorized for this scope")

    monkeypatch.setattr(server_module.client, "post", fake_post)

    result = parse_json(asyncio.run(server_module.send_message("conv-1", "SMS", "Hello")))
    error = get_error(result)

    assert error["status_code"] == 403
    assert len(telemetry_store.events) == 1
    event = telemetry_store.events[0]
    assert event.tool_name == "send_message"
    assert event.success is False
    assert event.upstream_status == 403
    assert event.scope_required == "conversations/message.write"


# ---------------------------------------------------------------------------
# Knowledge Base tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def kb_dir(tmp_path, server_module):
    """Point KB_DIR to a temp directory for isolation."""
    original = server_module.KB_DIR
    server_module.KB_DIR = tmp_path
    yield tmp_path
    server_module.KB_DIR = original


def test_kb_list_empty(server_module, kb_dir):
    result = parse_json(asyncio.run(server_module.kb_list()))
    data = get_data(result)
    assert data["count"] == 0
    assert data["documents"] == []


def test_kb_write_creates_doc(server_module, kb_dir):
    result = parse_json(asyncio.run(server_module.kb_write("Test Doc", "# Test Doc\n\nSome content.")))
    data = get_data(result)
    assert data["action"] == "created"
    assert data["document"]["slug"] == "test-doc"
    assert data["document"]["title"] == "Test Doc"
    assert (kb_dir / "test-doc.md").exists()


def test_kb_write_updates_existing(server_module, kb_dir):
    asyncio.run(server_module.kb_write("Test Doc", "# Test Doc\n\nV1"))
    result = parse_json(asyncio.run(server_module.kb_write("Test Doc", "# Test Doc\n\nV2")))
    data = get_data(result)
    assert data["action"] == "updated"
    assert "V2" in data["document"]["content"]


def test_kb_write_rejects_empty_content(server_module, kb_dir):
    result = parse_json(asyncio.run(server_module.kb_write("Empty", "")))
    error = get_error(result)
    assert error["field"] == "content"


def test_kb_read_returns_doc(server_module, kb_dir):
    asyncio.run(server_module.kb_write("My Notes", "# My Notes\n\nHello world."))
    result = parse_json(asyncio.run(server_module.kb_read("my-notes")))
    data = get_data(result)
    assert data["document"]["title"] == "My Notes"
    assert "Hello world" in data["document"]["content"]


def test_kb_read_missing_doc(server_module, kb_dir):
    result = parse_json(asyncio.run(server_module.kb_read("nonexistent")))
    error = get_error(result)
    assert error["field"] == "slug"
    assert "not found" in error["message"]


def test_kb_search_finds_matches(server_module, kb_dir):
    asyncio.run(server_module.kb_write("Sales Tips", "# Sales Tips\n\nAlways follow up within 5 minutes."))
    asyncio.run(server_module.kb_write("Inventory", "# Inventory\n\nPorsche Cayenne in stock."))

    result = parse_json(asyncio.run(server_module.kb_search("follow up")))
    data = get_data(result)
    assert data["count"] == 1
    assert data["results"][0]["slug"] == "sales-tips"


def test_kb_search_case_insensitive(server_module, kb_dir):
    asyncio.run(server_module.kb_write("Guide", "# Guide\n\nPORSCHE buyers want white glove service."))
    result = parse_json(asyncio.run(server_module.kb_search("porsche")))
    data = get_data(result)
    assert data["count"] == 1


def test_kb_search_empty_query(server_module, kb_dir):
    result = parse_json(asyncio.run(server_module.kb_search("")))
    error = get_error(result)
    assert error["field"] == "query"


def test_kb_delete_removes_doc(server_module, kb_dir):
    asyncio.run(server_module.kb_write("Temp", "# Temp\n\nDelete me."))
    assert (kb_dir / "temp.md").exists()

    result = parse_json(asyncio.run(server_module.kb_delete("temp")))
    data = get_data(result)
    assert data["deleted"] == "temp"
    assert not (kb_dir / "temp.md").exists()


def test_kb_delete_missing_doc(server_module, kb_dir):
    result = parse_json(asyncio.run(server_module.kb_delete("ghost")))
    error = get_error(result)
    assert error["field"] == "slug"


def test_kb_list_shows_all_docs(server_module, kb_dir):
    asyncio.run(server_module.kb_write("Doc A", "# Doc A\n\nFirst."))
    asyncio.run(server_module.kb_write("Doc B", "# Doc B\n\nSecond."))
    asyncio.run(server_module.kb_write("Doc C", "# Doc C\n\nThird."))

    result = parse_json(asyncio.run(server_module.kb_list()))
    data = get_data(result)
    assert data["count"] == 3
    slugs = [d["slug"] for d in data["documents"]]
    assert "doc-a" in slugs
    assert "doc-b" in slugs
    assert "doc-c" in slugs

"""Integration tests for conversation flow using FastAPI TestClient."""

import json
import sys
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="module", autouse=True)
def setup_db(tmp_path_factory):
    """Set up a temporary database before importing the app."""
    tmp_dir = tmp_path_factory.mktemp("data")
    db_path = str(tmp_dir / "test_conv.db")
    os.environ["RPM_DATABASE_PATH"] = db_path

    from backend import config
    config.settings.DATABASE_PATH = db_path
    config.settings.ANTHROPIC_API_KEY = "test-key"

    from backend.database import create_tables, get_db
    create_tables()

    # Insert a test car
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO cars
               (year, make, model, trim, price, mileage,
                exterior_color, interior_color, engine, transmission,
                vin, status, condition, description, highlights,
                image_url, date_listed, views)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (1967, "Shelby", "GT500", "Fastback", 189000, 43200,
             "Nightmist Blue", "Black Vinyl", "427 V8", "4-Speed Manual",
             "67402F8A0032100", "available", "excellent",
             "A stunning first-year GT500.", '["matching numbers"]',
             "https://placeholder.rpm-cars.com/cars/1.jpg", "2025-11-15", 2847),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def client():
    """Create a TestClient for the FastAPI app."""
    from backend.main import app
    return TestClient(app)


def _mock_text_block(text):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _mock_tool_block(tool_id, name, tool_input):
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = tool_input
    return block


class TestNewConversation:
    """Test creating a new conversation via the SMS endpoint."""

    @patch("backend.ai.engine.anthropic.Anthropic")
    def test_inbound_sms_creates_conversation(self, mock_anthropic_cls, client):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [_mock_text_block("hey yeah we've got some cool stuff right now")]
        mock_client.messages.create.return_value = mock_response

        response = client.post("/api/sms/inbound", json={
            "from_number": "+15551110000",
            "message": "hey do you have any muscle cars",
        })

        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert "conversation_id" in data
        assert len(data["messages"]) >= 1
        assert data["messages"][0]["text"]

    @patch("backend.ai.engine.anthropic.Anthropic")
    def test_inbound_sms_with_car_id(self, mock_anthropic_cls, client):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [_mock_text_block("yeah the GT500 is a beast")]
        mock_client.messages.create.return_value = mock_response

        response = client.post("/api/sms/inbound", json={
            "from_number": "+15552220000",
            "message": "tell me about this one",
            "car_id": 1,
        })

        assert response.status_code == 200
        data = response.json()
        assert "GT500" in data["messages"][0]["text"] or len(data["messages"]) >= 1


class TestLeadCapture:
    """Test that lead info gets saved when provided in messages."""

    @patch("backend.ai.engine.anthropic.Anthropic")
    def test_lead_saved_via_tool(self, mock_anthropic_cls, client):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        # First call: save_lead_info tool
        tool_response = MagicMock()
        tool_response.stop_reason = "tool_use"
        tool_response.content = [
            _mock_tool_block("call_lead", "save_lead_info", {
                "name": "Mike Thompson",
                "phone": "+15553330000",
                "budget_range": "150000-200000",
            }),
        ]

        # Second call: text response
        text_response = MagicMock()
        text_response.stop_reason = "end_turn"
        text_response.content = [_mock_text_block("nice to meet you Mike")]
        mock_client.messages.create.side_effect = [tool_response, text_response]

        response = client.post("/api/sms/inbound", json={
            "from_number": "+15553330000",
            "message": "hey I'm Mike, looking to spend around 150-200k on a muscle car",
        })

        assert response.status_code == 200

        # Verify lead was created in the database
        from backend.services.leads import get_lead_by_phone
        lead = get_lead_by_phone("+15553330000")
        assert lead is not None
        assert lead["name"] == "Mike Thompson"


class TestConversationHistory:
    """Test that conversation history is maintained across messages."""

    @patch("backend.ai.engine.anthropic.Anthropic")
    def test_history_maintained(self, mock_anthropic_cls, client):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        phone = "+15554440000"

        # First message
        resp1 = MagicMock()
        resp1.stop_reason = "end_turn"
        resp1.content = [_mock_text_block("hey what's up")]

        # Second message
        resp2 = MagicMock()
        resp2.stop_reason = "end_turn"
        resp2.content = [_mock_text_block("yeah we've got a few")]

        mock_client.messages.create.side_effect = [resp1, resp2]

        # Send first message
        client.post("/api/sms/inbound", json={
            "from_number": phone,
            "message": "hi there",
        })

        # Send second message
        client.post("/api/sms/inbound", json={
            "from_number": phone,
            "message": "what muscle cars do you have",
        })

        # Check that the conversation has history
        from backend.database import get_db
        conn = get_db()
        try:
            conv = conn.execute(
                "SELECT * FROM conversations WHERE phone_number = ? AND status = 'active'",
                (phone,),
            ).fetchone()
            assert conv is not None
            messages = json.loads(conv["messages"])
            # Should have at least 2 user messages and 2 assistant messages
            user_msgs = [m for m in messages if m["role"] == "user"]
            assistant_msgs = [m for m in messages if m["role"] == "assistant"]
            assert len(user_msgs) >= 2
            assert len(assistant_msgs) >= 2
        finally:
            conn.close()

    @patch("backend.ai.engine.anthropic.Anthropic")
    def test_same_phone_reuses_conversation(self, mock_anthropic_cls, client):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        phone = "+15555550000"

        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [_mock_text_block("hey")]
        mock_client.messages.create.return_value = mock_response

        # Send two messages from same number
        r1 = client.post("/api/sms/inbound", json={
            "from_number": phone, "message": "hello",
        })
        r2 = client.post("/api/sms/inbound", json={
            "from_number": phone, "message": "still there?",
        })

        # Both should use the same conversation_id
        assert r1.json()["conversation_id"] == r2.json()["conversation_id"]

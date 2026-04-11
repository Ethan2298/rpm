"""Tests for the AI engine with mocked Anthropic API calls."""

import json
import sys
import os
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.database import create_tables, get_db
from backend.ai.engine import get_ai_response


@pytest.fixture(scope="module", autouse=True)
def seed_db(tmp_path_factory):
    """Set up a temporary database for tests."""
    tmp_dir = tmp_path_factory.mktemp("data")
    db_path = str(tmp_dir / "test_engine.db")
    os.environ["RPM_DATABASE_PATH"] = db_path

    from backend import config
    config.settings.DATABASE_PATH = db_path
    config.settings.ANTHROPIC_API_KEY = "test-key"

    create_tables()

    # Insert one test car for tool use tests
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO cars
               (year, make, model, trim, price, mileage,
                exterior_color, interior_color, engine, transmission,
                vin, status, condition, description, highlights,
                image_url, date_listed, views)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (1969, "Chevrolet", "Camaro", "Z/28", 125000, 67800,
             "Hugger Orange", "Black", "302 V8", "4-Speed",
             "124379N50782100", "available", "excellent",
             "Real Z/28.", '["numbers matching"]',
             "https://placeholder.rpm-cars.com/cars/1.jpg", "2025-10-22", 1923),
        )
        conn.commit()
    finally:
        conn.close()


def _make_text_block(text):
    """Create a mock text content block."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_tool_use_block(tool_id, name, tool_input):
    """Create a mock tool_use content block."""
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = tool_input
    return block


class TestSimpleTextResponse:
    """Test that a simple end_turn response is returned correctly."""

    @patch("backend.ai.engine.anthropic.Anthropic")
    def test_returns_text(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [_make_text_block("yeah we've got a few camaros actually")]
        mock_client.messages.create.return_value = mock_response

        history = [{"role": "user", "content": "do you have any camaros", "timestamp": "2025-01-01T00:00:00Z"}]
        text, updated = get_ai_response(history, "+15551234567")

        assert text == "yeah we've got a few camaros actually"
        assert len(updated) == 2  # original user msg + assistant response
        assert updated[-1]["role"] == "assistant"

    @patch("backend.ai.engine.anthropic.Anthropic")
    def test_multi_text_blocks(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [
            _make_text_block("yeah that's a solid pick"),
            _make_text_block("been getting a lot of attention lately"),
        ]
        mock_client.messages.create.return_value = mock_response

        history = [{"role": "user", "content": "what about the GT500", "timestamp": "2025-01-01T00:00:00Z"}]
        text, updated = get_ai_response(history, "+15551234567")

        assert "solid pick" in text
        assert "attention" in text


class TestToolUseLoop:
    """Test that the engine handles tool_use stop_reason and re-calls the API."""

    @patch("backend.ai.engine.anthropic.Anthropic")
    def test_tool_use_then_text(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        # First call: tool_use
        tool_response = MagicMock()
        tool_response.stop_reason = "tool_use"
        tool_response.content = [
            _make_tool_use_block("call_001", "search_inventory", {"make": "Chevrolet"}),
        ]

        # Second call: end_turn with text
        text_response = MagicMock()
        text_response.stop_reason = "end_turn"
        text_response.content = [_make_text_block("yeah we've got a '69 Camaro Z/28 in Hugger Orange")]

        mock_client.messages.create.side_effect = [tool_response, text_response]

        history = [{"role": "user", "content": "any chevys?", "timestamp": "2025-01-01T00:00:00Z"}]
        text, updated = get_ai_response(history, "+15551234567")

        assert "Camaro" in text or "camaro" in text.lower()
        # Should have called the API twice
        assert mock_client.messages.create.call_count == 2

    @patch("backend.ai.engine.anthropic.Anthropic")
    def test_multiple_tool_calls(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        # First call: search
        search_response = MagicMock()
        search_response.stop_reason = "tool_use"
        search_response.content = [
            _make_tool_use_block("call_001", "search_inventory", {"make": "Chevrolet"}),
        ]

        # Second call: get details
        details_response = MagicMock()
        details_response.stop_reason = "tool_use"
        details_response.content = [
            _make_tool_use_block("call_002", "get_car_details", {"car_id": 1}),
        ]

        # Third call: final text
        final_response = MagicMock()
        final_response.stop_reason = "end_turn"
        final_response.content = [_make_text_block("that Z/28 is the real deal — numbers matching 302")]

        mock_client.messages.create.side_effect = [search_response, details_response, final_response]

        history = [{"role": "user", "content": "tell me about your Chevys", "timestamp": "2025-01-01T00:00:00Z"}]
        text, updated = get_ai_response(history, "+15551234567")

        assert mock_client.messages.create.call_count == 3
        assert "302" in text or "Z/28" in text


class TestResponseCleanliness:
    """Test that final responses don't contain tool artifacts."""

    @patch("backend.ai.engine.anthropic.Anthropic")
    def test_no_json_in_response(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [_make_text_block("yeah that camaro is clean, real deal Z/28")]
        mock_client.messages.create.return_value = mock_response

        history = [{"role": "user", "content": "is the camaro legit", "timestamp": "2025-01-01T00:00:00Z"}]
        text, _ = get_ai_response(history, "+15551234567")

        # Should not contain JSON artifacts
        assert "{" not in text
        assert "tool_use" not in text
        assert "tool_result" not in text

    @patch("backend.ai.engine.anthropic.Anthropic")
    def test_no_tool_names_in_response(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        # Simulate tool use followed by text
        tool_response = MagicMock()
        tool_response.stop_reason = "tool_use"
        tool_response.content = [
            _make_tool_use_block("call_001", "check_availability", {"car_id": 1}),
        ]

        text_response = MagicMock()
        text_response.stop_reason = "end_turn"
        text_response.content = [_make_text_block("yeah it's still available, been getting some looks though")]
        mock_client.messages.create.side_effect = [tool_response, text_response]

        history = [{"role": "user", "content": "is the camaro available", "timestamp": "2025-01-01T00:00:00Z"}]
        text, _ = get_ai_response(history, "+15551234567")

        assert "search_inventory" not in text
        assert "check_availability" not in text
        assert "get_car_details" not in text
        assert "save_lead_info" not in text
        assert "book_appointment" not in text

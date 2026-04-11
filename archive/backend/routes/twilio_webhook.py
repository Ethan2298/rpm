"""Twilio SMS webhook — receives real texts and replies via the AI agent.

Flow:
1. Twilio POSTs inbound SMS to /api/sms/incoming
2. We return an empty TwiML immediately (beats Twilio's 15s timeout)
3. In a background thread we run the AI agent and send the reply via Twilio REST API
"""

import json
import logging
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import Response

from twilio.rest import Client as TwilioClient
from twilio.request_validator import RequestValidator

from backend.config import settings
from backend.database import get_db
from backend.ai.engine import get_ai_response
from backend.ai.humanizer import humanize

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sms", tags=["twilio"])

EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_twilio_client() -> TwilioClient:
    return TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def _get_or_create_conversation(phone_number: str) -> dict:
    conn = get_db()
    try:
        conv = conn.execute(
            "SELECT * FROM conversations WHERE phone_number = ? AND status = 'active'",
            (phone_number,),
        ).fetchone()
        if conv:
            return conv
        cursor = conn.execute(
            "INSERT INTO conversations (phone_number, messages) VALUES (?, '[]')",
            (phone_number,),
        )
        conn.commit()
        return conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    finally:
        conn.close()


def _get_recent_assistant_messages(messages: list[dict], count: int = 5) -> list[str]:
    recent = []
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            if isinstance(content, str) and not content.startswith("["):
                recent.append(content)
            if len(recent) >= count:
                break
    return recent


def _send_sms(to: str, body: str) -> None:
    """Send a single SMS via Twilio REST API."""
    client = _get_twilio_client()
    kwargs = {"body": body, "to": to}
    if settings.TWILIO_MESSAGING_SERVICE_SID:
        kwargs["messaging_service_sid"] = settings.TWILIO_MESSAGING_SERVICE_SID
    else:
        kwargs["from_"] = settings.TWILIO_PHONE_NUMBER
    client.messages.create(**kwargs)


# ---------------------------------------------------------------------------
# /clear — reset conversation for a phone number
# ---------------------------------------------------------------------------

def _handle_clear(phone_number: str) -> None:
    """Delete the active conversation and any lead/appointment data for this number."""
    conn = get_db()
    try:
        # Close the active conversation
        conn.execute(
            "UPDATE conversations SET status = 'closed' "
            "WHERE phone_number = ? AND status = 'active'",
            (phone_number,),
        )

        # Remove lead tied to this phone (and its appointments)
        lead = conn.execute(
            "SELECT id FROM leads WHERE phone = ?", (phone_number,)
        ).fetchone()
        if lead:
            conn.execute("DELETE FROM appointments WHERE lead_id = ?", (lead["id"],))
            conn.execute("DELETE FROM leads WHERE id = ?", (lead["id"],))

        conn.commit()
    finally:
        conn.close()

    _send_sms(phone_number, "conversation cleared — text anything to start fresh")


# ---------------------------------------------------------------------------
# Background AI processing
# ---------------------------------------------------------------------------

def _process_and_reply(phone_number: str, body: str) -> None:
    """Run the AI agent and send the reply. Designed to run in a thread."""
    try:
        logger.info("Processing SMS from %s: %s", phone_number, body)
        conv = _get_or_create_conversation(phone_number)

        # Load existing messages
        try:
            messages = json.loads(conv["messages"]) if conv["messages"] else []
        except (json.JSONDecodeError, TypeError):
            messages = []

        now = datetime.now(timezone.utc).isoformat()
        messages.append({"role": "user", "content": body, "timestamp": now})

        # Run AI
        logger.info("Calling AI engine for %s...", phone_number)
        response_text, updated_messages = get_ai_response(
            conversation_history=messages,
            phone_number=phone_number,
        )
        logger.info("AI response for %s: %s", phone_number, response_text[:100])

        # Humanize
        recent_assistant = _get_recent_assistant_messages(updated_messages)
        response_parts = humanize(response_text, recent_assistant)

        # Save conversation
        conn = get_db()
        try:
            conn.execute(
                "UPDATE conversations SET messages = ?, last_message_at = ? WHERE id = ?",
                (json.dumps(updated_messages, default=str), now, conv["id"]),
            )
            conn.commit()
        finally:
            conn.close()

        # Send each message chunk via Twilio
        import time
        for part in response_parts:
            delay_s = part.get("delay_ms", 0) / 1000.0
            if delay_s > 0:
                time.sleep(delay_s)
            logger.info("Sending SMS to %s: %s", phone_number, part["text"])
            _send_sms(phone_number, part["text"])

        logger.info("All messages sent to %s", phone_number)

    except Exception:
        logger.exception("Error processing SMS from %s", phone_number)
        try:
            _send_sms(phone_number, "hey, give me one sec — something glitched on my end")
        except Exception:
            logger.exception("Failed to send error SMS to %s", phone_number)


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------

@router.post("/incoming")
async def twilio_incoming(request: Request):
    """Receive an inbound SMS from Twilio and reply asynchronously."""
    form = await request.form()
    from_number = form.get("From", "")
    body = (form.get("Body", "") or "").strip()

    if not from_number or not body:
        return Response(content=EMPTY_TWIML, media_type="application/xml")

    # Handle /clear command
    if body.lower() in ("/clear", "clear", "/reset", "reset"):
        threading.Thread(
            target=_handle_clear,
            args=(from_number,),
            daemon=True,
        ).start()
        return Response(content=EMPTY_TWIML, media_type="application/xml")

    # Process normally in background thread
    threading.Thread(
        target=_process_and_reply,
        args=(from_number, body),
        daemon=True,
    ).start()

    # Return empty TwiML immediately so Twilio doesn't timeout
    return Response(content=EMPTY_TWIML, media_type="application/xml")

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from backend.database import get_db
from backend.models import InboundSMS, SMSResponse
from backend.ai.engine import get_ai_response
from backend.ai.humanizer import humanize

router = APIRouter(prefix="/api/sms", tags=["sms"])


def _get_or_create_conversation(phone_number: str, car_id: int | None = None) -> dict:
    """Find an active conversation for this phone number, or create one."""
    conn = get_db()
    try:
        conv = conn.execute(
            "SELECT * FROM conversations WHERE phone_number = ? AND status = 'active'",
            (phone_number,),
        ).fetchone()

        if conv:
            return conv

        # Create new conversation
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
    """Extract recent assistant text messages for repetition checking."""
    recent = []
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            if isinstance(content, str) and not content.startswith("["):
                recent.append(content)
            if len(recent) >= count:
                break
    return recent


@router.post("/inbound", response_model=SMSResponse)
async def handle_inbound_sms(sms: InboundSMS):
    """Handle an inbound SMS message and generate AI response."""
    # Get or create conversation
    conv = _get_or_create_conversation(sms.from_number, sms.car_id)

    # Load existing messages
    try:
        messages = json.loads(conv["messages"]) if conv["messages"] else []
    except (json.JSONDecodeError, TypeError):
        messages = []

    # Append the new user message
    now = datetime.now(timezone.utc).isoformat()

    # If there's a car_id context, prepend it to the first message
    user_content = sms.message
    if sms.car_id and len(messages) == 0:
        user_content = f"[Customer is asking about car ID {sms.car_id}] {sms.message}"

    messages.append({
        "role": "user",
        "content": user_content,
        "timestamp": now,
    })

    # Get AI response
    try:
        response_text, updated_messages = get_ai_response(
            conversation_history=messages,
            phone_number=sms.from_number,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI engine error: {str(e)}")

    # Get recent assistant messages for humanizer
    recent_assistant = _get_recent_assistant_messages(updated_messages)

    # Humanize the response
    response_parts = humanize(response_text, recent_assistant)

    # Save updated conversation to DB
    conn = get_db()
    try:
        conn.execute(
            "UPDATE conversations SET messages = ?, last_message_at = ? WHERE id = ?",
            (json.dumps(updated_messages, default=str), now, conv["id"]),
        )
        conn.commit()
    finally:
        conn.close()

    return SMSResponse(
        messages=response_parts,
        conversation_id=conv["id"],
    )


@router.get("/conversations")
async def list_conversations():
    """List all SMS conversations."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM conversations ORDER BY last_message_at DESC"
        ).fetchall()
        return rows
    finally:
        conn.close()


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: int):
    """Get a single conversation with parsed messages."""
    conn = get_db()
    try:
        conv = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Parse the messages JSON for the response
        try:
            conv["messages"] = json.loads(conv["messages"]) if conv["messages"] else []
        except (json.JSONDecodeError, TypeError):
            conv["messages"] = []

        return conv
    finally:
        conn.close()

import json

from fastapi import APIRouter, HTTPException

from backend.database import get_db

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("")
async def list_conversations():
    """List all conversations."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM conversations ORDER BY last_message_at DESC"
        ).fetchall()
        return rows
    finally:
        conn.close()


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: int):
    """Get a single conversation with parsed messages."""
    conn = get_db()
    try:
        conv = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        try:
            conv["messages"] = json.loads(conv["messages"]) if conv["messages"] else []
        except (json.JSONDecodeError, TypeError):
            conv["messages"] = []

        return conv
    finally:
        conn.close()

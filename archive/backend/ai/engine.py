import json
from datetime import datetime, timezone

import anthropic

from backend.config import settings
from backend.ai.system_prompt import SYSTEM_PROMPT
from backend.ai.tools import TOOLS, execute_tool


def _make_api_messages(conversation_history: list[dict]) -> list[dict]:
    """Convert stored conversation history to Anthropic API message format.

    Stored messages have {role, content, timestamp} where content may be a
    string or a serialized list of content blocks (for tool_use / tool_result).
    The API expects content to be a string or list of block dicts.
    """
    api_messages = []
    for msg in conversation_history:
        content = msg["content"]
        # If content was serialized as JSON string representing blocks, deserialize
        if isinstance(content, str):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    content = parsed
            except (json.JSONDecodeError, TypeError):
                pass  # plain text, keep as-is
        api_messages.append({"role": msg["role"], "content": content})
    return api_messages


def _serialize_content(content) -> str:
    """Serialize message content for database storage.

    Plain text stays as text. Content block lists get JSON-encoded.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return json.dumps(content, default=str)
    return str(content)


def get_ai_response(
    conversation_history: list[dict],
    phone_number: str,
    system_prompt: str | None = None,
) -> tuple[str, list[dict]]:
    """Get a response from Claude, handling any tool use loops.

    Args:
        conversation_history: List of {role, content, timestamp} dicts.
        phone_number: The customer's phone number (for lead context).
        system_prompt: Override system prompt (defaults to SYSTEM_PROMPT).

    Returns:
        Tuple of (response_text, updated_conversation_history).
    """
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    prompt = system_prompt or SYSTEM_PROMPT

    # Build API-formatted messages
    api_messages = _make_api_messages(conversation_history)

    # Tool use loop — keep calling until we get a final text response
    max_iterations = 10
    for _ in range(max_iterations):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=prompt,
            messages=api_messages,
            tools=TOOLS,
        )

        # If the model stopped for end_turn (no more tool use), extract text
        if response.stop_reason == "end_turn":
            # Collect all text blocks
            text_parts = []
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)

            response_text = "\n".join(text_parts)

            # Store assistant response in history
            now = datetime.now(timezone.utc).isoformat()
            # Serialize content blocks for storage
            content_blocks = []
            for block in response.content:
                if block.type == "text":
                    content_blocks.append({"type": "text", "text": block.text})

            conversation_history.append({
                "role": "assistant",
                "content": _serialize_content(
                    response_text if len(content_blocks) == 1 else content_blocks
                ),
                "timestamp": now,
            })

            return response_text, conversation_history

        # Handle tool_use stop reason
        if response.stop_reason == "tool_use":
            # Build the full assistant content block list for the API
            assistant_content = []
            tool_uses = []
            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })
                    tool_uses.append(block)

            # Add assistant message with tool_use blocks
            api_messages.append({"role": "assistant", "content": assistant_content})

            # Store in conversation history
            now = datetime.now(timezone.utc).isoformat()
            conversation_history.append({
                "role": "assistant",
                "content": json.dumps(assistant_content, default=str),
                "timestamp": now,
            })

            # Execute each tool and build tool_result blocks
            tool_results = []
            for tool_block in tool_uses:
                result = execute_tool(tool_block.name, tool_block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": str(result),
                })

            # Add tool results as a user message
            api_messages.append({"role": "user", "content": tool_results})
            conversation_history.append({
                "role": "user",
                "content": json.dumps(tool_results, default=str),
                "timestamp": now,
            })

            # Continue the loop to get the next response
            continue

        # Unexpected stop reason — just extract any text we can
        text_parts = []
        for block in response.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
        response_text = "\n".join(text_parts) if text_parts else "hey, give me one sec"

        now = datetime.now(timezone.utc).isoformat()
        conversation_history.append({
            "role": "assistant",
            "content": response_text,
            "timestamp": now,
        })
        return response_text, conversation_history

    # If we somehow exhaust iterations, return a fallback
    return "hey let me get back to you on that", conversation_history

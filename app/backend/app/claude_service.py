import anthropic

from app.config import settings
from app.models import Message, Session
from app.prompts import build_system_prompt, extract_meta, parse_session_updates

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096


async def chat_with_claude(
    session: Session, messages: list[Message]
) -> tuple[str, dict]:
    """Send conversation to Claude and return (response_text, session_updates).

    Builds the system prompt from the current session phase, sends the full
    conversation history, and parses any META blocks from the response.
    """
    system_prompt = build_system_prompt(session)

    # Build messages list for the API
    api_messages = []
    for msg in messages:
        api_messages.append({"role": msg.role, "content": msg.content})

    # If this is the very first message in a new session, add an initial
    # assistant greeting so the interview starts naturally
    if not api_messages:
        api_messages.append(
            {
                "role": "user",
                "content": "Hello, I'd like help with my resume.",
            }
        )

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=api_messages,
    )

    raw_text = response.content[0].text

    # Extract META block and parse session updates
    clean_text, meta = extract_meta(raw_text)
    session_updates = parse_session_updates(meta)

    # Handle discovery_data merge
    if "_discovery_merge" in session_updates:
        merge_data = session_updates.pop("_discovery_merge")
        current = dict(session.discovery_data) if session.discovery_data else {}
        current.update(merge_data)
        session_updates["discovery_data"] = current

    return clean_text, session_updates

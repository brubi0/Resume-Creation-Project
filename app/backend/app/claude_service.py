from app.claude_client import ClaudeEmpty, create_message, response_text
from app.session_state import extract_meta

# Thinking is always on and counts toward max_tokens; replies are short, so this
# leaves ample headroom.
MAX_TOKENS = 16000


class EmptyReply(ClaudeEmpty):
    """The model answered with nothing the candidate could see."""


async def _call(system_prompt: str, api_messages: list[dict]) -> str:
    response = await create_message(
        effort="medium",
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=api_messages,
    )
    return response_text(response)


async def chat_with_claude(
    system_prompt: str, api_messages: list[dict]
) -> tuple[str, list]:
    """Send the conversation to Claude; return (clean_text, metas).

    The async client awaits the provider, so no DB transaction or lock is held and
    the event loop stays free. META blocks are returned as untrusted proposals
    (validated by session_state.validate_updates against the locked session).
    """
    # If this is the very first message in a new session, add an initial
    # greeting request so the interview starts naturally
    if not api_messages:
        api_messages = [{"role": "user", "content": "Hello, I'd like help with my resume."}]

    raw_text = await _call(system_prompt, api_messages)
    clean_text, metas = extract_meta(raw_text)
    if not clean_text:
        raise EmptyReply("The reply came back empty")
    return clean_text, metas

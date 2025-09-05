"""Session-backed one-time flash messages."""

from __future__ import annotations

from typing import TypedDict

from fastapi import Request

_SESSION_KEY = "__messages__"


class Message(TypedDict):
    level: str  # info|success|warning|error
    text: str


def add_message(request: Request, text: str, level: str = "info") -> None:
    """Append a message to the session store."""
    session = request.session
    messages: list[Message] = session.get(_SESSION_KEY, [])
    messages.append({"level": level, "text": text})
    session[_SESSION_KEY] = messages


def pop_messages(request: Request) -> list[Message]:
    """Return and clear one-time messages for this request."""
    session = request.session
    msgs = list(session.get(_SESSION_KEY, []))
    if _SESSION_KEY in session:
        del session[_SESSION_KEY]
    return msgs

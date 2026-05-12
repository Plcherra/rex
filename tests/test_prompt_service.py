from app.services.prompt_service import (
    FILE_CONTEXT_PREFIX,
    LONG_TERM_MEMORY_PREFIX,
    PERSONALITY_CONTEXT_PREFIX,
    PromptService,
    REX_PERSONALITY_PROMPT,
)


def test_prompt_service_always_includes_rex_personality():
    service = PromptService()

    messages = service.build_messages(user_message="Hello Rex")

    assert messages == [
        {
            "role": "system",
            "content": f"{PERSONALITY_CONTEXT_PREFIX}{REX_PERSONALITY_PROMPT}",
        },
        {"role": "user", "content": "Hello Rex"},
    ]
    assert "maximally honest, human-like, truth-seeking co-pilot" in (
        messages[0]["content"]
    )
    assert "fake positivity, vague disclaimers, or motivational fluff" in (
        messages[0]["content"]
    )
    assert "holds the user accountable" in messages[0]["content"]


def test_prompt_service_sanitizes_recent_message_history():
    service = PromptService()

    messages = service.build_messages(
        user_message="What now?",
        recent_messages=[
            {
                "id": "message-1",
                "role": "user",
                "content": "Earlier user message",
                "timestamp": "2026-05-12T12:00:00Z",
            },
            {
                "id": "message-2",
                "role": "assistant",
                "content": "Earlier assistant response",
                "timestamp": "2026-05-12T12:01:00Z",
            },
            {"role": "tool", "content": "Ignored unsupported role"},
            {"role": "user", "content": ""},
        ],
    )

    assert messages == [
        {
            "role": "system",
            "content": f"{PERSONALITY_CONTEXT_PREFIX}{REX_PERSONALITY_PROMPT}",
        },
        {"role": "user", "content": "Earlier user message"},
        {"role": "assistant", "content": "Earlier assistant response"},
        {"role": "user", "content": "What now?"},
    ]


def test_prompt_service_injects_time_conversation_memory_and_file_context():
    service = PromptService()

    messages = service.build_messages(
        user_message="Read this and help me decide.",
        recent_messages=[
            {"role": "assistant", "content": "What happened?"},
        ],
        relevant_memories=[
            {
                "memory_type": "preference",
                "content": "I prefer direct concise answers.",
                "relevance_reason": "Included high-priority user preference.",
            },
        ],
        file_context="Budget notes",
        conversation_metadata={
            "id": "conversation-1",
            "title": "Budget review",
            "timestamp": "2026-05-12T10:00:00Z",
            "last_message_timestamp": "2026-05-12T14:00:00Z",
        },
        time_context={
            "clock_context": "Tuesday afternoon (15:30 America/New_York (EDT))",
            "iso_timestamp": "2026-05-12T15:30:00-04:00",
            "date": "2026-05-12",
            "weekday": "Tuesday",
            "time": "15:30",
            "timezone": "America/New_York (EDT)",
            "previous_timestamp_delta": "earlier today",
        },
    )

    assert messages[0]["role"] == "system"
    system_content = messages[0]["content"]
    assert system_content.startswith(PERSONALITY_CONTEXT_PREFIX)
    assert "direct, natural, sharp" in system_content
    assert "Current time context:" in system_content
    assert "- Clock: Tuesday afternoon" in system_content
    assert "- Previous message delta: earlier today" in system_content
    assert "Conversation context:" in system_content
    assert "- Conversation ID: conversation-1" in system_content
    assert LONG_TERM_MEMORY_PREFIX in system_content
    assert "- preference: I prefer direct concise answers." in system_content
    assert "why recalled: Included high-priority user preference." in system_content
    assert messages[-3] == {"role": "assistant", "content": "What happened?"}
    assert messages[-2] == {
        "role": "user",
        "content": f"{FILE_CONTEXT_PREFIX}Budget notes",
    }
    assert messages[-1] == {
        "role": "user",
        "content": "Read this and help me decide.",
    }


def test_prompt_service_limits_injected_memory_context():
    service = PromptService()

    messages = service.build_messages(
        user_message="I need advice about work.",
        relevant_memories=[
            {
                "memory_type": "fact",
                "content": "work " * 1000,
                "importance": 5,
            },
        ],
    )

    memory_section = messages[0]["content"].split(LONG_TERM_MEMORY_PREFIX, 1)[1]
    assert len(memory_section) < 2200
    assert "[truncated]" in messages[0]["content"]


def test_prompt_service_trims_large_context_to_recent_messages():
    service = PromptService()

    messages = service.build_messages(
        user_message="latest question",
        recent_messages=[
            {"role": "user", "content": "old " * 10000},
            {"role": "assistant", "content": "recent answer"},
        ],
    )

    assert messages == [
        {
            "role": "system",
            "content": f"{PERSONALITY_CONTEXT_PREFIX}{REX_PERSONALITY_PROMPT}",
        },
        {"role": "assistant", "content": "recent answer"},
        {"role": "user", "content": "latest question"},
    ]


def test_prompt_service_trims_large_file_context_before_latest_user_message():
    service = PromptService()

    messages = service.build_messages(
        user_message="summarize",
        file_context="file " * 10000,
    )

    assert len(messages) == 3
    assert messages[0]["content"].startswith(PERSONALITY_CONTEXT_PREFIX)
    assert messages[1]["content"].startswith(FILE_CONTEXT_PREFIX)
    assert messages[1]["content"].endswith("[File truncated]")
    assert messages[2] == {"role": "user", "content": "summarize"}

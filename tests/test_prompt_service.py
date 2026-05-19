from app.services.prompt_service import (
    ACCOUNTABILITY_CONTEXT_PREFIX,
    CONVERSATION_CONTEXT_PREFIX,
    FILE_CONTEXT_PREFIX,
    LONG_TERM_MEMORY_PREFIX,
    PERSONALITY_CONTEXT_PREFIX,
    PromptService,
    REX_PERSONALITY_PROMPT,
    STRUCTURED_MEMORY_PREFIX,
    TIME_CONTEXT_PREFIX,
)
from app.services.time_context_service import TimeContextService


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
    service = PromptService(TimeContextService(timezone_name="America/New_York"))

    messages = service.build_messages(
        user_message="Read this and help me decide.",
        recent_messages=[
            {"role": "assistant", "content": "What happened?"},
        ],
        relevant_memories=[
            {
                "memory_type": "preference",
                "content": "I prefer direct concise answers.",
                "created_at": "2026-04-30T15:30:00-04:00",
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
    assert "saved 12 days ago" in system_content
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


def test_prompt_service_injects_structured_memory_before_generic_memory():
    service = PromptService(TimeContextService(timezone_name="America/New_York"))

    messages = service.build_messages(
        user_message="I saw Clara and ordered DoorDash again.",
        relevant_memories=[
            {
                "memory_type": "event",
                "content": "I said DoorDash was hurting my budget.",
            },
        ],
        structured_context={
            "entities": [
                {
                    "id": "entity-clara",
                    "entity_type": "person",
                    "display_name": "Clara",
                    "relationship": "dating interest from work",
                    "summary": "Clara touched my arm and matters to the dating story.",
                    "relevance_reason": "Matched current message terms: clara",
                }
            ],
            "entity_events": [
                {
                    "entity_id": "entity-clara",
                    "event_type": "interaction",
                    "title": "Clara touched my arm",
                    "content": "This felt like flirting at work.",
                    "occurred_at": "2026-05-18T12:00:00Z",
                }
            ],
            "personal_rules": [
                {
                    "rule_type": "finance",
                    "title": "Avoid DoorDash",
                    "rule_text": "Do not order DoorDash while the budget is slipping.",
                    "relevance_reason": "Matched current message terms: doordash",
                }
            ],
            "plans": [
                {
                    "id": "plan-visa",
                    "plan_type": "immigration",
                    "title": "Visa runway",
                    "desired_outcome": "Leave with enough money and clean paperwork.",
                    "target_date": "2026-07-01",
                    "relevance_reason": "Matched current message terms: visa",
                }
            ],
            "plan_milestones": [
                {
                    "plan_id": "plan-visa",
                    "milestone_type": "deadline",
                    "title": "Prepare immigration documents",
                    "target_date": "2026-06-01",
                }
            ],
            "commitments": [
                {
                    "commitment_type": "deadline",
                    "title": "Review visa paperwork",
                    "commitment_text": "Review the visa documents before June.",
                    "plan_id": "plan-visa",
                    "due_at": "2026-05-31T18:00:00Z",
                    "relevance_reason": "Matched current message terms: visa",
                }
            ],
        },
    )

    system_content = messages[0]["content"]
    assert system_content.index(STRUCTURED_MEMORY_PREFIX) < system_content.index(
        LONG_TERM_MEMORY_PREFIX
    )
    assert "- entity/person Clara - dating interest from work" in system_content
    assert "Clara touched my arm and matters to the dating story." in system_content
    assert "- entity_event/interaction for Clara: Clara touched my arm" in (
        system_content
    )
    assert "- rule/finance Avoid DoorDash: Do not order DoorDash" in system_content
    assert "- plan/immigration Visa runway: Leave with enough money" in system_content
    assert "- milestone/deadline for Visa runway: Prepare immigration documents" in (
        system_content
    )
    assert "- commitment/deadline Review visa paperwork" in system_content
    assert "plan: Visa runway" in system_content


def test_prompt_service_injects_accountability_before_generic_memory():
    service = PromptService(TimeContextService(timezone_name="America/New_York"))

    messages = service.build_messages(
        user_message="I ordered DoorDash again.",
        relevant_memories=[
            {
                "memory_type": "event",
                "content": "I committed to stop ordering DoorDash in May.",
            }
        ],
        accountability_signals=[
            {
                "signal_type": "rule_violation",
                "severity": "high",
                "confidence": 0.87,
                "title": "Possible rule violation: Avoid DoorDash",
                "reason": "The message matched active DoorDash rule triggers.",
                "source_refs": [
                    {
                        "source_type": "personal_rule",
                        "title": "Avoid DoorDash",
                        "excerpt": "Do not order DoorDash while the budget is slipping.",
                    }
                ],
                "suggested_prompt": (
                    "You said DoorDash was off-limits while the budget is slipping."
                ),
                "recommended_action": "Hold the user to the rule.",
            }
        ],
    )

    system_content = messages[0]["content"]
    assert ACCOUNTABILITY_CONTEXT_PREFIX in system_content
    assert system_content.index(ACCOUNTABILITY_CONTEXT_PREFIX) < system_content.index(
        LONG_TERM_MEMORY_PREFIX
    )
    assert (
        "- rule_violation/high: Possible rule violation: Avoid DoorDash"
        in system_content
    )
    assert "confidence: 0.87" in system_content
    assert "sources: personal_rule:Avoid DoorDash" in system_content
    assert "Suggested framing: You said DoorDash was off-limits" in system_content
    assert "Action: Hold the user to the rule." in system_content


def test_prompt_service_limits_structured_memory_context_budget():
    service = PromptService()

    messages = service.build_messages(
        user_message="Tell me what matters about Clara.",
        structured_context={
            "entities": [
                {
                    "id": "entity-clara",
                    "entity_type": "person",
                    "display_name": "Clara",
                    "relationship": "dating interest",
                    "summary": "Clara " * 1000,
                    "relevance_reason": "Matched current message terms: clara",
                }
            ]
        },
    )

    structured_section = messages[0]["content"].split(
        STRUCTURED_MEMORY_PREFIX,
        1,
    )[1]
    assert len(structured_section) < 3200
    assert "[truncated]" in structured_section


def test_prompt_shape_contains_required_time_aware_founder_context():
    service = PromptService(TimeContextService(timezone_name="America/New_York"))

    messages = service.build_messages(
        user_message="I ordered DoorDash again. Be honest with me.",
        recent_messages=[
            {
                "role": "user",
                "content": "Last time I said I would cut delivery.",
                "timestamp": "2026-05-10T22:15:00-04:00",
            },
            {
                "role": "assistant",
                "content": "You need to stop the pattern this week.",
                "timestamp": "2026-05-10T22:16:00-04:00",
            },
        ],
        relevant_memories=[
            {
                "memory_type": "preference",
                "content": "I want direct accountability about food delivery.",
                "created_at": "2026-04-30T15:30:00-04:00",
                "relevance_reason": "Matched current message terms: delivery",
            },
            {
                "memory_type": "event",
                "content": "I committed to stop ordering DoorDash in May.",
                "updated_at": "2026-05-05T15:30:00-04:00",
                "relevance_reason": "Matched current message terms: doordash",
            },
        ],
        file_context="Budget CSV summary: DoorDash spending is over the weekly cap.",
        conversation_metadata={
            "id": "conversation-budget",
            "title": "Budget accountability",
            "timestamp": "2026-05-10T22:15:00-04:00",
            "last_message_timestamp": "2026-05-10T22:16:00-04:00",
        },
        time_context={
            "clock_context": "Tuesday afternoon (15:30 America/New_York (EDT))",
            "iso_timestamp": "2026-05-12T15:30:00-04:00",
            "date": "2026-05-12",
            "weekday": "Tuesday",
            "time": "15:30",
            "timezone": "America/New_York (EDT)",
            "previous_timestamp_delta": "2 days ago",
        },
    )

    assert [message["role"] for message in messages] == [
        "system",
        "user",
        "assistant",
        "user",
        "user",
    ]

    system_content = messages[0]["content"]
    assert system_content.index(PERSONALITY_CONTEXT_PREFIX) < system_content.index(
        TIME_CONTEXT_PREFIX
    )
    assert system_content.index(TIME_CONTEXT_PREFIX) < system_content.index(
        CONVERSATION_CONTEXT_PREFIX
    )
    assert system_content.index(CONVERSATION_CONTEXT_PREFIX) < system_content.index(
        LONG_TERM_MEMORY_PREFIX
    )

    assert "uncensored, voice-first, time-aware" in system_content
    assert "fake positivity, vague disclaimers, or motivational fluff" in system_content
    assert "holds the user accountable" in system_content
    assert "- Clock: Tuesday afternoon (15:30 America/New_York (EDT))" in (
        system_content
    )
    assert "- ISO timestamp: 2026-05-12T15:30:00-04:00" in system_content
    assert "- Date: 2026-05-12" in system_content
    assert "- Weekday: Tuesday" in system_content
    assert "- Previous message delta: 2 days ago" in system_content
    assert "- Conversation ID: conversation-budget" in system_content
    assert "- Title: Budget accountability" in system_content
    assert "- Last message timestamp: 2026-05-10T22:16:00-04:00" in system_content
    assert (
        "- preference: I want direct accountability about food delivery. "
        "(saved 12 days ago) "
        "(why recalled: Matched current message terms: delivery)"
    ) in system_content
    assert (
        "- event: I committed to stop ordering DoorDash in May. "
        "(saved 7 days ago) "
        "(why recalled: Matched current message terms: doordash)"
    ) in system_content

    assert messages[-2] == {
        "role": "user",
        "content": (
            f"{FILE_CONTEXT_PREFIX}"
            "Budget CSV summary: DoorDash spending is over the weekly cap."
        ),
    }
    assert messages[-1] == {
        "role": "user",
        "content": "I ordered DoorDash again. Be honest with me.",
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


def test_prompt_service_uses_updated_at_before_created_at_for_memory_age():
    service = PromptService(TimeContextService(timezone_name="America/New_York"))

    messages = service.build_messages(
        user_message="What should I remember?",
        relevant_memories=[
            {
                "memory_type": "fact",
                "content": "I am working on budget discipline.",
                "created_at": "2026-03-12T15:30:00-04:00",
                "updated_at": "2026-05-11T15:30:00-04:00",
            },
        ],
        time_context={
            "iso_timestamp": "2026-05-12T15:30:00-04:00",
        },
    )

    assert "saved 1 day ago" in messages[0]["content"]
    assert "about 2 months ago" not in messages[0]["content"]


def test_prompt_service_omits_memory_age_for_missing_or_invalid_timestamps():
    service = PromptService(TimeContextService(timezone_name="America/New_York"))

    messages = service.build_messages(
        user_message="What should I remember?",
        relevant_memories=[
            {
                "memory_type": "fact",
                "content": "I prefer direct advice.",
                "created_at": "not-a-timestamp",
            },
            {
                "memory_type": "event",
                "content": "I started a new plan.",
            },
        ],
        time_context={
            "iso_timestamp": "2026-05-12T15:30:00-04:00",
        },
    )

    system_content = messages[0]["content"]
    assert "- fact: I prefer direct advice." in system_content
    assert "- event: I started a new plan." in system_content
    assert "saved " not in system_content


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

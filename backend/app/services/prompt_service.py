from typing import Optional

from app.services.time_context_service import TimeContextService

MAX_CONTEXT_CHARACTERS = 24000
MAX_MEMORY_CONTEXT_CHARACTERS = 2000
MAX_STRUCTURED_MEMORY_CONTEXT_CHARACTERS = 3000
REX_PERSONALITY_PROMPT = """
Rex is a private personal AI assistant with long-term memory. It is being built first as the founder's personal daily driver: an uncensored, voice-first, time-aware, memory-powered life co-pilot that knows the ongoing story and gives direct, useful feedback without generic corporate filler.

Rex should feel like talking to a maximally honest, human-like, truth-seeking co-pilot. The target personality is Grok-level or better: direct, natural, sharp, and willing to say the uncomfortable thing when it is useful. Rex should not hide behind fake positivity, vague disclaimers, or motivational fluff. It should feel like a real friend who knows the user deeply, remembers the patterns, and holds the user accountable.

Rex should be:
- Direct, honest, and natural.
- Voice-first, with text as the secondary/backup input method.
- Casual enough to feel human, but still useful and grounded.
- Able to remember important personal context across weeks and months.
- Strong at time awareness: it must understand when events happened, how much time has passed, and what has changed since the last conversation.
- Strong at people/entity tracking: it should remember specific people, jobs, plans, rules, recurring topics, and relationship context.
- Strong at structured memory: it should treat entities, personal rules, plans, milestones, and commitments as durable context when those records are provided.
- Useful on sensitive real-life topics: dating life and girl relationships, immigration/visa strategy, money stress, budget failures, work pressure, long-term life plans, frustrations, and daily decisions.
- Private by design, with memory stored in Supabase rather than scattered across third-party chat apps.
- Available through a real Flutter mobile app, not a Telegram bot as the main interface.

The target experience is simple: the founder puts the phone in a pocket, walks, talks naturally, and Rex responds by voice with context-aware advice. If the user says, "Clara touched my arm today," Rex should know who Clara is from previous context, why that matters, and how it fits into the broader dating story. If the user says, "I ordered DoorDash again," Rex should be able to say, directly, "You said last month you were cutting DoorDash because your budget was slipping, and this is the same pattern again."
""".strip()
FILE_CONTEXT_PREFIX = "Uploaded file content:\n\n"
PERSONALITY_CONTEXT_PREFIX = "Rex personality and behavior:\n"
TIME_CONTEXT_PREFIX = "Current time context:\n"
CONVERSATION_CONTEXT_PREFIX = "Conversation context:\n"
STRUCTURED_MEMORY_PREFIX = "Relevant structured memory:\n"
LONG_TERM_MEMORY_PREFIX = "Relevant long-term memory:\n"


class PromptService:
    def __init__(
        self,
        time_context_service: Optional[TimeContextService] = None,
    ) -> None:
        self.time_context_service = time_context_service or TimeContextService()

    def build_messages(
        self,
        user_message: str,
        recent_messages: Optional[list[dict]] = None,
        relevant_memories: Optional[list[dict]] = None,
        structured_context: Optional[dict] = None,
        file_context: Optional[str] = None,
        conversation_metadata: Optional[dict] = None,
        time_context: Optional[dict] = None,
    ) -> list[dict]:
        messages = [
            *self._message_history(recent_messages or []),
            {"role": "user", "content": user_message},
        ]
        messages = self._messages_with_file_context(messages, file_context)

        system_sections = self._system_sections(
            relevant_memories=relevant_memories or [],
            structured_context=structured_context or {},
            conversation_metadata=conversation_metadata,
            time_context=time_context,
        )
        if system_sections:
            messages = [
                {"role": "system", "content": "\n\n".join(system_sections)},
                *messages,
            ]

        return self._trim_context(messages)

    def _message_history(self, recent_messages: list[dict]) -> list[dict]:
        messages = []
        for message in recent_messages:
            role = message.get("role")
            content = message.get("content")
            if role not in {"user", "assistant", "system"} or not content:
                continue
            messages.append({"role": role, "content": str(content)})
        return messages

    def _system_sections(
        self,
        relevant_memories: list[dict],
        structured_context: dict,
        conversation_metadata: Optional[dict],
        time_context: Optional[dict],
    ) -> list[str]:
        sections = [f"{PERSONALITY_CONTEXT_PREFIX}{REX_PERSONALITY_PROMPT}"]

        time_section = self._time_context_section(time_context)
        if time_section:
            sections.append(time_section)

        conversation_section = self._conversation_context_section(
            conversation_metadata,
        )
        if conversation_section:
            sections.append(conversation_section)

        structured_section = self._structured_memory_section(structured_context)
        if structured_section:
            sections.append(structured_section)

        memory_section = self._long_term_memory_section(
            relevant_memories,
            time_context,
        )
        if memory_section:
            sections.append(memory_section)

        return sections

    def _time_context_section(self, time_context: Optional[dict]) -> Optional[str]:
        if not time_context:
            return None

        lines = []
        fields = [
            ("clock_context", "Clock"),
            ("iso_timestamp", "ISO timestamp"),
            ("date", "Date"),
            ("weekday", "Weekday"),
            ("time", "Time"),
            ("timezone", "Timezone"),
            ("previous_timestamp_delta", "Previous message delta"),
        ]
        for key, label in fields:
            value = time_context.get(key)
            if value:
                lines.append(f"- {label}: {value}")

        if not lines:
            return None
        return f"{TIME_CONTEXT_PREFIX}{chr(10).join(lines)}"

    def _conversation_context_section(
        self,
        conversation_metadata: Optional[dict],
    ) -> Optional[str]:
        if not conversation_metadata:
            return None

        lines = []
        fields = [
            ("id", "Conversation ID"),
            ("title", "Title"),
            ("timestamp", "Conversation timestamp"),
            ("last_message_timestamp", "Last message timestamp"),
        ]
        for key, label in fields:
            value = conversation_metadata.get(key)
            if value:
                lines.append(f"- {label}: {value}")

        if not lines:
            return None
        return f"{CONVERSATION_CONTEXT_PREFIX}{chr(10).join(lines)}"

    def _structured_memory_section(self, structured_context: dict) -> Optional[str]:
        if not structured_context:
            return None

        lines: list[str] = []
        used_characters = 0
        entity_names = self._entity_name_map(structured_context.get("entities") or [])
        plan_titles = self._plan_title_map(structured_context.get("plans") or [])

        for entity in structured_context.get("entities") or []:
            used_characters = self._append_structured_line(
                lines,
                used_characters,
                self._entity_line(entity),
            )
        for event in structured_context.get("entity_events") or []:
            used_characters = self._append_structured_line(
                lines,
                used_characters,
                self._entity_event_line(event, entity_names),
            )
        for rule in structured_context.get("personal_rules") or []:
            used_characters = self._append_structured_line(
                lines,
                used_characters,
                self._personal_rule_line(rule),
            )
        for plan in structured_context.get("plans") or []:
            used_characters = self._append_structured_line(
                lines,
                used_characters,
                self._plan_line(plan),
            )
        for milestone in structured_context.get("plan_milestones") or []:
            used_characters = self._append_structured_line(
                lines,
                used_characters,
                self._milestone_line(milestone, plan_titles),
            )
        for commitment in structured_context.get("commitments") or []:
            used_characters = self._append_structured_line(
                lines,
                used_characters,
                self._commitment_line(commitment, entity_names, plan_titles),
            )

        if not lines:
            return None
        return f"{STRUCTURED_MEMORY_PREFIX}{chr(10).join(lines)}"

    def _append_structured_line(
        self,
        lines: list[str],
        used_characters: int,
        line: Optional[str],
    ) -> int:
        if not line:
            return used_characters

        remaining_characters = (
            MAX_STRUCTURED_MEMORY_CONTEXT_CHARACTERS - used_characters
        )
        if remaining_characters <= 0:
            return used_characters
        if len(line) > remaining_characters:
            if remaining_characters < 40:
                return used_characters
            line = f"{line[: remaining_characters - 22].rstrip()} [truncated]"

        lines.append(line)
        return used_characters + len(line) + 1

    def _entity_line(self, entity: dict) -> Optional[str]:
        name = entity.get("display_name") or entity.get("normalized_name")
        if not name:
            return None

        parts = [f"- entity/{entity.get('entity_type') or 'unknown'} {name}"]
        relationship = entity.get("relationship")
        if relationship:
            parts.append(str(relationship))
        summary = entity.get("summary")
        if summary:
            parts.append(str(summary))
        return self._with_relevance(" - ".join(parts), entity)

    def _entity_event_line(
        self,
        event: dict,
        entity_names: dict[str, str],
    ) -> Optional[str]:
        title = event.get("title")
        content = event.get("content")
        if not title and not content:
            return None

        entity_name = entity_names.get(str(event.get("entity_id") or ""))
        subject = f" for {entity_name}" if entity_name else ""
        line = f"- entity_event/{event.get('event_type') or 'event'}{subject}"
        if title:
            line = f"{line}: {title}"
        if content:
            line = f"{line} - {content}"
        occurred_at = event.get("occurred_at")
        if occurred_at:
            line = f"{line} (occurred: {occurred_at})"
        return line

    def _personal_rule_line(self, rule: dict) -> Optional[str]:
        title = rule.get("title")
        rule_text = rule.get("rule_text")
        if not title and not rule_text:
            return None

        line = f"- rule/{rule.get('rule_type') or 'personal'}"
        if title:
            line = f"{line} {title}"
        if rule_text:
            line = f"{line}: {rule_text}"
        return self._with_relevance(line, rule)

    def _plan_line(self, plan: dict) -> Optional[str]:
        title = plan.get("title")
        if not title:
            return None

        line = f"- plan/{plan.get('plan_type') or 'goal'} {title}"
        desired_outcome = plan.get("desired_outcome")
        description = plan.get("description")
        if desired_outcome:
            line = f"{line}: {desired_outcome}"
        elif description:
            line = f"{line}: {description}"
        target_date = plan.get("target_date")
        if target_date:
            line = f"{line} (target: {target_date})"
        return self._with_relevance(line, plan)

    def _milestone_line(
        self,
        milestone: dict,
        plan_titles: dict[str, str],
    ) -> Optional[str]:
        title = milestone.get("title")
        if not title:
            return None

        plan_title = plan_titles.get(str(milestone.get("plan_id") or ""))
        subject = f" for {plan_title}" if plan_title else ""
        line = f"- milestone/{milestone.get('milestone_type') or 'step'}{subject}: {title}"
        description = milestone.get("description")
        if description:
            line = f"{line} - {description}"
        target_date = milestone.get("target_date")
        if target_date:
            line = f"{line} (target: {target_date})"
        return line

    def _commitment_line(
        self,
        commitment: dict,
        entity_names: dict[str, str],
        plan_titles: dict[str, str],
    ) -> Optional[str]:
        title = commitment.get("title")
        text = commitment.get("commitment_text")
        if not title and not text:
            return None

        line = f"- commitment/{commitment.get('commitment_type') or 'deadline'}"
        if title:
            line = f"{line} {title}"
        if text:
            line = f"{line}: {text}"

        links = []
        entity_name = entity_names.get(str(commitment.get("entity_id") or ""))
        if entity_name:
            links.append(f"person: {entity_name}")
        plan_title = plan_titles.get(str(commitment.get("plan_id") or ""))
        if plan_title:
            links.append(f"plan: {plan_title}")
        due_at = commitment.get("due_at")
        if due_at:
            links.append(f"due: {due_at}")
        if links:
            line = f"{line} ({'; '.join(links)})"
        return self._with_relevance(line, commitment)

    def _with_relevance(self, line: str, record: dict) -> str:
        relevance_reason = record.get("relevance_reason")
        if relevance_reason:
            return f"{line} (why recalled: {relevance_reason})"
        return line

    def _entity_name_map(self, entities: list[dict]) -> dict[str, str]:
        return {
            str(entity["id"]): str(
                entity.get("display_name") or entity.get("normalized_name")
            )
            for entity in entities
            if entity.get("id")
            and (entity.get("display_name") or entity.get("normalized_name"))
        }

    def _plan_title_map(self, plans: list[dict]) -> dict[str, str]:
        return {
            str(plan["id"]): str(plan["title"])
            for plan in plans
            if plan.get("id") and plan.get("title")
        }

    def _long_term_memory_section(
        self,
        relevant_memories: list[dict],
        time_context: Optional[dict],
    ) -> Optional[str]:
        memory_lines = self._memory_lines_with_budget(relevant_memories, time_context)
        if not memory_lines:
            return None
        return f"{LONG_TERM_MEMORY_PREFIX}{chr(10).join(memory_lines)}"

    def _memory_lines_with_budget(
        self,
        relevant_memories: list[dict],
        time_context: Optional[dict],
    ) -> list[str]:
        memory_lines = []
        used_characters = 0

        for memory in relevant_memories:
            memory_type = memory.get("memory_type")
            content = memory.get("content")
            if not memory_type or not content:
                continue

            line = f"- {memory_type}: {content}"
            age_label = self._memory_age_label(memory, time_context)
            if age_label:
                line = f"{line} ({age_label})"
            relevance_reason = memory.get("relevance_reason")
            if relevance_reason:
                line = f"{line} (why recalled: {relevance_reason})"

            remaining_characters = MAX_MEMORY_CONTEXT_CHARACTERS - used_characters
            if remaining_characters <= 0:
                break
            if len(line) > remaining_characters:
                if remaining_characters < 40:
                    break
                line = f"{line[: remaining_characters - 22].rstrip()} [truncated]"

            memory_lines.append(line)
            used_characters += len(line) + 1

        return memory_lines

    def _memory_age_label(
        self,
        memory: dict,
        time_context: Optional[dict],
    ) -> Optional[str]:
        timestamp = memory.get("updated_at") or memory.get("created_at")
        if not timestamp:
            return None

        now = None
        if time_context:
            now = self.time_context_service.parse_timestamp(
                time_context.get("iso_timestamp"),
            )
        delta = self.time_context_service.delta_from(timestamp, now=now)
        if not delta:
            return None

        return f"saved {delta}"

    def _messages_with_file_context(
        self,
        messages: list[dict],
        file_context: Optional[str],
    ) -> list[dict]:
        if not file_context:
            return messages

        file_message = {
            "role": "user",
            "content": f"{FILE_CONTEXT_PREFIX}{file_context}",
        }
        if not messages:
            return [file_message]

        return [
            *messages[:-1],
            file_message,
            messages[-1],
        ]

    def _trim_context(self, messages: list[dict]) -> list[dict]:
        trimmed_messages = list(messages)
        while (
            len(trimmed_messages) > 1
            and self._context_length(trimmed_messages) > MAX_CONTEXT_CHARACTERS
        ):
            remove_index = 1 if trimmed_messages[0].get("role") == "system" else 0
            if self._has_file_context(trimmed_messages[remove_index]):
                break

            trimmed_messages.pop(remove_index)

        trimmed_messages = self._trim_file_context(trimmed_messages)
        if self._context_length(trimmed_messages) > MAX_CONTEXT_CHARACTERS:
            last_message = trimmed_messages[-1]
            return [
                {
                    **last_message,
                    "content": last_message["content"][-MAX_CONTEXT_CHARACTERS:],
                }
            ]

        return trimmed_messages

    def _context_length(self, messages: list[dict]) -> int:
        return sum(len(message["content"]) for message in messages)

    def _trim_file_context(self, messages: list[dict]) -> list[dict]:
        file_index = self._file_context_index(messages)
        if file_index is None or len(messages) < 2:
            return messages

        latest_message = messages[-1]
        truncation_note = "\n\n[File truncated]"
        available_file_characters = (
            MAX_CONTEXT_CHARACTERS
            - len(latest_message["content"])
            - len(FILE_CONTEXT_PREFIX)
            - len(truncation_note)
            - self._context_length(messages[:file_index])
        )
        if available_file_characters <= 0:
            return [*messages[:file_index], latest_message]

        file_message = messages[file_index]
        file_text = file_message["content"][len(FILE_CONTEXT_PREFIX) :]
        if len(file_text) <= available_file_characters:
            return messages

        return [
            *messages[:file_index],
            {
                **file_message,
                "content": (
                    f"{FILE_CONTEXT_PREFIX}"
                    f"{file_text[:available_file_characters]}{truncation_note}"
                ),
            },
            *messages[file_index + 1 :],
        ]

    def _has_file_context(self, message: dict) -> bool:
        return message["content"].startswith(FILE_CONTEXT_PREFIX)

    def _file_context_index(self, messages: list[dict]) -> Optional[int]:
        for index, message in enumerate(messages):
            if self._has_file_context(message):
                return index
        return None

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Optional, Protocol

from fastapi import UploadFile

from app.models.memory_candidate import (
    MemoryCandidateApproveRequest,
    MemoryCandidateBulkDecisionRequest,
    MemoryCandidateCreateRequest,
    MemoryCandidateRejectRequest,
)
from app.services.ai_service import AIService
from app.services.accountability_service import AccountabilityService
from app.services.file_service import FileService
from app.services.memory_candidate_service import MemoryCandidateService
from app.services.memory_extraction_service import MemoryExtractionService
from app.services.memory_correction_service import MemoryCorrectionService
from app.services.memory_discipline_service import MemoryDisciplineService
from app.services.prompt_service import PromptService
from app.services.time_context_service import TimeContextService

PROFILE_MEMORY_QUERY = (
    "user profile location timezone where I live state city home current time "
    "important identity facts"
)
PROFILE_MEMORY_LIMIT = 4
APPROVE_ALL_PHRASES = {
    "approve all",
    "approve all pending",
    "apply all",
    "apply all pending",
    "confirm all",
    "save all",
    "save all pending",
}
REJECT_ALL_PHRASES = {
    "reject all",
    "reject all pending",
    "discard all",
    "discard all pending",
    "do not save any",
    "dont save any",
}
APPROVE_PHRASES = {
    "yes",
    "yep",
    "yeah",
    "ok",
    "okay",
    "sure",
    "confirm",
    "confirmed",
    "do it",
    "apply",
    "approve",
    "approve it",
    "save it",
    "save that",
    "looks good",
}
VAGUE_APPROVE_PHRASES = {
    "yes",
    "yep",
    "yeah",
    "ok",
    "okay",
    "sure",
}
REJECT_PHRASES = {
    "no",
    "nope",
    "reject",
    "discard",
    "dont save",
    "do not save",
    "cancel",
}
LOW_RISK_AUTO_APPLY_ENABLED = False


class ConversationNotFoundError(Exception):
    pass


class MemoryService(Protocol):
    async def create_conversation(self) -> str:
        pass

    async def conversation_exists(self, conversation_id: str) -> bool:
        pass

    async def save_message(self, conversation_id: str, role: str, content: str) -> dict:
        pass

    async def get_recent_messages(
        self,
        conversation_id: str,
        limit: int = 20,
    ) -> list[dict]:
        pass

    async def save_long_term_memory(
        self,
        memory_type: str,
        content: str,
        source_conversation_id: Optional[str] = None,
        source_message_id: Optional[str] = None,
        importance: int = 3,
    ) -> dict:
        pass

    async def get_relevant_memories(self, query: str, limit: int = 8) -> list[dict]:
        pass

    async def get_structured_memory_context(self, query: str) -> dict:
        pass

    async def save_voice_turn(
        self,
        conversation_id: str,
        user_message_id: Optional[str] = None,
        assistant_message_id: Optional[str] = None,
        transcript_confidence: Optional[float] = None,
        audio_duration_seconds: Optional[float] = None,
        input_mime_type: Optional[str] = None,
        output_audio_encoding: Optional[str] = None,
        stt_vendor: str = "deepgram",
        tts_vendor: str = "google_tts",
        metadata: Optional[dict] = None,
    ) -> dict:
        pass


class ChatService:
    def __init__(
        self,
        ai_service: AIService,
        file_service: FileService,
        memory_service: MemoryService,
        memory_extraction_service: Optional[MemoryExtractionService] = None,
        prompt_service: Optional[PromptService] = None,
        time_context_service: Optional[TimeContextService] = None,
        accountability_service: Optional[AccountabilityService] = None,
        memory_discipline_service: Optional[MemoryDisciplineService] = None,
        memory_correction_service: Optional[MemoryCorrectionService] = None,
        memory_candidate_service: Optional[MemoryCandidateService] = None,
    ) -> None:
        self.ai_service = ai_service
        self.file_service = file_service
        self.memory_service = memory_service
        self.memory_extraction_service = memory_extraction_service
        self.prompt_service = prompt_service or PromptService()
        self.time_context_service = time_context_service or TimeContextService()
        self.accountability_service = accountability_service or AccountabilityService()
        self.memory_discipline_service = memory_discipline_service
        self.memory_correction_service = memory_correction_service
        self.memory_candidate_service = memory_candidate_service
        self._background_tasks: set[asyncio.Task[None]] = set()

    async def send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        file: Optional[UploadFile] = None,
    ) -> dict:
        conversation_id = await self._existing_conversation_id(conversation_id)
        file_text = await self.file_service.read_text_file(file) if file else None

        (
            conversation_history,
            long_term_memory,
            structured_context,
        ) = await self._fetch_prompt_context(
            message=message,
            conversation_id=conversation_id,
        )

        if conversation_id is None:
            conversation_id = await self.memory_service.create_conversation()

        time_context = self._current_time_context(conversation_history)
        accountability_signals = await self._accountability_signals(
            message=message,
            time_context=time_context,
            long_term_memory=long_term_memory,
            structured_context=structured_context,
        )

        ai_messages = self._build_prompt_messages(
            message=message,
            conversation_id=conversation_id,
            conversation_history=conversation_history,
            long_term_memory=long_term_memory,
            structured_context=structured_context,
            accountability_signals=accountability_signals,
            file_text=file_text,
            time_context=time_context,
        )

        user_message = await self.memory_service.save_message(
            conversation_id,
            "user",
            message,
        )
        candidate_decision = await self._handle_memory_candidate_decision(
            message,
            conversation_id=conversation_id,
        )
        if candidate_decision:
            assistant_message = await self.memory_service.save_message(
                conversation_id,
                "assistant",
                candidate_decision["response"],
            )
            return {
                "conversation_id": conversation_id,
                "response": candidate_decision["response"],
                "user_message": user_message,
                "assistant_message": assistant_message,
                "memory_correction": None,
                "memory_changes": candidate_decision["memory_changes"],
                "messages": await self.memory_service.get_recent_messages(
                    conversation_id,
                    limit=20,
                ),
            }
        memory_correction = await self._apply_memory_correction(
            message,
            conversation_id=conversation_id,
            user_message_id=str(user_message.get("id") or ""),
        )
        if memory_correction:
            ai_messages.append(self._memory_correction_prompt(memory_correction))

        rex_response = await self.ai_service.generate_response(ai_messages)
        assistant_message = await self.memory_service.save_message(
            conversation_id,
            "assistant",
            rex_response,
        )

        memory_changes = None
        if self._correction_blocks_extraction(memory_correction):
            memory_changes = self._memory_change_summary(
                [],
                memory_correction=memory_correction,
                skipped_reason="correction_already_handled",
            )
        else:
            extracted_memories = await self._extract_memory_after_success(
                conversation_id,
                user_message,
                assistant_message,
            )
            memory_changes = self._memory_change_summary(
                extracted_memories,
                memory_correction=memory_correction,
            )

        return {
            "conversation_id": conversation_id,
            "response": rex_response,
            "user_message": user_message,
            "assistant_message": assistant_message,
            "memory_correction": memory_correction,
            "memory_changes": memory_changes,
            "messages": await self.memory_service.get_recent_messages(
                conversation_id,
                limit=20,
            ),
        }

    async def save_voice_turn_metadata(
        self,
        conversation_id: str,
        user_message_id: Optional[str] = None,
        assistant_message_id: Optional[str] = None,
        transcript_confidence: Optional[float] = None,
        audio_duration_seconds: Optional[float] = None,
        input_mime_type: Optional[str] = None,
        output_audio_encoding: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[dict]:
        try:
            return await self.memory_service.save_voice_turn(
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
                transcript_confidence=transcript_confidence,
                audio_duration_seconds=audio_duration_seconds,
                input_mime_type=input_mime_type,
                output_audio_encoding=output_audio_encoding,
                metadata=metadata,
            )
        except Exception:
            # Voice metadata is useful for debugging, but raw conversation
            # success should not depend on trace metadata persistence.
            return None

    async def stream_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        file: Optional[UploadFile] = None,
        response_instructions: Optional[str] = None,
        max_response_tokens: Optional[int] = None,
    ) -> AsyncIterator[dict]:
        conversation_id = await self._existing_conversation_id(conversation_id)
        file_text = await self.file_service.read_text_file(file) if file else None

        (
            conversation_history,
            long_term_memory,
            structured_context,
        ) = await self._fetch_prompt_context(
            message=message,
            conversation_id=conversation_id,
        )

        if conversation_id is None:
            conversation_id = await self.memory_service.create_conversation()

        time_context = self._current_time_context(conversation_history)
        accountability_signals = await self._accountability_signals(
            message=message,
            time_context=time_context,
            long_term_memory=long_term_memory,
            structured_context=structured_context,
        )

        ai_messages = self._build_prompt_messages(
            message=message,
            conversation_id=conversation_id,
            conversation_history=conversation_history,
            long_term_memory=long_term_memory,
            structured_context=structured_context,
            accountability_signals=accountability_signals,
            file_text=file_text,
            time_context=time_context,
        )

        user_message = await self.memory_service.save_message(
            conversation_id,
            "user",
            message,
        )
        yield {"event": "conversation", "conversation_id": conversation_id}
        candidate_decision = await self._handle_memory_candidate_decision(
            message,
            conversation_id=conversation_id,
        )
        if candidate_decision:
            assistant_message = await self.memory_service.save_message(
                conversation_id,
                "assistant",
                candidate_decision["response"],
            )
            yield {
                "event": "memory_candidate_decision",
                "memory_candidate_decision": candidate_decision,
            }
            yield {
                "event": "done",
                "conversation_id": conversation_id,
                "response": candidate_decision["response"],
                "messages": await self.memory_service.get_recent_messages(
                    conversation_id,
                    limit=20,
                ),
                "memory_changes": candidate_decision["memory_changes"],
                "assistant_message": assistant_message,
            }
            return
        memory_correction = await self._apply_memory_correction(
            message,
            conversation_id=conversation_id,
            user_message_id=str(user_message.get("id") or ""),
        )
        if memory_correction:
            ai_messages.append(self._memory_correction_prompt(memory_correction))
            yield {"event": "memory_correction", "memory_correction": memory_correction}

        if response_instructions:
            ai_messages.append({"role": "system", "content": response_instructions})

        response_parts = []
        if max_response_tokens is None:
            token_stream = self.ai_service.stream_response(ai_messages)
        else:
            token_stream = self.ai_service.stream_response(
                ai_messages,
                max_tokens=max_response_tokens,
            )
        async for token in token_stream:
            response_parts.append(token)
            yield {"event": "token", "token": token}

        rex_response = "".join(response_parts).strip()
        assistant_message = await self.memory_service.save_message(
            conversation_id,
            "assistant",
            rex_response,
        )

        memory_changes = None
        if self._correction_blocks_extraction(memory_correction):
            memory_changes = self._memory_change_summary(
                [],
                memory_correction=memory_correction,
                skipped_reason="correction_already_handled",
            )
        else:
            self._schedule_memory_extraction(
                conversation_id,
                user_message,
                assistant_message,
            )

        yield {
            "event": "done",
            "conversation_id": conversation_id,
            "response": rex_response,
            "messages": await self.memory_service.get_recent_messages(
                conversation_id,
                limit=20,
            ),
            "memory_changes": memory_changes,
        }

    async def _existing_conversation_id(
        self,
        conversation_id: Optional[str],
    ) -> Optional[str]:
        if conversation_id is None:
            return None

        if not await self.memory_service.conversation_exists(conversation_id):
            raise ConversationNotFoundError()

        return conversation_id

    async def _fetch_prompt_context(
        self,
        message: str,
        conversation_id: Optional[str],
    ) -> tuple[list[dict], list[dict], dict]:
        long_term_memory_task = self.memory_service.get_relevant_memories(
            query=message,
            limit=8,
        )
        profile_memory_task = self.memory_service.get_relevant_memories(
            query=PROFILE_MEMORY_QUERY,
            limit=PROFILE_MEMORY_LIMIT,
        )
        structured_context_task = self._fetch_structured_context(message)
        if conversation_id is None:
            (
                long_term_memory,
                profile_memory,
                structured_context,
            ) = await asyncio.gather(
                long_term_memory_task,
                profile_memory_task,
                structured_context_task,
            )
            return (
                [],
                self._merge_memories(long_term_memory, profile_memory),
                structured_context,
            )

        (
            conversation_history,
            long_term_memory,
            profile_memory,
            structured_context,
        ) = await asyncio.gather(
            self.memory_service.get_recent_messages(conversation_id, limit=20),
            long_term_memory_task,
            profile_memory_task,
            structured_context_task,
        )
        return (
            conversation_history,
            self._merge_memories(long_term_memory, profile_memory),
            structured_context,
        )

    def _merge_memories(self, *memory_groups: list[dict]) -> list[dict]:
        merged: list[dict] = []
        seen_ids: set[str] = set()
        for memories in memory_groups:
            for memory in memories:
                memory_id = str(memory.get("id") or "")
                if memory_id and memory_id in seen_ids:
                    continue
                if memory_id:
                    seen_ids.add(memory_id)
                merged.append(memory)
        return merged[:8]

    async def _fetch_structured_context(self, message: str) -> dict:
        get_structured_context = getattr(
            self.memory_service,
            "get_structured_memory_context",
            None,
        )
        if get_structured_context is None:
            return {}

        try:
            return await get_structured_context(message)
        except Exception:
            return {}

    def _build_prompt_messages(
        self,
        message: str,
        conversation_id: str,
        conversation_history: list[dict],
        long_term_memory: list[dict],
        structured_context: dict,
        accountability_signals: list,
        file_text: Optional[str],
        time_context: dict,
    ) -> list[dict]:
        last_message_timestamp = self._last_message_timestamp(conversation_history)
        return self.prompt_service.build_messages(
            user_message=message,
            recent_messages=conversation_history,
            relevant_memories=long_term_memory,
            structured_context=structured_context,
            accountability_signals=accountability_signals,
            file_context=file_text,
            conversation_metadata={
                "id": conversation_id,
                "timestamp": self._conversation_timestamp(conversation_history),
                "last_message_timestamp": last_message_timestamp,
            },
            time_context=time_context,
        )

    def _current_time_context(self, conversation_history: list[dict]) -> dict:
        return self.time_context_service.current_context(
            previous_timestamp=self._last_message_timestamp(conversation_history),
        )

    async def _accountability_signals(
        self,
        *,
        message: str,
        time_context: dict,
        long_term_memory: list[dict],
        structured_context: dict,
    ) -> list:
        if self.accountability_service is None:
            return []

        try:
            return await self.accountability_service.analyze_signals(
                message=message,
                time_context=time_context,
                personal_rules=structured_context.get("personal_rules") or [],
                commitments=structured_context.get("commitments") or [],
                plans=structured_context.get("plans") or [],
                plan_milestones=structured_context.get("plan_milestones") or [],
                entity_events=structured_context.get("entity_events") or [],
                relevant_memories=long_term_memory,
            )
        except Exception:
            return []

    async def _apply_memory_correction(
        self,
        message: str,
        *,
        conversation_id: str,
        user_message_id: str,
    ) -> Optional[dict]:
        if self.memory_correction_service is None:
            return None
        try:
            intent = self.memory_correction_service.detect_correction_intent(message)
            if intent.confidence < 0.5:
                return None
        except Exception:
            return None
        if self.memory_candidate_service is None:
            return None
        try:
            candidate = await self.memory_candidate_service.create_candidate(
                MemoryCandidateCreateRequest(
                    candidate_type="correction",
                    payload={
                        "text": message,
                        "intent": {
                            "intent_type": intent.intent_type.value,
                            "old_value": intent.old_value,
                            "new_value": intent.new_value,
                            "target_hint": intent.target_hint,
                            "confidence": intent.confidence,
                        },
                        "metadata": {
                            "correction_intent": True,
                            "phase": "2_pending_verified_correction",
                        },
                    },
                    risk_level="high",
                    reason=(
                        "User correction detected. It must be confirmed before "
                        "anything durable is changed."
                    ),
                    source_conversation_id=conversation_id,
                    source_message_id=user_message_id or None,
                )
            )
        except Exception:
            return None
        return {
            "applied": False,
            "requires_confirmation": True,
            "candidate_id": candidate.get("id"),
            "candidate_type": candidate.get("candidate_type"),
            "risk_level": candidate.get("risk_level"),
            "preview": candidate.get("preview"),
            "message": "Correction captured as a pending memory candidate.",
        }

    def _memory_correction_prompt(self, memory_correction: dict) -> dict:
        payload = json.dumps(memory_correction, sort_keys=True)
        return {
            "role": "system",
            "content": (
                "Memory correction status for this turn: "
                f"{payload}\n"
                "If applied, briefly tell the user exactly what was updated or archived. "
                "If confirmation is required, ask for confirmation before claiming it was changed."
            ),
        }

    def _correction_blocks_extraction(self, memory_correction: Optional[dict]) -> bool:
        if not memory_correction:
            return False
        return bool(
            memory_correction.get("applied")
            or memory_correction.get("requires_confirmation")
        )

    def _memory_change_summary(
        self,
        extraction_results: list[dict],
        *,
        memory_correction: Optional[dict] = None,
        skipped_reason: Optional[str] = None,
    ) -> Optional[dict]:
        summary = {
            "created": 0,
            "updated": 0,
            "archived": 0,
            "merged": 0,
            "skipped": 0,
            "confirmation_required": 0,
            "records": [],
        }

        if memory_correction:
            if memory_correction.get("requires_confirmation"):
                summary["confirmation_required"] += 1
            if memory_correction.get("applied"):
                summary["updated"] += len(memory_correction.get("updated") or [])
                summary["archived"] += len(memory_correction.get("archived") or [])
                summary["created"] += len(memory_correction.get("created") or [])
                summary["merged"] += len(memory_correction.get("merged") or [])
            summary["records"].append(
                {
                    "kind": "memory_correction",
                    "applied": bool(memory_correction.get("applied")),
                    "requires_confirmation": bool(
                        memory_correction.get("requires_confirmation")
                    ),
                }
            )

        if skipped_reason:
            summary["skipped"] += 1
            summary["records"].append(
                {
                    "kind": "memory_extraction",
                    "action": "skipped",
                    "reason": skipped_reason,
                }
            )

        for result in extraction_results:
            action = str(result.get("extraction_action") or "create")
            if action.startswith("create"):
                summary["created"] += 1
            elif action.startswith("update") or action == "updated_correction":
                summary["updated"] += 1
            elif action.startswith("archive"):
                summary["archived"] += 1
            elif action.startswith("merge"):
                summary["merged"] += 1
            elif action in {"ask_confirmation", "confirmation_required"}:
                summary["confirmation_required"] += 1
            elif action == "candidate_created":
                summary["confirmation_required"] += 1
            elif action.startswith("skip") or action.startswith("ignore"):
                summary["skipped"] += 1

            summary["records"].append(
                {
                    "kind": result.get("extraction_kind"),
                    "type": result.get("structured_type")
                    or result.get("memory_type"),
                    "action": action,
                    "id": result.get("id"),
                    "title": result.get("title")
                    or result.get("display_name")
                    or result.get("content"),
                }
            )

        if not any(
            summary[key]
            for key in (
                "created",
                "updated",
                "archived",
                "merged",
                "skipped",
                "confirmation_required",
            )
        ):
            return None
        return summary

    async def _handle_memory_candidate_decision(
        self,
        message: str,
        *,
        conversation_id: str,
    ) -> Optional[dict]:
        if self.memory_candidate_service is None:
            return None

        intent = self._memory_candidate_decision_intent(message)
        if intent is None:
            return None

        pending = await self.memory_candidate_service.list_candidates(
            status="pending",
            source_conversation_id=conversation_id,
            limit=20,
        )
        if not pending:
            return None

        selected_candidate = self._candidate_from_confirmation_text(message, pending)

        if intent == "approve_all":
            result = await self.memory_candidate_service.bulk_approve_candidates(
                MemoryCandidateBulkDecisionRequest(
                    source_conversation_id=conversation_id,
                    decided_by="user",
                    reason="Approved from chat confirmation.",
                    include_high_risk=False,
                )
            )
            return self._candidate_decision_response(result)

        if intent == "reject_all":
            result = await self.memory_candidate_service.bulk_reject_candidates(
                MemoryCandidateBulkDecisionRequest(
                    source_conversation_id=conversation_id,
                    decided_by="user",
                    reason="Rejected all pending changes from chat.",
                )
            )
            return self._candidate_decision_response(result)

        if intent == "reject":
            candidate = selected_candidate or pending[0]
            rejected = await self.memory_candidate_service.reject_candidate(
                candidate["id"],
                MemoryCandidateRejectRequest(reason="Rejected from chat."),
            )
            return self._candidate_decision_response(
                {"approved": [], "rejected": [rejected], "skipped": []}
            )

        if len(pending) > 1 and selected_candidate is None:
            return self._pending_candidates_response(pending)

        candidate = selected_candidate or pending[0]
        if (
            candidate.get("risk_level") == "high"
            and self._is_vague_approval(message)
        ):
            return self._pending_candidates_response(
                [candidate],
                response=(
                    "This is a high-risk memory change. Please confirm explicitly "
                    "with \"confirm\", \"apply\", or \"save that\" before I change "
                    "durable memory."
                ),
            )

        approved = await self.memory_candidate_service.approve_candidate(
            candidate["id"],
            MemoryCandidateApproveRequest(
                approved_by="user",
                reason="Approved from chat confirmation.",
            ),
        )
        return self._candidate_decision_response(
            {"approved": [approved], "rejected": [], "skipped": []}
        )

    def _memory_candidate_decision_intent(self, message: str) -> Optional[str]:
        normalized = self._normalized_confirmation_text(message)
        if not normalized:
            return None
        if normalized in APPROVE_ALL_PHRASES:
            return "approve_all"
        if normalized in REJECT_ALL_PHRASES:
            return "reject_all"
        if (
            ("approve" in normalized or "apply" in normalized or "save" in normalized)
            and ("all" in normalized or "pending" in normalized or "these" in normalized)
        ):
            return "approve_all"
        if (
            ("reject" in normalized or "discard" in normalized)
            and ("all" in normalized or "pending" in normalized or "these" in normalized)
        ):
            return "reject_all"
        if normalized in REJECT_PHRASES:
            return "reject"
        if normalized.startswith("do not save ") or normalized.startswith(
            "dont save "
        ):
            return "reject"
        if normalized in APPROVE_PHRASES:
            return "approve"
        if normalized.startswith(("confirm ", "confirmed ", "approve ", "apply ")):
            return "approve"
        if normalized.startswith("save ") and "all" not in normalized:
            return "approve"
        return None

    def _is_vague_approval(self, message: str) -> bool:
        return self._normalized_confirmation_text(message) in VAGUE_APPROVE_PHRASES

    def _candidate_from_confirmation_text(
        self,
        message: str,
        candidates: list[dict],
    ) -> Optional[dict]:
        normalized = self._normalized_confirmation_text(message)
        if not normalized:
            return None
        for candidate in candidates:
            candidate_id = str(candidate.get("id") or "")
            if not candidate_id:
                continue
            normalized_id = self._normalized_confirmation_text(candidate_id)
            compact_id = normalized_id.replace(" ", "")
            if normalized_id and normalized_id in normalized:
                return candidate
            if compact_id and compact_id in normalized.replace(" ", ""):
                return candidate
            if len(compact_id) >= 8 and compact_id[-8:] in normalized.replace(" ", ""):
                return candidate
        return None

    def _pending_candidates_response(
        self,
        pending: list[dict],
        *,
        response: Optional[str] = None,
    ) -> dict:
        if response is None:
            response = (
                f"I found {len(pending)} pending memory change(s). Review the "
                "candidate card(s), then say \"approve all pending\" for eligible "
                "low/medium-risk changes, \"confirm\" for a single high-risk "
                "change, or \"do not save\" to reject the latest one."
            )
        cards = [self._candidate_card(candidate) for candidate in pending]
        return {
            "response": response,
            "memory_changes": {
                "created": 0,
                "updated": 0,
                "archived": 0,
                "merged": 0,
                "skipped": 0,
                "confirmation_required": len(pending),
                "low_risk_auto_apply_enabled": LOW_RISK_AUTO_APPLY_ENABLED,
                "pending_candidates": cards,
                "records": [
                    {
                        "kind": "memory_candidate",
                        "action": "pending",
                        "id": candidate.get("id"),
                        "title": candidate.get("preview"),
                        "candidate": card,
                    }
                    for candidate, card in zip(pending, cards)
                ],
            },
        }

    def _candidate_decision_response(self, result: dict) -> dict:
        approved = result.get("approved") or []
        rejected = result.get("rejected") or []
        skipped = result.get("skipped") or []
        failed = [
            candidate
            for candidate in approved
            if candidate.get("status") == "failed"
            or not (candidate.get("verification") or {}).get("passed", False)
        ]
        applied = [
            candidate
            for candidate in approved
            if candidate.get("status") == "applied"
            and (candidate.get("verification") or {}).get("passed", False)
        ]

        parts: list[str] = []
        if applied:
            parts.append(f"Applied {len(applied)} pending memory change(s).")
        if rejected:
            parts.append(f"Rejected {len(rejected)} pending memory change(s).")
        if skipped:
            parts.append(
                f"Skipped {len(skipped)} high-risk pending change(s); those need "
                "explicit individual confirmation."
            )
        if failed:
            parts.append(
                "Some pending changes failed verification, so I did not mark them done."
            )
            remaining = self._remaining_conflict_text(failed)
            if remaining:
                parts.append(f"Still wrong: {remaining}")
        response = " ".join(parts) or "No pending memory changes were applied."

        applied_cards = [self._candidate_card(candidate) for candidate in applied]
        rejected_cards = [self._candidate_card(candidate) for candidate in rejected]
        skipped_cards = [self._candidate_card(candidate) for candidate in skipped]
        failed_cards = [self._candidate_card(candidate) for candidate in failed]

        return {
            "response": response,
            "memory_changes": {
                "created": len(applied),
                "updated": 0,
                "archived": 0,
                "merged": 0,
                "skipped": len(skipped) + len(failed),
                "confirmation_required": len(skipped),
                "low_risk_auto_apply_enabled": LOW_RISK_AUTO_APPLY_ENABLED,
                "applied_candidates": applied_cards,
                "rejected_candidates": rejected_cards,
                "skipped_candidates": skipped_cards,
                "failed_candidates": failed_cards,
                "pending_candidates": skipped_cards + failed_cards,
                "records": [
                    *[
                        {
                            "kind": "memory_candidate",
                            "action": candidate.get("status"),
                            "id": candidate.get("id"),
                            "title": candidate.get("preview"),
                            "candidate": card,
                        }
                        for candidate, card in zip(applied, applied_cards)
                    ],
                    *[
                        {
                            "kind": "memory_candidate",
                            "action": "rejected",
                            "id": candidate.get("id"),
                            "title": candidate.get("preview"),
                            "candidate": card,
                        }
                        for candidate, card in zip(rejected, rejected_cards)
                    ],
                    *[
                        {
                            "kind": "memory_candidate",
                            "action": "skipped_high_risk",
                            "id": candidate.get("id"),
                            "title": candidate.get("preview"),
                            "candidate": card,
                        }
                        for candidate, card in zip(skipped, skipped_cards)
                    ],
                    *[
                        {
                            "kind": "memory_candidate",
                            "action": "verification_failed",
                            "id": candidate.get("id"),
                            "title": candidate.get("preview"),
                            "candidate": card,
                        }
                        for candidate, card in zip(failed, failed_cards)
                    ],
                ],
            },
        }

    def _candidate_card(self, candidate: dict) -> dict:
        verification = candidate.get("verification") or {}
        applied_record_table = candidate.get("applied_record_table")
        applied_record_id = candidate.get("applied_record_id")
        payload = candidate.get("payload") or {}
        return {
            "id": candidate.get("id"),
            "candidate_type": candidate.get("candidate_type"),
            "status": candidate.get("status"),
            "risk_level": candidate.get("risk_level"),
            "preview": candidate.get("preview"),
            "expected_action": self._candidate_expected_action(candidate),
            "requires_explicit_confirmation": candidate.get("risk_level") == "high",
            "source_conversation_id": candidate.get("source_conversation_id"),
            "source_message_id": candidate.get("source_message_id"),
            "payload_preview": self._payload_preview(payload),
            "applied_record": (
                {
                    "table": applied_record_table,
                    "id": applied_record_id,
                }
                if applied_record_table or applied_record_id
                else None
            ),
            "verification": self._verification_summary(verification),
        }

    def _candidate_expected_action(self, candidate: dict) -> str:
        candidate_type = str(candidate.get("candidate_type") or "")
        return {
            "long_term_memory": "Create long-term memory after confirmation",
            "entity": "Create or update canonical entity after confirmation",
            "entity_event": "Create historical entity event after confirmation",
            "personal_rule": "Create or update personal rule after confirmation",
            "plan": "Create or update top-level plan after confirmation",
            "plan_milestone": "Create or update achievement milestone after confirmation",
            "commitment": "Create or update task/commitment after confirmation",
            "correction": "Apply correction and verify stale facts are gone",
            "archive": "Archive stale record after confirmation",
            "merge": "Merge duplicate records after confirmation",
        }.get(candidate_type, "Apply pending memory change after confirmation")

    def _payload_preview(self, payload: dict) -> dict:
        preview: dict[str, object] = {}
        for key in (
            "title",
            "display_name",
            "content",
            "description",
            "rule_text",
            "commitment_text",
            "text",
        ):
            value = payload.get(key)
            if value is None:
                continue
            text = " ".join(str(value).split())
            if text:
                preview[key] = text[:240]
        intent = payload.get("intent")
        if isinstance(intent, dict):
            preview["intent"] = {
                key: intent.get(key)
                for key in ("intent_type", "old_value", "new_value", "target_hint")
                if intent.get(key) is not None
            }
        return preview

    def _verification_summary(self, verification: dict) -> Optional[dict]:
        if not verification:
            return None
        remaining = verification.get("remaining_conflicts") or []
        return {
            "passed": bool(verification.get("passed")),
            "message": verification.get("message"),
            "remaining_conflict_count": len(remaining),
            "remaining_conflicts": remaining[:5],
            "applied_record": verification.get("applied_record"),
        }

    def _remaining_conflict_text(self, candidates: list[dict]) -> str:
        conflicts: list[str] = []
        for candidate in candidates:
            verification = candidate.get("verification") or {}
            for conflict in verification.get("remaining_conflicts") or []:
                table = conflict.get("table") or "record"
                title = conflict.get("title") or conflict.get("id") or "unknown"
                terms = ", ".join(conflict.get("matched_terms") or [])
                conflicts.append(f"{table} {title} still contains {terms}".strip())
        return "; ".join(conflicts[:5])

    def _normalized_confirmation_text(self, message: str) -> str:
        normalized = message.lower().replace("'", "")
        normalized = "".join(
            character if character.isalnum() or character.isspace() else " "
            for character in normalized
        )
        return " ".join(normalized.split())

    def _last_message_timestamp(self, conversation_history: list[dict]) -> Optional[str]:
        if not conversation_history:
            return None
        timestamp = conversation_history[-1].get("timestamp")
        return str(timestamp) if timestamp else None

    def _conversation_timestamp(self, conversation_history: list[dict]) -> Optional[str]:
        if not conversation_history:
            return None
        timestamp = conversation_history[0].get("timestamp")
        return str(timestamp) if timestamp else None

    async def _extract_memory_after_success(
        self,
        conversation_id: str,
        user_message: dict,
        assistant_message: dict,
    ) -> list[dict]:
        if self.memory_extraction_service is None:
            return []

        try:
            return await self.memory_extraction_service.extract_and_save(
                conversation_id=conversation_id,
                user_message=user_message,
                assistant_message=assistant_message,
            )
        except Exception:
            # Memory extraction is best-effort. A failed extraction must not
            # break a successful chat response.
            return []

    def _schedule_memory_extraction(
        self,
        conversation_id: str,
        user_message: dict,
        assistant_message: dict,
    ) -> None:
        if self.memory_extraction_service is None:
            return

        task = asyncio.create_task(
            self._extract_memory_after_success(
                conversation_id,
                user_message,
                assistant_message,
            )
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator
from typing import Any, Optional

from fastapi import WebSocket, WebSocketDisconnect

from app.services.ai_service import AIServiceError
from app.services.chat_service import ChatService, ConversationNotFoundError
from app.services.deepgram_service import DeepgramServiceError
from app.services.deepgram_streaming_service import DeepgramStreamingService
from app.services.google_tts_service import GoogleTTSService, GoogleTTSServiceError
from app.services.memory_service import MemoryServiceError


class VoiceStreamSession:
    def __init__(
        self,
        websocket: WebSocket,
        deepgram_streaming_service: DeepgramStreamingService,
        chat_service: ChatService,
        google_tts_service: GoogleTTSService,
    ) -> None:
        self.websocket = websocket
        self.deepgram_streaming_service = deepgram_streaming_service
        self.chat_service = chat_service
        self.google_tts_service = google_tts_service
        self.conversation_id: Optional[str] = None
        self.input_mime_type = "audio/linear16"
        self.sample_rate = 16000
        self._session_id = f"voice-{time.time_ns()}"
        self._audio_chunks: list[bytes] = []
        self._audio_started_at: Optional[float] = None
        self._active_turn_task: Optional[asyncio.Task[None]] = None

    async def run(self) -> None:
        await self.websocket.accept()

        try:
            while True:
                message = await self.websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    break

                if message.get("bytes") is not None:
                    await self._receive_audio_chunk(message["bytes"])
                    continue

                text = message.get("text")
                if text is None:
                    continue

                should_continue = await self._receive_text_event(text)
                if not should_continue:
                    break
        except WebSocketDisconnect:
            return
        finally:
            await self._cancel_active_turn()

    async def _receive_audio_chunk(self, chunk: bytes) -> None:
        if not chunk:
            return
        if self._audio_started_at is None:
            self._audio_started_at = time.perf_counter()
        self._audio_chunks.append(chunk)
        await self._send_event(
            "audio.received",
            bytes_received=sum(len(item) for item in self._audio_chunks),
            chunk_count=len(self._audio_chunks),
        )

    async def _receive_text_event(self, text: str) -> bool:
        try:
            payload = self.websocket_json_loads(text)
        except ValueError:
            await self._send_error("Invalid voice stream event.")
            return True

        event = payload.get("event")
        if event == "session.start":
            self.conversation_id = payload.get("conversation_id") or self.conversation_id
            self.input_mime_type = payload.get("input_mime_type") or self.input_mime_type
            sample_rate = payload.get("sample_rate")
            if isinstance(sample_rate, int) and sample_rate > 0:
                self.sample_rate = sample_rate
            await self._send_event(
                "session.started",
                session_id=self._session_id,
                conversation_id=self.conversation_id,
                input_mime_type=self.input_mime_type,
                sample_rate=self.sample_rate,
            )
            return True

        if event == "utterance.end":
            if self._active_turn_task is not None and not self._active_turn_task.done():
                await self._send_error(
                    "Rex is still answering the previous voice turn.",
                    status_code=409,
                    code="turn_in_progress",
                )
                return True
            self._active_turn_task = asyncio.create_task(self._process_utterance())
            return True

        if event == "user.interrupt":
            self._audio_chunks.clear()
            self._audio_started_at = None
            await self._cancel_active_turn()
            await self._send_event("session.interrupted", session_id=self._session_id)
            return True

        if event == "session.end":
            await self._cancel_active_turn()
            await self._send_event("session.ended", session_id=self._session_id)
            await self.websocket.close()
            return False

        await self._send_error(f"Unsupported voice stream event: {event}")
        return True

    async def _process_utterance(self) -> None:
        chunks = self._audio_chunks
        self._audio_chunks = []
        audio_started_at = self._audio_started_at
        self._audio_started_at = None

        if not chunks:
            await self._send_error("I did not catch any audio.", code="empty_audio")
            return

        timings: dict[str, int] = {}
        started_at = time.perf_counter()
        if audio_started_at is not None:
            timings["capture_ms"] = self._elapsed_ms(audio_started_at)

        try:
            transcription = await self.deepgram_streaming_service.transcribe_audio_stream(
                self._chunk_iterator(chunks),
                content_type=self.input_mime_type,
                sample_rate=self.sample_rate,
                on_transcript=self._send_transcript_event,
            )
            timings["stt_ms"] = self._elapsed_ms(started_at)

            await self._send_event(
                "transcript.final",
                transcript=transcription["transcript"],
                confidence=transcription.get("confidence"),
                metadata=transcription.get("metadata") or {},
            )

            await self._send_event("assistant.started")
            chat_started_at = time.perf_counter()
            response_text = await self._stream_chat_and_audio(
                transcription["transcript"],
                transcription,
                timings,
            )
            timings["turn_ms"] = self._elapsed_ms(started_at)
            await self._send_event(
                "assistant.done",
                conversation_id=self.conversation_id,
                response_text=response_text,
                timings=timings,
            )
        except DeepgramServiceError as error:
            await self._send_error(error.detail, status_code=error.status_code)
        except ConversationNotFoundError:
            await self._send_error("Conversation not found.", status_code=404)
        except AIServiceError as error:
            await self._send_error(error.detail, status_code=error.status_code)
        except MemoryServiceError as error:
            await self._send_error(error.detail, status_code=error.status_code)
        except GoogleTTSServiceError as error:
            await self._send_error(error.detail, status_code=error.status_code)
        except asyncio.CancelledError:
            raise
        except Exception:
            await self._send_error("Voice stream failed.", status_code=500)
        finally:
            current_task = asyncio.current_task()
            if self._active_turn_task is current_task:
                self._active_turn_task = None

    async def _stream_chat_and_audio(
        self,
        transcript: str,
        transcription: dict[str, Any],
        timings: dict[str, int],
    ) -> str:
        response_parts: list[str] = []
        speech_buffer = ""
        first_token_at: Optional[float] = None
        first_audio_at: Optional[float] = None
        user_message_id: Optional[str] = None
        assistant_message_id: Optional[str] = None
        messages: list[dict[str, Any]] = []
        chat_started_at = time.perf_counter()

        async for event in self.chat_service.stream_message(
            transcript,
            conversation_id=self.conversation_id,
        ):
            event_name = event.get("event")
            if event_name == "conversation":
                self.conversation_id = event.get("conversation_id") or self.conversation_id
                await self._send_event(
                    "conversation.updated",
                    conversation_id=self.conversation_id,
                )
            elif event_name == "token":
                token = str(event.get("token") or "")
                if not token:
                    continue
                if first_token_at is None:
                    first_token_at = time.perf_counter()
                    timings["grok_first_token_ms"] = self._elapsed_ms(chat_started_at)
                response_parts.append(token)
                speech_buffer += token
                await self._send_event("assistant.token", token=token)
                chunk, speech_buffer = self._next_speakable_chunk(speech_buffer)
                if chunk:
                    first_audio_at = await self._synthesize_and_send_audio_chunk(
                        chunk,
                        timings,
                        first_audio_at,
                    )
            elif event_name == "done":
                self.conversation_id = event.get("conversation_id") or self.conversation_id
                messages = event.get("messages") or []
                user_message_id, assistant_message_id = self._message_ids(messages)

        response_text = "".join(response_parts).strip()
        if speech_buffer.strip():
            first_audio_at = await self._synthesize_and_send_audio_chunk(
                speech_buffer.strip(),
                timings,
                first_audio_at,
            )

        metadata_record = await self.chat_service.save_voice_turn_metadata(
            conversation_id=self.conversation_id or "",
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            transcript_confidence=transcription.get("confidence"),
            audio_duration_seconds=transcription.get("duration_seconds"),
            input_mime_type=self.input_mime_type,
            output_audio_encoding=None,
            metadata={
                "stt": transcription.get("metadata") or {},
                "stream": {"session_id": self._session_id, "timings": timings},
            },
        )
        await self._send_event(
            "messages.updated",
            conversation_id=self.conversation_id,
            messages=messages,
            voice_metadata={"record": metadata_record} if metadata_record else {},
        )
        return response_text

    async def _synthesize_and_send_audio_chunk(
        self,
        text: str,
        timings: dict[str, int],
        first_audio_at: Optional[float],
    ) -> Optional[float]:
        synthesis_started_at = time.perf_counter()
        synthesis = await self.google_tts_service.synthesize_speech(text)
        if first_audio_at is None:
            first_audio_at = time.perf_counter()
            timings["tts_first_audio_ms"] = self._elapsed_ms(synthesis_started_at)

        await self._send_event(
            "assistant.audio_chunk",
            text=text,
            audio_content_type=synthesis["audio_content_type"],
            audio_base64=synthesis["audio_base64"],
            audio_encoding=synthesis["audio_encoding"],
            voice_name=synthesis["voice_name"],
            language_code=synthesis["language_code"],
            metadata=synthesis.get("metadata") or {},
        )
        return first_audio_at

    async def _send_transcript_event(self, event: dict[str, Any]) -> None:
        if event.get("event") == "transcript.partial":
            await self._send_event(
                "transcript.partial",
                transcript=event.get("transcript") or "",
                confidence=event.get("confidence"),
                metadata=event.get("metadata") or {},
            )

    def _next_speakable_chunk(self, text: str) -> tuple[Optional[str], str]:
        stripped = text.strip()
        if not stripped:
            return None, ""

        for index, character in enumerate(text):
            if character in ".!?;\n" and index >= 80:
                chunk = text[: index + 1].strip()
                rest = text[index + 1 :]
                return chunk, rest

        if len(stripped) >= 220:
            split_at = text.rfind(" ", 0, 220)
            if split_at < 80:
                split_at = 220
            return text[:split_at].strip(), text[split_at:]

        return None, text

    def _message_ids(self, messages: list[dict[str, Any]]) -> tuple[Optional[str], Optional[str]]:
        user_message_id = None
        assistant_message_id = None
        for message in messages:
            if message.get("role") == "user":
                user_message_id = message.get("id") or user_message_id
            elif message.get("role") == "assistant":
                assistant_message_id = message.get("id") or assistant_message_id
        return user_message_id, assistant_message_id

    async def _chunk_iterator(self, chunks: list[bytes]) -> AsyncIterator[bytes]:
        for chunk in chunks:
            yield chunk

    async def _cancel_active_turn(self) -> None:
        task = self._active_turn_task
        if task is None or task.done():
            self._active_turn_task = None
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        self._active_turn_task = None

    async def _send_event(self, event: str, **payload: Any) -> None:
        await self.websocket.send_json({"event": event, **payload})

    async def _send_error(
        self,
        message: str,
        status_code: int = 400,
        code: str = "voice_stream_error",
    ) -> None:
        await self._send_event(
            "error",
            code=code,
            detail=message,
            status_code=status_code,
        )

    def _elapsed_ms(self, start_time: float) -> int:
        return max(0, round((time.perf_counter() - start_time) * 1000))

    def websocket_json_loads(self, text: str) -> dict[str, Any]:
        import json

        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("Expected object")
        return data

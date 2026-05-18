from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Optional
from urllib.parse import urlencode

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from app.config import Settings, get_settings
from app.services.deepgram_service import DeepgramServiceError

TranscriptCallback = Callable[[dict[str, Any]], Awaitable[None]]


class DeepgramStreamingService:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    async def transcribe_audio_stream(
        self,
        audio_chunks: AsyncIterator[bytes],
        content_type: str,
        sample_rate: int = 16000,
        on_transcript: Optional[TranscriptCallback] = None,
    ) -> dict[str, Any]:
        if not self.settings.deepgram_api_key:
            raise DeepgramServiceError(
                "Voice transcription is not configured.",
                status_code=503,
            )

        url = self._stream_url(sample_rate=sample_rate)
        final_segments: list[str] = []
        confidence: Optional[float] = None
        duration_seconds: Optional[float] = None
        request_id: Optional[str] = None
        sent_any_audio = False
        speech_final_received = False

        try:
            async with websockets.connect(
                url,
                additional_headers={
                    "Authorization": f"Token {self.settings.deepgram_api_key}",
                },
                open_timeout=self.settings.deepgram_timeout_seconds,
                close_timeout=5,
            ) as websocket:
                async for chunk in audio_chunks:
                    if not chunk:
                        continue
                    sent_any_audio = True
                    await websocket.send(chunk)

                if not sent_any_audio:
                    raise DeepgramServiceError("I did not catch any audio.", status_code=400)

                await websocket.send(json.dumps({"type": "CloseStream"}))

                while True:
                    try:
                        raw_message = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=0.8
                            if speech_final_received
                            else self.settings.deepgram_timeout_seconds,
                        )
                    except asyncio.TimeoutError:
                        if speech_final_received:
                            break
                        raise DeepgramServiceError(
                            "Deepgram transcription timed out.",
                            status_code=503,
                        )
                    except ConnectionClosed:
                        break

                    event = self._parse_message(raw_message)
                    if event is None:
                        continue

                    if event["event"] == "metadata":
                        request_id = event["metadata"].get("request_id") or request_id
                        duration = event["metadata"].get("duration")
                        if isinstance(duration, (int, float)):
                            duration_seconds = float(duration)
                        continue

                    if on_transcript is not None:
                        await on_transcript(event)

                    if event["event"] == "transcript.final":
                        transcript = str(event["transcript"] or "").strip()
                        if transcript:
                            self._append_final_segment(final_segments, transcript)
                        confidence = event.get("confidence")
                        if event.get("speech_final"):
                            speech_final_received = True
        except DeepgramServiceError:
            raise
        except (OSError, TimeoutError, WebSocketException) as error:
            raise DeepgramServiceError(
                "Cannot reach Deepgram right now.",
                status_code=503,
            ) from error

        final_transcript = " ".join(final_segments).strip()
        if not final_transcript:
            raise DeepgramServiceError("I did not catch any audio.", status_code=422)

        return {
            "transcript": final_transcript,
            "confidence": confidence,
            "duration_seconds": duration_seconds,
            "metadata": {
                "request_id": request_id,
                "model": self.settings.deepgram_model,
                "language": self.settings.deepgram_language,
                "content_type": content_type,
                "transport": "websocket",
            },
        }

    def _stream_url(self, sample_rate: int) -> str:
        base_url = self.settings.deepgram_base_url.rstrip("/").replace(
            "https://",
            "wss://",
            1,
        ).replace("http://", "ws://", 1)
        query = urlencode(
            {
                "model": self.settings.deepgram_model,
                "language": self.settings.deepgram_language,
                "smart_format": "true",
                "interim_results": "true",
                "endpointing": "true",
                "vad_events": "true",
                "encoding": "linear16",
                "sample_rate": sample_rate,
                "channels": 1,
            }
        )
        return f"{base_url}/listen?{query}"

    def _append_final_segment(self, segments: list[str], transcript: str) -> None:
        if not segments:
            segments.append(transcript)
            return

        previous = segments[-1]
        if transcript == previous or previous.endswith(transcript):
            return
        if transcript.startswith(previous):
            segments[-1] = transcript
            return
        segments.append(transcript)

    def _parse_message(self, raw_message: str | bytes) -> Optional[dict[str, Any]]:
        if isinstance(raw_message, bytes):
            raw_message = raw_message.decode("utf-8", errors="ignore")

        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError:
            return None

        message_type = payload.get("type")
        if message_type == "Metadata":
            return {
                "event": "metadata",
                "metadata": payload.get("metadata") or payload,
            }
        if message_type != "Results":
            return None

        channel = payload.get("channel") or {}
        alternatives = channel.get("alternatives") or []
        alternative = alternatives[0] if alternatives else {}
        transcript = str(alternative.get("transcript") or "").strip()
        if not transcript:
            return None

        is_final = bool(payload.get("is_final"))
        speech_final = bool(payload.get("speech_final"))
        event_name = "transcript.final" if is_final else "transcript.partial"
        confidence = alternative.get("confidence")

        return {
            "event": event_name,
            "transcript": transcript,
            "confidence": confidence if isinstance(confidence, (int, float)) else None,
            "speech_final": speech_final,
            "metadata": {
                "vendor": "deepgram",
                "transport": "websocket",
            },
        }

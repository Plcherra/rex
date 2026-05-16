from typing import Any, Optional

import httpx

from app.config import Settings, get_settings
from app.services.http_client import request_with_retries


class DeepgramServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 503) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class DeepgramService:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        content_type: str,
        filename: Optional[str] = None,
    ) -> dict[str, Any]:
        if not self.settings.deepgram_api_key:
            raise DeepgramServiceError(
                "Voice transcription is not configured.",
                status_code=503,
            )
        if not audio_bytes:
            raise DeepgramServiceError("I did not catch any audio.", status_code=400)

        try:
            response = await request_with_retries(
                "POST",
                self.settings.deepgram_transcription_url,
                headers={
                    "Authorization": f"Token {self.settings.deepgram_api_key}",
                    "Content-Type": content_type,
                },
                params={
                    "model": self.settings.deepgram_model,
                    "language": self.settings.deepgram_language,
                    "smart_format": "true",
                },
                content=audio_bytes,
                timeout=self.settings.deepgram_timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise self._http_status_error(error.response) from error
        except (httpx.RequestError, TimeoutError) as error:
            raise DeepgramServiceError(
                "Cannot reach Deepgram right now.",
                status_code=503,
            ) from error

        try:
            payload = response.json()
        except ValueError as error:
            raise DeepgramServiceError(
                "Deepgram returned an unreadable response.",
                status_code=502,
            ) from error
        result = self._parse_transcription(payload)
        if not result["transcript"]:
            raise DeepgramServiceError("I did not catch any audio.", status_code=422)

        result["metadata"]["filename"] = filename
        result["metadata"]["content_type"] = content_type
        return result

    def _parse_transcription(self, payload: dict[str, Any]) -> dict[str, Any]:
        metadata = payload.get("metadata") or {}
        results = payload.get("results") or {}
        channels = results.get("channels") or []
        first_alternative: dict[str, Any] = {}

        if channels:
            alternatives = channels[0].get("alternatives") or []
            if alternatives:
                first_alternative = alternatives[0] or {}

        transcript = str(first_alternative.get("transcript") or "").strip()
        confidence = first_alternative.get("confidence")
        duration = metadata.get("duration")

        return {
            "transcript": transcript,
            "confidence": confidence if isinstance(confidence, (int, float)) else None,
            "duration_seconds": duration if isinstance(duration, (int, float)) else None,
            "metadata": {
                "request_id": metadata.get("request_id"),
                "model": self.settings.deepgram_model,
                "language": self.settings.deepgram_language,
                "detected_language": first_alternative.get("detected_language"),
            },
        }

    def _http_status_error(self, response: httpx.Response) -> DeepgramServiceError:
        detail = self._deepgram_error_detail(response)
        if response.status_code in {401, 403}:
            return DeepgramServiceError(
                detail or "Deepgram authentication failed. Check the API key.",
                status_code=503,
            )
        if response.status_code == 400:
            return DeepgramServiceError(
                detail or "Deepgram rejected the audio request.",
                status_code=400,
            )
        if response.status_code == 413:
            return DeepgramServiceError(
                "Voice recording is too long.",
                status_code=413,
            )
        if response.status_code == 429:
            return DeepgramServiceError(
                detail or "Deepgram is rate limiting transcription right now.",
                status_code=503,
            )

        return DeepgramServiceError(
            detail or "Deepgram transcription failed.",
            status_code=503,
        )

    def _deepgram_error_detail(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return response.text.strip()

        if not isinstance(data, dict):
            return response.text.strip()

        for key in ("err_msg", "message", "detail", "error"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                nested_message = value.get("message") or value.get("detail")
                if isinstance(nested_message, str) and nested_message.strip():
                    return nested_message.strip()

        return response.text.strip()

import asyncio
import base64
import binascii
import json
import time
from typing import Any, Optional

import httpx

from app.config import Settings, get_settings
from app.services.http_client import request_with_retries


class GoogleTTSServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 503) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class GoogleTTSService:
    max_text_characters = 5000

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._cached_access_token: Optional[str] = None
        self._cached_access_token_expires_at = 0.0

    async def synthesize_speech(self, text: str) -> dict[str, Any]:
        normalized_text = text.strip()
        if not normalized_text:
            raise GoogleTTSServiceError("Text to speak cannot be empty.", status_code=400)
        if len(normalized_text) > self.max_text_characters:
            raise GoogleTTSServiceError(
                "Text is too long for voice playback.",
                status_code=400,
            )
        if not self.settings.google_tts_is_configured:
            raise GoogleTTSServiceError(
                "Voice playback is not configured.",
                status_code=503,
            )

        access_token = await self._access_token()
        payload = self._synthesis_payload(normalized_text)

        try:
            response = await request_with_retries(
                "POST",
                self.settings.google_tts_synthesize_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json; charset=utf-8",
                    "x-goog-user-project": self.settings.google_tts_project_id or "",
                },
                json=payload,
                timeout=self.settings.google_tts_timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise self._http_status_error(error.response) from error
        except (httpx.RequestError, TimeoutError) as error:
            raise GoogleTTSServiceError(
                "Cannot reach Google Text-to-Speech right now.",
                status_code=503,
            ) from error

        result = self._parse_synthesis_response(response)
        result["metadata"]["text_character_count"] = len(normalized_text)
        return result

    async def _access_token(self) -> str:
        if (
            self._cached_access_token
            and time.time() < self._cached_access_token_expires_at - 60
        ):
            return self._cached_access_token

        token, expires_at = await asyncio.to_thread(self._load_access_token)
        self._cached_access_token = token
        self._cached_access_token_expires_at = expires_at or (time.time() + 3000)
        return token

    def _load_access_token(self) -> tuple[str, Optional[float]]:
        try:
            scopes = ["https://www.googleapis.com/auth/cloud-platform"]
            if self.settings.google_tts_credentials_json:
                credentials_info = json.loads(self.settings.google_tts_credentials_json)

                from google.auth.transport.requests import Request
                from google.oauth2 import service_account

                credentials = service_account.Credentials.from_service_account_info(
                    credentials_info,
                    scopes=scopes,
                )
            elif self.settings.google_application_credentials:
                from google.auth.transport.requests import Request
                from google.oauth2 import service_account

                credentials = service_account.Credentials.from_service_account_file(
                    self.settings.google_application_credentials,
                    scopes=scopes,
                )
            else:
                raise GoogleTTSServiceError(
                    "Voice playback is not configured.",
                    status_code=503,
                )

            credentials.refresh(Request())
            if not credentials.token:
                raise GoogleTTSServiceError(
                    "Google Text-to-Speech authentication failed.",
                    status_code=503,
                )

            expires_at = credentials.expiry.timestamp() if credentials.expiry else None
            return credentials.token, expires_at
        except GoogleTTSServiceError:
            raise
        except (ImportError, OSError, ValueError, json.JSONDecodeError) as error:
            raise GoogleTTSServiceError(
                "Google Text-to-Speech credentials are invalid.",
                status_code=503,
            ) from error

    def _synthesis_payload(self, text: str) -> dict[str, Any]:
        return {
            "input": {"text": text},
            "voice": {
                "languageCode": self.settings.google_tts_language_code,
                "name": self.settings.google_tts_voice_name,
            },
            "audioConfig": {
                "audioEncoding": self.settings.google_tts_audio_encoding,
                "speakingRate": self.settings.google_tts_speaking_rate,
                "pitch": self.settings.google_tts_pitch,
            },
        }

    def _parse_synthesis_response(self, response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except (ValueError, binascii.Error) as error:
            raise GoogleTTSServiceError(
                "Google Text-to-Speech returned an unreadable response.",
                status_code=502,
            ) from error

        audio_base64 = data.get("audioContent")
        if not isinstance(audio_base64, str) or not audio_base64.strip():
            raise GoogleTTSServiceError(
                "Google Text-to-Speech returned no audio.",
                status_code=502,
            )

        try:
            base64.b64decode(audio_base64, validate=True)
        except ValueError as error:
            raise GoogleTTSServiceError(
                "Google Text-to-Speech returned invalid audio.",
                status_code=502,
            ) from error

        return {
            "audio_content_type": self._audio_content_type(),
            "audio_base64": audio_base64,
            "audio_encoding": self.settings.google_tts_audio_encoding,
            "voice_name": self.settings.google_tts_voice_name,
            "language_code": self.settings.google_tts_language_code,
            "metadata": {
                "vendor": "google_tts",
                "text_character_count": None,
            },
        }

    def _audio_content_type(self) -> str:
        encoding = self.settings.google_tts_audio_encoding.upper()
        if encoding == "MP3":
            return "audio/mpeg"
        if encoding == "LINEAR16":
            return "audio/wav"
        if encoding == "OGG_OPUS":
            return "audio/ogg"
        return "application/octet-stream"

    def _http_status_error(self, response: httpx.Response) -> GoogleTTSServiceError:
        detail = self._google_error_detail(response)
        if response.status_code in {401, 403}:
            return GoogleTTSServiceError(
                detail or "Google Text-to-Speech authentication failed.",
                status_code=503,
            )
        if response.status_code == 400:
            return GoogleTTSServiceError(
                detail or "Google Text-to-Speech rejected the voice request.",
                status_code=400,
            )
        if response.status_code == 429:
            return GoogleTTSServiceError(
                detail or "Google Text-to-Speech is rate limiting voice playback.",
                status_code=503,
            )
        return GoogleTTSServiceError(
            detail or "Google Text-to-Speech failed.",
            status_code=503,
        )

    def _google_error_detail(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return response.text.strip()

        if not isinstance(data, dict):
            return response.text.strip()

        error = data.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()

        for key in ("message", "detail", "error"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        return response.text.strip()

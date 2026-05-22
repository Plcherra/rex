import json
from collections.abc import AsyncIterator
from typing import Optional

import httpx

from app.config import Settings, get_settings
from app.services.http_client import request_with_retries


class AIServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 503) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class AIService:
    max_prompt_characters = 30000

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    async def generate_response(self, messages: list[dict]) -> str:
        prompt_messages = self._validated_prompt_messages(messages)

        payload = {
            "model": self.settings.grok_model,
            "messages": prompt_messages,
            "stream": False,
        }

        try:
            response = await request_with_retries(
                "POST",
                self.settings.grok_chat_url,
                headers={
                    "Authorization": f"Bearer {self.settings.grok_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.settings.grok_timeout_seconds,
            )
            response.raise_for_status()

            return self._parse_grok_response(response.text)
        except httpx.HTTPStatusError as error:
            raise self._http_status_error(error.response) from error
        except (httpx.RequestError, TimeoutError) as error:
            raise AIServiceError("Cannot reach Grok API right now.") from error
        except json.JSONDecodeError as error:
            raise AIServiceError(
                "Grok API returned an unreadable response.",
                status_code=500,
            ) from error

    async def stream_response(
        self,
        messages: list[dict],
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        prompt_messages = self._validated_prompt_messages(messages)
        payload = {
            "model": self.settings.grok_model,
            "messages": prompt_messages,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        try:
            from app.services.http_client import get_http_client

            client = get_http_client()
            async with client.stream(
                "POST",
                self.settings.grok_chat_url,
                headers={
                    "Authorization": f"Bearer {self.settings.grok_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.settings.grok_timeout_seconds,
            ) as response:
                response.raise_for_status()
                async for token in self._parse_grok_stream(response):
                    yield token
        except httpx.HTTPStatusError as error:
            raise self._http_status_error(error.response) from error
        except (httpx.RequestError, TimeoutError) as error:
            raise AIServiceError("Cannot reach Grok API right now.") from error
        except json.JSONDecodeError as error:
            raise AIServiceError(
                "Grok API returned an unreadable streaming response.",
                status_code=500,
            ) from error

    def _validated_prompt_messages(self, messages: list[dict]) -> list[dict]:
        if not self.settings.grok_api_key:
            raise AIServiceError("Grok API key is not configured.", status_code=503)
        if not self.settings.grok_model:
            raise AIServiceError("Grok model is not configured.", status_code=503)

        prompt_messages = self._prompt_messages(messages)
        if self._prompt_length(prompt_messages) > self.max_prompt_characters:
            raise AIServiceError(
                "Message context is too large. Shorten the file or start a new chat.",
                status_code=400,
            )

        return prompt_messages

    def _prompt_messages(self, messages: list[dict]) -> list[dict]:
        return [
            {"role": message["role"], "content": message["content"]}
            for message in messages
        ]

    def _prompt_length(self, messages: list[dict]) -> int:
        return sum(len(message["content"]) for message in messages)

    def _parse_grok_response(self, raw_response: str) -> str:
        data = json.loads(raw_response)
        choices = data.get("choices", [])
        if not choices:
            raise AIServiceError("Grok API returned no response.", status_code=502)

        message = choices[0].get("message", {})
        content = message.get("content", "")
        return str(content).strip()

    async def _parse_grok_stream(
        self,
        response: httpx.Response,
    ) -> AsyncIterator[str]:
        async for line in response.aiter_lines():
            line = line.strip()
            if not line or line.startswith(":"):
                continue
            if line.startswith("data:"):
                line = line[5:].strip()
            if line == "[DONE]":
                break

            data = json.loads(line)
            choices = data.get("choices", [])
            if not choices:
                continue

            delta = choices[0].get("delta", {})
            content = delta.get("content")
            if content:
                yield str(content)

    def _http_status_error(self, response: httpx.Response) -> AIServiceError:
        detail = self._grok_error_detail(response)
        if response.status_code == 429:
            return AIServiceError(
                detail or "Grok is at capacity right now. Try again in a few minutes.",
                status_code=503,
            )
        if response.status_code == 400:
            return AIServiceError(
                detail or "Grok rejected the request configuration.",
                status_code=502,
            )
        if response.status_code in {401, 403}:
            return AIServiceError(
                detail or "Grok API authentication failed. Check the API key.",
                status_code=503,
            )
        return AIServiceError(
            detail or "Grok API returned an error.",
            status_code=503,
        )

    def _grok_error_detail(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except json.JSONDecodeError:
            return response.text.strip()

        if not isinstance(data, dict):
            return response.text.strip()

        for key in ("error", "detail", "message"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                nested_message = value.get("message") or value.get("detail")
                if isinstance(nested_message, str) and nested_message.strip():
                    return nested_message.strip()

        return response.text.strip()

import json
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings, get_settings


class AIServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 503) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class AIService:
    max_prompt_characters = 30000
    system_prompt = """
You are Rex, a personal AI advisor.
Be direct, straightforward, and honest.
Do not use fluff, filler, fake enthusiasm, or vague motivation.
Give practical answers.
If something is unclear, ask a simple clarifying question.
If the user is wrong, say so respectfully and explain why.
Keep responses concise unless the user asks for detail.
""".strip()

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    def generate_response(self, messages: list[dict]) -> str:
        prompt_messages = self._build_prompt_messages(messages)
        if self._prompt_length(prompt_messages) > self.max_prompt_characters:
            raise AIServiceError(
                "Message context is too large. Shorten the file or start a new chat.",
                status_code=400,
            )

        payload = {
            "model": self.settings.ollama_model,
            "messages": prompt_messages,
            "stream": False,
        }

        try:
            request = Request(
                self.settings.ollama_chat_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(
                request,
                timeout=self.settings.ollama_timeout_seconds,
            ) as response:
                raw_response = response.read().decode("utf-8")

            return self._parse_ollama_response(raw_response)
        except HTTPError as error:
            raise AIServiceError("Rex's brain returned an error.") from error
        except (URLError, TimeoutError) as error:
            raise AIServiceError(
                "Cannot reach Rex's brain right now. Is Ollama running?"
            ) from error
        except json.JSONDecodeError as error:
            raise AIServiceError(
                "Rex's brain returned an unreadable response.",
                status_code=500,
            ) from error

    def _build_prompt_messages(self, messages: list[dict]) -> list[dict]:
        return [
            {"role": "system", "content": self.system_prompt},
            *[
                {"role": message["role"], "content": message["content"]}
                for message in messages
            ],
        ]

    def _prompt_length(self, messages: list[dict]) -> int:
        return sum(len(message["content"]) for message in messages)

    def _parse_ollama_response(self, raw_response: str) -> str:
        if "\n" in raw_response.strip():
            return self._parse_streaming_response(raw_response)

        data = json.loads(raw_response)
        return data.get("message", {}).get("content", "").strip()

    def _parse_streaming_response(self, raw_response: str) -> str:
        content_parts = []
        for line in raw_response.splitlines():
            if not line.strip():
                continue

            data = json.loads(line)
            content = data.get("message", {}).get("content", "")
            if content:
                content_parts.append(content)

        return "".join(content_parts).strip()

import pytest
from fastapi import HTTPException

from app import database
from app.services import memory_service
from app.services.chat_service import ChatService, FILE_CONTEXT_PREFIX
from app.services.file_service import FileService


class FakeAIService:
    def __init__(self):
        self.messages = []

    def generate_response(self, messages):
        self.messages = messages
        return "Rex response"


class FakeUpload:
    def __init__(self, filename, content):
        self.filename = filename
        self._content = content

    async def read(self):
        return self._content


@pytest.fixture()
def temp_database(tmp_path):
    original_database_path = database.DATABASE_PATH
    database.DATABASE_PATH = tmp_path / "rex-test.db"
    memory_service.init()

    yield

    database.DATABASE_PATH = original_database_path


@pytest.mark.asyncio
async def test_file_upload_rejects_files_over_2mb():
    file_service = FileService()
    upload = FakeUpload("notes.txt", b"a" * (2 * 1024 * 1024 + 1))

    with pytest.raises(HTTPException) as error:
        await file_service.read_text_file(upload)

    assert error.value.status_code == 413
    assert error.value.detail == "Uploaded file is too large. Maximum size is 2MB."


@pytest.mark.asyncio
async def test_chat_service_handles_normal_chat(temp_database):
    ai_service = FakeAIService()
    chat_service = ChatService(ai_service, FileService())

    result = await chat_service.send_message("Hello Rex")

    assert result["conversation_id"] == 1
    assert result["response"] == "Rex response"
    assert [message["role"] for message in result["messages"]] == [
        "user",
        "assistant",
    ]
    assert ai_service.messages[-1]["content"] == "Hello Rex"


@pytest.mark.asyncio
async def test_chat_service_handles_file_upload(temp_database):
    ai_service = FakeAIService()
    chat_service = ChatService(ai_service, FileService())
    upload = FakeUpload("notes.md", b"Project notes")

    result = await chat_service.send_message("Read this file", file=upload)

    assert result["response"] == "Rex response"
    assert ai_service.messages[-2]["content"] == (
        f"{FILE_CONTEXT_PREFIX}Project notes"
    )
    assert ai_service.messages[-1]["content"] == "Read this file"

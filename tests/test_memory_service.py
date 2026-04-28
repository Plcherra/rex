import pytest

from app import database
from app.services import memory_service


@pytest.fixture()
def temp_database(tmp_path):
    original_database_path = database.DATABASE_PATH
    database.DATABASE_PATH = tmp_path / "rex-test.db"
    memory_service.init()

    yield

    database.DATABASE_PATH = original_database_path


def test_create_new_conversation(temp_database):
    conversation_id = memory_service.create_conversation()

    assert conversation_id == 1
    assert memory_service.conversation_exists(conversation_id)


def test_save_and_retrieve_messages(temp_database):
    conversation_id = memory_service.create_conversation()

    user_message = memory_service.save_message(
        conversation_id,
        "user",
        "Hello Rex",
    )
    assistant_message = memory_service.save_message(
        conversation_id,
        "assistant",
        "What are you thinking?",
    )

    messages = memory_service.get_recent_messages(conversation_id)

    assert user_message["role"] == "user"
    assert assistant_message["role"] == "assistant"
    assert [message["content"] for message in messages] == [
        "Hello Rex",
        "What are you thinking?",
    ]

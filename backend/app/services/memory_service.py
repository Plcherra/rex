from sqlite3 import Connection, Row

from app.database import get_connection


def init() -> None:
    with get_connection() as connection:
        _create_conversations_table(connection)
        _create_messages_table(connection)


def create_conversation() -> int:
    with get_connection() as connection:
        cursor = connection.execute("INSERT INTO conversations DEFAULT VALUES")
        return int(cursor.lastrowid)


def conversation_exists(conversation_id: int) -> bool:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        return row is not None


def save_message(conversation_id: int, role: str, content: str) -> dict:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO messages (conversation_id, role, content)
            VALUES (?, ?, ?)
            """,
            (conversation_id, role, content),
        )
        row = connection.execute(
            """
            SELECT id, conversation_id, role, content, timestamp
            FROM messages
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return _message_to_dict(row)


def get_recent_messages(conversation_id: int, limit: int = 20) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, conversation_id, role, content, timestamp
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (conversation_id, limit),
        ).fetchall()

    return [_message_to_dict(row) for row in reversed(rows)]


def _create_conversations_table(connection: Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _create_messages_table(connection: Connection) -> None:
    columns = _table_columns(connection, "messages")
    expected_columns = {"id", "conversation_id", "role", "content", "timestamp"}

    if not columns:
        _create_fresh_messages_table(connection)
        return

    if not expected_columns.issubset(columns):
        _migrate_legacy_messages_table(connection)


def _create_fresh_messages_table(connection: Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations (id)
        )
        """
    )


def _migrate_legacy_messages_table(connection: Connection) -> None:
    connection.execute("ALTER TABLE messages RENAME TO messages_legacy")
    _create_fresh_messages_table(connection)

    cursor = connection.execute("INSERT INTO conversations DEFAULT VALUES")
    conversation_id = int(cursor.lastrowid)
    legacy_columns = _table_columns(connection, "messages_legacy")

    timestamp_column = "created_at" if "created_at" in legacy_columns else "CURRENT_TIMESTAMP"
    connection.execute(
        f"""
        INSERT INTO messages (id, conversation_id, role, content, timestamp)
        SELECT id, ?, role, content, {timestamp_column}
        FROM messages_legacy
        """,
        (conversation_id,),
    )
    connection.execute("DROP TABLE messages_legacy")


def _table_columns(connection: Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row["name"]) for row in rows}


def _message_to_dict(row: Row) -> dict:
    return {
        "id": row["id"],
        "conversation_id": row["conversation_id"],
        "role": row["role"],
        "content": row["content"],
        "timestamp": row["timestamp"],
    }

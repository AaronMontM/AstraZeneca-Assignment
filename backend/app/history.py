import uuid

from datetime import datetime, timezone
from typing import Any, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class HistoryStore:
    """
    PostgreSQL persistence layer for conversations, messages
    and LLM usage statistics.
    """

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.initialize()

    def _connect(self):
        return psycopg.connect(
            self.database_url,
            row_factory=dict_row
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    # -----------------------------------------------------------------
    # Database initialization
    # -----------------------------------------------------------------

    def initialize(self) -> None:

        statements = [

            """
            CREATE TABLE IF NOT EXISTS conversations (
                id UUID PRIMARY KEY,
                title TEXT,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS messages (
                id BIGSERIAL PRIMARY KEY,
                conversation_id UUID NOT NULL
                    REFERENCES conversations(id)
                    ON DELETE CASCADE,
                role TEXT NOT NULL
                    CHECK (role IN ('user', 'assistant', 'system')),
                content TEXT NOT NULL,
                route TEXT,
                evidence JSONB,
                tools_used JSONB,
                created_at TIMESTAMPTZ NOT NULL
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS usage_events (
                id BIGSERIAL PRIMARY KEY,
                conversation_id UUID
                    REFERENCES conversations(id)
                    ON DELETE SET NULL,
                operation TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                created_at TIMESTAMPTZ NOT NULL
            )
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_messages_conversation
            ON messages(conversation_id)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_usage_conversation
            ON usage_events(conversation_id)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_conversations_updated
            ON conversations(updated_at DESC)
            """
        ]

        with self._connect() as connection:

            for statement in statements:
                connection.execute(statement)

    # -----------------------------------------------------------------
    # Database health
    # -----------------------------------------------------------------

    def ping(self) -> bool:

        with self._connect() as connection:
            connection.execute("SELECT 1")

        return True

    # -----------------------------------------------------------------
    # Conversations
    # -----------------------------------------------------------------

    def create_conversation(
        self,
        title: Optional[str] = None
    ) -> str:

        conversation_id = str(uuid.uuid4())
        now = self._now()

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO conversations (
                    id,
                    title,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    conversation_id,
                    title,
                    now,
                    now
                )
            )

        return conversation_id

    def get_conversation(
        self,
        conversation_id: str
    ) -> Optional[dict]:

        with self._connect() as connection:

            conversation = connection.execute(
                """
                SELECT
                    id,
                    title,
                    created_at,
                    updated_at
                FROM conversations
                WHERE id = %s
                """,
                (conversation_id,)
            ).fetchone()

            if conversation is None:
                return None

            messages = connection.execute(
                """
                SELECT
                    id,
                    role,
                    content,
                    route,
                    evidence,
                    tools_used,
                    created_at
                FROM messages
                WHERE conversation_id = %s
                ORDER BY created_at, id
                """,
                (conversation_id,)
            ).fetchall()

        return {
            **conversation,
            "id": str(conversation["id"]),
            "messages": messages
        }

    def list_conversations(
        self,
        limit: int = 50
    ) -> list[dict]:

        if not 1 <= limit <= 100:
            raise ValueError(
                "Limit must be between 1 and 100."
            )

        with self._connect() as connection:

            rows = connection.execute(
                """
                SELECT
                    c.id,
                    c.title,
                    c.created_at,
                    c.updated_at,
                    COUNT(m.id) AS message_count
                FROM conversations c
                LEFT JOIN messages m
                    ON m.conversation_id = c.id
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT %s
                """,
                (limit,)
            ).fetchall()

        return [
            {
                **row,
                "id": str(row["id"])
            }
            for row in rows
        ]

    def delete_conversation(
        self,
        conversation_id: str
    ) -> bool:

        with self._connect() as connection:

            result = connection.execute(
                """
                DELETE FROM conversations
                WHERE id = %s
                """,
                (conversation_id,)
            )

        return result.rowcount > 0

    # -----------------------------------------------------------------
    # Messages
    # -----------------------------------------------------------------

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        route: Optional[str] = None,
        evidence: Optional[Any] = None,
        tools_used: Optional[list[str]] = None
    ) -> int:

        if role not in {"user", "assistant", "system"}:
            raise ValueError(
                f"Unsupported message role: {role}"
            )

        now = self._now()

        with self._connect() as connection:

            result = connection.execute(
                """
                INSERT INTO messages (
                    conversation_id,
                    role,
                    content,
                    route,
                    evidence,
                    tools_used,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    conversation_id,
                    role,
                    content,
                    route,
                    Jsonb(evidence) if evidence is not None else None,
                    Jsonb(tools_used) if tools_used is not None else None,
                    now
                )
            )

            message_id = result.fetchone()["id"]

            connection.execute(
                """
                UPDATE conversations
                SET updated_at = %s
                WHERE id = %s
                """,
                (now, conversation_id)
            )

        return message_id

    def get_recent_messages(
        self,
        conversation_id: str,
        limit: int = 10
    ) -> list[dict]:

        if limit < 1:
            raise ValueError(
                "Limit must be greater than zero."
            )

        with self._connect() as connection:

            rows = connection.execute(
                """
                SELECT
                    role,
                    content
                FROM messages
                WHERE conversation_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (
                    conversation_id,
                    limit
                )
            ).fetchall()

        # Restore chronological order.
        return list(reversed(rows))

    # -----------------------------------------------------------------
    # LLM usage
    # -----------------------------------------------------------------

    def record_usage(
        self,
        operation: str,
        model: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        conversation_id: Optional[str] = None
    ) -> None:

        with self._connect() as connection:

            connection.execute(
                """
                INSERT INTO usage_events (
                    conversation_id,
                    operation,
                    model,
                    prompt_tokens,
                    completion_tokens,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    conversation_id,
                    operation,
                    model,
                    prompt_tokens,
                    completion_tokens,
                    self._now()
                )
            )

    def get_usage_summary(
        self,
        conversation_id: Optional[str] = None
    ) -> dict:

        if conversation_id is None:

            totals_query = """
                SELECT
                    COUNT(*) AS total_calls,
                    COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) AS completion_tokens
                FROM usage_events
            """

            breakdown_query = """
                SELECT
                    operation,
                    model,
                    COUNT(*) AS calls,
                    COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) AS completion_tokens
                FROM usage_events
                GROUP BY operation, model
                ORDER BY operation, model
            """

            parameters = ()

        else:

            totals_query = """
                SELECT
                    COUNT(*) AS total_calls,
                    COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) AS completion_tokens
                FROM usage_events
                WHERE conversation_id = %s
            """

            breakdown_query = """
                SELECT
                    operation,
                    model,
                    COUNT(*) AS calls,
                    COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) AS completion_tokens
                FROM usage_events
                WHERE conversation_id = %s
                GROUP BY operation, model
                ORDER BY operation, model
            """

            parameters = (conversation_id,)

        with self._connect() as connection:

            totals = connection.execute(
                totals_query,
                parameters
            ).fetchone()

            breakdown = connection.execute(
                breakdown_query,
                parameters
            ).fetchall()

        result = dict(totals)

        result["total_tokens"] = (
            result["prompt_tokens"]
            + result["completion_tokens"]
        )

        result["breakdown"] = breakdown

        return result
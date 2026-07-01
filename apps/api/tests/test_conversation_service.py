from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from industrial_agent.database.session import create_session_factory
from industrial_agent.models.conversation import Conversation
from industrial_agent.services.conversation import (
    ConversationNotFoundError,
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
)


def test_create_conversation_persists_values_across_sessions(
    database_session: Session,
    database_engine: Engine,
) -> None:
    conversation = create_conversation(
        database_session,
        title="Yield investigation",
    )
    conversation_id = conversation.id
    database_session.close()

    factory = create_session_factory(database_engine)
    with factory() as verification_session:
        persisted = verification_session.get(Conversation, conversation_id)
        count = verification_session.scalar(
            select(func.count()).select_from(Conversation)
        )

    assert isinstance(conversation_id, UUID)
    assert persisted is not None
    assert persisted.title == "Yield investigation"
    assert persisted.created_at is not None
    assert count == 1


def test_list_conversations_orders_newest_then_uuid(
    database_session: Session,
) -> None:
    older = Conversation(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Older",
        created_at=datetime(2026, 7, 30, 5, 0, tzinfo=UTC),
    )
    tied_low = Conversation(
        id=UUID("00000000-0000-0000-0000-000000000002"),
        title="Tied low",
        created_at=datetime(2026, 7, 30, 6, 0, tzinfo=UTC),
    )
    tied_high = Conversation(
        id=UUID("00000000-0000-0000-0000-000000000003"),
        title="Tied high",
        created_at=datetime(2026, 7, 30, 6, 0, tzinfo=UTC),
    )
    database_session.add_all([older, tied_low, tied_high])
    database_session.commit()

    conversations = list_conversations(database_session)

    assert [item.id for item in conversations] == [
        tied_high.id,
        tied_low.id,
        older.id,
    ]


def test_get_conversation_returns_persisted_entity(
    database_session: Session,
) -> None:
    expected = create_conversation(
        database_session,
        title="Yield investigation",
    )

    result = get_conversation(database_session, expected.id)

    assert result is expected


def test_get_conversation_raises_for_unknown_id(
    database_session: Session,
) -> None:
    unknown_id = UUID("00000000-0000-0000-0000-000000000099")

    with pytest.raises(ConversationNotFoundError):
        get_conversation(database_session, unknown_id)


def test_delete_conversation_removes_entity(
    database_session: Session,
) -> None:
    conversation = create_conversation(
        database_session,
        title="Yield investigation",
    )

    delete_conversation(database_session, conversation.id)

    assert database_session.get(Conversation, conversation.id) is None


def test_delete_conversation_raises_for_unknown_id(
    database_session: Session,
) -> None:
    unknown_id = UUID("00000000-0000-0000-0000-000000000099")

    with pytest.raises(ConversationNotFoundError):
        delete_conversation(database_session, unknown_id)

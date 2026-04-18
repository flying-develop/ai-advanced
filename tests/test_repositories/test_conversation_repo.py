"""Unit tests for ConversationRepository."""

# third-party
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# local
from src.models.conversation import Conversation, Message
from src.repositories.conversation_repo import ConversationRepository


class TestGetOrCreate:
    """Tests for ConversationRepository.get_or_create."""

    async def test_creates_new_conversation_when_none_exists(
        self,
        conversation_repo: ConversationRepository,
        session: AsyncSession,
    ) -> None:
        """No active conversation → a new one is persisted and returned."""
        conv = await conversation_repo.get_or_create(user_id=1)

        assert conv.id is not None
        assert conv.user_id == 1
        assert conv.is_active is True

        result = await session.execute(
            select(Conversation).where(Conversation.user_id == 1)
        )
        assert result.scalar_one_or_none() is not None

    async def test_returns_existing_active_conversation(
        self,
        conversation_repo: ConversationRepository,
    ) -> None:
        """Active conversation already exists → returns it without creating a duplicate."""
        first = await conversation_repo.get_or_create(user_id=1)
        second = await conversation_repo.get_or_create(user_id=1)

        assert first.id == second.id

    async def test_creates_new_after_old_is_deactivated(
        self,
        conversation_repo: ConversationRepository,
    ) -> None:
        """After deactivation, get_or_create returns a brand-new conversation."""
        old = await conversation_repo.get_or_create(user_id=1)
        await conversation_repo.deactivate(old)

        new = await conversation_repo.get_or_create(user_id=1)

        assert new.id != old.id
        assert new.is_active is True


class TestAddMessage:
    """Tests for ConversationRepository.add_message."""

    async def test_message_saved_with_correct_role_and_content(
        self,
        conversation_repo: ConversationRepository,
        session: AsyncSession,
    ) -> None:
        """add_message persists role and content exactly as passed."""
        conv = await conversation_repo.get_or_create(user_id=2)
        msg = await conversation_repo.add_message(
            conversation_id=conv.id, role="user", content="Test content"
        )

        assert msg.id is not None
        assert msg.role == "user"
        assert msg.content == "Test content"
        assert msg.conversation_id == conv.id

    async def test_multiple_roles_saved_independently(
        self,
        conversation_repo: ConversationRepository,
        session: AsyncSession,
    ) -> None:
        """User and assistant messages are stored separately with correct roles."""
        conv = await conversation_repo.get_or_create(user_id=2)
        await conversation_repo.add_message(
            conversation_id=conv.id, role="user", content="Hello"
        )
        await conversation_repo.add_message(
            conversation_id=conv.id, role="assistant", content="Hi there"
        )

        result = await session.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.id)
        )
        messages = list(result.scalars().all())
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"


class TestGetRecentMessages:
    """Tests for ConversationRepository.get_recent_messages."""

    async def test_limit_returns_last_n_messages(
        self,
        conversation_repo: ConversationRepository,
    ) -> None:
        """get_recent_messages(limit=3) returns only the last 3 messages."""
        conv = await conversation_repo.get_or_create(user_id=3)
        for i in range(10):
            await conversation_repo.add_message(
                conversation_id=conv.id, role="user", content=f"msg {i}"
            )

        recent = await conversation_repo.get_recent_messages(
            conversation_id=conv.id, limit=3
        )

        assert len(recent) == 3

    async def test_messages_returned_in_chronological_order(
        self,
        conversation_repo: ConversationRepository,
    ) -> None:
        """Messages are ordered oldest-first so the LLM sees them in conversation order."""
        conv = await conversation_repo.get_or_create(user_id=3)
        for i in range(5):
            await conversation_repo.add_message(
                conversation_id=conv.id, role="user", content=f"msg {i}"
            )

        messages = await conversation_repo.get_recent_messages(
            conversation_id=conv.id, limit=5
        )

        contents = [m.content for m in messages]
        assert contents == ["msg 0", "msg 1", "msg 2", "msg 3", "msg 4"]

    async def test_returns_empty_list_for_empty_conversation(
        self,
        conversation_repo: ConversationRepository,
    ) -> None:
        """No messages yet → returns an empty list without error."""
        conv = await conversation_repo.get_or_create(user_id=3)
        messages = await conversation_repo.get_recent_messages(
            conversation_id=conv.id, limit=10
        )
        assert messages == []

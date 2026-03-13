"""
Tests for lib/classes/case_manager.py

Covers the core operations of GuildModCaseManager:
  - create_case  (WARN / KICK / MUTE / BAN)
  - get_case_by_id
  - get_cases_by_user
  - update_case
  - delete_case

dpytest is used to provide a realistic Discord environment (guild + members)
without a live bot token.  The SQLAlchemy session is replaced with an AsyncMock
so tests run without a database.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import discord.ext.test as dpytest
import pytest

from lib.classes.case_manager import (
    CaseNotFoundException,
    GuildModCaseManager,
)
from lib.enums.moderation import CaseSource, CaseType
from lib.sql.sql import ModCase


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_session(*preset_cases: ModCase) -> AsyncMock:
    """Return a mock AsyncSession pre-loaded with *preset_cases*.

    Every ``session.execute()`` call returns a result where:
    - ``scalar_one_or_none()`` → the first preset case (or None)
    - ``scalars().all()``      → all preset cases
    """
    session = AsyncMock()
    session.add = MagicMock()  # sync in SQLAlchemy; leave as plain MagicMock

    result = MagicMock()
    result.scalar_one_or_none.return_value = preset_cases[0] if preset_cases else None
    result.scalars.return_value.all.return_value = list(preset_cases)
    session.execute = AsyncMock(return_value=result)

    return session


def _make_case(
    case_id: str = "testcase",
    case_type: CaseType = CaseType.WARN,
    guild_id: int = 1,
    user_id: int = 100,
    creator_id: int = 200,
    reason: str = "Test reason",
    resolved: bool = False,
    time_expires: datetime | None = None,
) -> ModCase:
    """Construct an in-memory ModCase with sensible defaults."""
    case = ModCase(
        type=case_type,
        guild_id=guild_id,
        user_id=user_id,
        creator_user_id=creator_id,
        description=reason,
        external=False,
        resolved=resolved,
    )
    # These fields are normally set by the database; assign them manually so
    # tests that inspect them don't see None.
    case.id = case_id
    case.time_created = datetime.now()
    case.time_updated = None
    case.time_expires = time_expires
    # Relationships default to [] on transient objects but be explicit here.
    case.comments = []
    case.scheduled_tasks = []
    return case


# ── create_case ────────────────────────────────────────────────────────────────


class TestCreateCase:
    """GuildModCaseManager.create_case"""

    async def test_warn_case_stores_correct_fields(self, bot: discord.Client) -> None:
        """A WARN case is stored with the right type, user, guild and reason."""
        cfg = dpytest.get_config()
        guild = cfg.guilds[0]
        member = cfg.members[0]

        bot.fetch_guild_config = AsyncMock(return_value=None)  # type: ignore[attr-defined]
        session = _make_session()

        with (
            patch("lib.classes.case_manager.GuildLogger") as MockLogger,
            patch(
                "lib.classes.case_manager.send_dm",
                new_callable=AsyncMock,
                return_value=(True, ""),
            ),
        ):
            MockLogger.return_value.titanium_warn = AsyncMock()

            manager = GuildModCaseManager(bot, guild, session)  # type: ignore[arg-type]
            case, dm_ok, _ = await manager.create_case(
                action=CaseType.WARN,
                user=member,
                creator_user=member,
                reason="Spamming in general",
            )

        assert case.type == CaseType.WARN
        assert case.user_id == member.id
        assert case.creator_user_id == member.id
        assert case.guild_id == guild.id
        assert case.description == "Spamming in general"
        assert dm_ok is True

    async def test_warn_case_starts_unresolved(self, bot: discord.Client) -> None:
        """WARN cases must begin with resolved=False — they can be closed later."""
        cfg = dpytest.get_config()
        guild, member = cfg.guilds[0], cfg.members[0]

        bot.fetch_guild_config = AsyncMock(return_value=None)  # type: ignore[attr-defined]
        session = _make_session()

        with (
            patch("lib.classes.case_manager.GuildLogger") as MockLogger,
            patch("lib.classes.case_manager.send_dm", new_callable=AsyncMock, return_value=(True, "")),
        ):
            MockLogger.return_value.titanium_warn = AsyncMock()

            case, _, _ = await GuildModCaseManager(bot, guild, session).create_case(  # type: ignore[arg-type]
                action=CaseType.WARN,
                user=member,
                creator_user=member,
                reason="First warning",
            )

        assert case.resolved is False

    async def test_kick_case_is_immediately_resolved(self, bot: discord.Client) -> None:
        """KICK cases must be auto-resolved (there is no un-kick action)."""
        cfg = dpytest.get_config()
        guild, member = cfg.guilds[0], cfg.members[0]

        bot.fetch_guild_config = AsyncMock(return_value=None)  # type: ignore[attr-defined]
        session = _make_session()

        with (
            patch("lib.classes.case_manager.GuildLogger") as MockLogger,
            patch("lib.classes.case_manager.send_dm", new_callable=AsyncMock, return_value=(True, "")),
        ):
            MockLogger.return_value.titanium_kick = AsyncMock()

            case, _, _ = await GuildModCaseManager(bot, guild, session).create_case(  # type: ignore[arg-type]
                action=CaseType.KICK,
                user=member,
                creator_user=member,
                reason="Rule violation",
            )

        assert case.resolved is True

    async def test_new_ban_closes_existing_open_bans(self, bot: discord.Client) -> None:
        """When a BAN is created any prior open BAN cases for the same user are resolved."""
        cfg = dpytest.get_config()
        guild, member = cfg.guilds[0], cfg.members[0]

        old_ban = _make_case(
            case_id="oldbann1",
            case_type=CaseType.BAN,
            guild_id=guild.id,
            user_id=member.id,
            resolved=False,
        )
        bot.fetch_guild_config = AsyncMock(return_value=None)  # type: ignore[attr-defined]
        session = _make_session(old_ban)

        with (
            patch("lib.classes.case_manager.GuildLogger") as MockLogger,
            patch("lib.classes.case_manager.send_dm", new_callable=AsyncMock, return_value=(True, "")),
        ):
            MockLogger.return_value.titanium_ban = AsyncMock()

            await GuildModCaseManager(bot, guild, session).create_case(  # type: ignore[arg-type]
                action=CaseType.BAN,
                user=member,
                creator_user=member,
                reason="Severe violation",
            )

        assert old_ban.resolved is True

    async def test_new_mute_closes_existing_open_mutes(self, bot: discord.Client) -> None:
        """When a MUTE is created any prior open MUTE cases for the same user are resolved."""
        cfg = dpytest.get_config()
        guild, member = cfg.guilds[0], cfg.members[0]

        old_mute = _make_case(
            case_id="oldmute1",
            case_type=CaseType.MUTE,
            guild_id=guild.id,
            user_id=member.id,
            resolved=False,
        )
        bot.fetch_guild_config = AsyncMock(return_value=None)  # type: ignore[attr-defined]
        session = _make_session(old_mute)

        with (
            patch("lib.classes.case_manager.GuildLogger") as MockLogger,
            patch("lib.classes.case_manager.send_dm", new_callable=AsyncMock, return_value=(True, "")),
        ):
            MockLogger.return_value.titanium_mute = AsyncMock()

            await GuildModCaseManager(bot, guild, session).create_case(  # type: ignore[arg-type]
                action=CaseType.MUTE,
                user=member,
                creator_user=member,
                reason="Disruptive behaviour",
            )

        assert old_mute.resolved is True

    async def test_create_case_calls_guild_logger(self, bot: discord.Client) -> None:
        """The appropriate GuildLogger method is called once after creating a case."""
        cfg = dpytest.get_config()
        guild, member = cfg.guilds[0], cfg.members[0]

        bot.fetch_guild_config = AsyncMock(return_value=None)  # type: ignore[attr-defined]
        session = _make_session()

        with (
            patch("lib.classes.case_manager.GuildLogger") as MockLogger,
            patch("lib.classes.case_manager.send_dm", new_callable=AsyncMock, return_value=(True, "")),
        ):
            mock_warn = AsyncMock()
            MockLogger.return_value.titanium_warn = mock_warn

            await GuildModCaseManager(bot, guild, session).create_case(  # type: ignore[arg-type]
                action=CaseType.WARN,
                user=member,
                creator_user=member,
                reason="Bad language",
            )

        mock_warn.assert_called_once()

    async def test_create_case_passes_correct_source_to_send_dm(self, bot: discord.Client) -> None:
        """The module name forwarded to send_dm reflects the CaseSource."""
        cfg = dpytest.get_config()
        guild, member = cfg.guilds[0], cfg.members[0]

        bot.fetch_guild_config = AsyncMock(return_value=None)  # type: ignore[attr-defined]
        session = _make_session()

        with (
            patch("lib.classes.case_manager.GuildLogger") as MockLogger,
            patch(
                "lib.classes.case_manager.send_dm",
                new_callable=AsyncMock,
                return_value=(True, ""),
            ) as mock_send_dm,
        ):
            MockLogger.return_value.titanium_warn = AsyncMock()

            await GuildModCaseManager(bot, guild, session).create_case(  # type: ignore[arg-type]
                action=CaseType.WARN,
                user=member,
                creator_user=member,
                reason="Test",
                source=CaseSource.AUTOMOD,
            )

        _, kwargs = mock_send_dm.call_args
        assert kwargs["module"] == "Automod"


# ── get_case_by_id ─────────────────────────────────────────────────────────────


class TestGetCaseById:
    """GuildModCaseManager.get_case_by_id"""

    async def test_returns_matching_case(self, bot: discord.Client) -> None:
        """The exact ModCase object is returned when it exists in the session."""
        cfg = dpytest.get_config()
        guild = cfg.guilds[0]

        expected = _make_case(case_id="abc12345", guild_id=guild.id)
        session = _make_session(expected)

        result = await GuildModCaseManager(bot, guild, session).get_case_by_id("abc12345")  # type: ignore[arg-type]

        assert result is expected

    async def test_raises_case_not_found_exception(self, bot: discord.Client) -> None:
        """CaseNotFoundException is raised when no matching case exists."""
        cfg = dpytest.get_config()
        guild = cfg.guilds[0]

        session = _make_session()  # scalar_one_or_none returns None

        with pytest.raises(CaseNotFoundException):
            await GuildModCaseManager(bot, guild, session).get_case_by_id("doesnotexist")  # type: ignore[arg-type]


# ── get_cases_by_user ──────────────────────────────────────────────────────────


class TestGetCasesByUser:
    """GuildModCaseManager.get_cases_by_user"""

    async def test_returns_empty_sequence_when_no_cases(self, bot: discord.Client) -> None:
        """An empty sequence is returned when the user has no cases on record."""
        cfg = dpytest.get_config()
        guild, member = cfg.guilds[0], cfg.members[0]

        session = _make_session()

        result = await GuildModCaseManager(bot, guild, session).get_cases_by_user(member.id)  # type: ignore[arg-type]

        assert list(result) == []

    async def test_returns_all_cases_for_user(self, bot: discord.Client) -> None:
        """All stored cases for the given user are returned."""
        cfg = dpytest.get_config()
        guild, member = cfg.guilds[0], cfg.members[0]

        cases = [
            _make_case(case_id="case0001", user_id=member.id, guild_id=guild.id),
            _make_case(
                case_id="case0002",
                user_id=member.id,
                guild_id=guild.id,
                case_type=CaseType.BAN,
            ),
        ]
        session = _make_session(*cases)

        result = await GuildModCaseManager(bot, guild, session).get_cases_by_user(member.id)  # type: ignore[arg-type]

        assert len(result) == 2


# ── update_case ────────────────────────────────────────────────────────────────


class TestUpdateCase:
    """GuildModCaseManager.update_case"""

    async def test_updates_reason(self, bot: discord.Client) -> None:
        """Supplying a new reason replaces case.description."""
        cfg = dpytest.get_config()
        guild = cfg.guilds[0]

        case = _make_case(reason="Old reason")
        session = _make_session(case)

        updated = await GuildModCaseManager(bot, guild, session).update_case(  # type: ignore[arg-type]
            case_id="testcase", reason="New reason", resolved=None
        )

        assert updated.description == "New reason"

    async def test_marks_case_as_resolved(self, bot: discord.Client) -> None:
        """Passing resolved=True closes the case."""
        cfg = dpytest.get_config()
        guild = cfg.guilds[0]

        case = _make_case(resolved=False)
        session = _make_session(case)

        updated = await GuildModCaseManager(bot, guild, session).update_case(  # type: ignore[arg-type]
            case_id="testcase", reason=None, resolved=True
        )

        assert updated.resolved is True

    async def test_updates_expiry_with_duration(self, bot: discord.Client) -> None:
        """Providing a duration sets case.time_expires relative to the current time."""
        cfg = dpytest.get_config()
        guild = cfg.guilds[0]

        case = _make_case()
        session = _make_session(case)
        duration = timedelta(days=7)

        before = datetime.now()
        updated = await GuildModCaseManager(bot, guild, session).update_case(  # type: ignore[arg-type]
            case_id="testcase", reason=None, resolved=None, duration=duration
        )
        after = datetime.now()

        assert updated.time_expires is not None
        expected_low = before + duration
        expected_high = after + duration
        assert expected_low <= updated.time_expires <= expected_high

    async def test_raises_when_case_not_found(self, bot: discord.Client) -> None:
        """CaseNotFoundException bubbles up from the underlying get_case_by_id call."""
        cfg = dpytest.get_config()
        guild = cfg.guilds[0]

        session = _make_session()  # no cases

        with pytest.raises(CaseNotFoundException):
            await GuildModCaseManager(bot, guild, session).update_case(  # type: ignore[arg-type]
                case_id="missing", reason="something", resolved=None
            )


# ── delete_case ────────────────────────────────────────────────────────────────


class TestDeleteCase:
    """GuildModCaseManager.delete_case"""

    async def test_delete_resolved_case_calls_session_delete(self, bot: discord.Client) -> None:
        """Deleting an already-resolved case calls session.delete with the case object."""
        cfg = dpytest.get_config()
        guild = cfg.guilds[0]

        # Use a pre-resolved case so close_case (which needs DM mocks) is skipped.
        case = _make_case(resolved=True)
        session = _make_session(case)

        with patch("lib.classes.case_manager.GuildLogger") as MockLogger:
            MockLogger.return_value.titanium_case_delete = AsyncMock()

            await GuildModCaseManager(bot, guild, session).delete_case("testcase")  # type: ignore[arg-type]

        session.delete.assert_called_once_with(case)

    async def test_delete_raises_when_case_not_found(self, bot: discord.Client) -> None:
        """Deleting a non-existent case raises CaseNotFoundException."""
        cfg = dpytest.get_config()
        guild = cfg.guilds[0]

        session = _make_session()  # no cases

        with pytest.raises(CaseNotFoundException):
            await GuildModCaseManager(bot, guild, session).delete_case("missing")  # type: ignore[arg-type]

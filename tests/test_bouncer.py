"""
Tests for cogs/bouncer/bouncer.py

Covers the member-analysis logic inside BouncerMonitorCog.handle_event:
  - USERNAME criteria (trigger / no-trigger / case-insensitive / whole-word guard)
  - AGE criteria (triggers on JOIN / skipped on UPDATE events)
  - AVATAR criteria (no avatar triggers / avatar present does not trigger)
  - Rule filters (disabled rule / evaluate_for_existing_members guard on UPDATE)
  - Bouncer guards (guild not configured / bouncer disabled / moderation disabled /
    administrator is immune)

Strategy
--------
* ``BouncerMonitorCog`` is registered on a minimal dpytest Bot so real
  ``discord.Member`` objects (which pass the ``isinstance`` guard) are available.
* ``handle_event`` is called directly rather than via dpytest event simulation.
* External I/O is suppressed with ``unittest.mock.patch``:
  - ``get_session``          (SQLAlchemy session factory)
  - ``case_managers``        (whole module reference, avoids real DB / DM calls)
  - ``GuildLogger``          (log-channel writer)
  - ``log_error``            (error reporter)
* Trigger vs. no-trigger is verified via the
  ``GuildLogger.return_value.titanium_bouncer_trigger`` call count — the single
  most reliable observable side-effect of handle_event firing a rule.
"""

from __future__ import annotations

import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import discord
import discord.ext.commands as commands
import discord.ext.test as dpytest
import pytest_asyncio
from discord.client import _LoopSentinel

from cogs.bouncer.bouncer import BouncerMonitorCog
from lib.enums.bouncer import BouncerActionType, BouncerCriteriaType, BouncerEventType
from lib.sql.sql import BouncerAction, BouncerCriteria, BouncerRule


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_session_patch() -> MagicMock:
    """Return a mock that can replace ``get_session`` in the bouncer module."""
    session = AsyncMock()
    session.add = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    return MagicMock(return_value=ctx)


def _make_warn_action(rule_id: uuid.UUID) -> BouncerAction:
    """Return a WARN BouncerAction (easiest to verify without real Discord API)."""
    action = BouncerAction(
        rule_id=rule_id,
        action_type=BouncerActionType.WARN,
        duration=None,
        role_id=None,
        reason="Test warn",
    )
    action.id = 1
    return action


def _make_username_criteria(
    rule_id: uuid.UUID,
    words: list[str],
    *,
    whole_word: bool = False,
    case_sensitive: bool = False,
) -> BouncerCriteria:
    criteria = BouncerCriteria(
        rule_id=rule_id,
        criteria_type=BouncerCriteriaType.USERNAME,
        account_age=None,
        words=words,
        match_whole_word=whole_word,
        case_sensitive=case_sensitive,
    )
    criteria.id = 1
    return criteria


def _make_age_criteria(rule_id: uuid.UUID, account_age: int) -> BouncerCriteria:
    """Criteria that fires when ``(utcnow - created_at).seconds <= account_age``."""
    criteria = BouncerCriteria(
        rule_id=rule_id,
        criteria_type=BouncerCriteriaType.AGE,
        account_age=account_age,
        words=[],
        match_whole_word=False,
        case_sensitive=False,
    )
    criteria.id = 2
    return criteria


def _make_avatar_criteria(rule_id: uuid.UUID) -> BouncerCriteria:
    """Criteria that fires when the member has no avatar."""
    criteria = BouncerCriteria(
        rule_id=rule_id,
        criteria_type=BouncerCriteriaType.AVATAR,
        account_age=None,
        words=[],
        match_whole_word=False,
        case_sensitive=False,
    )
    criteria.id = 3
    return criteria


def _make_rule(
    guild_id: int,
    criteria: list[BouncerCriteria],
    actions: list[BouncerAction],
    *,
    enabled: bool = True,
    evaluate_for_existing_members: bool = True,
) -> BouncerRule:
    """Build an in-memory BouncerRule with the supplied criteria and actions."""
    rule_id = uuid.uuid4()
    rule = BouncerRule(
        guild_id=guild_id,
        rule_name="test-rule",
        enabled=enabled,
        evaluate_for_existing_members=evaluate_for_existing_members,
    )
    rule.id = rule_id
    # Fix up back-references so criteria.rule_id matches
    for c in criteria:
        c.rule_id = rule_id
    for a in actions:
        a.rule_id = rule_id
    rule.criteria = criteria
    rule.actions = actions
    return rule


def _make_config(
    guild_id: int,
    rules: list[BouncerRule],
    *,
    bouncer_enabled: bool = True,
    moderation_enabled: bool = True,
) -> MagicMock:
    """Build a minimal mock GuildSettings with bouncer configuration."""
    config = MagicMock()
    config.guild_id = guild_id
    config.bouncer_enabled = bouncer_enabled
    config.moderation_enabled = moderation_enabled
    config.bouncer_settings = MagicMock()
    config.bouncer_settings.rules = rules
    config.moderation_settings = MagicMock()
    config.moderation_settings.ban_days = 0
    return config


def _make_case_managers_patch() -> MagicMock:
    """Return a mock that can replace ``case_managers`` in the bouncer module.

    The mock manager's ``create_case`` returns a (case, dm_success, dm_error)
    triple so callers that unpack the return value don't crash.
    """
    mock_manager = AsyncMock()
    mock_manager.create_case = AsyncMock(return_value=(MagicMock(), True, None))

    mock_cm = MagicMock()
    mock_cm.GuildModCaseManager.return_value = mock_manager

    return mock_cm


# ── Shared patch targets ────────────────────────────────────────────────────────

_GET_SESSION = "cogs.bouncer.bouncer.get_session"
_GUILD_LOGGER = "cogs.bouncer.bouncer.GuildLogger"
_LOG_ERROR = "cogs.bouncer.bouncer.log_error"
_CASE_MANAGERS = "cogs.bouncer.bouncer.case_managers"


# ── Fixtures ────────────────────────────────────────────────────────────────────


class _BouncerTestBot(commands.Bot):
    """Minimal bot subclass matching the attributes BouncerMonitorCog reads."""

    error_emoji = "❌"
    success_emoji = "✅"
    warn_emoji = "⚠️"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.guild_configs: dict = {}
        self.automod_messages: dict = {}
        self.malicious_links: list[str] = []
        self.phishing_links: list[str] = []

    async def setup_hook(self) -> None:
        pass

    async def fetch_guild_config(self, guild_id: int) -> MagicMock | None:  # type: ignore[override]
        return self.guild_configs.get(guild_id)


@pytest_asyncio.fixture
async def bouncer_bot() -> AsyncGenerator[_BouncerTestBot, None]:
    """Bot with BouncerMonitorCog loaded, using dpytest with two members."""
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    b = _BouncerTestBot(command_prefix="!", intents=intents)

    if isinstance(b.loop, _LoopSentinel):
        await b._async_setup_hook()

    dpytest.configure(b, members=["Alice", "Bob"])

    cog = BouncerMonitorCog(b)
    # Suppress importlib.reload so it does not invalidate class identities
    # (e.g. CaseNotFoundException) used by other test modules.
    with patch("cogs.bouncer.bouncer.importlib"):
        await b.add_cog(cog)

    yield b


# ── Bouncer Guards ─────────────────────────────────────────────────────────────


class TestBouncerGuards:
    """Tests that handle_event exits early under expected conditions."""

    async def test_guild_not_in_configs_is_skipped(
        self, bouncer_bot: _BouncerTestBot
    ) -> None:
        """Members from guilds absent from bot.guild_configs must be silently ignored."""
        cfg = dpytest.get_config()
        member = cfg.members[0]
        cog: BouncerMonitorCog = bouncer_bot.get_cog("BouncerMonitorCog")  # type: ignore[assignment]

        # Deliberately leave guild_configs empty
        with (
            patch(_GET_SESSION, _make_session_patch()),
            patch(_GUILD_LOGGER) as mock_logger,
            patch(_LOG_ERROR, new_callable=AsyncMock),
        ):
            mock_logger.return_value.titanium_bouncer_trigger = AsyncMock()
            await cog.handle_event(member, BouncerEventType.JOIN)

        mock_logger.return_value.titanium_bouncer_trigger.assert_not_awaited()

    async def test_bouncer_disabled_is_skipped(self, bouncer_bot: _BouncerTestBot) -> None:
        """When bouncer_enabled=False the cog must not apply any rules."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id
        member = cfg.members[0]
        cog: BouncerMonitorCog = bouncer_bot.get_cog("BouncerMonitorCog")  # type: ignore[assignment]

        rule = _make_rule(
            guild_id,
            [_make_username_criteria(uuid.uuid4(), ["alice"])],
            [_make_warn_action(uuid.uuid4())],
        )
        bouncer_bot.guild_configs[guild_id] = _make_config(
            guild_id, [rule], bouncer_enabled=False
        )

        with (
            patch(_GET_SESSION, _make_session_patch()),
            patch(_GUILD_LOGGER) as mock_logger,
            patch(_LOG_ERROR, new_callable=AsyncMock),
        ):
            mock_logger.return_value.titanium_bouncer_trigger = AsyncMock()
            await cog.handle_event(member, BouncerEventType.JOIN)

        mock_logger.return_value.titanium_bouncer_trigger.assert_not_awaited()

    async def test_moderation_disabled_is_skipped(self, bouncer_bot: _BouncerTestBot) -> None:
        """When moderation_enabled=False the cog must not apply any rules."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id
        member = cfg.members[0]
        cog: BouncerMonitorCog = bouncer_bot.get_cog("BouncerMonitorCog")  # type: ignore[assignment]

        rule = _make_rule(
            guild_id,
            [_make_username_criteria(uuid.uuid4(), ["alice"])],
            [_make_warn_action(uuid.uuid4())],
        )
        bouncer_bot.guild_configs[guild_id] = _make_config(
            guild_id, [rule], moderation_enabled=False
        )

        with (
            patch(_GET_SESSION, _make_session_patch()),
            patch(_GUILD_LOGGER) as mock_logger,
            patch(_LOG_ERROR, new_callable=AsyncMock),
        ):
            mock_logger.return_value.titanium_bouncer_trigger = AsyncMock()
            await cog.handle_event(member, BouncerEventType.JOIN)

        mock_logger.return_value.titanium_bouncer_trigger.assert_not_awaited()

    async def test_administrator_member_is_immune(self, bouncer_bot: _BouncerTestBot) -> None:
        """Members with the administrator permission must not be processed by bouncer."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id
        member = cfg.members[0]
        cog: BouncerMonitorCog = bouncer_bot.get_cog("BouncerMonitorCog")  # type: ignore[assignment]

        rule = _make_rule(
            guild_id,
            [_make_username_criteria(uuid.uuid4(), ["alice"])],
            [_make_warn_action(uuid.uuid4())],
        )
        bouncer_bot.guild_configs[guild_id] = _make_config(guild_id, [rule])

        admin_perms = discord.Permissions(administrator=True)
        with (
            patch(_GET_SESSION, _make_session_patch()),
            patch(_GUILD_LOGGER) as mock_logger,
            patch(_LOG_ERROR, new_callable=AsyncMock),
            patch.object(
                type(member), "guild_permissions", new_callable=PropertyMock, return_value=admin_perms
            ),
        ):
            mock_logger.return_value.titanium_bouncer_trigger = AsyncMock()
            await cog.handle_event(member, BouncerEventType.JOIN)

        mock_logger.return_value.titanium_bouncer_trigger.assert_not_awaited()

    async def test_disabled_rule_is_skipped(self, bouncer_bot: _BouncerTestBot) -> None:
        """A rule with enabled=False must never trigger regardless of criteria."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id
        member = cfg.members[0]
        cog: BouncerMonitorCog = bouncer_bot.get_cog("BouncerMonitorCog")  # type: ignore[assignment]

        # Rule matches "alice" in the username, but is disabled
        rule = _make_rule(
            guild_id,
            [_make_username_criteria(uuid.uuid4(), ["alice"])],
            [_make_warn_action(uuid.uuid4())],
            enabled=False,
        )
        bouncer_bot.guild_configs[guild_id] = _make_config(guild_id, [rule])

        with (
            patch(_GET_SESSION, _make_session_patch()),
            patch(_GUILD_LOGGER) as mock_logger,
            patch(_LOG_ERROR, new_callable=AsyncMock),
        ):
            mock_logger.return_value.titanium_bouncer_trigger = AsyncMock()
            await cog.handle_event(member, BouncerEventType.JOIN)

        mock_logger.return_value.titanium_bouncer_trigger.assert_not_awaited()

    async def test_evaluate_for_existing_members_false_skips_update(
        self, bouncer_bot: _BouncerTestBot
    ) -> None:
        """A rule with evaluate_for_existing_members=False must be skipped for UPDATE events."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id
        member = cfg.members[0]
        cog: BouncerMonitorCog = bouncer_bot.get_cog("BouncerMonitorCog")  # type: ignore[assignment]

        rule = _make_rule(
            guild_id,
            [_make_username_criteria(uuid.uuid4(), ["alice"])],
            [_make_warn_action(uuid.uuid4())],
            evaluate_for_existing_members=False,
        )
        bouncer_bot.guild_configs[guild_id] = _make_config(guild_id, [rule])

        with (
            patch(_GET_SESSION, _make_session_patch()),
            patch(_GUILD_LOGGER) as mock_logger,
            patch(_LOG_ERROR, new_callable=AsyncMock),
            patch(_CASE_MANAGERS, _make_case_managers_patch()),
        ):
            mock_logger.return_value.titanium_bouncer_trigger = AsyncMock()
            await cog.handle_event(member, BouncerEventType.UPDATE)

        mock_logger.return_value.titanium_bouncer_trigger.assert_not_awaited()


# ── Username Criteria ──────────────────────────────────────────────────────────


class TestUsernameDetection:
    """Tests for BouncerCriteriaType.USERNAME in handle_event."""

    async def test_blocked_username_triggers_action(
        self, bouncer_bot: _BouncerTestBot
    ) -> None:
        """A member whose name contains a blocked word fires the configured action."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id
        # dpytest creates the first member with name "Alice"
        member = cfg.members[0]
        cog: BouncerMonitorCog = bouncer_bot.get_cog("BouncerMonitorCog")  # type: ignore[assignment]

        rule_id = uuid.uuid4()
        rule = _make_rule(
            guild_id,
            [_make_username_criteria(rule_id, ["alice"])],
            [_make_warn_action(rule_id)],
        )
        bouncer_bot.guild_configs[guild_id] = _make_config(guild_id, [rule])

        with (
            patch(_GET_SESSION, _make_session_patch()),
            patch(_GUILD_LOGGER) as mock_logger,
            patch(_LOG_ERROR, new_callable=AsyncMock),
            patch(_CASE_MANAGERS, _make_case_managers_patch()),
        ):
            mock_logger.return_value.titanium_bouncer_trigger = AsyncMock()
            await cog.handle_event(member, BouncerEventType.JOIN)

        mock_logger.return_value.titanium_bouncer_trigger.assert_awaited_once()

    async def test_clean_username_does_not_trigger(
        self, bouncer_bot: _BouncerTestBot
    ) -> None:
        """A member whose name does not match the blocked word produces no action."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id
        member = cfg.members[0]  # name = "Alice"
        cog: BouncerMonitorCog = bouncer_bot.get_cog("BouncerMonitorCog")  # type: ignore[assignment]

        rule_id = uuid.uuid4()
        # "blocked" does not appear anywhere in "Alice"
        rule = _make_rule(
            guild_id,
            [_make_username_criteria(rule_id, ["blocked"])],
            [_make_warn_action(rule_id)],
        )
        bouncer_bot.guild_configs[guild_id] = _make_config(guild_id, [rule])

        with (
            patch(_GET_SESSION, _make_session_patch()),
            patch(_GUILD_LOGGER) as mock_logger,
            patch(_LOG_ERROR, new_callable=AsyncMock),
        ):
            mock_logger.return_value.titanium_bouncer_trigger = AsyncMock()
            await cog.handle_event(member, BouncerEventType.JOIN)

        mock_logger.return_value.titanium_bouncer_trigger.assert_not_awaited()

    async def test_username_match_is_case_insensitive_by_default(
        self, bouncer_bot: _BouncerTestBot
    ) -> None:
        """Username matching is case-insensitive when case_sensitive=False (the default)."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id
        member = cfg.members[0]  # name = "Alice"
        cog: BouncerMonitorCog = bouncer_bot.get_cog("BouncerMonitorCog")  # type: ignore[assignment]

        rule_id = uuid.uuid4()
        # Rule word is uppercase; member name is title-case → still matches
        rule = _make_rule(
            guild_id,
            [_make_username_criteria(rule_id, ["ALICE"], case_sensitive=False)],
            [_make_warn_action(rule_id)],
        )
        bouncer_bot.guild_configs[guild_id] = _make_config(guild_id, [rule])

        with (
            patch(_GET_SESSION, _make_session_patch()),
            patch(_GUILD_LOGGER) as mock_logger,
            patch(_LOG_ERROR, new_callable=AsyncMock),
            patch(_CASE_MANAGERS, _make_case_managers_patch()),
        ):
            mock_logger.return_value.titanium_bouncer_trigger = AsyncMock()
            await cog.handle_event(member, BouncerEventType.JOIN)

        mock_logger.return_value.titanium_bouncer_trigger.assert_awaited_once()

    async def test_whole_word_match_ignores_substrings(
        self, bouncer_bot: _BouncerTestBot
    ) -> None:
        """With match_whole_word=True, a word that is a substring of the name must not trigger."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id
        member = cfg.members[0]  # name = "Alice"
        cog: BouncerMonitorCog = bouncer_bot.get_cog("BouncerMonitorCog")  # type: ignore[assignment]

        rule_id = uuid.uuid4()
        # "ali" is a substring of "alice" but not a whole word
        rule = _make_rule(
            guild_id,
            [_make_username_criteria(rule_id, ["ali"], whole_word=True)],
            [_make_warn_action(rule_id)],
        )
        bouncer_bot.guild_configs[guild_id] = _make_config(guild_id, [rule])

        with (
            patch(_GET_SESSION, _make_session_patch()),
            patch(_GUILD_LOGGER) as mock_logger,
            patch(_LOG_ERROR, new_callable=AsyncMock),
        ):
            mock_logger.return_value.titanium_bouncer_trigger = AsyncMock()
            await cog.handle_event(member, BouncerEventType.JOIN)

        mock_logger.return_value.titanium_bouncer_trigger.assert_not_awaited()


# ── Account Age Criteria ───────────────────────────────────────────────────────


class TestAccountAgeCriteria:
    """Tests for BouncerCriteriaType.AGE in handle_event."""

    async def test_new_account_triggers_age_rule_on_join(
        self, bouncer_bot: _BouncerTestBot
    ) -> None:
        """A freshly created account triggers the age rule on JOIN."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id
        member = cfg.members[0]
        cog: BouncerMonitorCog = bouncer_bot.get_cog("BouncerMonitorCog")  # type: ignore[assignment]

        rule_id = uuid.uuid4()
        # account_age = 86400 means the rule fires whenever the timedelta's
        # .seconds component is ≤ 86400.  Because .seconds is always 0–86399
        # this condition is always satisfied.
        rule = _make_rule(
            guild_id,
            [_make_age_criteria(rule_id, account_age=86400)],
            [_make_warn_action(rule_id)],
        )
        bouncer_bot.guild_configs[guild_id] = _make_config(guild_id, [rule])

        with (
            patch(_GET_SESSION, _make_session_patch()),
            patch(_GUILD_LOGGER) as mock_logger,
            patch(_LOG_ERROR, new_callable=AsyncMock),
            patch(_CASE_MANAGERS, _make_case_managers_patch()),
        ):
            mock_logger.return_value.titanium_bouncer_trigger = AsyncMock()
            await cog.handle_event(member, BouncerEventType.JOIN)

        mock_logger.return_value.titanium_bouncer_trigger.assert_awaited_once()

    async def test_age_rule_is_skipped_for_update_events(
        self, bouncer_bot: _BouncerTestBot
    ) -> None:
        """AGE criteria must not be evaluated for UPDATE events (join-only check)."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id
        member = cfg.members[0]
        cog: BouncerMonitorCog = bouncer_bot.get_cog("BouncerMonitorCog")  # type: ignore[assignment]

        rule_id = uuid.uuid4()
        rule = _make_rule(
            guild_id,
            [_make_age_criteria(rule_id, account_age=86400)],
            [_make_warn_action(rule_id)],
        )
        bouncer_bot.guild_configs[guild_id] = _make_config(guild_id, [rule])

        with (
            patch(_GET_SESSION, _make_session_patch()),
            patch(_GUILD_LOGGER) as mock_logger,
            patch(_LOG_ERROR, new_callable=AsyncMock),
        ):
            mock_logger.return_value.titanium_bouncer_trigger = AsyncMock()
            # UPDATE event → AGE check is skipped → no trigger
            await cog.handle_event(member, BouncerEventType.UPDATE)

        mock_logger.return_value.titanium_bouncer_trigger.assert_not_awaited()


# ── Avatar Criteria ────────────────────────────────────────────────────────────


class TestAvatarCriteria:
    """Tests for BouncerCriteriaType.AVATAR in handle_event."""

    async def test_no_avatar_triggers_rule(self, bouncer_bot: _BouncerTestBot) -> None:
        """A member without an avatar triggers the AVATAR rule.

        dpytest members have ``avatar = None`` by default, so no patching is
        needed for this case.
        """
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id
        member = cfg.members[0]
        assert member.avatar is None, "dpytest member unexpectedly has an avatar"

        cog: BouncerMonitorCog = bouncer_bot.get_cog("BouncerMonitorCog")  # type: ignore[assignment]

        rule_id = uuid.uuid4()
        rule = _make_rule(
            guild_id,
            [_make_avatar_criteria(rule_id)],
            [_make_warn_action(rule_id)],
        )
        bouncer_bot.guild_configs[guild_id] = _make_config(guild_id, [rule])

        with (
            patch(_GET_SESSION, _make_session_patch()),
            patch(_GUILD_LOGGER) as mock_logger,
            patch(_LOG_ERROR, new_callable=AsyncMock),
            patch(_CASE_MANAGERS, _make_case_managers_patch()),
        ):
            mock_logger.return_value.titanium_bouncer_trigger = AsyncMock()
            await cog.handle_event(member, BouncerEventType.JOIN)

        mock_logger.return_value.titanium_bouncer_trigger.assert_awaited_once()

    async def test_member_with_avatar_does_not_trigger(
        self, bouncer_bot: _BouncerTestBot
    ) -> None:
        """A member who has an avatar must not trigger the AVATAR rule."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id
        member = cfg.members[0]
        cog: BouncerMonitorCog = bouncer_bot.get_cog("BouncerMonitorCog")  # type: ignore[assignment]

        rule_id = uuid.uuid4()
        rule = _make_rule(
            guild_id,
            [_make_avatar_criteria(rule_id)],
            [_make_warn_action(rule_id)],
        )
        bouncer_bot.guild_configs[guild_id] = _make_config(guild_id, [rule])

        fake_avatar = MagicMock()
        with (
            patch(_GET_SESSION, _make_session_patch()),
            patch(_GUILD_LOGGER) as mock_logger,
            patch(_LOG_ERROR, new_callable=AsyncMock),
            # Temporarily give the member a non-None avatar
            patch.object(type(member), "avatar", new_callable=PropertyMock, return_value=fake_avatar),
        ):
            mock_logger.return_value.titanium_bouncer_trigger = AsyncMock()
            await cog.handle_event(member, BouncerEventType.JOIN)

        mock_logger.return_value.titanium_bouncer_trigger.assert_not_awaited()

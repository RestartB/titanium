"""
Tests for cogs/moderation/automod.py

Covers the message-analysis logic inside AutomodMonitorCog.handle_message:
  - Bad word detection (trigger / no-trigger / case-insensitive / whole-word guard)
  - Spam detection by message count (trigger at threshold / quiet below it /
    old messages excluded from the look-back window)
  - Automod guards (guild not configured, automod or moderation disabled)
  - Malicious-link detection

Strategy
--------
* ``AutomodMonitorCog`` is loaded into a real ``commands.Bot`` via dpytest, so
  the full ``on_message`` → ``handle_message`` event path is exercised.
* External I/O is suppressed with ``unittest.mock.patch``:
  - ``get_session`` (the SQLAlchemy session factory)
  - ``GuildLogger`` (log-channel writer)
  - ``log_error`` (error reporter)
* When an action fires the cog calls ``message.channel.send()``, which dpytest
  captures in its sent-message queue.  This makes trigger/no-trigger assertions
  clean and reliable.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import discord.ext.commands as commands
import discord.ext.test as dpytest
import pytest
import pytest_asyncio
from discord.client import _LoopSentinel

from cogs.moderation.automod import AutomodMonitorCog
from lib.enums.automod import AutomodActionType, AutomodAntispamType, AutomodRuleType
from lib.sql.sql import AutomodAction, AutomodRule


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_session_patch() -> MagicMock:
    """Return a mock that can replace ``get_session`` in the automod module.

    ``get_session()`` is an ``@asynccontextmanager``, so calling it must
    return an async context manager that yields a session.
    """
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


def _make_send_message_action(
    guild_id: int,
    rule_id: uuid.UUID,
    content: str = "Automod triggered.",
) -> AutomodAction:
    """SEND_MESSAGE action — easiest to verify because dpytest captures channel.send()."""
    action = AutomodAction(
        guild_id=guild_id,
        rule_id=rule_id,
        rule_type=AutomodRuleType.BADWORD_DETECTION,
        action_type=AutomodActionType.SEND_MESSAGE,
        message_content=content,
        message_reply=False,
        message_mention=False,
        message_embed=False,
        embed_colour=None,
        duration=None,
        reason=None,
        role_id=None,
    )
    action.id = 1
    return action


def _make_badword_rule(
    guild_id: int,
    words: list[str],
    *,
    threshold: int = 1,
    duration: int = 60,
    whole_word: bool = False,
    case_sensitive: bool = False,
    actions: list[AutomodAction] | None = None,
) -> AutomodRule:
    """Construct an in-memory BADWORD_DETECTION AutomodRule."""
    rule_id = uuid.uuid4()
    rule = AutomodRule(
        guild_id=guild_id,
        rule_type=AutomodRuleType.BADWORD_DETECTION,
        antispam_type=None,
        rule_name="test-badword-rule",
        words=words,
        match_whole_word=whole_word,
        case_sensitive=case_sensitive,
        threshold=threshold,
        duration=duration,
    )
    rule.id = rule_id
    rule.actions = actions or []
    return rule


def _make_spam_rule(
    guild_id: int,
    antispam_type: AutomodAntispamType,
    threshold: int,
    duration: int = 60,
    actions: list[AutomodAction] | None = None,
) -> AutomodRule:
    """Construct an in-memory SPAM_DETECTION AutomodRule."""
    rule_id = uuid.uuid4()
    rule = AutomodRule(
        guild_id=guild_id,
        rule_type=AutomodRuleType.SPAM_DETECTION,
        antispam_type=antispam_type,
        rule_name="test-spam-rule",
        words=[],
        match_whole_word=False,
        case_sensitive=False,
        threshold=threshold,
        duration=duration,
    )
    rule.id = rule_id
    rule.actions = actions or []
    return rule


def _make_config(
    guild_id: int,
    *,
    badword_rules: list[AutomodRule] | None = None,
    spam_rules: list[AutomodRule] | None = None,
    malicious_link_rules: list[AutomodRule] | None = None,
    phishing_link_rules: list[AutomodRule] | None = None,
    automod_enabled: bool = True,
    moderation_enabled: bool = True,
) -> MagicMock:
    """Build a minimal mock GuildSettings with automod configuration."""
    config = MagicMock()
    config.guild_id = guild_id
    config.automod_enabled = automod_enabled
    config.moderation_enabled = moderation_enabled
    config.automod_settings = MagicMock()
    config.automod_settings.badword_detection_rules = badword_rules or []
    config.automod_settings.spam_detection_rules = spam_rules or []
    config.automod_settings.malicious_link_rules = malicious_link_rules or []
    config.automod_settings.phishing_link_rules = phishing_link_rules or []
    config.moderation_settings = MagicMock()
    config.moderation_settings.ban_days = 0
    return config


# ── Fixtures ───────────────────────────────────────────────────────────────────


class _AutomodTestBot(commands.Bot):
    """Minimal bot subclass that matches the attributes AutomodMonitorCog reads
    from ``self.bot`` at runtime (mirrors ``TitaniumBot``)."""

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
async def automod_bot() -> AsyncGenerator[_AutomodTestBot, None]:
    """Bot with AutomodMonitorCog loaded, using dpytest with two members."""
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    b = _AutomodTestBot(command_prefix="!", intents=intents)

    if isinstance(b.loop, _LoopSentinel):
        await b._async_setup_hook()

    dpytest.configure(b, members=["Alice", "Bob"])

    cog = AutomodMonitorCog(b)
    # cog_load calls importlib.reload on several modules, which creates new class
    # objects and breaks other test modules that hold references to the originals.
    # Suppress the reloads while still registering the cog's event listeners.
    with patch("cogs.moderation.automod.importlib"):
        await b.add_cog(cog)

    yield b


# ── Shared patch stack for tests that expect punishments to fire ───────────────

_EXTERN_PATCHES = (
    "cogs.moderation.automod.GuildLogger",
    "cogs.moderation.automod.log_error",
    "lib.classes.case_manager.GuildLogger",
    "lib.classes.case_manager.send_dm",
)


# ── Bad Word Detection ─────────────────────────────────────────────────────────


class TestBadWordDetection:
    """Tests for badword_detection_rules in handle_message."""

    async def test_blocked_word_triggers_action(self, automod_bot: _AutomodTestBot) -> None:
        """A message containing a blocked word fires the configured action."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id

        rule = _make_badword_rule(guild_id, ["badword"])
        rule.actions = [_make_send_message_action(guild_id, rule.id)]

        automod_bot.guild_configs[guild_id] = _make_config(guild_id, badword_rules=[rule])

        with (
            patch("cogs.moderation.automod.get_session", _make_session_patch()),
            patch("cogs.moderation.automod.GuildLogger") as mock_logger,
            patch("cogs.moderation.automod.log_error", new_callable=AsyncMock),
        ):
            mock_logger.return_value.titanium_automod_trigger = AsyncMock()
            await dpytest.message("this contains badword in it")

        sent = dpytest.get_message()
        assert "Titanium Automod" in sent.content

    async def test_clean_message_does_not_trigger(self, automod_bot: _AutomodTestBot) -> None:
        """A message without any blocked word produces no automod response."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id

        rule = _make_badword_rule(guild_id, ["badword"])
        rule.actions = [_make_send_message_action(guild_id, rule.id)]

        automod_bot.guild_configs[guild_id] = _make_config(guild_id, badword_rules=[rule])

        with (
            patch("cogs.moderation.automod.get_session", _make_session_patch()),
            patch("cogs.moderation.automod.GuildLogger") as mock_logger,
            patch("cogs.moderation.automod.log_error", new_callable=AsyncMock),
        ):
            mock_logger.return_value.titanium_automod_trigger = AsyncMock()
            await dpytest.message("this is a perfectly normal message")

        assert dpytest.verify().message().nothing()

    async def test_blocked_word_is_case_insensitive_by_default(
        self, automod_bot: _AutomodTestBot
    ) -> None:
        """Bad word rules are case-insensitive by default (case_sensitive=False)."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id

        # rule word is lowercase; message uses uppercase
        rule = _make_badword_rule(guild_id, ["banned"], case_sensitive=False)
        rule.actions = [_make_send_message_action(guild_id, rule.id)]

        automod_bot.guild_configs[guild_id] = _make_config(guild_id, badword_rules=[rule])

        with (
            patch("cogs.moderation.automod.get_session", _make_session_patch()),
            patch("cogs.moderation.automod.GuildLogger") as mock_logger,
            patch("cogs.moderation.automod.log_error", new_callable=AsyncMock),
        ):
            mock_logger.return_value.titanium_automod_trigger = AsyncMock()
            await dpytest.message("BANNED from saying that")

        sent = dpytest.get_message()
        assert "Titanium Automod" in sent.content

    async def test_whole_word_match_ignores_substrings(
        self, automod_bot: _AutomodTestBot
    ) -> None:
        """With match_whole_word=True, a word embedded inside another word must not trigger."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id

        # "bad" appears inside "badminton" — should NOT trigger
        rule = _make_badword_rule(guild_id, ["bad"], whole_word=True)
        rule.actions = [_make_send_message_action(guild_id, rule.id)]

        automod_bot.guild_configs[guild_id] = _make_config(guild_id, badword_rules=[rule])

        with (
            patch("cogs.moderation.automod.get_session", _make_session_patch()),
            patch("cogs.moderation.automod.GuildLogger") as mock_logger,
            patch("cogs.moderation.automod.log_error", new_callable=AsyncMock),
        ):
            mock_logger.return_value.titanium_automod_trigger = AsyncMock()
            await dpytest.message("I love playing badminton")

        assert dpytest.verify().message().nothing()

    async def test_whole_word_match_triggers_on_isolated_word(
        self, automod_bot: _AutomodTestBot
    ) -> None:
        """With match_whole_word=True, the exact word as a standalone token still triggers."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id

        rule = _make_badword_rule(guild_id, ["bad"], whole_word=True)
        rule.actions = [_make_send_message_action(guild_id, rule.id)]

        automod_bot.guild_configs[guild_id] = _make_config(guild_id, badword_rules=[rule])

        with (
            patch("cogs.moderation.automod.get_session", _make_session_patch()),
            patch("cogs.moderation.automod.GuildLogger") as mock_logger,
            patch("cogs.moderation.automod.log_error", new_callable=AsyncMock),
        ):
            mock_logger.return_value.titanium_automod_trigger = AsyncMock()
            await dpytest.message("that is really bad behaviour")

        sent = dpytest.get_message()
        assert "Titanium Automod" in sent.content

    async def test_threshold_greater_than_one_requires_multiple_occurrences(
        self, automod_bot: _AutomodTestBot
    ) -> None:
        """A threshold of 2 means a single occurrence must NOT trigger the rule."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id

        rule = _make_badword_rule(guild_id, ["spam"], threshold=2)
        rule.actions = [_make_send_message_action(guild_id, rule.id)]

        automod_bot.guild_configs[guild_id] = _make_config(guild_id, badword_rules=[rule])

        with (
            patch("cogs.moderation.automod.get_session", _make_session_patch()),
            patch("cogs.moderation.automod.GuildLogger") as mock_logger,
            patch("cogs.moderation.automod.log_error", new_callable=AsyncMock),
        ):
            mock_logger.return_value.titanium_automod_trigger = AsyncMock()
            # Only one occurrence of "spam" — below threshold of 2
            await dpytest.message("this is spam")

        assert dpytest.verify().message().nothing()

    async def test_threshold_met_by_multiple_occurrences_in_one_message(
        self, automod_bot: _AutomodTestBot
    ) -> None:
        """A single message with the blocked word repeated enough times meets the threshold."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id

        rule = _make_badword_rule(guild_id, ["spam"], threshold=2)
        rule.actions = [_make_send_message_action(guild_id, rule.id)]

        automod_bot.guild_configs[guild_id] = _make_config(guild_id, badword_rules=[rule])

        with (
            patch("cogs.moderation.automod.get_session", _make_session_patch()),
            patch("cogs.moderation.automod.GuildLogger") as mock_logger,
            patch("cogs.moderation.automod.log_error", new_callable=AsyncMock),
        ):
            mock_logger.return_value.titanium_automod_trigger = AsyncMock()
            # "spam" appears twice — meets threshold of 2
            await dpytest.message("spam spam spam")

        sent = dpytest.get_message()
        assert "Titanium Automod" in sent.content


# ── Spam Detection ─────────────────────────────────────────────────────────────


class TestSpamDetection:
    """Tests for spam_detection_rules (MESSAGE count type) in handle_message."""

    async def test_message_count_at_threshold_triggers_rule(
        self, automod_bot: _AutomodTestBot
    ) -> None:
        """Sending exactly *threshold* messages in the time window fires the spam rule."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id

        threshold = 3
        rule = _make_spam_rule(
            guild_id, AutomodAntispamType.MESSAGE, threshold=threshold, duration=60
        )
        rule.actions = [_make_send_message_action(guild_id, rule.id, "Spam detected.")]

        automod_bot.guild_configs[guild_id] = _make_config(guild_id, spam_rules=[rule])

        with (
            patch("cogs.moderation.automod.get_session", _make_session_patch()),
            patch("cogs.moderation.automod.GuildLogger") as mock_logger,
            patch("cogs.moderation.automod.log_error", new_callable=AsyncMock),
        ):
            mock_logger.return_value.titanium_automod_trigger = AsyncMock()
            for _ in range(threshold):
                await dpytest.message("hello")

        # The third message should have triggered the rule
        sent = dpytest.get_message()
        assert "Titanium Automod" in sent.content

    async def test_message_count_below_threshold_does_not_trigger(
        self, automod_bot: _AutomodTestBot
    ) -> None:
        """Sending fewer messages than the threshold must not fire the spam rule."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id

        threshold = 3
        rule = _make_spam_rule(
            guild_id, AutomodAntispamType.MESSAGE, threshold=threshold, duration=60
        )
        rule.actions = [_make_send_message_action(guild_id, rule.id, "Spam detected.")]

        automod_bot.guild_configs[guild_id] = _make_config(guild_id, spam_rules=[rule])

        with (
            patch("cogs.moderation.automod.get_session", _make_session_patch()),
            patch("cogs.moderation.automod.GuildLogger") as mock_logger,
            patch("cogs.moderation.automod.log_error", new_callable=AsyncMock),
        ):
            mock_logger.return_value.titanium_automod_trigger = AsyncMock()
            # Send one fewer message than the threshold
            for _ in range(threshold - 1):
                await dpytest.message("hello")

        assert dpytest.verify().message().nothing()

    async def test_messages_outside_time_window_are_ignored(
        self, automod_bot: _AutomodTestBot
    ) -> None:
        """Messages older than the rule's duration window must not count towards the threshold."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id

        threshold = 3
        # Very short window: 1 second
        rule = _make_spam_rule(
            guild_id, AutomodAntispamType.MESSAGE, threshold=threshold, duration=1
        )
        rule.actions = [_make_send_message_action(guild_id, rule.id, "Spam detected.")]

        automod_bot.guild_configs[guild_id] = _make_config(guild_id, spam_rules=[rule])

        with (
            patch("cogs.moderation.automod.get_session", _make_session_patch()),
            patch("cogs.moderation.automod.GuildLogger") as mock_logger,
            patch("cogs.moderation.automod.log_error", new_callable=AsyncMock),
        ):
            mock_logger.return_value.titanium_automod_trigger = AsyncMock()
            # Manually pre-populate two "old" messages (timestamped 10 seconds ago)
            old_ts = datetime.now() - timedelta(seconds=10)
            from lib.classes.automod_message import AutomodMessage

            for i in range(2):
                automod_bot.automod_messages.setdefault(guild_id, {}).setdefault(
                    cfg.members[0].id, []
                ).append(
                    AutomodMessage(
                        user_id=cfg.members[0].id,
                        message_id=i,
                        channel_id=cfg.channels[0].id,
                        triggered_word_rule_amount={},
                        malicious_link_count=0,
                        phishing_link_count=0,
                        mention_count=0,
                        word_count=1,
                        newline_count=1,
                        link_count=0,
                        attachment_count=0,
                        emoji_count=0,
                        timestamp=old_ts,
                    )
                )

            # One fresh message: combined with the two old ones that should be outside the
            # 1-second window this must NOT reach the threshold of 3
            await dpytest.message("one fresh message")

        assert dpytest.verify().message().nothing()

    async def test_spam_rule_is_independent_per_user(
        self, automod_bot: _AutomodTestBot
    ) -> None:
        """Message counts are tracked per-user; one user's messages cannot trigger another's spam."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id

        threshold = 3
        rule = _make_spam_rule(
            guild_id, AutomodAntispamType.MESSAGE, threshold=threshold, duration=60
        )
        rule.actions = [_make_send_message_action(guild_id, rule.id, "Spam detected.")]

        automod_bot.guild_configs[guild_id] = _make_config(guild_id, spam_rules=[rule])

        alice, bob = cfg.members[0], cfg.members[1]

        with (
            patch("cogs.moderation.automod.get_session", _make_session_patch()),
            patch("cogs.moderation.automod.GuildLogger") as mock_logger,
            patch("cogs.moderation.automod.log_error", new_callable=AsyncMock),
        ):
            mock_logger.return_value.titanium_automod_trigger = AsyncMock()
            # Alice and Bob each send one message — neither alone reaches threshold 3
            await dpytest.message("hello from alice", member=alice)
            await dpytest.message("hello from bob", member=bob)

        assert dpytest.verify().message().nothing()


# ── Automod Guards ─────────────────────────────────────────────────────────────


class TestAutomodGuards:
    """Tests that handle_message exits early under expected conditions."""

    async def test_guild_not_in_configs_is_skipped(
        self, automod_bot: _AutomodTestBot
    ) -> None:
        """Messages from guilds absent from bot.guild_configs must be silently ignored."""
        # Deliberately do NOT populate guild_configs — the guild is "unknown"
        with (
            patch("cogs.moderation.automod.get_session", _make_session_patch()),
            patch("cogs.moderation.automod.GuildLogger"),
            patch("cogs.moderation.automod.log_error", new_callable=AsyncMock),
        ):
            await dpytest.message("a message from an unknown guild")

        assert dpytest.verify().message().nothing()

    async def test_automod_disabled_is_skipped(self, automod_bot: _AutomodTestBot) -> None:
        """When automod_enabled=False the cog must not apply any rules."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id

        rule = _make_badword_rule(guild_id, ["trigger"])
        rule.actions = [_make_send_message_action(guild_id, rule.id)]

        automod_bot.guild_configs[guild_id] = _make_config(
            guild_id, badword_rules=[rule], automod_enabled=False
        )

        with (
            patch("cogs.moderation.automod.get_session", _make_session_patch()),
            patch("cogs.moderation.automod.GuildLogger"),
            patch("cogs.moderation.automod.log_error", new_callable=AsyncMock),
        ):
            await dpytest.message("this contains trigger word")

        assert dpytest.verify().message().nothing()

    async def test_moderation_disabled_is_skipped(self, automod_bot: _AutomodTestBot) -> None:
        """When moderation_enabled=False the cog must not apply any rules."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id

        rule = _make_badword_rule(guild_id, ["trigger"])
        rule.actions = [_make_send_message_action(guild_id, rule.id)]

        automod_bot.guild_configs[guild_id] = _make_config(
            guild_id, badword_rules=[rule], moderation_enabled=False
        )

        with (
            patch("cogs.moderation.automod.get_session", _make_session_patch()),
            patch("cogs.moderation.automod.GuildLogger"),
            patch("cogs.moderation.automod.log_error", new_callable=AsyncMock),
        ):
            await dpytest.message("this contains trigger word")

        assert dpytest.verify().message().nothing()

    async def test_no_rules_configured_means_no_action(
        self, automod_bot: _AutomodTestBot
    ) -> None:
        """Automod enabled but with no rules configured must not send any messages."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id

        # Empty config: automod on, but zero rules
        automod_bot.guild_configs[guild_id] = _make_config(guild_id)

        with (
            patch("cogs.moderation.automod.get_session", _make_session_patch()),
            patch("cogs.moderation.automod.GuildLogger"),
            patch("cogs.moderation.automod.log_error", new_callable=AsyncMock),
        ):
            await dpytest.message("any message at all")

        assert dpytest.verify().message().nothing()


# ── Malicious Link Detection ───────────────────────────────────────────────────


class TestMaliciousLinkDetection:
    """Tests for malicious_link_rules in handle_message."""

    async def test_known_malicious_link_triggers_action(
        self, automod_bot: _AutomodTestBot
    ) -> None:
        """A message containing a URL on the bot's malicious-link list fires the configured action."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id

        automod_bot.malicious_links = ["evil.example.com"]

        rule_id = uuid.uuid4()
        mal_rule = AutomodRule(
            guild_id=guild_id,
            rule_type=AutomodRuleType.MALICIOUS_LINK,
            antispam_type=None,
            rule_name="malicious-link-rule",
            words=[],
            match_whole_word=False,
            case_sensitive=False,
            threshold=1,
            duration=60,
        )
        mal_rule.id = rule_id
        mal_rule.actions = [_make_send_message_action(guild_id, rule_id, "Malicious link!")]

        automod_bot.guild_configs[guild_id] = _make_config(
            guild_id, malicious_link_rules=[mal_rule]
        )

        with (
            patch("cogs.moderation.automod.get_session", _make_session_patch()),
            patch("cogs.moderation.automod.GuildLogger") as mock_logger,
            patch("cogs.moderation.automod.log_error", new_callable=AsyncMock),
        ):
            mock_logger.return_value.titanium_automod_trigger = AsyncMock()
            await dpytest.message("check out https://evil.example.com/page")

        sent = dpytest.get_message()
        assert "Titanium Automod" in sent.content

    async def test_unknown_link_does_not_trigger_malicious_rule(
        self, automod_bot: _AutomodTestBot
    ) -> None:
        """A URL not on the malicious list must not trigger the malicious-link rule."""
        cfg = dpytest.get_config()
        guild_id = cfg.guilds[0].id

        automod_bot.malicious_links = ["evil.example.com"]

        rule_id = uuid.uuid4()
        mal_rule = AutomodRule(
            guild_id=guild_id,
            rule_type=AutomodRuleType.MALICIOUS_LINK,
            antispam_type=None,
            rule_name="malicious-link-rule",
            words=[],
            match_whole_word=False,
            case_sensitive=False,
            threshold=1,
            duration=60,
        )
        mal_rule.id = rule_id
        mal_rule.actions = [_make_send_message_action(guild_id, rule_id, "Malicious link!")]

        automod_bot.guild_configs[guild_id] = _make_config(
            guild_id, malicious_link_rules=[mal_rule]
        )

        with (
            patch("cogs.moderation.automod.get_session", _make_session_patch()),
            patch("cogs.moderation.automod.GuildLogger"),
            patch("cogs.moderation.automod.log_error", new_callable=AsyncMock),
        ):
            await dpytest.message("visit https://safe.example.com instead")

        assert dpytest.verify().message().nothing()

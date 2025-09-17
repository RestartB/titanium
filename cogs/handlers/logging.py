import importlib
import logging
from typing import TYPE_CHECKING, Sequence

import discord
from discord.ext import commands

from lib.classes import guild_logger
from lib.classes.guild_logger import GuildLogger

if TYPE_CHECKING:
    from main import TitaniumBot


class EventLoggingCog(commands.Cog):
    """Monitors Discord events from servers and logs them"""

    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        importlib.reload(guild_logger)

    async def cog_unload(self) -> None:
        pass

    @commands.Cog.listener()
    async def on_automod_rule_create(self, rule: discord.AutoModRule) -> None:
        guild_logger = GuildLogger(self.bot, rule.guild)
        await guild_logger.automod_rule_create(rule)

    @commands.Cog.listener()
    async def on_automod_rule_update(self, rule: discord.AutoModRule) -> None:
        guild_logger = GuildLogger(self.bot, rule.guild)
        await guild_logger.automod_rule_update(rule)

    @commands.Cog.listener()
    async def on_automod_rule_delete(self, rule: discord.AutoModRule) -> None:
        guild_logger = GuildLogger(self.bot, rule.guild)
        await guild_logger.automod_rule_delete(rule)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        guild_logger = GuildLogger(self.bot, channel.guild)
        await guild_logger.channel_create(channel)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        guild_logger = GuildLogger(self.bot, channel.guild)
        await guild_logger.channel_delete(channel)

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel
    ) -> None:
        guild_logger = GuildLogger(self.bot, after.guild)
        await guild_logger.channel_update(before, after)

    @commands.Cog.listener()
    async def on_guild_update(
        self, before: discord.Guild, after: discord.Guild
    ) -> None:
        guild_logger = GuildLogger(self.bot, after)
        await guild_logger.guild_name_update(before, after)
        await guild_logger.guild_afk_channel_update(before, after)
        await guild_logger.guild_afk_timeout_update(before, after)
        await guild_logger.guild_icon_update(before, after)

    @commands.Cog.listener()
    async def on_guild_emojis_update(
        self,
        guild: discord.Guild,
        before: Sequence[discord.Emoji],
        after: Sequence[discord.Emoji],
    ) -> None:
        guild_logger = GuildLogger(self.bot, guild)
        await guild_logger.guild_emoji_create(before, after)
        await guild_logger.guild_emoji_delete(before, after)

    @commands.Cog.listener()
    async def on_guild_stickers_update(
        self,
        guild: discord.Guild,
        before: Sequence[discord.GuildSticker],
        after: Sequence[discord.GuildSticker],
    ) -> None:
        guild_logger = GuildLogger(self.bot, guild)
        await guild_logger.guild_sticker_create(before, after)
        await guild_logger.guild_sticker_delete(before, after)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite) -> None:
        if not invite.guild or not isinstance(
            invite.guild, (discord.Guild, discord.PartialInviteGuild)
        ):
            return

        guild_logger = GuildLogger(self.bot, invite.guild)
        await guild_logger.guild_invite_create(invite)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite) -> None:
        if not invite.guild or not isinstance(
            invite.guild, (discord.Guild, discord.PartialInviteGuild)
        ):
            return

        guild_logger = GuildLogger(self.bot, invite.guild)
        await guild_logger.guild_invite_delete(invite)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        guild_logger = GuildLogger(self.bot, member.guild)
        await guild_logger.member_join(member)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        guild_logger = GuildLogger(self.bot, member.guild)
        await guild_logger.member_leave(member)

    @commands.Cog.listener()
    async def on_member_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        guild_logger = GuildLogger(self.bot, after.guild)
        await guild_logger.member_nickname_update(before, after)
        await guild_logger.member_roles_update(before, after)
        await guild_logger.member_timeout(before, after)
        await guild_logger.member_untimeout(before, after)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, member: discord.Member) -> None:
        guild_logger = GuildLogger(self.bot, guild)
        await guild_logger.member_ban(member)

    @commands.Cog.listener()
    async def on_member_unban(
        self, guild: discord.Guild, member: discord.Member
    ) -> None:
        guild_logger = GuildLogger(self.bot, guild)
        await guild_logger.member_unban(member)

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry) -> None:
        if entry.action == discord.AuditLogAction.kick:
            guild_logger = GuildLogger(self.bot, entry.guild)
            await guild_logger.member_kick(entry)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent) -> None:
        if not payload.guild_id:
            return

        if "content" not in payload.data:
            logging.info("No content in payload data")
            return

        if (
            payload.cached_message
            and payload.cached_message.content == payload.data["content"]
        ):
            logging.info("Message content is the same as cached message")
            return

        logging.info(payload.data["content"])

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        guild_logger = GuildLogger(self.bot, guild)
        await guild_logger.message_edit(payload)

    @commands.Cog.listener()
    async def on_raw_message_delete(
        self, payload: discord.RawMessageDeleteEvent
    ) -> None:
        if not payload.guild_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        guild_logger = GuildLogger(self.bot, guild)
        await guild_logger.message_delete(payload)

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(
        self, payload: discord.RawBulkMessageDeleteEvent
    ) -> None:
        if not payload.guild_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        guild_logger = GuildLogger(self.bot, guild)
        await guild_logger.message_bulk_delete(payload)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild:
            return

        guild_logger = GuildLogger(self.bot, message.guild)
        await guild_logger.poll_create(message)
        await guild_logger.poll_delete(message)

    @commands.Cog.listener()
    async def on_reaction_clear(
        self, message: discord.Message, reactions: list[discord.Reaction]
    ) -> None:
        if not message.guild:
            return

        guild_logger = GuildLogger(self.bot, message.guild)
        await guild_logger.reaction_clear(message, reactions)

    @commands.Cog.listener()
    async def on_reaction_clear_emoji(self, reaction: discord.Reaction) -> None:
        if not reaction.message.guild:
            return

        guild_logger = GuildLogger(self.bot, reaction.message.guild)
        await guild_logger.reaction_clear_emoji(reaction)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        if not role.guild:
            return

        guild_logger = GuildLogger(self.bot, role.guild)
        await guild_logger.role_create(role)

    @commands.Cog.listener()
    async def on_guild_role_update(
        self, before: discord.Role, after: discord.Role
    ) -> None:
        if not before.guild:
            return

        guild_logger = GuildLogger(self.bot, before.guild)
        await guild_logger.role_update(before, after)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        if not role.guild:
            return

        guild_logger = GuildLogger(self.bot, role.guild)
        await guild_logger.role_delete(role)

    @commands.Cog.listener()
    async def on_scheduled_event_create(self, event: discord.ScheduledEvent) -> None:
        if not event.guild:
            return

        guild_logger = GuildLogger(self.bot, event.guild)
        await guild_logger.scheduled_event_create(event)

    @commands.Cog.listener()
    async def on_scheduled_event_update(
        self, before: discord.ScheduledEvent, after: discord.ScheduledEvent
    ) -> None:
        if not before.guild:
            return

        guild_logger = GuildLogger(self.bot, before.guild)
        await guild_logger.scheduled_event_update(before, after)

    @commands.Cog.listener()
    async def on_scheduled_event_delete(self, event: discord.ScheduledEvent) -> None:
        if not event.guild:
            return

        guild_logger = GuildLogger(self.bot, event.guild)
        await guild_logger.scheduled_event_delete(event)

    @commands.Cog.listener()
    async def on_soundboard_sound_create(self, sound: discord.SoundboardSound) -> None:
        if not sound.guild:
            return

        guild_logger = GuildLogger(self.bot, sound.guild)
        await guild_logger.soundboard_sound_create(sound)

    @commands.Cog.listener()
    async def on_soundboard_sound_update(
        self, before: discord.SoundboardSound, after: discord.SoundboardSound
    ) -> None:
        if not before.guild:
            return

        guild_logger = GuildLogger(self.bot, before.guild)
        await guild_logger.soundboard_sound_update(before, after)

    @commands.Cog.listener()
    async def on_soundboard_sound_delete(self, sound: discord.SoundboardSound) -> None:
        if not sound.guild:
            return

        guild_logger = GuildLogger(self.bot, sound.guild)
        await guild_logger.soundboard_sound_delete(sound)

    @commands.Cog.listener()
    async def on_stage_instance_create(self, stage: discord.StageInstance) -> None:
        if not stage.guild:
            return

        guild_logger = GuildLogger(self.bot, stage.guild)
        await guild_logger.stage_instance_create(stage)

    @commands.Cog.listener()
    async def on_stage_instance_update(
        self, before: discord.StageInstance, after: discord.StageInstance
    ) -> None:
        if not before.guild:
            return

        guild_logger = GuildLogger(self.bot, before.guild)
        await guild_logger.stage_instance_update(before, after)

    @commands.Cog.listener()
    async def on_stage_instance_delete(self, stage: discord.StageInstance) -> None:
        if not stage.guild:
            return

        guild_logger = GuildLogger(self.bot, stage.guild)
        await guild_logger.stage_instance_delete(stage)

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread) -> None:
        if not thread.guild:
            return

        guild_logger = GuildLogger(self.bot, thread.guild)
        await guild_logger.thread_create(thread)

    @commands.Cog.listener()
    async def on_thread_update(
        self, before: discord.Thread, after: discord.Thread
    ) -> None:
        if not before.guild:
            return

        guild_logger = GuildLogger(self.bot, before.guild)
        await guild_logger.thread_update(before, after)

    @commands.Cog.listener()
    async def on_thread_remove(self, thread: discord.Thread) -> None:
        if not thread.guild:
            return

        guild_logger = GuildLogger(self.bot, thread.guild)
        await guild_logger.thread_remove(thread)

    @commands.Cog.listener()
    async def on_raw_thread_delete(self, payload: discord.RawThreadDeleteEvent) -> None:
        if not payload.guild_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        guild_logger = GuildLogger(self.bot, guild)
        await guild_logger.thread_delete(payload)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if not member.guild:
            return

        guild_logger = GuildLogger(self.bot, member.guild)
        await guild_logger.voice_join(member, before, after)
        await guild_logger.voice_leave(member, before, after)
        await guild_logger.voice_move(member, before, after)
        await guild_logger.voice_mute(member, before, after)
        await guild_logger.voice_unmute(member, before, after)
        await guild_logger.voice_deafen(member, before, after)
        await guild_logger.voice_undeafen(member, before, after)


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(EventLoggingCog(bot))

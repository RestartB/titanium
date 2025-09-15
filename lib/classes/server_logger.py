import logging
from datetime import timedelta
from textwrap import shorten
from typing import TYPE_CHECKING, Any, Optional, Sequence

import discord
from humanize.time import naturaldelta

from lib.embeds.mod_actions import banned, kicked, muted, unbanned, unmuted, warned
from lib.sql import AutomodAction, AutomodRule, AvailableWebhook, ModCase, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class ServerLogger:
    """Server logging class, used to log Discord events to server webhooks"""

    def __init__(
        self, bot: "TitaniumBot", guild: discord.Guild | discord.PartialInviteGuild
    ):
        self.bot = bot
        self.guild = guild
        self.config = bot.server_configs.get(guild.id)

    def _exists_and_enabled(self, entry: str) -> bool:
        if (
            not self.config
            or not self.config.logging_enabled
            or not self.config.logging_settings
        ):
            return False

        field_value = getattr(self.config.logging_settings, entry, None)
        if not field_value:
            return False

        return True

    async def _find_webhook(self, channel_id: int) -> Optional[str]:
        if self.guild.id in self.bot.available_webhooks:
            for webhook in self.bot.available_webhooks[self.guild.id]:
                if webhook.channel_id == channel_id:
                    return webhook.webhook_url

        # Get channel
        if isinstance(self.guild, discord.PartialInviteGuild):
            self.guild = await self.bot.fetch_guild(self.guild.id)

        channel = self.guild.get_channel(channel_id)
        if channel is None or isinstance(channel, discord.CategoryChannel):
            return None
        try:
            # Create a webhook
            webhook = await channel.create_webhook(name="Managed by Titanium")

            async with get_session() as session:
                session.add(
                    AvailableWebhook(
                        guild_id=self.guild.id,
                        channel_id=channel.id,
                        webhook_url=webhook.url,
                    )
                )

            await self.bot.refresh_guild_config_cache(self.guild.id)
            return webhook.url
        except Exception as e:
            logging.error(f"Failed to create webhook: {e}")
            return None

    async def _send_to_webhook(
        self,
        url: Optional[str],
        embed: discord.Embed,
        view: discord.ui.View | None = None,
    ) -> None:
        if url is None:
            return

        try:
            webhook = discord.Webhook.from_url(url, client=self.bot)

            if view:
                result = await webhook.send(content="mepw", embed=embed, view=view)
            else:
                result = await webhook.send(content="mepw", embed=embed)
            return result
        except Exception as e:
            logging.error(f"Failed to send webhook: {e}")
            return None

    async def _get_audit_log_entry(
        self,
        action: discord.AuditLogAction,
        target: Optional[Any] = None,
    ) -> Optional[discord.AuditLogEntry]:
        # Get audit log
        if not isinstance(self.guild, discord.Guild):
            return None

        logs = self.guild.audit_logs(limit=1, action=action)

        async for entry in logs:
            if not target or (target and entry.target == target):
                return entry

        return None

    async def _add_user_footer(
        self, embed: discord.Embed, log: Optional[discord.AuditLogEntry]
    ) -> None:
        if log and log.user:
            embed.set_footer(
                text=f"@{log.user.name}", icon_url=log.user.display_avatar.url
            )

    async def app_command_perm_update(
        self, event: discord.RawAppCommandPermissionsUpdateEvent
    ) -> None:
        # FIXME - implement this log type
        pass

    async def automod_rule_create(self, rule: discord.AutoModRule) -> None:
        if not self._exists_and_enabled("dc_automod_rule_create_id"):
            return

        embed = discord.Embed(
            title="AutoMod Rule Created",
            description=f"**Rule Name:** `{rule.name}`\n**Rule ID:** `{rule.id}`",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )

        log = await self._get_audit_log_entry(
            discord.AuditLogAction.automod_rule_create
        )
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.dc_automod_rule_create_id
            ),
            embed,
        )

    async def automod_rule_delete(self, rule: discord.AutoModRule) -> None:
        if not self._exists_and_enabled("dc_automod_rule_delete_id"):
            return

        embed = discord.Embed(
            title="AutoMod Rule Deleted",
            description=f"**Rule Name:** `{rule.name}`\n**Rule ID:** `{rule.id}`",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )

        log = await self._get_audit_log_entry(
            discord.AuditLogAction.automod_rule_delete
        )
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.dc_automod_rule_delete_id
            ),
            embed,
        )

    async def automod_rule_update(self, rule: discord.AutoModRule) -> None:
        if not self._exists_and_enabled("dc_automod_rule_update_id"):
            return

        embed = discord.Embed(
            title="AutoMod Rule Edited",
            description=f"**Rule Name:** `{rule.name}`\n**Rule ID:** `{rule.id}`",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )

        log = await self._get_audit_log_entry(
            discord.AuditLogAction.automod_rule_update
        )
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.dc_automod_rule_update_id
            ),
            embed,
        )

    async def channel_create(self, channel: discord.abc.GuildChannel) -> None:
        if not self._exists_and_enabled("channel_create_id"):
            return

        embed = discord.Embed(
            title="Channel Created",
            description=f"**Channel Name:** `#{channel.name}` ({channel.mention})\n**Channel ID:** `{channel.id}`\n**Channel Type:** `{str(channel.type).split('.')[-1].title()}`",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )

        log = await self._get_audit_log_entry(discord.AuditLogAction.channel_create)
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.channel_create_id),
            embed,
        )

    async def channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        if not self._exists_and_enabled("channel_delete_id"):
            return

        embed = discord.Embed(
            title="Channel Deleted",
            description=f"**Channel Name:** `#{channel.name}`\n**Channel ID:** `{channel.id}`\n**Channel Type:** `{str(channel.type).split('.')[-1].title()}`",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )

        log = await self._get_audit_log_entry(discord.AuditLogAction.channel_delete)
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.channel_delete_id),
            embed,
        )

    async def channel_update(
        self,
        before: discord.abc.GuildChannel,
        after: discord.abc.GuildChannel,
    ) -> None:
        if not self._exists_and_enabled("channel_update_id"):
            return

        changes = []

        if before.name != after.name:
            changes.append(f"**Name:** `#{before.name}` ➔ `#{after.name}`")
        if before.position != after.position:
            changes.append(f"**Position:** `{before.position}` ➔ `{after.position}`")
        if len(before.overwrites) != len(after.overwrites):
            changes.append(
                f"**Permission Overwrites:** `{len(before.overwrites)} overwrites` ➔ `{len(after.overwrites)}` overwrites"
            )

        if not changes:
            return

        embed = discord.Embed(
            title="Channel Updated",
            description=f"**Channel Name:** `#{after.name}` ({after.mention})\n**Channel ID:** `{after.id}`\n\n"
            + "\n".join(changes),
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )

        log = await self._get_audit_log_entry(discord.AuditLogAction.channel_update)
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.channel_update_id),
            embed,
        )

    async def guild_name_update(
        self, before: discord.Guild, after: discord.Guild
    ) -> None:
        if not self._exists_and_enabled("guild_name_update_id"):
            return

        if before.name == after.name:
            return

        embed = discord.Embed(
            title="Guild Name Updated",
            description=f"**Old Name:** `{before.name}`\n**New Name:** `{after.name}`",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=after.icon.url if after.icon else None)

        log = await self._get_audit_log_entry(discord.AuditLogAction.guild_update)
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.guild_name_update_id),
            embed,
        )

    async def guild_afk_channel_update(
        self, before: discord.Guild, after: discord.Guild
    ) -> None:
        if not self._exists_and_enabled("guild_afk_channel_update_id"):
            return

        if before.afk_channel == after.afk_channel:
            return

        embed = discord.Embed(
            title="Guild AFK Channel Updated",
            description=f"**Old AFK Channel:** `{before.afk_channel.mention if before.afk_channel else 'None'}`\n**New AFK Channel:** `{after.afk_channel.mention if after.afk_channel else 'None'}`",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=after.icon.url if after.icon else None)

        log = await self._get_audit_log_entry(discord.AuditLogAction.guild_update)
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.guild_afk_channel_update_id
            ),
            embed,
        )

    async def guild_afk_timeout_update(
        self, before: discord.Guild, after: discord.Guild
    ) -> None:
        if not self._exists_and_enabled("guild_afk_timeout_update_id"):
            return

        if before.afk_timeout == after.afk_timeout:
            return

        embed = discord.Embed(
            title="Guild AFK Timeout Updated",
            description=f"**Old AFK Timeout:** `{before.afk_timeout} seconds`\n**New AFK Timeout:** `{after.afk_timeout} seconds`",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=after.icon.url if after.icon else None)

        log = await self._get_audit_log_entry(discord.AuditLogAction.guild_update)
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.guild_afk_timeout_update_id
            ),
            embed,
        )

    async def guild_icon_update(
        self, before: discord.Guild, after: discord.Guild
    ) -> None:
        if not self._exists_and_enabled("guild_icon_update_id"):
            return

        if before.icon == after.icon:
            return

        embed = discord.Embed(
            title="Guild Icon Updated",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=after.icon.url if after.icon else None)

        embed.description = (
            f"\n\n**Old Icon:** [Link]({before.icon.url})"
            if before.icon
            else "\n\n**Old Icon:** `None`"
        )
        embed.description += (
            f"\n**New Icon:** [Link]({after.icon.url})"
            if after.icon
            else "\n**New Icon:** `None`"
        )

        log = await self._get_audit_log_entry(discord.AuditLogAction.guild_update)
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.guild_icon_update_id),
            embed,
        )

    async def guild_emoji_create(
        self,
        before: Sequence[discord.Emoji],
        after: Sequence[discord.Emoji],
    ) -> None:
        if not self._exists_and_enabled("guild_emoji_create_id"):
            return

        before_ids = {e.id for e in before}
        added = [e for e in after if e.id not in before_ids]
        embeds = []

        for emoji in added:
            embed = discord.Embed(
                title="Emoji Added",
                description=f"**Name:** `{emoji.name}` (<:{emoji.id}:>)",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )
            embed.set_thumbnail(url=emoji.url if emoji.url else None)

            log = await self._get_audit_log_entry(discord.AuditLogAction.emoji_create)
            await self._add_user_footer(embed, log)

            embeds.append(embed)

        for embed in embeds:
            assert self.config is not None and self.config.logging_settings is not None
            await self._send_to_webhook(
                await self._find_webhook(
                    self.config.logging_settings.guild_emoji_create_id
                ),
                embed,
            )

    async def guild_emoji_delete(
        self,
        before: Sequence[discord.Emoji],
        after: Sequence[discord.Emoji],
    ) -> None:
        if not self._exists_and_enabled("guild_emoji_delete_id"):
            return

        after_ids = {e.id for e in after}
        removed = [e for e in before if e.id not in after_ids]
        embeds = []

        for emoji in removed:
            embed = discord.Embed(
                title="Emoji Removed",
                description=f"**Name:** `{emoji.name}`",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow(),
            )
            embed.set_thumbnail(url=emoji.url if emoji.url else None)

            log = await self._get_audit_log_entry(discord.AuditLogAction.emoji_delete)
            await self._add_user_footer(embed, log)

            embeds.append(embed)

        for embed in embeds:
            assert self.config is not None and self.config.logging_settings is not None
            await self._send_to_webhook(
                await self._find_webhook(
                    self.config.logging_settings.guild_emoji_delete_id
                ),
                embed,
            )

    async def guild_sticker_create(
        self,
        before: Sequence[discord.GuildSticker],
        after: Sequence[discord.GuildSticker],
    ) -> None:
        if not self._exists_and_enabled("guild_sticker_create_id"):
            return

        before_ids = {e.id for e in before}
        added = [e for e in after if e.id not in before_ids]
        embeds = []

        for sticker in added:
            embed = discord.Embed(
                title="Sticker Added",
                description=f"**Name:** `{sticker.name}`",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )
            embed.set_thumbnail(url=sticker.url if sticker.url else None)

            log = await self._get_audit_log_entry(discord.AuditLogAction.sticker_create)
            await self._add_user_footer(embed, log)

        for embed in embeds:
            assert self.config is not None and self.config.logging_settings is not None
            await self._send_to_webhook(
                await self._find_webhook(
                    self.config.logging_settings.guild_sticker_create_id
                ),
                embed,
            )

    async def guild_sticker_delete(
        self,
        before: Sequence[discord.GuildSticker],
        after: Sequence[discord.GuildSticker],
    ) -> None:
        if not self._exists_and_enabled("guild_sticker_delete_id"):
            return

        after_ids = {e.id for e in after}
        removed = [e for e in before if e.id not in after_ids]
        embeds = []

        for sticker in removed:
            embed = discord.Embed(
                title="Sticker Removed",
                description=f"**Name:** `{sticker.name}`",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow(),
            )
            embed.set_thumbnail(url=sticker.url if sticker.url else None)

            log = await self._get_audit_log_entry(discord.AuditLogAction.sticker_delete)
            await self._add_user_footer(embed, log)

        for embed in embeds:
            assert self.config is not None and self.config.logging_settings is not None
            await self._send_to_webhook(
                await self._find_webhook(
                    self.config.logging_settings.guild_sticker_delete_id
                ),
                embed,
            )

    async def guild_invite_create(self, invite: discord.Invite) -> None:
        if not self._exists_and_enabled("guild_invite_create_id"):
            return

        # Channel
        if invite.channel:
            if not isinstance(invite.channel, discord.Object):
                channel_display = f"{invite.channel.mention} (`#{invite.channel.name}`)"
            else:
                channel_display = f"<#{invite.channel.id}> (`{invite.channel.id}`)"
        else:
            channel_display = "`Unknown`"

        # Inviter name
        if invite.inviter:
            if not isinstance(invite.inviter, discord.Object):
                inviter_display = f"@{invite.inviter.name}"
            else:
                inviter_display = f"Inviter: {invite.inviter.id}"

        embed = discord.Embed(
            title="Invite Created",
            description=f"**Code:** `{invite.code}`\n"
            f"**Channel:** {channel_display}\n"
            f"**Max Uses:** `{invite.max_uses}`\n"
            f"**Temporary:** `{invite.temporary}`",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )

        if invite.inviter:
            embed.set_footer(
                text=inviter_display,
                icon_url=invite.inviter.display_avatar.url
                if not isinstance(invite.inviter, discord.Object)
                and invite.inviter.display_avatar
                else None,
            )

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.guild_invite_create_id
            ),
            embed,
        )

    async def guild_invite_delete(self, invite: discord.Invite) -> None:
        if not self._exists_and_enabled("guild_invite_delete_id"):
            return

        embed = discord.Embed(
            title="Invite Deleted",
            description=f"**Code:** `{invite.code}`",
            color=discord.Color.red(),
        )

        log = await self._get_audit_log_entry(discord.AuditLogAction.invite_delete)
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.guild_invite_delete_id
            ),
            embed,
        )

    async def member_join(self, member: discord.Member) -> None:
        if not self._exists_and_enabled("member_join_id"):
            return

        embed = discord.Embed(
            title="Member Joined",
            description=f"**User:** {member.mention} (`@{member.name}`)"
            f"**ID:** `{member.id}`"
            f"\n**Account Created:** <t:{int(member.created_at.timestamp())}:R>",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.member_join_id),
            embed,
        )

    async def member_leave(self, member: discord.Member) -> None:
        if not self._exists_and_enabled("member_leave_id"):
            return

        embed = discord.Embed(
            title="Member Left",
            description=f"**User:** {member.mention} (`@{member.name}`)"
            f"**ID:** `{member.id}`"
            f"\n**Account Created:** <t:{int(member.created_at.timestamp())}:R>",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.member_leave_id),
            embed,
        )

    async def member_nickname_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        if not self._exists_and_enabled("member_nickname_update_id"):
            return

        if before.nick == after.nick:
            return

        embed = discord.Embed(
            title="Member Nickname Updated",
            description=f"**User:** {after.mention} (`@{after.name}`)\n"
            f"**ID:** `{after.id}`\n\n"
            f"**Old Nickname:** `{before.nick}`\n"
            f"**New Nickname:** `{after.nick}`",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=after.display_avatar.url)

        log = await self._get_audit_log_entry(
            discord.AuditLogAction.member_update, target=after
        )
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.member_nickname_update_id
            ),
            embed,
        )

    async def member_roles_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        if not self._exists_and_enabled("member_roles_update_id"):
            return

        # Get updated roles
        before_ids = [e.id for e in before.roles]
        after_ids = [e.id for e in after.roles]

        added = [e for e in after.roles if e.id not in before_ids]
        removed = [e for e in before.roles if e.id not in after_ids]

        if not added and not removed:
            return

        embed = discord.Embed(
            title="Member Roles Updated",
            description=f"**User:** {after.mention} (`@{after.name}`)\n"
            f"**ID:** `{after.id}`",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=after.display_avatar.url)

        if added:
            embed.add_field(
                name="Roles Added",
                value=", ".join([e.mention for e in added]),
                inline=False,
            )

        if removed:
            embed.add_field(
                name="Roles Removed",
                value=", ".join([e.mention for e in removed]),
                inline=False,
            )

        log = await self._get_audit_log_entry(
            discord.AuditLogAction.member_update, target=after
        )
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.member_roles_update_id
            ),
            embed,
        )

    async def member_ban(self, member: discord.User | discord.Member) -> None:
        if not self._exists_and_enabled("member_ban_id"):
            return

        embed = discord.Embed(
            title="Member Banned",
            description=f"**User:** {member.mention} (`@{member.name}`)\n"
            f"**ID:** `{member.id}`\n"
            f"**Account Created:** <t:{int(member.created_at.timestamp())}:R>",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        log = await self._get_audit_log_entry(discord.AuditLogAction.ban, target=member)
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.member_ban_id),
            embed,
        )

    async def member_unban(self, member: discord.User | discord.Member) -> None:
        if not self._exists_and_enabled("member_unban_id"):
            return

        embed = discord.Embed(
            title="Member Unbanned",
            description=f"**User:** {member.mention} (`@{member.name}`)\n"
            f"**ID:** `{member.id}`\n"
            f"**Account Created:** <t:{int(member.created_at.timestamp())}:R>",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        log = await self._get_audit_log_entry(
            discord.AuditLogAction.unban, target=member
        )
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.member_unban_id),
            embed,
        )

    # We only get an audit log record for this
    async def member_kick(self, entry: discord.AuditLogEntry) -> None:
        if not self._exists_and_enabled("member_kick_id"):
            return

        if not entry.action == discord.AuditLogAction.kick:
            return

        if not isinstance(entry.target, discord.Member) and not isinstance(
            entry.target, discord.User
        ):
            return

        if isinstance(entry.target, discord.Object):
            entry.target = await self.bot.fetch_user(entry.target.id)

        embed = discord.Embed(
            title="Member Kicked",
            description=f"**User:** {entry.target.mention} (`@{entry.target.name}`)\n"
            f"**ID:** `{entry.target.id}`\n"
            f"**Reason:** {entry.reason}",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=entry.target.display_avatar.url)
        await self._add_user_footer(embed, entry)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.member_kick_id),
            embed,
        )

    async def member_timeout(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        if not self._exists_and_enabled("member_timeout_id"):
            return

        if before.timed_out_until == after.timed_out_until:
            return

        if after.timed_out_until is None:
            return

        # Timeout added or updated
        embed = discord.Embed(
            title="Member Timed Out",
            description=f"**User:** {after.mention} (`@{after.name}`)\n"
            f"**ID:** `{after.id}`\n"
            f"**Timeout Until:** <t:{int(after.timed_out_until.timestamp())}:R>",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=after.display_avatar.url)

        log = await self._get_audit_log_entry(
            discord.AuditLogAction.member_update, target=after
        )
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.member_timeout_id),
            embed,
        )

    async def member_untimeout(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        if not self._exists_and_enabled("member_untimeout_id"):
            return

        if before.timed_out_until == after.timed_out_until:
            return

        if after.timed_out_until is not None:
            return

        embed = discord.Embed(
            title="Member Timeout Removed",
            description=f"**User:** {after.mention} (`@{after.name}`)\n"
            f"**ID:** `{after.id}`",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=after.display_avatar.url)

        log = await self._get_audit_log_entry(
            discord.AuditLogAction.member_update, target=after
        )
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.member_untimeout_id),
            embed,
        )

    async def message_edit(self, event: discord.RawMessageUpdateEvent) -> None:
        if not self._exists_and_enabled("message_edit_id"):
            return

        embed = discord.Embed(
            title="Message Edited",
            description=f"**Message ID:** `{event.message_id}`\n"
            f"**Channel:** <#{event.channel_id}>\n"
            f"**Author:** {event.message.author.mention}\n",
        )

        if event.cached_message:
            embed.add_field(
                name="Old Content", value=event.cached_message.content, inline=False
            )
        embed.add_field(name="New Content", value=event.message.content, inline=False)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.message_edit_id),
            embed,
        )

    # FIXME: doesn't work
    async def message_delete(self, event: discord.RawMessageDeleteEvent) -> None:
        if not self._exists_and_enabled("message_delete_id"):
            return

        embed = discord.Embed(
            title="Message Deleted",
            description=f"**Message ID:** `{event.message_id}`\n"
            f"**Channel:** <#{event.channel_id}>",
        )

        if event.cached_message and embed.description:
            embed.description += f"\n**Author:** {event.cached_message.author.mention}"
            embed.add_field(
                name="Content", value=event.cached_message.content, inline=False
            )

        log = await self._get_audit_log_entry(
            discord.AuditLogAction.message_delete, target=event.cached_message
        )
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.message_delete_id),
            embed,
        )

    async def message_bulk_delete(
        self, event: discord.RawBulkMessageDeleteEvent
    ) -> None:
        if not self._exists_and_enabled("message_bulk_delete_id"):
            return

        embed = discord.Embed(
            title=f"{len(event.message_ids)} Messages Bulk Deleted",
            description=f"**Channel:** <#{event.channel_id}>\n",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )

        log = await self._get_audit_log_entry(
            discord.AuditLogAction.message_bulk_delete, target=event
        )
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.message_bulk_delete_id
            ),
            embed,
        )

    async def poll_create(self, message: discord.Message) -> None:
        if not self._exists_and_enabled("poll_create_id"):
            return

        if (
            isinstance(message.channel, discord.DMChannel)
            or isinstance(message.channel, discord.GroupChannel)
        ) or not message.poll:
            return

        embed = discord.Embed(
            title="Poll Created",
            description=f"**Message ID:** `{message.id}`\n"
            f"**Channel:** {message.channel.mention}\n"
            f"**Author:** {message.author.mention}\n"
            f"**Question:** {message.poll.question}",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=message.author.display_avatar.url)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.poll_create_id),
            embed,
        )

    async def poll_delete(self, message: discord.Message) -> None:
        if not self._exists_and_enabled("poll_delete_id"):
            return

        if (
            isinstance(message.channel, discord.DMChannel)
            or isinstance(message.channel, discord.GroupChannel)
        ) or not message.poll:
            return

        embed = discord.Embed(
            title="Poll Deleted",
            description=f"**Message ID:** `{message.id}`\n"
            f"**Channel:** {message.channel.mention}\n"
            f"**Author:** {message.author.mention}\n"
            f"**Question:** {message.poll.question}\n"
            f"**Total Votes:** `{message.poll.total_votes}`",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=message.author.display_avatar.url)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.poll_delete_id),
            embed,
        )

    async def reaction_clear(
        self, message: discord.Message, reactions: list[discord.Reaction]
    ) -> None:
        if not self._exists_and_enabled("reaction_clear_id"):
            return

        if isinstance(message.channel, discord.DMChannel) or isinstance(
            message.channel, discord.GroupChannel
        ):
            return

        embed = discord.Embed(
            title="Reactions Cleared",
            description=f"**Message ID:** `{message.id}`\n"
            f"**Channel:** {message.channel.mention}\n"
            f"**Author:** {message.author.mention}\n"
            f"**Total Unique Reactions:** `{len(reactions)}`",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=message.author.display_avatar.url)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.reaction_clear_id),
            embed,
        )

    async def reaction_clear_emoji(self, reaction: discord.Reaction) -> None:
        if not self._exists_and_enabled("reaction_clear_emoji_id"):
            return

        message = reaction.message

        if isinstance(message.channel, discord.DMChannel) or isinstance(
            message.channel, discord.GroupChannel
        ):
            return

        embed = discord.Embed(
            title="Reaction Cleared",
            description=f"**Message ID:** `{message.id}`\n"
            f"**Channel:** {message.channel.mention}\n"
            f"**Author:** {message.author.mention}\n"
            f"**Reaction:** {reaction.emoji} ({reaction.normal_count + reaction.burst_count} total)",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=message.author.display_avatar.url)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.reaction_clear_emoji_id
            ),
            embed,
        )

    async def role_create(self, role: discord.Role) -> None:
        if not self._exists_and_enabled("role_create_id"):
            return

        embed = discord.Embed(
            title="Role Created",
            description=f"**Role Name:** `{role.name}`\n"
            f"**Role ID:** `{role.id}`\n"
            f"**Color:** `#{role.color.value:06x}`\n"
            f"**Display Separately:** `{'Yes' if role.hoist else 'No'}`\n"
            f"**Mentionable:** `{'Yes' if role.mentionable else 'No'}`\n"
            f"**Position:** `{role.position}`",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )

        log = await self._get_audit_log_entry(discord.AuditLogAction.role_create)
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.role_create_id),
            embed,
        )

    async def role_delete(self, role: discord.Role) -> None:
        if not self._exists_and_enabled("role_delete_id"):
            return

        embed = discord.Embed(
            title="Role Deleted",
            description=f"**Role Name:** `{role.name}`\n"
            f"**Role ID:** `{role.id}`\n"
            f"**Color:** `#{role.color.value:06x}`\n"
            f"**Display Separately:** `{'Yes' if role.hoist else 'No'}`\n"
            f"**Mentionable:** `{'Yes' if role.mentionable else 'No'}`\n"
            f"**Position:** `{role.position}`",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )

        log = await self._get_audit_log_entry(discord.AuditLogAction.role_delete)
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.role_delete_id),
            embed,
        )

    async def role_update(self, before: discord.Role, after: discord.Role) -> None:
        if not self._exists_and_enabled("role_update_id"):
            return

        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` ➔ `{after.name}`")
        if before.color != after.color:
            changes.append(
                f"**Color:** `#{before.color.value:06x}` ➔ `#{after.color.value:06x}`"
            )
        if before.hoist != after.hoist:
            changes.append(
                f"**Display Separately:** `{'Yes' if before.hoist else 'No'}` ➔ `{'Yes' if after.hoist else 'No'}`"
            )
        if before.mentionable != after.mentionable:
            changes.append(
                f"**Mentionable:** `{'Yes' if before.mentionable else 'No'}` ➔ `{'Yes' if after.mentionable else 'No'}`"
            )
        if before.position != after.position:
            changes.append(f"**Position:** `{before.position}` ➔ `{after.position}`")

        if len(changes) == 0:
            return

        embed = discord.Embed(
            title="Role Updated",
            description="\n".join(changes),
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )

        log = await self._get_audit_log_entry(discord.AuditLogAction.role_update)
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.role_update_id),
            embed,
        )

    async def scheduled_event_create(self, event: discord.ScheduledEvent):
        if not self._exists_and_enabled("scheduled_event_create_id"):
            return

        embed = discord.Embed(
            title="Scheduled Event Created",
            description=(
                f"**Event Name:** `{event.name}`\n"
                f"**Event ID:** `{event.id}`\n"
                f"**Start Time:** <t:{int(event.start_time.timestamp())}:R> (<t:{int(event.start_time.timestamp())}:F>)\n"
                + (
                    f"**End Time:** <t:{int(event.end_time.timestamp())}:R> (<t:{int(event.end_time.timestamp())}:F>)\n"
                    if event.end_time is not None
                    else "**End Time:** `None`\n"
                )
                + f"**Location:** `{event.location}`\n",
            ),
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )

        log = await self._get_audit_log_entry(
            discord.AuditLogAction.scheduled_event_create
        )
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.scheduled_event_create_id
            ),
            embed,
        )

    async def scheduled_event_delete(self, event: discord.ScheduledEvent):
        if not self._exists_and_enabled("scheduled_event_delete_id"):
            return

        embed = discord.Embed(
            title="Scheduled Event Deleted",
            description=(
                f"**Event Name:** `{event.name}`\n"
                f"**Event ID:** `{event.id}`\n"
                f"**Start Time:** <t:{int(event.start_time.timestamp())}:R> (<t:{int(event.start_time.timestamp())}:F>)\n"
                + (
                    f"**End Time:** <t:{int(event.end_time.timestamp())}:R> (<t:{int(event.end_time.timestamp())}:F>)\n"
                    if event.end_time is not None
                    else "**End Time:** `None`\n"
                )
                + f"**Location:** `{event.location}`\n"
            ),
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )

        log = await self._get_audit_log_entry(
            discord.AuditLogAction.scheduled_event_delete
        )
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.scheduled_event_delete_id
            ),
            embed,
        )

    async def scheduled_event_update(
        self, before: discord.ScheduledEvent, after: discord.ScheduledEvent
    ):
        if not self._exists_and_enabled("scheduled_event_update_id"):
            return

        changes = []
        if after.name != before.name:
            changes.append(f"**Name:** `{before.name}` ➔ `{after.name}`")
        if after.start_time != before.start_time:
            changes.append(
                f"**Start Time:** <t:{int(before.start_time.timestamp())}:R> (<t:{int(before.start_time.timestamp())}:F>) ➔ <t:{int(after.start_time.timestamp())}:R> (<t:{int(after.start_time.timestamp())}:F>)"
            )
        if after.end_time != before.end_time:
            changes.append(
                f"**End Time:** <t:{int(before.end_time.timestamp())}:R> (<t:{int(before.end_time.timestamp())}:F>)"
                if before.end_time is not None
                else "**End Time:** `None`"
                + f" ➔ <t:{int(after.end_time.timestamp())}:R> (<t:{int(after.end_time.timestamp())}:F>)"
                if after.end_time is not None
                else "**End Time:** `None`"
            )
        if after.location != before.location:
            changes.append(f"**Location:** `{before.location}` ➔ `{after.location}`")

        if len(changes) == 0:
            return

        embed = discord.Embed(
            title="Scheduled Event Updated",
            description="\n".join(changes),
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )

        log = await self._get_audit_log_entry(
            discord.AuditLogAction.scheduled_event_update
        )
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.scheduled_event_update_id
            ),
            embed,
        )

    async def soundboard_sound_create(self, sound: discord.SoundboardSound) -> None:
        if not self._exists_and_enabled("soundboard_sound_create_id"):
            return

        embed = discord.Embed(
            title="Soundboard Sound Created",
            description=(
                f"**Sound Name:** `{sound.name}`\n"
                f"**Sound ID:** `{sound.id}`\n"
                f"**Emoji:** {sound.emoji}\n"
                f"**Volume:** `{int(sound.volume)}%`\n"
            ),
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )

        if sound.user:
            embed.set_author(
                name=sound.user.name, icon_url=sound.user.display_avatar.url
            )

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.soundboard_sound_create_id
            ),
            embed,
        )

    async def soundboard_sound_delete(self, sound: discord.SoundboardSound) -> None:
        if not self._exists_and_enabled("soundboard_sound_delete_id"):
            return

        embed = discord.Embed(
            title="Soundboard Sound Deleted",
            description=(
                f"**Sound Name:** `{sound.name}`\n"
                f"**Sound ID:** `{sound.id}`\n"
                f"**Emoji:** {sound.emoji}\n"
                f"**Volume:** `{int(sound.volume)}%`\n"
            ),
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )

        if sound.user:
            embed.set_author(
                name=sound.user.name, icon_url=sound.user.display_avatar.url
            )

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.soundboard_sound_delete_id
            ),
            embed,
        )

    async def soundboard_sound_update(
        self, before: discord.SoundboardSound, after: discord.SoundboardSound
    ):
        if not self._exists_and_enabled("soundboard_sound_update_id"):
            return

        changes = []
        if before.emoji != after.emoji:
            changes.append(f"**Emoji:** {before.emoji} ➔ {after.emoji}")
        if before.volume != after.volume:
            changes.append(
                f"**Volume:** `{int(before.volume)}%` ➔ `{int(after.volume)}%`"
            )

        embed = discord.Embed(
            title="Soundboard Sound Updated",
            description=(
                f"**Sound Name:** `{before.name}` ➔ `{after.name}`\n"
                f"**Sound ID:** `{before.id}`\n"
                "\n".join(changes)
            ),
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )

        if after.user:
            embed.set_author(
                name=after.user.name, icon_url=after.user.display_avatar.url
            )

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.soundboard_sound_update_id
            ),
            embed,
        )

    async def stage_instance_create(self, instance: discord.StageInstance) -> None:
        if not self._exists_and_enabled("stage_instance_create_id"):
            return

        embed = discord.Embed(
            title="Stage Instance Created",
            description=(
                f"**Topic:** `{instance.topic}`\n"
                + f"**Channel:** {instance.channel.mention} (`#{instance.channel.name}`)\n"
                if instance.channel
                else "**Channel:** Unknown\n"
                + f"**Scheduled:** {'Yes' if instance.scheduled_event_id else 'No'}"
            ),
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )

        log = await self._get_audit_log_entry(
            discord.AuditLogAction.stage_instance_create
        )
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.stage_instance_create_id
            ),
            embed,
        )

    async def stage_instance_delete(self, instance: discord.StageInstance) -> None:
        if not self._exists_and_enabled("stage_instance_delete_id"):
            return

        embed = discord.Embed(
            title="Stage Instance Deleted",
            description=(
                f"**Topic:** `{instance.topic}`\n"
                + f"**Channel:** {instance.channel.mention} (`#{instance.channel.name}`)\n"
                if instance.channel
                else "**Channel:** Unknown\n"
                + f"**Scheduled:** {'Yes' if instance.scheduled_event_id else 'No'}"
            ),
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )

        log = await self._get_audit_log_entry(
            discord.AuditLogAction.stage_instance_delete
        )
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.stage_instance_delete_id
            ),
            embed,
        )

    async def stage_instance_update(
        self, before: discord.StageInstance, after: discord.StageInstance
    ) -> None:
        if not self._exists_and_enabled("stage_instance_update_id"):
            return

        if before.topic == after.topic:
            return

        embed = discord.Embed(
            title="Stage Instance Updated",
            description=(
                f"**Topic:** `{before.topic}` ➔ `{after.topic}`"
                + f"**Channel:** {after.channel.mention} (`#{after.channel.name}`)\n"
                if after.channel
                else "**Channel:** Unknown\n"
            ),
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )

        log = await self._get_audit_log_entry(
            discord.AuditLogAction.stage_instance_update
        )
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.stage_instance_update_id
            ),
            embed,
        )

    async def thread_create(self, thread: discord.Thread) -> None:
        if not self._exists_and_enabled("thread_create_id"):
            return

        embed = discord.Embed(
            title="Thread Created",
            description=(
                f"**Thread Name:** `{thread.name}`\n"
                f"**Thread ID:** `{thread.id}`\n"
                + f"**Channel:** {thread.parent.mention} (`#{thread.parent.name}`)\n"
                if thread.parent
                else "**Channel:** `Unknown`"
                + f"**Auto Archive Duration:** `{thread.auto_archive_duration} minutes`\n"
                f"**Type:** `{str(thread.type).split('.')[-1].replace('_', ' ').title()}`\n"
                f"**Created By:** {thread.owner.mention if thread.owner else 'Unknown'}\n"
            ),
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.thread_create_id),
            embed,
        )

    async def thread_update(
        self, before: discord.Thread, after: discord.Thread
    ) -> None:
        if not self._exists_and_enabled("thread_update_id"):
            return

        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` ➔ `{after.name}`")
        if before.archived != after.archived:
            changes.append(
                f"**Archived:** `{'Yes' if before.archived else 'No'}` ➔ `{'Yes' if after.archived else 'No'}`"
            )
        if before.locked != after.locked:
            changes.append(
                f"**Locked:** `{'Yes' if before.locked else 'No'}` ➔ `{'Yes' if after.locked else 'No'}`"
            )
        if before.auto_archive_duration != after.auto_archive_duration:
            changes.append(
                f"**Auto Archive Duration:** `{before.auto_archive_duration} minutes` ➔ `{after.auto_archive_duration} minutes`"
            )

        if len(changes) == 0:
            return

        embed = discord.Embed(
            title="Thread Updated",
            description=(
                f"**Thread ID:** `{after.id}`\n"
                + f"**Channel:** {after.parent.mention} (`#{after.parent.name}`)\n"
                if after.parent
                else "**Channel:** `Unknown`" + "\n".join(changes)
            ),
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.thread_update_id),
            embed,
        )

    async def thread_remove(self, thread: discord.Thread) -> None:
        if not self._exists_and_enabled("thread_remove_id"):
            return

        embed = discord.Embed(
            title="Thread Removed",
            description=(
                f"**Thread Name:** `{thread.name}`\n"
                f"**Thread ID:** `{thread.id}`\n"
                + f"**Channel:** {thread.parent.mention} (`#{thread.parent.name}`)\n"
                if thread.parent
                else "**Channel:** `Unknown`"
            ),
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.thread_remove_id),
            embed,
        )

    async def thread_delete(self, payload: discord.RawThreadDeleteEvent) -> None:
        if not self._exists_and_enabled("thread_delete_id"):
            return

        if payload.thread:
            embed = discord.Embed(
                title="Thread Deleted",
                description=(
                    f"**Thread Name:** `{payload.thread.name}`\n"
                    f"**Thread ID:** `{payload.thread.id}`\n"
                    + f"**Channel:** {payload.thread.parent.mention} (`#{payload.thread.parent.name}`)\n"
                    if payload.thread.parent
                    else "**Channel:** `Unknown`"
                ),
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow(),
            )
        else:
            embed = discord.Embed(
                title="Thread Deleted",
                description=(
                    f"**Thread ID:** `{payload.thread_id}`\n"
                    f"**Channel:** <#{payload.parent_id}> (`#{payload.parent_id}`)\n"
                ),
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow(),
            )

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.thread_delete_id),
            embed,
        )

    async def voice_join(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if not self._exists_and_enabled("voice_join_id"):
            return

        if before.channel is not None or after.channel is None:
            return

        embed = discord.Embed(
            title="Voice Channel Joined",
            description=(
                f"**User:** {member.mention} (`@{member.name}`)\n"
                f"**ID:** `{member.id}`\n"
                f"**Channel:** {after.channel.mention} (`#{after.channel.name}`)\n"
            ),
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.voice_join_id),
            embed,
        )

    async def voice_leave(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if not self._exists_and_enabled("voice_leave_id"):
            return

        if before.channel is None or after.channel is not None:
            return

        embed = discord.Embed(
            title="Voice Channel Left",
            description=(
                f"**User:** {member.mention} (`@{member.name}`)\n"
                f"**ID:** `{member.id}`\n"
                f"**Channel:** {before.channel.mention} (`#{before.channel.name}`)\n"
            ),
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.voice_leave_id),
            embed,
        )

    async def voice_move(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if not self._exists_and_enabled("voice_move_id"):
            return

        if (
            before.channel == after.channel
            or before.channel is None
            or after.channel is None
        ):
            return

        embed = discord.Embed(
            title="Switched Voice Channel",
            description=(
                f"**User:** {member.mention} (`@{member.name}`)\n"
                f"**ID:** `{member.id}`\n"
                f"**From:** {before.channel.mention} (`#{before.channel.name}`)\n"
                f"**To:** {after.channel.mention} (`#{after.channel.name}`)\n"
            ),
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        log = await self._get_audit_log_entry(discord.AuditLogAction.member_move)
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.voice_move_id),
            embed,
        )

    async def voice_mute(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if not self._exists_and_enabled("voice_mute_id"):
            return

        if before.mute == after.mute:
            return

        if not after.mute:
            return

        embed = discord.Embed(
            title="Member Muted in Voice Channel",
            description=(
                f"**User:** {member.mention} (`@{member.name}`)\n"
                f"**ID:** `{member.id}`\n"
                + f"**Channel:** {after.channel.mention} (`#{after.channel.name}`)\n"
                if after.channel
                else "**Channel:** `Unknown`"
            ),
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        log = await self._get_audit_log_entry(
            discord.AuditLogAction.member_update, target=member
        )
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.voice_mute_id),
            embed,
        )

    async def voice_unmute(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if not self._exists_and_enabled("voice_unmute_id"):
            return

        if before.mute == after.mute:
            return

        if after.mute:
            return

        embed = discord.Embed(
            title="Member Unmuted in Voice Channel",
            description=(
                f"**User:** {member.mention} (`@{member.name}`)\n"
                f"**ID:** `{member.id}`\n"
                + f"**Channel:** {after.channel.mention} (`#{after.channel.name}`)\n"
                if after.channel
                else "**Channel:** `Unknown`"
            ),
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        log = await self._get_audit_log_entry(
            discord.AuditLogAction.member_update, target=member
        )
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.voice_unmute_id),
            embed,
        )

    async def voice_deafen(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if not self._exists_and_enabled("voice_deafen_id"):
            return

        if before.deaf == after.deaf:
            return

        if not after.deaf:
            return

        embed = discord.Embed(
            title="Member Deafened in Voice Channel",
            description=(
                f"**User:** {member.mention} (`@{member.name}`)\n"
                f"**ID:** `{member.id}`\n"
                + f"**Channel:** {after.channel.mention} (`#{after.channel.name}`)\n"
                if after.channel
                else "**Channel:** `Unknown`"
            ),
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        log = await self._get_audit_log_entry(
            discord.AuditLogAction.member_update, target=member
        )
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.voice_deafen_id),
            embed,
        )

    async def voice_undeafen(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if not self._exists_and_enabled("voice_undeafen_id"):
            return

        if before.deaf == after.deaf:
            return

        if after.deaf:
            return

        embed = discord.Embed(
            title="Member Undeafened in Voice Channel",
            description=(
                f"**User:** {member.mention} (`@{member.name}`)\n"
                f"**ID:** `{member.id}`\n"
                + f"**Channel:** {after.channel.mention} (`#{after.channel.name}`)\n"
                if after.channel
                else "**Channel:** `Unknown`"
            ),
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        log = await self._get_audit_log_entry(
            discord.AuditLogAction.member_update, target=member
        )
        await self._add_user_footer(embed, log)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.voice_undeafen_id),
            embed,
        )

    async def titanium_warn(
        self,
        case: ModCase,
        creator: discord.User | discord.Member,
        target: discord.User | discord.Member,
        dm_success: bool,
        dm_error: str,
    ) -> None:
        if not self._exists_and_enabled("titanium_warn_id"):
            return

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.titanium_warn_id),
            warned(self.bot, target, creator, case, dm_success, dm_error),
        )

    async def titanium_mute(
        self,
        case: ModCase,
        creator: discord.User | discord.Member,
        target: discord.User | discord.Member,
        dm_success: bool,
        dm_error: str,
    ) -> None:
        if not self._exists_and_enabled("titanium_mute_id"):
            return

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.titanium_mute_id),
            muted(self.bot, target, creator, case, dm_success, dm_error),
        )

    async def titanium_unmute(
        self,
        case: ModCase,
        creator: discord.User | discord.Member,
        target: discord.User | discord.Member,
        dm_success: bool,
        dm_error: str,
    ) -> None:
        if not self._exists_and_enabled("titanium_unmute_id"):
            return

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.titanium_unmute_id),
            unmuted(self.bot, target, creator, case, dm_success, dm_error),
        )

    async def titanium_kick(
        self,
        case: ModCase,
        creator: discord.User | discord.Member,
        target: discord.User | discord.Member,
        dm_success: bool,
        dm_error: str,
    ) -> None:
        if not self._exists_and_enabled("titanium_kick_id"):
            return

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.titanium_kick_id),
            kicked(self.bot, target, creator, case, dm_success, dm_error),
        )

    async def titanium_ban(
        self,
        case: ModCase,
        creator: discord.User | discord.Member,
        target: discord.User | discord.Member,
        dm_success: bool,
        dm_error: str,
    ) -> None:
        if not self._exists_and_enabled("titanium_ban_id"):
            return

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.titanium_ban_id),
            banned(self.bot, target, creator, case, dm_success, dm_error),
        )

    async def titanium_unban(
        self,
        case: ModCase,
        creator: discord.User | discord.Member,
        target: discord.User | discord.Member,
        dm_success: bool,
        dm_error: str,
    ) -> None:
        if not self._exists_and_enabled("titanium_unban_id"):
            return

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(self.config.logging_settings.titanium_unban_id),
            unbanned(self.bot, target, creator, case, dm_success, dm_error),
        )

    async def titanium_case_comment(
        self, case: ModCase, creator: discord.Member, comment: str
    ) -> None:
        if not self._exists_and_enabled("titanium_case_comment_id"):
            return

        try:
            user = await self.bot.fetch_user(case.creator_user_id)
        except Exception:
            user = None

        embed = discord.Embed(
            title=f"Comment added to `{case.id}`{f' (@{user.name})' if user else ''}",
            description=comment,
            color=discord.Color.blue(),
        )

        embed.set_footer(text=f"@{creator.name}", icon_url=creator.display_avatar.url)

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.titanium_case_comment_id
            ),
            embed=embed,
        )

    async def titanium_automod_trigger(
        self,
        rules: list[AutomodRule],
        actions: list[AutomodAction],
        message: discord.Message,
    ) -> None:
        if not self._exists_and_enabled("titanium_automod_trigger_id"):
            return

        if isinstance(message.channel, (discord.DMChannel, discord.GroupChannel)):
            return

        embed = discord.Embed(
            title="Titanium Automod",
            description=f"{message.author.mention} (`@{message.author.name}`, `{message.author.id}`) triggered automod in {message.channel.mention}"
            f"({f'`#{message.channel.name}`, ' if not isinstance(message.channel, discord.PartialMessageable) else ''}`{message.channel.id}`).",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="Triggered Rules",
            value="\n".join(
                f"**{rule.rule_name}** (`{rule.id}`) - **{rule.threshold} occurrences** in **{rule.duration} seconds**"
                for rule in rules
            ),
            inline=False,
        )

        embed.add_field(
            name="Actions Taken",
            value="\n".join(
                f"**{action.action_type.capitalize()}** (`{naturaldelta(timedelta(seconds=action.duration)) if action.duration else 'permanent'}`): {shorten(action.reason, width=100, placeholder='...')}"
                for action in actions
            ),
            inline=False,
        )

        assert self.config is not None and self.config.logging_settings is not None
        await self._send_to_webhook(
            await self._find_webhook(
                self.config.logging_settings.titanium_automod_trigger_id
            ),
            embed=embed,
        )

import asyncio
import logging
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from lib.cases.case_manager import GuildModCaseManager
from lib.classes.guild_logger import GuildLogger
from lib.embeds.dm_notifs import banned_dm, kicked_dm, muted_dm, warned_dm
from lib.helpers.log_error import log_error
from lib.helpers.send_dm import send_dm
from lib.sql.sql import BouncerAction, BouncerRule, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class BouncerMonitorCog(commands.Cog):
    """Monitors joiners and member updates for bouncer triggers and creates cases/punishments"""

    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot
        self.logger: logging.Logger = logging.getLogger("bouncer")
        self.event_queue: asyncio.Queue[discord.Member] = asyncio.Queue()
        self.event_queue_task = self.bot.loop.create_task(self.queue_worker())

    def cog_unload(self) -> None:
        self.event_queue.shutdown(immediate=True)

    async def queue_worker(self):
        self.logger.info("Bouncer handler started.")
        while True:
            try:
                await self.bot.wait_until_ready()
                event = await self.event_queue.get()
            except asyncio.QueueShutDown:
                return

            try:
                await self.event_handler(event)
            except Exception as e:
                await log_error(
                    module="Bouncer",
                    guild_id=event.guild.id if event.guild else None,
                    error=f"An unknown error occurred while processing bouncer for member @{event.name} ({event.id})",
                    exc=e,
                )
            finally:
                self.event_queue.task_done()

    async def event_handler(self, member: discord.Member):
        self.logger.debug(f"Processing member join/update: {member.id}")
        # Check for server ID in config list
        if (
            not member.guild
            or member.guild.id not in self.bot.guild_configs
            or not self.bot.guild_configs[member.guild.id].bouncer_settings
            or not member
            or not isinstance(member, discord.Member)
            or not self.bot.user
        ):
            self.logger.debug("Bouncer initial checks failed, skipping member")
            return

        triggers: list[BouncerRule] = []
        punishments: list[BouncerAction] = []

        if not self.bot.guild_configs[member.guild.id].bouncer_enabled:
            self.logger.debug("Bouncer is not enabled, skipping member")
            return

        config = self.bot.guild_configs[member.guild.id].bouncer_settings

        for rule in config.rules:
            spotted = False

            if not rule.enabled:
                continue

            for criteria in rule.criteria:
                if str(criteria.criteria_type) == "username":
                    if criteria.match_whole_word:
                        for word in (
                            [w.lower() for w in member.name.split()]
                            + (
                                [w.lower() for w in member.global_name.split()]
                                if member.global_name
                                else []
                            )
                            + [x.lower() for x in member.display_name.split()]
                        ):
                            if criteria.match_whole_word and word in criteria.words:
                                spotted = True
                                break
                            elif not criteria.match_whole_word and any(
                                w in word for w in criteria.words
                            ):
                                spotted = True
                                break
                elif str(criteria.criteria_type) == "tag" and member.primary_guild:
                    if (
                        criteria.match_whole_word
                        and str(member.primary_guild.tag) in criteria.words
                    ):
                        spotted = True
                        break
                    elif not criteria.match_whole_word and any(
                        w in str(member.primary_guild.tag) for w in criteria.words
                    ):
                        spotted = True
                        break
                elif str(criteria.criteria_type) == "age":
                    if (discord.utils.utcnow() - member.created_at).seconds <= criteria.account_age:
                        spotted = True
                        break
                elif str(criteria.criteria_type) == "avatar":
                    if not member.avatar:
                        spotted = True
                        break

            if spotted:
                triggers.append(rule)
                for action in rule.actions:
                    action: BouncerAction
                    punishments.append(action)

        # Get list of punishment types
        punishment_types = list(set(action.action_type for action in punishments))

        async with get_session() as session:
            manager = GuildModCaseManager(member.guild, session)

            for punishment in punishments:
                if str(punishment.action_type) == "add_role":
                    role = member.guild.get_role(punishment.role_id)

                    if role and role not in member.roles:
                        try:
                            await member.add_roles(role, reason=f"Bouncer: {punishment.reason}")
                        except discord.Forbidden as e:
                            await log_error(
                                module="Bouncer",
                                guild_id=member.guild.id,
                                error=f"Titanium was not allowed to add the {role.name} ({role.id}) role to {member.name} ({member.id})",
                                details=e.text,
                            )
                        except discord.HTTPException as e:
                            await log_error(
                                module="Bouncer",
                                guild_id=member.guild.id,
                                error=f"Unknown Discord error while adding role {role.name} ({role.id}) to {member.name} ({member.id})",
                                details=e.text,
                            )
                elif str(punishment.action_type) == "remove_role":
                    role = member.guild.get_role(punishment.role_id)

                    if role and role in member.roles:
                        try:
                            await member.remove_roles(role, reason=f"Bouncer: {punishment.reason}")
                        except discord.Forbidden as e:
                            await log_error(
                                module="Bouncer",
                                guild_id=member.guild.id,
                                error=f"Titanium was not allowed to remove the {role.name} ({role.id}) role from {member.name} ({member.id})",
                                details=e.text,
                            )
                        except discord.HTTPException as e:
                            await log_error(
                                module="Bouncer",
                                guild_id=member.guild.id,
                                error=f"Unknown Discord error while removing role {role.name} ({role.id}) from {member.name} ({member.id})",
                                details=e.text,
                            )
                elif str(punishment.action_type) == "toggle_role":
                    role = member.guild.get_role(punishment.role_id)

                    if role:
                        try:
                            if role in member.roles:
                                await member.remove_roles(
                                    role, reason=f"Bouncer: {punishment.reason}"
                                )
                            else:
                                await member.add_roles(role, reason=f"Bouncer: {punishment.reason}")
                        except discord.Forbidden as e:
                            await log_error(
                                module="Bouncer",
                                guild_id=member.guild.id,
                                error=f"Titanium was not allowed to toggle the {role.name} ({role.id}) role for {member.name} ({member.id})",
                                details=e.text,
                            )
                        except discord.HTTPException as e:
                            await log_error(
                                module="Bouncer",
                                guild_id=member.guild.id,
                                error=f"Unknown Discord error while toggling role {role.name} ({role.id}) for {member.name} ({member.id})",
                                details=e.text,
                            )
                elif str(punishment.action_type) == "warn":
                    case = await manager.create_case(
                        action="warn",
                        user_id=member.id,
                        creator_user_id=self.bot.user.id,
                        reason=f"Bouncer: {punishment.reason}",
                    )

                    await send_dm(
                        embed=warned_dm(self.bot, member, case),
                        user=member,
                        source_guild=member.guild,
                        module="Bouncer",
                        action="warning",
                    )
                elif str(punishment.action_type) == "mute":
                    # Check if user is already timed out
                    if member.is_timed_out():
                        continue

                    # Time out user
                    try:
                        await member.timeout(
                            (
                                timedelta(seconds=punishment.duration)
                                if punishment.duration > 0
                                and timedelta(seconds=punishment.duration).total_seconds()
                                <= 2419200
                                else timedelta(seconds=2419200)
                            ),
                            reason=f"Bouncer: {punishment.reason}",
                        )

                        case = await manager.create_case(
                            action="mute",
                            user_id=member.id,
                            creator_user_id=self.bot.user.id,
                            reason=f"Bouncer: {punishment.reason}",
                            duration=(
                                timedelta(seconds=punishment.duration)
                                if punishment.duration > 0
                                else None
                            ),
                        )

                        await send_dm(
                            embed=muted_dm(self.bot, member, case),
                            user=member,
                            source_guild=member.guild,
                            module="Bouncer",
                            action="muting",
                        )
                    except discord.Forbidden as e:
                        await log_error(
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Titanium was not allowed to mute {member.name} ({member.id})",
                            details=e.text,
                        )
                    except discord.HTTPException as e:
                        await log_error(
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Unknown Discord error while muting {member.name} ({member.id})",
                            details=e.text,
                        )

                elif str(punishment.action_type) == "kick" and "ban" not in punishment_types:
                    # Kick user
                    try:
                        await member.kick(
                            reason=f"Bouncer: {punishment.reason}",
                        )

                        case = await manager.create_case(
                            action="kick",
                            user_id=member.id,
                            creator_user_id=self.bot.user.id,
                            reason=f"Bouncer: {punishment.reason}",
                        )

                        await send_dm(
                            embed=kicked_dm(self.bot, member, case),
                            user=member,
                            source_guild=member.guild,
                            module="Bouncer",
                            action="kicking",
                        )
                    except discord.Forbidden as e:
                        await log_error(
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Titanium was not allowed to kick {member.name} ({member.id})",
                            details=e.text,
                        )
                    except discord.HTTPException as e:
                        await log_error(
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Unknown Discord error while kicking {member.name} ({member.id})",
                            details=e.text,
                        )

                elif str(punishment.action_type) == "ban":
                    # Ban user
                    try:
                        await member.ban(
                            reason=f"Bouncer: {punishment.reason}",
                        )

                        case = await manager.create_case(
                            action="ban",
                            user_id=member.id,
                            creator_user_id=self.bot.user.id,
                            reason=f"Bouncer: {punishment.reason}",
                            duration=(
                                timedelta(seconds=punishment.duration)
                                if punishment.duration > 0
                                else None
                            ),
                        )

                        await send_dm(
                            embed=banned_dm(self.bot, member, case),
                            user=member,
                            source_guild=member.guild,
                            module="Bouncer",
                            action="banning",
                        )
                    except discord.Forbidden as e:
                        await log_error(
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Titanium was not allowed to ban {member.name} ({member.id})",
                            details=e.text,
                        )
                    except discord.HTTPException as e:
                        await log_error(
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Unknown Discord error while banning {member.name} ({member.id})",
                            details=e.text,
                        )

        if triggers:
            guild_logger = GuildLogger(self.bot, member.guild)
            await guild_logger.titanium_bouncer_trigger(
                rules=triggers,
                actions=punishments,
                member=member,
            )

        self.logger.debug(f"Processed member event from {member.guild.id}: {member.id}")

    # Listen for member joins
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        try:
            await self.event_queue.put(member)
        except asyncio.QueueShutDown:
            return

    # Listen for member updates
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        try:
            await self.event_queue.put(after)
        except asyncio.QueueShutDown:
            return


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(BouncerMonitorCog(bot))

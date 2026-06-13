import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lib.classes.case_manager import GuildModCaseManager
from lib.enums.scheduled_events import EventType
from lib.helpers.cache import get_or_fetch_member, get_or_fetch_user
from lib.helpers.log_error import log_error
from lib.sql.sql import ScheduledTask, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class ScheduledTasksCog(commands.Cog):
    """Scheduled tasks handler - reads database for scheduled tasks and executes them"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.logger: logging.Logger = logging.getLogger("tasks")

        self.waiting_tasks: list[uuid.UUID] = []
        self.waiting_tasks_lock = asyncio.Lock()

        self.task_queue: asyncio.Queue[ScheduledTask] = asyncio.Queue()

    async def cog_load(self) -> None:
        # Start workers
        for _ in range(3):
            self.bot.loop.create_task(self.queue_worker())

        self.task_fetcher.start()

    async def cog_unload(self) -> None:
        self.task_fetcher.cancel()
        self.task_queue.shutdown(immediate=True)

    async def queue_worker(self):
        """Worker that grabs tasks from the processing queue"""

        self.logger.info("Scheduled task queue worker started.")
        while True:
            try:
                await self.bot.wait_until_ready()
                task = await self.task_queue.get()
            except asyncio.QueueShutDown:
                return

            self.logger.info(f"Grabbed task {task.id} ({task.type}) from the queue")

            try:
                await self.task_handler(task)
            except Exception as e:
                await log_error(
                    bot=self.bot,
                    module="ScheduledTasks",
                    guild_id=task.guild_id,
                    error="An unexpected internal error occurred while processing a scheduled task",
                    details=f"Task ID: {task.id}\nType: {task.type.value}\nUser ID: {task.user_id}\nChannel ID: {task.channel_id}\nRole ID: {task.role_id}\nMessage ID: {task.message_id}\nCase ID: {task.case_id}",
                    exc=e,
                )
            finally:
                self.logger.info(f"Task {task.id} complete, removing from database")

                try:
                    # Remove from database if exists
                    async with get_session() as session:
                        stmt = await session.get(ScheduledTask, task.id)
                        if stmt:
                            await session.delete(stmt)

                    async with self.waiting_tasks_lock:
                        self.waiting_tasks.remove(task.id)
                except ValueError:
                    pass

                self.task_queue.task_done()

    async def task_handler(self, task: ScheduledTask) -> None:
        """Handles a task from the queue worker"""

        if task.type == EventType.MUTE_REFRESH:
            if not task.guild_id or not task.user_id:
                raise ValueError("Guild ID or user ID is missing (mute refresh)")

            if not task.duration:
                raise ValueError("Duration is missing (mute refresh)")

            # Mute refresh task
            guild = self.bot.get_guild(task.guild_id)
            if not guild:
                return

            member = guild.get_member(task.user_id)
            if not member:
                return

            if not member.is_timed_out():
                return

            try:
                await member.timeout(
                    discord.utils.utcnow() + timedelta(seconds=task.duration),
                    reason=f"{task.case_id} - continuing mute",
                )
            except Exception as e:
                await log_error(
                    bot=self.bot,
                    module="ScheduledTasks",
                    guild_id=task.guild_id,
                    error=f"Failed to refresh mute for {member.id} in guild {guild.name} ({guild.id})",
                    exc=e,
                )
        elif task.type == EventType.PERMA_MUTE_REFRESH:
            if not task.guild_id or not task.user_id:
                raise ValueError("Guild ID or user ID is missing (perma mute refresh)")

            # Perma mute refresh task
            guild = self.bot.get_guild(task.guild_id)
            if not guild:
                return

            member = guild.get_member(task.user_id)
            if not member:
                return

            if not member.is_timed_out():
                return

            try:
                await member.timeout(
                    discord.utils.utcnow() + timedelta(days=28),
                    reason=f"{task.case_id} - continuing perma mute",
                )
            except Exception as e:
                await log_error(
                    bot=self.bot,
                    module="ScheduledTasks",
                    guild_id=task.guild_id,
                    error=f"Failed to refresh perma mute for {member.id} in guild {guild.name} ({guild.id})",
                    exc=e,
                )
        elif task.type == EventType.CLOSE_MUTE:
            if not task.guild_id or not task.user_id or not task.case_id:
                raise ValueError("Guild ID, user ID or case ID is missing (close mute)")

            # Close mute cases task
            guild = self.bot.get_guild(task.guild_id)

            if not guild:
                return

            member = guild.get_member(task.user_id)
            if not member:
                return

            try:
                async with get_session() as session:
                    case_manager = GuildModCaseManager(bot=self.bot, guild=guild, session=session)
                    await case_manager.close_case(
                        case_id=task.case_id,
                    )
            except Exception as e:
                await log_error(
                    bot=self.bot,
                    module="ScheduledTasks",
                    guild_id=task.guild_id,
                    error=f"Failed to send unmute info for {task.user_id} in guild {guild.name} ({guild.id})",
                    exc=e,
                )
        elif task.type == EventType.UNBAN and task.case_id:
            if not task.guild_id or not task.user_id:
                raise ValueError("Guild ID or user ID is missing (unban)")

            # Auto unban task
            guild = self.bot.get_guild(task.guild_id)
            if not guild:
                return

            try:
                await guild.unban(
                    discord.Object(id=task.user_id),
                    reason=f"{task.case_id} - ban expired",
                )

                async with get_session() as session:
                    case_manager = GuildModCaseManager(bot=self.bot, guild=guild, session=session)
                    await case_manager.close_case(
                        case_id=task.case_id,
                    )
            except Exception as e:
                await log_error(
                    bot=self.bot,
                    module="ScheduledTasks",
                    guild_id=task.guild_id,
                    error=f"Failed to auto unban {task.user_id} in guild {guild.name} ({guild.id})",
                    exc=e,
                )
        elif task.type == EventType.REMINDER:
            reminder = task.reminder
            if not reminder:
                return

            try:
                if reminder.dm:
                    channel = await get_or_fetch_user(self.bot, reminder.user_id)
                    if not channel:
                        return
                    member = channel
                else:
                    if not task.guild_id or not reminder.channel_id:
                        raise ValueError("Guild ID or channel ID is missing (reminder)")

                    guild = self.bot.get_guild(task.guild_id)
                    if not guild:
                        return

                    channel = guild.get_channel(reminder.channel_id)
                    if not channel:
                        return

                    if not isinstance(channel, discord.abc.Messageable):
                        return

                    member = await get_or_fetch_member(self.bot, guild, reminder.user_id)
                    if not member:
                        return

                    permissions = channel.permissions_for(guild.me)
                    if not permissions.view_channel or not permissions.send_messages:
                        await log_error(
                            bot=self.bot,
                            module="Reminders",
                            guild_id=task.guild_id,
                            error=f"No permissions to send reminder message in #{channel.name} ({channel.id})",
                            send_webhook=False,
                        )
                        return

                    member_permissions = channel.permissions_for(member)
                    if not member_permissions.view_channel:
                        return

                embed = discord.Embed(
                    title="⏰ Reminder",
                    description=reminder.content,
                    timestamp=reminder.time_created,
                    colour=discord.Colour.light_grey(),
                ).set_footer(
                    text=f"@{member.name} • Created at",
                    icon_url=member.display_avatar.url,
                )

                reply_message = None
                if task.message_id:
                    try:
                        reply_message = await channel.fetch_message(task.message_id)
                        self.logger.debug("fetched message for reminder")
                    except Exception as e:
                        self.logger.debug("can't get message for reminder", exc_info=e)
                        pass
                else:
                    self.logger.debug("no message id for reminder")

                if reply_message:
                    await reply_message.reply(embed=embed)
                else:
                    await channel.send(
                        content=member.mention if not reminder.dm and not reply_message else None,
                        embed=embed,
                    )
            finally:
                await reminder.delete()

        else:
            self.logger.warning(
                f"Task {task.id} has unknown task type: {task.type} (guild: {task.guild_id})"
            )

    @tasks.loop(seconds=1)
    async def task_fetcher(self) -> None:
        """Gets tasks from the database and adds them to the queue every second"""

        await self.bot.wait_until_ready()
        async with get_session() as session:
            # Fetch all tasks that are due
            stmt = (
                select(ScheduledTask)
                .options(selectinload(ScheduledTask.reminder))
                .where(ScheduledTask.time_scheduled <= datetime.now(timezone.utc))
            )
            result = await session.execute(stmt)
            results = result.scalars().all()

            for task in results:
                async with self.waiting_tasks_lock:
                    if task.id in self.waiting_tasks:
                        continue

                    self.logger.debug(f"Adding task {task.id} to queue")
                    self.waiting_tasks.append(task.id)
                await self.task_queue.put(task)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(ScheduledTasksCog(bot))

import asyncio
import logging
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks
from sqlalchemy import func, select

from lib.classes.case_manager import GuildModCaseManager
from lib.enums.scheduled_events import EventType
from lib.helpers.log_error import log_error
from lib.sql.sql import ScheduledTask, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class ScheduledTasksCog(commands.Cog):
    """Scheduled tasks handler - reads database for scheduled tasks and executes them"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.logger: logging.Logger = logging.getLogger("tasks")

        self.waiting_tasks: list[int] = []
        self.waiting_tasks_lock = asyncio.Lock()

        self.task_queue: asyncio.Queue[ScheduledTask] = asyncio.Queue()

        # Start workers
        for i in range(3):
            self.bot.loop.create_task(self.queue_worker())

    def cog_unload(self) -> None:
        self.task_queue.shutdown(immediate=True)

    async def queue_worker(self):
        """Worker that grabs tasks from the processing queue"""

        self.logger.info("Scheduled task queue worker started.")
        while True:
            try:
                await self.bot.wait_until_ready()
                task = await self.task_queue.get()

                async with self.waiting_tasks_lock:
                    self.waiting_tasks.append(task.id)
            except asyncio.QueueShutDown:
                return

            try:
                await self.task_handler(task)
            except Exception as e:
                await log_error(
                    module="ScheduledTasks",
                    guild_id=task.guild_id,
                    error="An unexpected internal error occurred while processing a scheduled task",
                    details=f"Task ID: {task.id}\nType: {task.type.value}\nUser ID: {task.user_id}\nChannel ID: {task.channel_id}\nRole ID: {task.role_id}\nMessage ID: {task.message_id}\nCase ID: {task.case_id}",
                    exc=e,
                )
            finally:
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
                    module="ScheduledTasks",
                    guild_id=task.guild_id,
                    error=f"Failed to refresh mute for {member.id} in guild {guild.name} ({guild.id})",
                    exc=e,
                )
        elif task.type == EventType.PERMA_MUTE_REFRESH:
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
                    reason=f"{task.case_id} - continuing mute",
                )
            except Exception as e:
                await log_error(
                    module="ScheduledTasks",
                    guild_id=task.guild_id,
                    error=f"Failed to refresh perma mute for {member.id} in guild {guild.name} ({guild.id})",
                    exc=e,
                )
        elif task.type == EventType.CLOSE_MUTE:
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
                    module="ScheduledTasks",
                    guild_id=task.guild_id,
                    error=f"Failed to send unmute info for {task.user_id} in guild {guild.name} ({guild.id})",
                    exc=e,
                )
        elif task.type == EventType.UNBAN:
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
                    module="ScheduledTasks",
                    guild_id=task.guild_id,
                    error=f"Failed to auto unban {task.user_id} in guild {guild.name} ({guild.id})",
                    exc=e,
                )

    @tasks.loop(seconds=1)
    async def task_fetcher(self) -> None:
        """Gets tasks from the database and adds them to the queue every second"""

        await self.bot.wait_until_ready()
        async with get_session() as session:
            # Fetch all tasks that are due
            stmt = select(ScheduledTask).where(
                ScheduledTask.time_scheduled <= func.strftime("%s", "now")
            )
            result = await session.execute(stmt)
            results = result.scalars().all()

            for task in results:
                async with self.waiting_tasks_lock:
                    if task.id in self.waiting_tasks:
                        continue

                self.waiting_tasks.append(task.id)
                await self.task_queue.put(task)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(ScheduledTasksCog(bot))

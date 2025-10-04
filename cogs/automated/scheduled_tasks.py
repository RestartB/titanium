import asyncio
import logging
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks
from sqlalchemy import func, select

from lib.sql import ScheduledTask, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class ScheduledTasksCog(commands.Cog):
    """Scheduled tasks handler - reads database for scheduled tasks and executes them"""

    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot
        self.logger: logging.Logger = logging.getLogger("tasks")
        self.queued_tasks: list[int] = []
        self.task_queue: asyncio.Queue[ScheduledTask] = asyncio.Queue()
        self.task_queue_task = self.bot.loop.create_task(self.queue_worker())

    def cog_unload(self) -> None:
        self.task_queue.shutdown(immediate=True)

    async def queue_worker(self):
        """Worker that grabs tasks from the processing queue"""

        self.logger.info("Scheduled task queue worker started.")
        while True:
            try:
                await self.bot.wait_until_ready()
                task = await self.task_queue.get()
                self.queued_tasks.append(task.id)
            except asyncio.QueueShutDown:
                return

            try:
                await self.task_handler(task)
            except Exception as e:
                self.logger.error("Error processing scheduled task:")
                self.logger.exception(e)
            finally:
                try:
                    # Remove from database if exists
                    async with get_session() as session:
                        stmt = await session.get(ScheduledTask, task.id)
                        if stmt:
                            await session.delete(stmt)

                    self.queued_tasks.remove(task.id)
                except ValueError:
                    pass

                self.task_queue.task_done()

    async def task_handler(self, task: ScheduledTask) -> None:
        """Handles a task from the queue worker"""

        if task.type == "refresh_mute":
            # Mute refresh task
            guild = self.bot.get_guild(task.guild_id)
            if not guild:
                return

            member = guild.get_member(task.user_id)
            if not member:
                return

            await member.timeout(
                discord.utils.utcnow() + timedelta(seconds=task.duration),
                reason=f"{task.case_id} - continuing mute",
            )
        elif task.type == "perma_mute_refresh":
            # Perma mute refresh task
            guild = self.bot.get_guild(task.guild_id)
            if not guild:
                return

            member = guild.get_member(task.user_id)
            if not member:
                return

            try:
                await member.timeout(
                    discord.utils.utcnow() + timedelta(days=28),
                    reason=f"{task.case_id} - continuing mute",
                )
            except Exception as e:
                self.logger.error(
                    f"[TASKS] Failed to refresh perma mute for {member.id} in guild {guild.name} ({guild.id})"
                )
                self.logger.exception(e)
        elif task.type == "unban":
            # Auto unban task
            guild = self.bot.get_guild(task.guild_id)
            if not guild:
                return

            try:
                await guild.unban(
                    discord.Object(id=task.user_id),
                    reason=f"{task.case_id} - ban expired",
                )
            except Exception as e:
                self.logger.error(
                    f"[TASKS] Failed to auto unban {task.user_id} in guild {guild.name} ({guild.id})"
                )
                self.logger.exception(e)

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
                if task.id in self.queued_tasks:
                    continue

                self.queued_tasks.append(task.id)
                await self.task_queue.put(task)


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(ScheduledTasksCog(bot))

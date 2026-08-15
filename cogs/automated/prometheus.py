from typing import TYPE_CHECKING

from discord.ext import commands, tasks
from prometheus_client import Gauge
from sqlalchemy import func, select

from lib.sql.sql import GuildSettings, ModCase, ScheduledTask, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


scheduled_task_amounts = Gauge("scheduled_task_amount", "Amount of pending scheduled tasks")
mod_case_amounts = Gauge("stored_mod_cases", "Amount of stored mod cases in database")
guild_config_amounts = Gauge("stored_guild_configs", "Amount of stored guild configs in database")


class PrometheusCog(commands.Cog):
    """Automatic task and event handlers to update some prometheus stats"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        # Start tasks
        self.counter_update.start()

    async def cog_unload(self) -> None:
        # Stop tasks on unload
        self.counter_update.cancel()

    # Prometheus update task
    @tasks.loop(minutes=1)
    async def counter_update(self) -> None:
        await self.bot.wait_until_ready()

        async with get_session() as session:
            scheduled_task_amounts.set(
                (await session.execute(select(func.count()).select_from(ScheduledTask))).scalar()
                or 0
            )
            mod_case_amounts.set(
                (await session.execute(select(func.count()).select_from(ModCase))).scalar() or 0
            )
            guild_config_amounts.set(
                (await session.execute(select(func.count()).select_from(GuildSettings))).scalar()
                or 0
            )


async def setup(bot: TitaniumBot):
    await bot.add_cog(PrometheusCog(bot))

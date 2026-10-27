from typing import TYPE_CHECKING

from discord.ext import commands, tasks
from discord.utils import utcnow
from sqlalchemy import delete

from lib.sql.sql import TagEditLink, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class CleanupTasks(commands.Cog):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.tag_link_cleanup.start()

    async def cog_unload(self) -> None:
        self.tag_link_cleanup.cancel()

    # Check for expired links
    @tasks.loop(minutes=1)
    async def tag_link_cleanup(self) -> None:
        await self.bot.wait_until_ready()

        async with get_session() as session:
            await session.execute(delete(TagEditLink).where(TagEditLink.expires_at <= utcnow()))


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(CleanupTasks(bot))

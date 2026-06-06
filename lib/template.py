from typing import TYPE_CHECKING

from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from main import TitaniumBot


@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class TemplateCog(commands.Cog, description="Template cog."):
    """Cog template."""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="command")
    async def info(self, ctx: commands.Context["TitaniumBot"]) -> None:
        pass


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(TemplateCog(bot))

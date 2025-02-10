import discord
from discord import Color, app_commands
from discord.ext import commands
from url_cleaner import UrlCleaner


class StripTracking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.cleaner = UrlCleaner()
        self.cleaner.ruler.update_rules()

    # Tracking Strip command
    @app_commands.command(
        name="strip-tracking", description="Remove known trackers from a URL."
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(url="The URL to strip tracking from.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissable message only visible to you. Defaults to false."
    )
    async def strip_tracking(
        self, interaction: discord.Interaction, url: str, ephemeral: bool = False
    ):
        await interaction.response.defer(ephemeral=True)

        url = self.cleaner.clean(url)

        embed = discord.Embed(
            title="URL: Tracking Stripped", description=url, color=Color.random()
        )
        embed.set_footer(
            text=f"@{interaction.user.name}",
            icon_url=interaction.user.display_avatar.url,
        )

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(StripTracking(bot))

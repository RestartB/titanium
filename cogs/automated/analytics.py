import os
from typing import TYPE_CHECKING, Union

import discord
from discord import Color, app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from main import TitaniumBot


class Analytics(commands.Cog):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    async def _send_embed(self, embed: discord.Embed, raw: bool = False) -> None:
        if self.bot.user:
            embed.set_author(
                name=f"{self.bot.user.name}#{self.bot.user.discriminator}",
                icon_url=self.bot.user.display_avatar,
            )

        if raw:
            webhook_url = os.getenv("RAW_ANALYTICS_WEBHOOK")
        else:
            webhook_url = os.getenv("ANALYTICS_WEBHOOK")

        if webhook_url:
            webhook = discord.Webhook.from_url(
                webhook_url,
                client=self.bot,
            )
            await webhook.send(embed=embed)

    # Analytics for slash commands
    @commands.Cog.listener()
    async def on_app_command_completion(
        self,
        interaction: discord.Interaction,
        command: Union[app_commands.Command, app_commands.ContextMenu],
    ) -> None:
        embed = discord.Embed(
            title=f"@{interaction.user.name} ran an app command",
            description=f"`/{command.qualified_name}`",
            timestamp=interaction.created_at,
        )
        embed.add_field(name="User", value=f"{interaction.user.mention} (`{interaction.user.id}`)")

        await self._send_embed(embed)

    # Analytics for raw interactions
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=f"@{interaction.user.name} started an interaction",
            description=f"`{str(interaction.type)}`",
            timestamp=interaction.created_at,
        )
        embed.add_field(name="User", value=f"{interaction.user.mention} (`{interaction.user.id}`)")

        await self._send_embed(embed, raw=True)

    # Analytics for prefix commands
    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context["TitaniumBot"]):
        if ctx.command is None:
            return

        embed = discord.Embed(
            title=f"@{ctx.author.name} ran a prefix command",
            description=f"`{ctx.clean_prefix}{ctx.command.qualified_name}`",
            timestamp=ctx.message.created_at,
        )
        embed.add_field(name="User", value=f"{ctx.author.mention} (`{ctx.author.id}`)")

        await self._send_embed(embed)

    # Analytics for server joins
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        embed = discord.Embed(
            title="Joined Guild",
            description=f"Titanium has joined the `{guild.name}` guild.",
            timestamp=discord.utils.utcnow(),
            colour=Color.green(),
        )
        embed.set_thumbnail(url=guild.icon)
        embed.set_image(url=guild.banner)

        await self._send_embed(embed)

    # Analytics for server removes
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        embed = discord.Embed(
            title="Left Guild",
            description=f"Titanium has left the `{guild.name}` guild.",
            timestamp=discord.utils.utcnow(),
            colour=Color.red(),
        )
        embed.set_thumbnail(url=guild.icon)
        embed.set_image(url=guild.banner)

        await self._send_embed(embed)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(Analytics(bot))

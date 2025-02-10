import asyncio

import discord
from discord import Color
from discord.ext import commands


class ViewTimeout(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Listen for Interaction
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        # Wait a second to give a chance to other commands
        await asyncio.sleep(1)

        try:
            # If this succeeds, no one has responded, it's probably timed out
            await interaction.response.defer(ephemeral=True)
        except discord.errors.InteractionResponded:
            return

        try:
            # Get original response, disable all buttons
            response = await interaction.original_response()
            view = discord.ui.View.from_message(response)

            for item in view.children:
                try:
                    if item.style != discord.ButtonStyle.url:
                        item.disabled = True
                except Exception:
                    item.disabled = True

            # Edit the message
            await response.edit(view=view)

            # Send an error
            embed = discord.Embed(
                title="Error",
                description="This view has expired. Please run the command again.",
                color=Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except (
            discord.errors.NotFound
        ):  # Can't find the original message, skip disabling buttons
            # Send an error
            embed = discord.Embed(
                title="Error",
                description="This view has expired. Please run the command again.",
                color=Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(ViewTimeout(bot))

import dataclasses
from typing import TYPE_CHECKING

import discord
from discord import ButtonStyle, Colour, Interaction
from discord.ui import Button, View, button

from lib.classes.quote_config import QuoteData
from lib.enums.images import ImageFormats
from lib.logic.quote import create_quote_image

if TYPE_CHECKING:
    from main import TitaniumBot


class QuoteView(View):
    def __init__(self, bot: TitaniumBot, data: QuoteData):
        super().__init__(timeout=3600 * 24)
        self.bot = bot
        self.data = data

        if not data.fade:
            self.fade_mode.label = "Enable Fade"
            self.fade_mode.emoji = "🕶️"
            self.fade_mode.style = ButtonStyle.green

        if data.bw_mode:
            self.colour_mode.label = "Colour"
            self.colour_mode.emoji = "🎨"

        if data.light_mode:
            self.theme_mode.label = "Dark Mode"
            self.theme_mode.emoji = "🌙"

    @button(label="Disable Fade", emoji="👓", style=ButtonStyle.red)
    async def fade_mode(self, interaction: Interaction["TitaniumBot"], button: Button):
        await interaction.response.defer(ephemeral=True)

        if self.data.fade:
            self.data.fade = False
            self.fade_mode.label = "Enable Fade"
            self.fade_mode.emoji = "🕶️"
            self.fade_mode.style = ButtonStyle.green
        else:
            self.data.fade = True
            self.fade_mode.label = "Disable Fade"
            self.fade_mode.emoji = "👓"
            self.fade_mode.style = ButtonStyle.red

        file = await create_quote_image(self.data, renderer=self.bot.browser_renderer)
        await interaction.edit_original_response(attachments=[file], view=self)

    @button(label="Black and White", emoji="⚫", style=ButtonStyle.grey)
    async def colour_mode(self, interaction: Interaction["TitaniumBot"], button: Button):
        await interaction.response.defer(ephemeral=True)

        if self.data.bw_mode:
            self.data.bw_mode = False
            self.colour_mode.label = "Black and White"
            self.colour_mode.emoji = "⚫"
        else:
            self.data.bw_mode = True
            self.colour_mode.label = "Colour"
            self.colour_mode.emoji = "🎨"

        file = await create_quote_image(self.data, renderer=self.bot.browser_renderer)
        await interaction.edit_original_response(attachments=[file], view=self)

    @button(label="Light Mode", emoji="☀️", style=ButtonStyle.grey)
    async def theme_mode(self, interaction: Interaction["TitaniumBot"], button: Button):
        await interaction.response.defer(ephemeral=True)

        if self.data.light_mode:
            self.data.light_mode = False
            self.theme_mode.label = "Light Mode"
            self.theme_mode.emoji = "☀️"
        else:
            self.data.light_mode = True
            self.theme_mode.label = "Dark Mode"
            self.theme_mode.emoji = "🌙"

        file = await create_quote_image(self.data, renderer=self.bot.browser_renderer)
        await interaction.edit_original_response(attachments=[file], view=self)

    @button(label="PNG", emoji="🖼️", style=ButtonStyle.grey)
    async def png_button(self, interaction: Interaction["TitaniumBot"], button: Button):
        await interaction.response.defer(ephemeral=True)

        copy_data = dataclasses.replace(self.data)
        copy_data.output_format = ImageFormats.PNG

        file = await create_quote_image(copy_data, renderer=self.bot.browser_renderer)
        await interaction.followup.send(file=file, ephemeral=True)

    @button(emoji="🗑️", style=ButtonStyle.red)
    async def delete_button(self, interaction: Interaction["TitaniumBot"], button: Button):
        await interaction.response.defer(ephemeral=True)

        if self.data.user.id != interaction.user.id or not interaction.permissions.manage_messages:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Not Allowed",
                description="You didn't send the original message. Only the original message author or users with Manage Message permissions can delete the quote.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        await interaction.delete_original_response()

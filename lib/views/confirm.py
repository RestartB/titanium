from typing import TYPE_CHECKING

import discord
from discord import ButtonStyle, Colour, Interaction
from discord.ui import Button, View, button

if TYPE_CHECKING:
    from main import TitaniumBot


class ConfirmView(View):
    def __init__(
        self,
        bot: TitaniumBot,
        original_user: discord.User | discord.Member,
        timeout: float = 5,
        ephemeral: bool = False,
    ):
        super().__init__(timeout=timeout)

        self.value = False
        self.interaction: Interaction | None = None
        self.original_user = original_user
        self.ephemeral = ephemeral

        self.confirm.emoji = bot.success_emoji

    async def interaction_check(self, interaction: Interaction["TitaniumBot"]) -> bool:
        if interaction.user.id != self.original_user.id:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Not Allowed",
                description="Only the user who sent the command can interact with this button.",
                colour=Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False

        return True

    @button(label="Confirm", style=ButtonStyle.green)
    async def confirm(self, interaction: Interaction, button: Button):
        await interaction.response.defer(ephemeral=self.ephemeral)

        self.value = True
        self.interaction = interaction
        self.stop()

    @button(label="Cancel", style=ButtonStyle.gray)
    async def cancel(self, interaction: Interaction["TitaniumBot"], button: Button):
        await interaction.response.defer(ephemeral=self.ephemeral)

        self.value = False
        self.interaction = interaction
        self.stop()

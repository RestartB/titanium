from typing import TYPE_CHECKING

from discord import ButtonStyle, Interaction
from discord.ui import Button, View, button

if TYPE_CHECKING:
    from main import TitaniumBot


# FIXME: handle confirmation view expiring
class ConfirmView(View):
    def __init__(self, bot: TitaniumBot, timeout: float = 60.0, ephemeral: bool = False):
        super().__init__(timeout=timeout)

        self.value = False
        self.timed_out = False
        self.interaction: Interaction | None = None
        self.ephemeral = ephemeral

        self.confirm.emoji = bot.success_emoji

    async def on_timeout(self) -> None:
        self.timed_out = True

    @button(label="Confirm", style=ButtonStyle.green)
    async def confirm(self, interaction: Interaction, button: Button):
        await interaction.response.defer(ephemeral=self.ephemeral)

        self.value = True
        self.interaction = interaction
        self.stop()

    @button(label="Cancel", style=ButtonStyle.gray)
    async def cancel(self, interaction: Interaction, button: Button):
        await interaction.response.defer(ephemeral=self.ephemeral)

        self.value = False
        self.interaction = interaction
        self.stop()

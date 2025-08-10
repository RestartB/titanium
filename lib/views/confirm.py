from typing import TYPE_CHECKING

from discord import ButtonStyle, Interaction
from discord.ui import Button, View, button

if TYPE_CHECKING:
    from main import TitaniumBot


class ConfirmView(View):
    def __init__(
        self,
        bot: "TitaniumBot",
        timeout: float = 60.0,
    ):
        super().__init__(timeout=timeout)
        self.value = False
        self.interaction: Interaction | None = None

        self.confirm.emoji = bot.success_emoji

    @button(label="Confirm", style=ButtonStyle.green)
    async def confirm(self, button: Button, interaction: Interaction):
        self.value = True
        self.interaction = interaction
        self.stop()

    @button(label="Cancel", style=ButtonStyle.gray)
    async def cancel(self, button: Button, interaction: Interaction):
        self.value = False
        self.interaction = interaction
        self.stop()

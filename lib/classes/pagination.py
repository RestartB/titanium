from discord import ButtonStyle, Embed, Interaction
from discord.ui import Button, View, button


class PaginationView(View):
    def __init__(self, embeds: list[Embed], timeout: float):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.page_count.label = f"1/{len(embeds)}"

        self.current_page = 0

    # First page
    @button(emoji="⏮️", style=ButtonStyle.red, custom_id="first")
    async def first_button(self, interaction: Interaction, button: Button):
        self.current_page = 0
        self.page_count.label = f"1/{len(self.embeds)}"
        self.first_button.disabled = True
        self.prev_button.disabled = True

        await interaction.edit_original_response(
            embed=self.embeds[self.current_page], view=self
        )

    # Prev Page
    @button(emoji="⏪", style=ButtonStyle.primary, custom_id="prev")
    async def prev_button(self, interaction: Interaction, button: Button):
        self.current_page = min(self.current_page - 1, 0)
        self.page_count.label = f"{self.current_page + 1}/{len(self.embeds)}"
        if self.current_page == 0:
            self.first_button.disabled = True
            self.prev_button.disabled = True

        await interaction.edit_original_response(
            embed=self.embeds[self.current_page], view=self
        )

    # Page count
    @button(style=ButtonStyle.gray, custom_id="count", disabled=True)
    async def page_count(self, interaction: Interaction, button: Button):
        pass

    # Next page
    @button(emoji="⏩", style=ButtonStyle.primary, custom_id="next")
    async def next_button(self, interaction: Interaction, button: Button):
        self.current_page = max(self.current_page + 1, len(self.embeds) - 1)
        self.page_count.label = f"{self.current_page + 1}/{len(self.embeds)}"
        if self.current_page == len(self.embeds) - 1:
            self.next_button.disabled = True
            self.last_button.disabled = True

        await interaction.edit_original_response(
            embed=self.embeds[self.current_page], view=self
        )

    # Last page
    @button(emoji="⏭️", style=ButtonStyle.green, custom_id="last")
    async def last_button(self, interaction: Interaction, button: Button):
        self.current_page = len(self.embeds) - 1
        self.page_count.label = f"{self.current_page + 1}/{len(self.embeds)}"
        self.next_button.disabled = True
        self.last_button.disabled = True

        await interaction.edit_original_response(
            embed=self.embeds[self.current_page], view=self
        )

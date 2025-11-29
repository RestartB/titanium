from discord import ButtonStyle, Embed, Interaction
from discord.ui import Button, View, button


class PaginationView(View):
    def __init__(
        self,
        embeds: list[Embed] | list[list[Embed]],
        timeout: float,
        custom_buttons: list[Button] = [],
        page_offset: int = 0,
        footer_embed: int = -1,
    ):
        super().__init__(timeout=timeout)
        self.footer_embed = footer_embed
        self.embeds: list[list[Embed]] = []

        for embed_group in embeds:
            if isinstance(embed_group, list):
                self.embeds.append(embed_group)
            else:
                self.embeds.append([embed_group])

        for custom_button in custom_buttons:
            self.add_item(custom_button)

        self.page_count.label = f"1/{len(embeds)}"
        self.current_page = min(max(page_offset - 1, 0), len(embeds) - 1)

        if self.current_page == 0:
            self.first_button.disabled = True
            self.prev_button.disabled = True

        if self.current_page == len(embeds) - 1:
            self.next_button.disabled = True
            self.last_button.disabled = True

    async def _set_footer(self, interaction: Interaction):
        self.embeds[self.current_page][self.footer_embed].set_footer(
            text=f"Controlling: @{interaction.user.name}",
            icon_url=interaction.user.display_avatar.url,
        )

    # First page
    @button(emoji="⏮️", style=ButtonStyle.red, custom_id="first")
    async def first_button(self, interaction: Interaction, button: Button):
        await interaction.response.defer()

        self.current_page = 0
        self.page_count.label = f"1/{len(self.embeds)}"

        self.first_button.disabled = True
        self.prev_button.disabled = True
        self.next_button.disabled = False
        self.last_button.disabled = False

        await self._set_footer(interaction)
        await interaction.edit_original_response(
            embeds=self.embeds[self.current_page],
            view=self,
        )

    # Prev Page
    @button(emoji="⏪", style=ButtonStyle.primary, custom_id="prev")
    async def prev_button(self, interaction: Interaction, button: Button):
        await interaction.response.defer()

        self.current_page = max(self.current_page - 1, 0)
        self.page_count.label = f"{self.current_page + 1}/{len(self.embeds)}"

        if self.current_page == 0:
            self.first_button.disabled = True
            self.prev_button.disabled = True

        self.next_button.disabled = False
        self.last_button.disabled = False

        await self._set_footer(interaction)
        await interaction.edit_original_response(
            embeds=self.embeds[self.current_page],
            view=self,
        )

    # Page count
    @button(style=ButtonStyle.gray, custom_id="count", disabled=True)
    async def page_count(self, interaction: Interaction, button: Button):
        pass

    # Next page
    @button(emoji="⏩", style=ButtonStyle.primary, custom_id="next")
    async def next_button(self, interaction: Interaction, button: Button):
        await interaction.response.defer()

        self.current_page = min(self.current_page + 1, len(self.embeds) - 1)
        self.page_count.label = f"{self.current_page + 1}/{len(self.embeds)}"

        if self.current_page == len(self.embeds) - 1:
            self.next_button.disabled = True
            self.last_button.disabled = True

        self.first_button.disabled = False
        self.prev_button.disabled = False

        await self._set_footer(interaction)
        await interaction.edit_original_response(
            embeds=self.embeds[self.current_page],
            view=self,
        )

    # Last page
    @button(emoji="⏭️", style=ButtonStyle.green, custom_id="last")
    async def last_button(self, interaction: Interaction, button: Button):
        await interaction.response.defer()

        self.current_page = len(self.embeds) - 1
        self.page_count.label = f"{self.current_page + 1}/{len(self.embeds)}"

        self.first_button.disabled = False
        self.prev_button.disabled = False
        self.next_button.disabled = True
        self.last_button.disabled = True

        await self._set_footer(interaction)
        await interaction.edit_original_response(
            embeds=self.embeds[self.current_page],
            view=self,
        )

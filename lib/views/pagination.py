from typing import Sequence

from discord import ButtonStyle, Colour, Embed, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, View, button
from sqlalchemy import select
from sqlalchemy.orm import InstrumentedAttribute

from lib.helpers.page_generators import generate_lb_embeds
from lib.sql.sql import LeaderboardUserStats, get_session


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


class LeaderboardReloadPageView(PaginationView):
    def __init__(
        self,
        embeds: list[Embed] | list[list[Embed]],
        timeout: float,
        title: str,
        error_description: str,
        sort_type: InstrumentedAttribute[int],
        reload_type: str,
        error_emoji: str,
        page_offset: int = 0,
        footer_embed: int = -1,
    ):
        super().__init__(embeds, timeout, [], page_offset, footer_embed)

        self.title = title
        self.error_description = error_description
        self.sort_type = sort_type
        self.reload_type = reload_type
        self.error_emoji = error_emoji

    # Reload
    @button(
        label="Reload Data",
        emoji="🔃",
        style=ButtonStyle.secondary,
        custom_id="reload",
        row=1,
    )
    async def reload_button(self, interaction: Interaction, button: Button):
        await interaction.response.defer()

        if not interaction.guild:
            return

        async with get_session() as session:
            stmt = (
                select(LeaderboardUserStats)
                .where(LeaderboardUserStats.guild_id == interaction.guild.id)
                .order_by(self.sort_type.desc())
                .limit(1000)
            )
            result = await session.execute(stmt)
            top_users = result.scalars().all()

            if not top_users:
                embed = Embed(
                    title=f"{self.error_emoji} No Data",
                    description=self.error_description,
                    colour=Colour.red(),
                )
                await interaction.followup.send(embed=embed)
                return

            self.embeds = [
                [embed]
                for embed in generate_lb_embeds(
                    guild=interaction.guild,
                    author=interaction.user,
                    top_users=top_users,
                    title=self.title,
                    attr=self.reload_type,
                )
            ]

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


class PageControls(ActionRow):
    def __init__(self, layout: PaginationV2View):
        super().__init__()
        self.layout = layout

    @button(emoji="⏮️", style=ButtonStyle.red, custom_id="first")
    async def first_button(self, interaction: Interaction, button: Button):
        await interaction.response.defer()
        self.layout.current_page = 0
        await self.layout._update_page(interaction)

    @button(emoji="⏪", style=ButtonStyle.primary, custom_id="prev")
    async def prev_button(self, interaction: Interaction, button: Button):
        await interaction.response.defer()
        self.layout.current_page = max(self.layout.current_page - 1, 0)
        await self.layout._update_page(interaction)

    @button(label="1/1", style=ButtonStyle.gray, custom_id="count", disabled=True)
    async def page_count_label(self, interaction: Interaction, button: Button):
        pass

    @button(emoji="⏩", style=ButtonStyle.primary, custom_id="next")
    async def next_button(self, interaction: Interaction, button: Button):
        await interaction.response.defer()
        self.layout.current_page = min(self.layout.current_page + 1, len(self.layout.pages) - 1)
        await self.layout._update_page(interaction)

    @button(emoji="⏭️", style=ButtonStyle.green, custom_id="last")
    async def last_button(self, interaction: Interaction, button: Button):
        await interaction.response.defer()
        self.layout.current_page = len(self.layout.pages) - 1
        await self.layout._update_page(interaction)


class PaginationV2View(LayoutView):
    def __init__(self, pages: Sequence[Container]):
        super().__init__()

        self.pages = pages
        self.current_page = 0

        if self.pages:
            self.add_item(self.pages[0])

            self.page_controls = PageControls(self)
            self.page_count_label = self.page_controls.page_count_label
            self.page_count_label.label = f"1/{len(self.pages)}"

            self.page_controls.first_button.disabled = True
            self.page_controls.prev_button.disabled = True

            if len(self.pages) == 1:
                self.page_controls.next_button.disabled = True
                self.page_controls.last_button.disabled = True

            self.add_item(self.page_controls)

    async def _update_page(self, interaction: Interaction):
        # Clear all items
        self.clear_items()

        # Add current page
        self.add_item(self.pages[self.current_page])
        self.add_item(self.page_controls)
        self.page_count_label.label = f"{self.current_page + 1}/{len(self.pages)}"

        # Update button states
        self.page_controls.first_button.disabled = self.current_page == 0
        self.page_controls.prev_button.disabled = self.current_page == 0
        self.page_controls.next_button.disabled = self.current_page == len(self.pages) - 1
        self.page_controls.last_button.disabled = self.current_page == len(self.pages) - 1

        await interaction.edit_original_response(view=self)

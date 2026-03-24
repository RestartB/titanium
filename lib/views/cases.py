from typing import TYPE_CHECKING, Optional

import discord

from lib.embeds.cases import case_embed, comment_deleted, comment_edited, not_your_comment
from lib.embeds.general import guild_only
from lib.helpers.components import embed_to_v2
from lib.sql.sql import ModCase, ModCaseComment
from lib.views.pagination import PaginationV2View

if TYPE_CHECKING:
    from main import TitaniumBot


class CommentModal(discord.ui.Modal, title="Enter Content"):
    def __init__(self, case: Optional[ModCase] = None, comment: Optional[ModCaseComment] = None):
        super().__init__(timeout=360)

        if not case and not comment:
            raise ValueError("No case or comment was provided")

        self.case = case
        self.comment = comment

        if comment:
            if not isinstance(self.comment_label.component, discord.ui.TextInput):
                return

            self.comment_label.component.default = comment.comment

    comment_label = discord.ui.Label(
        text="Content",
        description="Enter the content of the comment here.",
        component=discord.ui.TextInput(
            style=discord.TextStyle.long,
            min_length=1,
            max_length=1000,
            required=True,
        ),
    )

    async def on_submit(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        await interaction.response.defer(ephemeral=True)

        if not isinstance(interaction.user, discord.Member) or not interaction.guild:
            await interaction.edit_original_response(
                view=embed_to_v2(guild_only(interaction.client))
            )
            return

        if not isinstance(self.comment_label.component, discord.ui.TextInput):
            raise Exception("Text input component is of wrong type")

        if self.comment:
            await self.comment.edit_comment(self.comment_label.component.value)

            await interaction.edit_original_response(
                view=embed_to_v2(comment_edited(interaction.client))
            )
        elif self.case:
            await self.case.add_comment(
                member=interaction.user,
                content=self.comment_label.component.value,
                bot=interaction.client,
                guild=interaction.guild,
            )

            await interaction.followup.send(
                view=embed_to_v2(comment_edited(interaction.client)), ephemeral=True
            )
        else:
            raise ValueError("No case or comment was available")


class DeleteCommentButton(discord.ui.Button):
    def __init__(self, comment: ModCaseComment) -> None:
        super().__init__(label="Delete", emoji="🗑️", style=discord.ButtonStyle.red)
        self.comment = comment

    async def callback(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id != self.comment.user_id:
            await interaction.edit_original_response(
                view=embed_to_v2(not_your_comment(interaction.client))
            )
            return

        await self.comment.delete_comment()
        await interaction.edit_original_response(
            view=embed_to_v2(comment_deleted(interaction.client))
        )


class EditCommentButton(discord.ui.Button):
    def __init__(self, comment: ModCaseComment) -> None:
        super().__init__(label="Edit", emoji="✏️", style=discord.ButtonStyle.secondary)
        self.comment = comment

    async def callback(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        if interaction.user.id != self.comment.user_id:
            await interaction.edit_original_response(
                view=embed_to_v2(not_your_comment(interaction.client))
            )
            return

        modal = CommentModal(comment=self.comment)
        await interaction.response.send_modal(modal)


class OptionsRow(discord.ui.ActionRow):
    def __init__(self, comment: ModCaseComment) -> None:
        super().__init__()

        self.add_item(EditCommentButton(comment))
        self.add_item(DeleteCommentButton(comment))


class MenuButton(discord.ui.Button):
    def __init__(self, bot: TitaniumBot, comment: ModCaseComment) -> None:
        super().__init__(emoji=bot.menu_emoji)
        self.comment = comment

    async def callback(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id != self.comment.user_id:
            await interaction.followup.send(
                view=embed_to_v2(not_your_comment(interaction.client)), ephemeral=True
            )
            return

        view = discord.ui.LayoutView()
        options_row = OptionsRow(self.comment)

        await interaction.followup.send(view=view.add_item(options_row), ephemeral=True)


class Comment(discord.ui.Section):
    def __init__(self, bot: TitaniumBot, comment: ModCaseComment) -> None:
        super().__init__(accessory=MenuButton(bot, comment))
        self.add_item(
            discord.ui.TextDisplay(
                content=f"-# <@{comment.user_id}> - <t:{int(comment.time_created.timestamp())}:d>\n{discord.utils.escape_markdown(discord.utils.escape_mentions(comment.comment))}"
            )
        )


class CommentPageContainer(discord.ui.Container):
    def __init__(
        self,
        bot: TitaniumBot,
        case: ModCase,
        comments: list[ModCaseComment],
        show_case_button: bool = True,
    ):
        super().__init__(accent_colour=discord.Colour.light_grey())

        self.add_item(
            discord.ui.TextDisplay(
                content=f"## `{case.id}` - Comments\n{bot.info_emoji} There are **{len(case.comments)} comment{'s' if len(case.comments) > 1 else ''}** to show."
            )
        )

        self.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))

        for comment in comments:
            self.add_item(Comment(bot, comment))

        self.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))

        buttons = discord.ui.ActionRow()

        if show_case_button:
            buttons.add_item(ViewCaseButton(case=case, bot=bot))

        buttons.add_item(
            discord.ui.Button(
                label="View all comments",
                url=f"https://dash.titaniumbot.me/guild/{case.guild_id}/moderation/cases/{case.id}",
                style=discord.ButtonStyle.link,
            )
        )

        self.add_item(buttons)


class ViewCaseButton(discord.ui.Button):
    def __init__(self, case: ModCase, bot: TitaniumBot):
        super().__init__(label="View case", emoji=bot.info_emoji)
        self.case = case

    async def callback(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        await interaction.response.defer(ephemeral=True)

        if (
            not isinstance(interaction.user, discord.Member)
            or not interaction.user.guild_permissions.manage_guild
        ):
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Missing Permissions",
                description="You are missing Manage Server permissions to use this feature.",
                colour=discord.Colour.red(),
            )

            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Get creator
        creator = interaction.client.get_user(self.case.creator_user_id)

        if not creator:
            creator = self.case.creator_user_id

        # Get target
        target = interaction.client.get_user(self.case.user_id)

        if not target:
            target = self.case.user_id

        await interaction.followup.send(
            embed=case_embed(
                bot=interaction.client,
                case=self.case,
                creator=creator,
                target=target,
            ),
            view=discord.ui.View().add_item(
                discord.ui.Button(
                    label="View in browser",
                    url=f"https://dash.titaniumbot.me/guild/{self.case.guild_id}/moderation/cases/{self.case.id}",
                    style=discord.ButtonStyle.link,
                )
            ),
            ephemeral=True,
        )


class ViewCommentsButton(discord.ui.Button):
    def __init__(self, case: ModCase):
        super().__init__(label="View comments", emoji="💬")
        self.case = case

    async def callback(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        await interaction.response.defer(ephemeral=True)

        if (
            not isinstance(interaction.user, discord.Member)
            or not interaction.user.guild_permissions.manage_guild
        ):
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Missing Permissions",
                description="You are missing Manage Server permissions to use this feature.",
                colour=discord.Colour.red(),
            )

            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        pages: list[CommentPageContainer] = []
        current_page = []

        for comment in self.case.comments:
            current_page.append(comment)

            if len(current_page) % 5 != 0:
                continue

            container = CommentPageContainer(
                interaction.client, self.case, current_page, show_case_button=False
            )
            pages.append(container)
            current_page = []

        if current_page:
            container = CommentPageContainer(
                interaction.client, self.case, current_page, show_case_button=False
            )
            pages.append(container)

        layout = PaginationV2View(pages)
        await interaction.followup.send(
            view=layout, allowed_mentions=discord.AllowedMentions.none(), ephemeral=True
        )

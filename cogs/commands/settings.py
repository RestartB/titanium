from typing import TYPE_CHECKING

import discord
from discord import (
    AllowedMentions,
    ButtonStyle,
    Colour,
    Embed,
    Interaction,
    SeparatorSpacing,
    app_commands,
)
from discord.ext import commands
from discord.ui import (
    ActionRow,
    Button,
    Container,
    LayoutView,
    Modal,
    Section,
    Select,
    Separator,
    TextDisplay,
    TextInput,
    Thumbnail,
)
from sqlalchemy import delete, select
from sqlalchemy.orm.attributes import flag_modified

from lib.embeds.general import cancelled
from lib.helpers.hybrid import SlashCommandOnly
from lib.helpers.strings import dashboard_url
from lib.helpers.validation import is_valid_uuid
from lib.sql.sql import (
    GameStat,
    GuildSettings,
    LeaderboardUserStats,
    ModCaseComment,
    OptOutIDs,
    Reminder,
    Tag,
    UserRep,
    get_session,
)
from lib.views.confirm import ConfirmView
from lib.views.pagination import PaginationV2View
from lib.views.tags_modals import TagModal

if TYPE_CHECKING:
    from main import TitaniumBot


# region Buttons
class OpenPageButton(Button["SettingsView"]):
    def __init__(
        self,
        target_view: LayoutView,
        label: str = "",
        style: discord.ButtonStyle = ButtonStyle.secondary,
        disabled: bool = False,
    ) -> None:
        super().__init__(label=label, style=style, disabled=disabled)
        self.target_view = target_view

    async def callback(self, interaction: Interaction["TitaniumBot"]) -> None:
        await interaction.response.defer(ephemeral=True)
        await interaction.edit_original_response(
            view=self.target_view, allowed_mentions=AllowedMentions.none()
        )


class FeatureToggleButton(Button["SettingsView"]):
    def __init__(self, bot: TitaniumBot, settings: GuildSettings, feature_attr: str) -> None:
        super().__init__(label="\N{BELL}", style=ButtonStyle.green)

        self.bot = bot
        self.settings = settings
        self.feature_attr = feature_attr

        self.update_button()

    def update_button(self):
        enabled = getattr(self.settings, self.feature_attr)
        if enabled:
            self.label = "Enabled"
            self.emoji = self.bot.success_emoji
            self.style = ButtonStyle.green
        else:
            self.label = "Disabled"
            self.emoji = self.bot.error_emoji
            self.style = ButtonStyle.red

    async def callback(self, interaction: Interaction["TitaniumBot"]) -> None:
        if not interaction.guild_id:
            raise RuntimeError("No guild ID")

        if not interaction.permissions.administrator:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Not Allowed",
                description="You must have the Administrator permission to complete this action.",
                colour=Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        current_value = getattr(self.settings, self.feature_attr)
        new_value = not current_value

        async with get_session() as session:
            guild_settings = await session.get(GuildSettings, interaction.guild_id)
            if not guild_settings:
                guild_settings = GuildSettings(guild_id=interaction.guild_id)
                session.add(guild_settings)

            setattr(guild_settings, self.feature_attr, new_value)
        await self.bot.refresh_guild_config_cache(interaction.guild_id)

        self.settings = guild_settings
        self.update_button()

        await interaction.response.edit_message(
            view=self.view, allowed_mentions=AllowedMentions.none()
        )


class BackButtonHomeReload(Button["SettingsView"]):
    def __init__(self) -> None:
        super().__init__(label="Back", style=ButtonStyle.red)

    async def callback(self, interaction: Interaction["TitaniumBot"]) -> None:
        await interaction.response.defer(ephemeral=True)

        guild_settings = None
        if (
            interaction.is_guild_integration()
            and interaction.guild
            and isinstance(interaction.user, discord.Member)
        ):
            guild_settings = await interaction.client.fetch_guild_config(interaction.guild.id)

        await interaction.edit_original_response(
            view=SettingsView(interaction, interaction.client, guild_settings),
            allowed_mentions=AllowedMentions.none(),
        )


# endregion


# region Tag Views
def _get_if_server_tag_allowed(
    interaction: discord.Interaction["TitaniumBot"], config: GuildSettings | None
) -> bool:
    return bool(
        interaction.guild
        and isinstance(interaction.user, discord.Member)
        and interaction.is_guild_integration()
        and interaction.permissions.manage_guild
        and config
        and config.tags_enabled
    )


async def build_tags_pagination_view(
    interaction: discord.Interaction["TitaniumBot"],
    user_tag: bool,
    previous_view: LayoutView | None,
) -> LayoutView:
    if user_tag:
        stmt = (
            select(Tag)
            .where(Tag.is_user, Tag.owner_id == interaction.user.id)
            .order_by(Tag.name.asc())
        )
    else:
        stmt = select(Tag).where(Tag.guild_id == interaction.guild_id).order_by(Tag.name.asc())

    async with get_session() as session:
        tags = (await session.execute(stmt)).scalars().all()

    if len(tags) == 0:
        container_pages = [
            SelectTagContainer(
                this_page=[],
                user_tag=user_tag,
                previous_view=previous_view,
            )
        ]
        view = PaginationV2View(container_pages, timeout=600)
        return view

    pages: list[list[Tag]] = []
    page: list[Tag] = []
    for i, tag in enumerate(tags, start=1):
        page.append(tag)

        if i % 25 == 0:
            pages.append(page)
            page = []
    if page:
        pages.append(page)

    container_pages = [
        SelectTagContainer(
            this_page=page,
            user_tag=user_tag,
            previous_view=previous_view,
        )
        for page in pages
    ]
    view = PaginationV2View(container_pages, timeout=600)

    for container_page in container_pages:
        container_page.dropdown.my_view = view

    return view


class BackButtonTagReload(Button["SettingsView"]):
    def __init__(self, user_tag: bool, previous_view: PaginationV2View) -> None:
        super().__init__(label="Back", style=ButtonStyle.red)
        self.user_tag = user_tag
        self.previous_view = previous_view

    async def callback(self, interaction: Interaction["TitaniumBot"]) -> None:
        await interaction.response.defer(ephemeral=True)
        view = await build_tags_pagination_view(
            interaction=interaction,
            user_tag=self.user_tag,
            previous_view=self.previous_view.pages[0].previous_view
            if isinstance(self.previous_view.pages[0], SelectTagContainer)
            else None,
        )
        await interaction.edit_original_response(view=view, allowed_mentions=AllowedMentions.none())


class TagActionsOptionRow(ActionRow):
    def __init__(
        self, tag: str, user_tag: bool, previous_view: PaginationV2View, my_view: LayoutView
    ) -> None:
        super().__init__()
        self.tag = tag
        self.user_tag = user_tag
        self.previous_view = previous_view
        self.my_view = my_view

    @discord.ui.button(label="Delete", style=ButtonStyle.red)
    async def delete_button(
        self, interaction: discord.Interaction["TitaniumBot"], button: discord.ui.Button
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if button.label == "Delete":
            button.label = "Press again to confirm"
            await interaction.edit_original_response(
                view=self.my_view, allowed_mentions=AllowedMentions.none()
            )
            return

        config = (
            await interaction.client.fetch_guild_config(interaction.guild_id)
            if interaction.guild_id and interaction.is_guild_integration()
            else None
        )

        if not self.user_tag and not _get_if_server_tag_allowed(interaction, config):
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} No Permissions",
                description="You are not allowed to create or modify server tags. Please ensure you have the **Manage Guild** permission.",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        async with get_session() as session:
            to_delete = await session.get(Tag, self.tag)

            if (
                not to_delete
                or (
                    self.user_tag
                    and (not to_delete.is_user or to_delete.owner_id != interaction.user.id)
                )
                or (
                    not self.user_tag
                    and (to_delete.is_user or to_delete.guild_id != interaction.guild_id)
                )
            ):
                embed = discord.Embed(
                    title=f"{interaction.client.error_emoji} Not Found",
                    description="Couldn't find the tag. Maybe it was deleted?",
                    colour=discord.Colour.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            await session.delete(to_delete)

        view = await build_tags_pagination_view(
            interaction=interaction,
            user_tag=self.user_tag,
            previous_view=self.previous_view.pages[0].previous_view
            if isinstance(self.previous_view.pages[0], SelectTagContainer)
            else None,
        )
        await interaction.edit_original_response(view=view, allowed_mentions=AllowedMentions.none())

        embed = discord.Embed(
            title=f"{interaction.client.success_emoji} Deleted",
            description=f"The `{to_delete.name}` tag was deleted.",
            colour=Colour.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Edit", style=ButtonStyle.blurple)
    async def edit_button(
        self, interaction: discord.Interaction["TitaniumBot"], button: discord.ui.Button
    ) -> None:
        if not is_valid_uuid(self.tag):
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Invalid Tag",
                description="The provided tag is invalid. Please select a tag from the list.",
                colour=discord.Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        config = (
            await interaction.client.fetch_guild_config(interaction.guild_id)
            if interaction.guild_id and interaction.is_guild_integration()
            else None
        )

        if not self.user_tag and not _get_if_server_tag_allowed(interaction, config):
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} No Permissions",
                description="You are not allowed to create or modify server tags. Please ensure you have the **Manage Guild** permission.",
                colour=discord.Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        async with get_session() as session:
            to_edit = await session.get(Tag, self.tag)

        if (
            not to_edit
            or (self.user_tag and (not to_edit.is_user or to_edit.owner_id != interaction.user.id))
            or (not self.user_tag and (to_edit.is_user or to_edit.guild_id != interaction.guild_id))
        ):
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Not Found",
                description="Couldn't find the tag. Maybe it was deleted?",
                colour=discord.Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        modal = TagModal(
            server_tag_allowed=not self.user_tag,
            user_tag_allowed=self.user_tag,
            existing_tag=to_edit,
        )
        await interaction.response.send_modal(modal)


class TagsActionsView(LayoutView):
    def __init__(self, tag: str, user_tag: bool, previous_view: PaginationV2View) -> None:
        super().__init__(timeout=600)
        self.tag = tag
        self.user_tag = user_tag

        top_section = Section(
            TextDisplay("## Select an action\nEdit or delete the tag."),
            accessory=BackButtonTagReload(user_tag=user_tag, previous_view=previous_view),
        )

        container = Container(
            top_section,
            Separator(spacing=SeparatorSpacing.large),
            TagActionsOptionRow(
                tag=tag, user_tag=user_tag, previous_view=previous_view, my_view=self
            ),
            accent_colour=Colour.light_grey(),
        )

        self.add_item(container)


class TagSelectDropdown(Select):
    def __init__(
        self, tags: list[Tag], user_tag: bool, my_view: PaginationV2View | None = None
    ) -> None:
        super().__init__()
        self.user_tag = user_tag
        self.tags = tags
        self.my_view = my_view

        for tag in tags:
            self.add_option(label=tag.name, value=str(tag.id))

    async def callback(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        await interaction.response.defer(ephemeral=True)

        if not self.values[0]:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Select a Tag",
                description="Please select a tag to continue.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if self.my_view is None:
            raise RuntimeError("my_view must be set before interaction")

        await interaction.edit_original_response(
            view=TagsActionsView(
                tag=self.values[0], user_tag=self.user_tag, previous_view=self.my_view
            ),
            allowed_mentions=AllowedMentions.none(),
        )


class SelectTagContainer(Container):
    def __init__(
        self,
        this_page: list[Tag],
        user_tag: bool,
        previous_view: LayoutView | None,
        my_view: PaginationV2View | None = None,
    ) -> None:
        super().__init__(accent_colour=Colour.light_grey())
        self.previous_view = previous_view

        if previous_view:
            top_section = Section(
                accessory=OpenPageButton(
                    target_view=previous_view, label="Back", style=ButtonStyle.red
                )
            )
        else:
            top_section = Section(
                accessory=Button(label="Back", style=ButtonStyle.red, disabled=True)
            )
        top_section.add_item(TextDisplay("## Select a Tag\nSelect a tag to update or delete."))

        self.add_item(top_section)
        self.add_item(Separator(spacing=SeparatorSpacing.large))

        if len(this_page) == 0:
            self.add_item(TextDisplay("**No tags were found.**"))
        else:
            self.dropdown = TagSelectDropdown(tags=this_page, user_tag=user_tag, my_view=my_view)
            self.add_item(ActionRow(self.dropdown))


class ServerTagsActionRow(ActionRow):
    def __init__(self, previous_view: LayoutView) -> None:
        super().__init__()
        self.previous_view = previous_view

    @discord.ui.button(label="Add", style=ButtonStyle.green)
    async def add_button(
        self, interaction: discord.Interaction["TitaniumBot"], button: discord.ui.Button
    ):
        config = (
            await interaction.client.fetch_guild_config(interaction.guild_id)
            if interaction.guild_id and interaction.is_guild_integration()
            else None
        )
        server_tag_allowed = _get_if_server_tag_allowed(interaction, config)

        if not server_tag_allowed:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Not Allowed",
                description="You are not allowed to manage server tags in this server.",
                colour=discord.Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        modal = TagModal(server_tag_allowed=server_tag_allowed, user_tag_allowed=False)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Update or Remove", style=ButtonStyle.blurple)
    async def modify_button(
        self, interaction: discord.Interaction["TitaniumBot"], button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)

        config = (
            await interaction.client.fetch_guild_config(interaction.guild_id)
            if interaction.guild_id and interaction.is_guild_integration()
            else None
        )
        server_tag_allowed = _get_if_server_tag_allowed(interaction, config)

        if not server_tag_allowed:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Not Allowed",
                description="You are not allowed to manage server tags in this server.",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        view = await build_tags_pagination_view(
            interaction=interaction, user_tag=False, previous_view=self.previous_view
        )
        await interaction.edit_original_response(view=view, allowed_mentions=AllowedMentions.none())


class UserTagsActionRow(ActionRow):
    def __init__(self, previous_view: LayoutView) -> None:
        super().__init__()
        self.previous_view = previous_view

    @discord.ui.button(label="Add", style=ButtonStyle.green)
    async def add_button(
        self, interaction: discord.Interaction["TitaniumBot"], button: discord.ui.Button
    ):
        user_tag_allowed = interaction.user.id not in interaction.client.opt_out
        if not user_tag_allowed:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Opted Out",
                description="You have opted out of optional data collection, so you are not allowed to manage user tags.",
                colour=discord.Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        modal = TagModal(server_tag_allowed=False, user_tag_allowed=user_tag_allowed)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Update or Remove", style=ButtonStyle.blurple)
    async def modify_button(
        self, interaction: discord.Interaction["TitaniumBot"], button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)
        view = await build_tags_pagination_view(
            interaction=interaction, user_tag=True, previous_view=self.previous_view
        )
        await interaction.edit_original_response(view=view, allowed_mentions=AllowedMentions.none())


class ServerTagsView(LayoutView):
    def __init__(
        self,
    ) -> None:
        super().__init__(timeout=600)

        top_section = Section(
            TextDisplay("## Server Tags\nAdd, delete or update server tags."),
            accessory=BackButtonHomeReload(),
        )

        container = Container(
            top_section,
            Separator(spacing=SeparatorSpacing.large),
            ServerTagsActionRow(previous_view=self),
            accent_colour=Colour.light_grey(),
        )
        self.add_item(container)


class UserTagsView(LayoutView):
    def __init__(
        self,
    ) -> None:
        super().__init__(timeout=600)

        top_section = Section(
            TextDisplay("## User Tags\nAdd, delete or update user tags."),
            accessory=BackButtonHomeReload(),
        )

        container = Container(
            top_section,
            Separator(spacing=SeparatorSpacing.large),
            UserTagsActionRow(previous_view=self),
            accent_colour=Colour.light_grey(),
        )
        self.add_item(container)


# endregion


# region Prefix Views
class PrefixModal(Modal, title="Add Prefix"):
    def __init__(self, previous_view: LayoutView) -> None:
        super().__init__()
        self.previous_view = previous_view

        self.prefix_input = TextInput(label="Prefix", placeholder="t!", min_length=1, max_length=5)
        self.add_item(self.prefix_input)

    async def on_submit(self, interaction: Interaction["TitaniumBot"]) -> None:
        if not interaction.guild_id:
            raise RuntimeError("No guild ID")

        await interaction.response.defer(ephemeral=True)

        if not interaction.permissions.administrator:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Not Allowed",
                description="You must have the Administrator permission to complete this action.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        async with get_session() as session:
            guild_settings = await session.get(GuildSettings, interaction.guild_id)

            if not guild_settings:
                guild_settings = GuildSettings(guild_id=interaction.guild_id)
                session.add(guild_settings)

            if len(guild_settings.prefixes) >= 5:
                embed = discord.Embed(
                    title=f"{interaction.client.error_emoji} Limit Reached",
                    description="You can only have up to 5 custom prefixes.",
                    colour=Colour.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            guild_settings.prefixes.append(self.prefix_input.value)
            flag_modified(guild_settings, "prefixes")

        await interaction.client.refresh_guild_config_cache(interaction.guild_id)
        await interaction.edit_original_response(
            view=PrefixView(interaction.client, guild_settings, self.previous_view),
            allowed_mentions=AllowedMentions.none(),
        )


class AddPrefixButton(Button["PrefixView"]):
    def __init__(self, previous_view: LayoutView) -> None:
        super().__init__(label="Add Prefix", style=ButtonStyle.green)
        self.previous_view = previous_view

    async def callback(self, interaction: Interaction["TitaniumBot"]) -> None:
        if not interaction.permissions.administrator:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Not Allowed",
                description="You must have the Administrator permission to complete this action.",
                colour=Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.send_modal(PrefixModal(self.previous_view))


class PrefixDropdown(Select):
    def __init__(self, prefixes: list[str], previous_view: LayoutView) -> None:
        super().__init__()
        self.prefixes = prefixes
        self.previous_view = previous_view

        for prefix in prefixes:
            self.add_option(label=prefix)

    async def callback(self, interaction: Interaction["TitaniumBot"]) -> None:
        if not interaction.guild_id:
            raise RuntimeError("No guild ID")

        await interaction.response.defer(ephemeral=True)

        if not interaction.permissions.administrator:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Not Allowed",
                description="You must have the Administrator permission to complete this action.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        async with get_session() as session:
            guild_settings = await session.get(GuildSettings, interaction.guild_id)

            if not guild_settings:
                guild_settings = GuildSettings(guild_id=interaction.guild_id)
                session.add(guild_settings)

            try:
                guild_settings.prefixes.remove(self.values[0])
                flag_modified(guild_settings, "prefixes")
            except ValueError:
                embed = discord.Embed(
                    title=f"{interaction.client.error_emoji} Not Found",
                    description="Couldn't find the prefix to remove.",
                    colour=Colour.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

        await interaction.client.refresh_guild_config_cache(interaction.guild_id)
        await interaction.edit_original_response(
            view=PrefixView(interaction.client, guild_settings, self.previous_view),
            allowed_mentions=AllowedMentions.none(),
        )

        embed = discord.Embed(
            title=f"{interaction.client.success_emoji} Deleted",
            description=f"The `{self.values[0]}` prefix was deleted.",
            colour=Colour.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


class PrefixView(LayoutView):
    def __init__(
        self, bot: TitaniumBot, settings: GuildSettings, previous_view: LayoutView
    ) -> None:
        super().__init__(timeout=600)

        top_section = Section(
            TextDisplay(
                "## Prefixes\nManage the prefixes that Titanium will respond to. You can also ping Titanium or use slash commands."
            ),
            accessory=BackButtonHomeReload(),
        )

        allow_prefix = Section(
            TextDisplay(
                "### Allow Prefix Commands\nAllow server members to interact with Titanium using prefix commands, as well as slash commands. Slash commands are always enabled."
            ),
            accessory=FeatureToggleButton(bot=bot, settings=settings, feature_attr="allow_prefix"),
        )
        not_allowed = Section(
            TextDisplay(
                "### Send Not Allowed Error\nSend a not allowed error to the user if they try to run prefix commands when they are disabled, in a blacklisted channel, or when they have a blacklisted role."
            ),
            accessory=FeatureToggleButton(
                bot=bot, settings=settings, feature_attr="send_not_allowed"
            ),
        )
        loading = Section(
            TextDisplay(
                "### Show Loading Reaction\nEnable or disable the loading reaction that appears when Titanium is processing a prefix command. The loading indicator will always show for slash commands."
            ),
            accessory=FeatureToggleButton(
                bot=bot, settings=settings, feature_attr="loading_reaction"
            ),
        )

        container = Container(
            top_section,
            Separator(spacing=SeparatorSpacing.large),
            allow_prefix,
            not_allowed,
            loading,
            Separator(spacing=SeparatorSpacing.small),
            TextDisplay(
                f"### Blocked Channels & Roles\nAdd channels and roles that Titanium will ignore prefix commands from in the {dashboard_url(settings.guild_id)}."
            ),
            Separator(spacing=SeparatorSpacing.small),
            TextDisplay("### Prefix List\nThe list of prefixes that Titanium will respond to."),
            TextDisplay(
                f"{bot.user.mention if bot.user else '`@Titanium`'}, `{'`, `'.join(settings.prefixes)}`"
                if settings.prefixes
                else f"{bot.user.mention if bot.user else '`@Titanium`'}"
            ),
            accent_colour=Colour.light_grey(),
        )

        if len(settings.prefixes) < 5:
            container.add_item(Separator(spacing=SeparatorSpacing.small))
            container.add_item(
                TextDisplay(
                    "### Add Prefix\nClick the button below to add a new prefix to the list."
                )
            )
            container.add_item(ActionRow(AddPrefixButton(previous_view=previous_view)))

        self.dropdown = PrefixDropdown(prefixes=settings.prefixes, previous_view=previous_view)
        if settings.prefixes:
            container.add_item(Separator(spacing=SeparatorSpacing.small))
            container.add_item(
                TextDisplay(
                    "### Remove Prefix\nSelect a prefix from the dropdown below to remove it."
                )
            )
            container.add_item(ActionRow(self.dropdown))

        self.add_item(container)


# endregion


class ModulesView(LayoutView):
    def __init__(
        self,
        bot: TitaniumBot,
        settings: GuildSettings,
    ) -> None:
        super().__init__(timeout=600)

        top_section = Section(
            TextDisplay("## Modules\nEnable or disable various feature modules."),
            accessory=BackButtonHomeReload(),
        )
        mod_section = Section(
            TextDisplay("### Moderation\nModerate your server members and create cases."),
            accessory=FeatureToggleButton(bot, settings, "moderation_enabled"),
        )
        automod_section = Section(
            TextDisplay(
                "### Automod\nAllow Titanium to moderate your server for you. Requires **Moderation** module to be enabled."
            ),
            accessory=FeatureToggleButton(bot, settings, "automod_enabled"),
        )
        bouncer_section = Section(
            TextDisplay(
                "### Bouncer\nAllow Titanium to monitor users as they join. Requires **Moderation** module to be enabled."
            ),
            accessory=FeatureToggleButton(bot, settings, "bouncer_enabled"),
        )
        logging_section = Section(
            TextDisplay("### Logging\nLog various events that happen in your server."),
            accessory=FeatureToggleButton(bot, settings, "logging_enabled"),
        )
        fireboard_section = Section(
            TextDisplay("### Fireboard\nLet server members highlight messages they love."),
            accessory=FeatureToggleButton(bot, settings, "fireboard_enabled"),
        )
        leaderboard_section = Section(
            TextDisplay("### Leaderboard\nTrack engagement and activity in your server."),
            accessory=FeatureToggleButton(bot, settings, "leaderboard_enabled"),
        )
        server_counters_section = Section(
            TextDisplay(
                "### Server Counters\nDisplay various server statistics and counters in your channel list."
            ),
            accessory=FeatureToggleButton(bot, settings, "server_counters_enabled"),
        )
        confessions_section = Section(
            TextDisplay("### Confessions\nAllow server members to make anonymous confessions."),
            accessory=FeatureToggleButton(bot, settings, "confessions_enabled"),
        )
        tags_section = Section(
            TextDisplay("### Tags\nSend server wide quick responses with key words."),
            accessory=FeatureToggleButton(bot, settings, "tags_enabled"),
        )
        rep_section = Section(
            TextDisplay("### Rep\nThank members by giving them rep points."),
            accessory=FeatureToggleButton(bot, settings, "rep_enabled"),
        )

        container = Container(
            top_section,
            Separator(spacing=SeparatorSpacing.large),
            mod_section,
            automod_section,
            bouncer_section,
            logging_section,
            fireboard_section,
            leaderboard_section,
            server_counters_section,
            confessions_section,
            tags_section,
            rep_section,
            accent_colour=Colour.light_grey(),
        )

        self.add_item(container)


class SettingsView(LayoutView):
    def __init__(
        self,
        interaction: Interaction["TitaniumBot"],
        bot: TitaniumBot,
        settings: GuildSettings | None,
    ) -> None:
        super().__init__(timeout=600)

        if settings and interaction.guild:
            if interaction.guild.icon:
                top_section = Section(
                    TextDisplay(
                        f"## Settings\nManage settings for your account and this server. To manage more server settings, please go to the {dashboard_url(interaction.guild.id)}."
                    ),
                    accessory=Thumbnail(media=interaction.guild.icon.url),
                )
            else:
                top_section = TextDisplay(
                    f"## Settings\nManage settings for your account and this server. To manage more server settings, please go to the {dashboard_url(interaction.guild.id)}."
                )
        else:
            if bot.user:
                top_section = Section(
                    TextDisplay("## Settings\nManage settings for your account."),
                    accessory=Thumbnail(media=bot.user.display_avatar.url),
                )
            else:
                top_section = TextDisplay("## Settings\nManage settings for your account.")

        container = Container(
            top_section,
            Separator(spacing=SeparatorSpacing.large),
            accent_colour=Colour.light_grey(),
        )

        if settings and interaction.permissions.administrator:
            modules_section = Section(
                TextDisplay("### Modules\nToggle various Titanium modules in this server."),
                accessory=OpenPageButton(
                    target_view=ModulesView(bot=bot, settings=settings),
                    label="Manage",
                ),
            )
            prefixes_section = Section(
                TextDisplay(
                    "### Prefixes\nManage the prefixes that Titanium will respond to in this server."
                ),
                accessory=OpenPageButton(
                    target_view=PrefixView(bot=bot, settings=settings, previous_view=self),
                    label="Manage",
                ),
            )

            container.add_item(modules_section)
            container.add_item(prefixes_section)

        if _get_if_server_tag_allowed(interaction, settings):
            server_tags_section = Section(
                TextDisplay("### Server Tags\nAdd, delete or update server tags."),
                accessory=OpenPageButton(target_view=ServerTagsView(), label="Manage"),
            )
            container.add_item(server_tags_section)

        user_tags_str = "### User Tags\n"
        if interaction.user.id in interaction.client.opt_out:
            user_tags_str += "You have opted out of optional data collection, so you are not allowed to manage user tags."
        else:
            user_tags_str += "Add, delete and update user tags."

        user_tags_section = Section(
            TextDisplay(user_tags_str),
            accessory=OpenPageButton(
                target_view=UserTagsView(),
                label="Manage",
                disabled=(interaction.user.id in interaction.client.opt_out),
            ),
        )

        container.add_item(user_tags_section)
        self.add_item(container)


class GuildSettingsCog(commands.Cog, name="Settings", description="Manage server settings."):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    @commands.command(name="settings", description="Please use the slash command version instead.")
    async def settings_prefix(self, ctx: commands.Context["TitaniumBot"]) -> None:
        raise SlashCommandOnly

    @app_commands.command(
        name="settings",
        description="Manage Titanium's settings for your account and the server.",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.checks.cooldown(1, 5)
    async def settings(self, interaction: Interaction["TitaniumBot"]) -> None:
        if not self.bot.user:
            return

        await interaction.response.defer(ephemeral=True)

        guild_settings = None
        if (
            interaction.is_guild_integration()
            and interaction.guild
            and isinstance(interaction.user, discord.Member)
        ):
            guild_settings = await self.bot.fetch_guild_config(interaction.guild.id)

        view = SettingsView(interaction, self.bot, guild_settings)
        await interaction.followup.send(
            view=view, ephemeral=True, allowed_mentions=discord.AllowedMentions.none()
        )

    @app_commands.command(
        name="opt-out",
        description="Opt out of optional data collection, and delete optional data stored in Titanium's systems.",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.checks.cooldown(1, 10)
    async def remove_data(self, interaction: Interaction["TitaniumBot"]) -> None:
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id in self.bot.opt_out:
            await interaction.followup.send(
                embed=Embed(
                    title=f"{self.bot.success_emoji} Already Opted Out",
                    description="You are already opted out of optional data collection.",
                    colour=Colour.green(),
                ),
                ephemeral=True,
            )
            return

        embed = Embed(
            title=f"{self.bot.warn_emoji} Are you sure?",
            description="If you opt out, Titanium will delete optional data associated with your account (such as tags and leaderboard stats). New optional data will not be collected unless you opt in again.",
            colour=Colour.orange(),
        )
        embed.add_field(
            name=f"{self.bot.info_emoji} Required Data",
            value="You cannot opt out of required operational data, including command analytics, error logs, server (guild) data, and moderation cases.",
        )

        view = ConfirmView(bot=self.bot, original_user=interaction.user, ephemeral=True)
        view.interaction = interaction

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        timed_out = await view.wait()

        if timed_out or not view.value:
            await view.interaction.edit_original_response(embed=cancelled(self.bot), view=None)
            return

        if interaction.user.id in self.bot.opt_out:
            await view.interaction.edit_original_response(
                embed=Embed(
                    title=f"{self.bot.success_emoji} Already Opted Out",
                    description="You are already opted out of optional data collection.",
                    colour=Colour.green(),
                ),
                view=None,
            )
            return

        async with get_session() as session:
            opt_out_entry = OptOutIDs(id=interaction.user.id)
            session.add(opt_out_entry)

            await session.commit()
            await self.bot.refresh_opt_out()

            # fmt: off
            await session.execute(delete(LeaderboardUserStats).where(LeaderboardUserStats.user_id == interaction.user.id))
            await session.execute(delete(Tag).where(Tag.is_user, Tag.owner_id == interaction.user.id))
            await session.execute(delete(Reminder).where(Reminder.user_id == interaction.user.id))
            await session.execute(delete(ModCaseComment).where(ModCaseComment.user_id == interaction.user.id))
            await session.execute(delete(GameStat).where(GameStat.user_id == interaction.user.id))
            await session.execute(delete(UserRep).where(UserRep.user_id == interaction.user.id))
            # fmt: on

        await view.interaction.edit_original_response(
            embed=Embed(
                title=f"{self.bot.success_emoji} Opted Out",
                description="You have opted out of future optional data collection. User data has been removed.",
                colour=Colour.green(),
            ),
            view=None,
        )

    @app_commands.command(name="opt-in", description="Opt back into optional data collection.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.checks.cooldown(1, 10)
    async def opt_in(self, interaction: Interaction["TitaniumBot"]) -> None:
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id not in self.bot.opt_out:
            await interaction.followup.send(
                embed=Embed(
                    title=f"{self.bot.success_emoji} Already Opted In",
                    description="You are already opted into data collection, and can make use of all Titanium features.",
                    colour=Colour.green(),
                ),
                ephemeral=True,
            )
            return

        embed = Embed(
            title=f"{self.bot.warn_emoji} Are you sure?",
            description="By opting back into optional data collection, you will be able to use all Titanium features again.",
            colour=Colour.orange(),
        )

        view = ConfirmView(bot=self.bot, original_user=interaction.user, ephemeral=True)
        view.interaction = interaction

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        timed_out = await view.wait()

        if timed_out or not view.value:
            await view.interaction.edit_original_response(embed=cancelled(self.bot), view=None)
            return

        if interaction.user.id not in self.bot.opt_out:
            await view.interaction.edit_original_response(
                embed=Embed(
                    title=f"{self.bot.success_emoji} Already Opted In",
                    description="You are already opted into data collection, and can make use of all Titanium features.",
                    colour=Colour.green(),
                ),
                view=None,
            )
            return

        async with get_session() as session:
            await session.execute(delete(OptOutIDs).where(OptOutIDs.id == interaction.user.id))
        await self.bot.refresh_opt_out()

        await view.interaction.edit_original_response(
            embed=Embed(
                title=f"{self.bot.success_emoji} Opted In",
                description="You have back into optional data collection. You can now use all Titanium features again.",
                colour=Colour.green(),
            ),
            view=None,
        )


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(GuildSettingsCog(bot))

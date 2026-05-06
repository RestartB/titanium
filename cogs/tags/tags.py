import asyncio
from typing import TYPE_CHECKING, Any, Literal

import discord
from discord import app_commands
from discord.ext import commands
from rapidfuzz import fuzz, process
from sqlalchemy import select

from lib.embeds.general import cancelled
from lib.helpers.validation import is_valid_uuid
from lib.sql.sql import Tag, get_session
from lib.views.pagination import PaginationView

if TYPE_CHECKING:
    from main import TitaniumBot

# FIXME: handle confirmation view expiring


class TagOptionView(discord.ui.View):
    def __init__(self, bot: TitaniumBot, timeout: float = 60.0, ephemeral: bool = False):
        super().__init__(timeout=timeout)

        self.value = None
        self.timed_out = False
        self.interaction: discord.Interaction | None = None
        self.ephemeral = ephemeral

    async def on_timeout(self) -> None:
        self.timed_out = True

    @discord.ui.button(label="Server Tag")
    async def server(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=self.ephemeral)

        self.value = True
        self.interaction = interaction
        self.stop()

    @discord.ui.button(label="User Tag")
    async def user(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=self.ephemeral)

        self.value = False
        self.interaction = interaction
        self.stop()


async def tag_autocomplete_base(
    bot: TitaniumBot, interaction: discord.Interaction["TitaniumBot"], current: str, verify: bool
) -> list[app_commands.Choice[str]]:
    if not current:
        return [
            app_commands.Choice(name="Start typing to search for a server or user tag", value="")
        ]

    server_tags_allowed = verify
    user_tags_allowed = True

    if server_tags_allowed and interaction.guild:
        config = await bot.fetch_guild_config(interaction.guild.id)
        if config and not config.tags_enabled:
            user_tags_allowed = False

        if config and config.tag_settings and not config.tag_settings.allow_user_tags:
            user_tags_allowed = False

    server_tags = []
    user_tags = []

    async with get_session() as session:
        if server_tags_allowed and interaction.guild:
            stmt = select(Tag).where(Tag.guild_id == interaction.guild.id)
            results = await session.execute(stmt)
            server_tags = results.scalars().all()

        if user_tags_allowed:
            stmt = select(Tag).where(Tag.owner_id == interaction.user.id, Tag.is_user)
            results = await session.execute(stmt)
            user_tags = results.scalars().all()

    if not server_tags and not user_tags:
        return []

    server_fuzz = None
    if server_tags_allowed and interaction.guild and server_tags:
        server_fuzz = await asyncio.to_thread(
            process.extract,
            current,
            server_tags,
            scorer=fuzz.WRatio,
            limit=5,
            score_cutoff=65,
            processor=lambda tag: tag.name if isinstance(tag, Tag) else tag,
        )

    user_fuzz = None
    if user_tags_allowed and user_tags:
        user_fuzz = await asyncio.to_thread(
            process.extract,
            current,
            user_tags,
            scorer=fuzz.WRatio,
            limit=5,
            score_cutoff=65,
            processor=lambda tag: tag.name if isinstance(tag, Tag) else tag,
        )

    results = []
    if server_fuzz:
        for result in server_fuzz:
            results.append(
                app_commands.Choice(name=f"Server: {result[0].name}", value=str(result[0].id))
            )
    if user_fuzz:
        for result in user_fuzz:
            results.append(
                app_commands.Choice(name=f"User: {result[0].name}", value=str(result[0].id))
            )

    return results


class TagCommandsCog(commands.Cog):
    def __init__(self, bot: TitaniumBot) -> None:
        bot.pre_not_found = self.command_not_found_hook
        self.bot = bot

    def __server_tag_available(
        self, ctx: commands.Context["TitaniumBot"] | discord.Interaction["TitaniumBot"]
    ) -> bool:
        author = ctx.author if isinstance(ctx, commands.Context) else ctx.user
        return bool(
            ctx.guild
            and isinstance(author, discord.Member)
            and ctx.guild.id in [role.id for role in author.roles]
        )

    async def command_not_found_hook(
        self, ctx: commands.Context["TitaniumBot"], error: Any
    ) -> bool:
        if not self.__server_tag_available(ctx) or not ctx.guild:
            return False

        config = await self.bot.fetch_guild_config(ctx.guild.id)
        if not config or (
            not config.tags_enabled
            or not config.tag_settings
            or not config.tag_settings.prefix_fallback
        ):
            return False

        for tag in config.tag_settings.tags:
            if not (tag.name == ctx.invoked_with or str(tag.id) == ctx.invoked_with):
                continue

            await ctx.reply(content=tag.content, allowed_mentions=discord.AllowedMentions.none())
            return True

        return False

    async def tag_autocomplete(
        self, interaction: discord.Interaction["TitaniumBot"], current: str
    ) -> list[app_commands.Choice[str]]:
        return await tag_autocomplete_base(
            bot=self.bot,
            interaction=interaction,
            current=current,
            verify=self.__server_tag_available(interaction),
        )

    async def cog_check(self, ctx: commands.Context["TitaniumBot"]) -> bool:
        await ctx.defer()

        if not ctx.guild:
            return True

        config = await self.bot.fetch_guild_config(ctx.guild.id)
        if not config or not config.tags_enabled:
            await ctx.reply(
                embed=discord.Embed(
                    colour=discord.Colour.red(),
                    title=f"{self.bot.error_emoji} Tags Disabled",
                    description="The tags module is disabled in this server. Ask a server admin to turn it on using the `/settings overview` command or the Titanium Dashboard.",
                ),
                ephemeral=True,
            )
            return False

        if config and config.tags_enabled and not config.tag_settings:
            await ctx.bot.init_guild(ctx.guild.id)

        return True

    # Use tag command
    @commands.hybrid_group(
        name="tag", aliases=["tags"], fallback="use", description="Send a server or user tag."
    )
    @commands.cooldown(1, 3)
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(tag="The tag to send.")
    @app_commands.autocomplete(tag=tag_autocomplete)
    async def tags_group(self, ctx: commands.Context["TitaniumBot"], tag: str):
        if not tag:
            embed = discord.Embed(
                title=f"{ctx.bot.error_emoji} Enter a tag name",
                description="Please enter a tag name when sending the command.",
                colour=discord.Colour.red(),
            )
            return await ctx.reply(embed=embed)

        user_tags_allowed = True
        server_tags_allowed = self.__server_tag_available(ctx)

        if server_tags_allowed and ctx.guild:
            config = await self.bot.fetch_guild_config(ctx.guild.id)
            if config and not config.tags_enabled:
                user_tags_allowed = False

            if config and config.tag_settings and not config.tag_settings.allow_user_tags:
                user_tags_allowed = False

        tag_data: Tag | None = None
        server_result: Tag | None = None
        user_result: Tag | None = None

        async with get_session() as session:
            if is_valid_uuid(tag):
                tag_data = await session.get(Tag, tag)

            if not tag_data:
                if server_tags_allowed and ctx.guild:
                    stmt = select(Tag).where(Tag.name == tag, Tag.guild_id == ctx.guild.id)
                    results = await session.execute(stmt)
                    server_result = results.scalar_one_or_none()

                if user_tags_allowed:
                    stmt = select(Tag).where(
                        Tag.name == tag, Tag.is_user, Tag.owner_id == ctx.author.id
                    )
                    results = await session.execute(stmt)
                    user_result = results.scalar_one_or_none()

        view = None
        if server_result and user_result:
            embed = discord.Embed(
                title=f"{ctx.bot.info_emoji} Select an option",
                description="There is a server tag and user tag available with the same name. Select which one you want to send.",
                colour=discord.Colour.light_grey(),
            )

            view = TagOptionView(self.bot)
            await ctx.reply(embed=embed, view=view)
            await view.wait()

            if not view.interaction:
                raise Exception("Impossible: interaction is missing")

            if view.value is None:
                return await view.interaction.edit_original_response(
                    embed=cancelled(self.bot), view=None
                )

            if view.value:
                tag_data = server_result
            else:
                tag_data = user_result

        if not tag_data:
            tag_data = server_result or user_result

        if (
            not tag_data
            or (tag_data.is_user and tag_data.owner_id != ctx.author.id)
            or (not tag_data.is_user and (not ctx.guild or tag_data.guild_id != ctx.guild.id))
        ):
            embed = discord.Embed(
                title=f"{ctx.bot.error_emoji} Not Found",
                description=f"Couldn't find a tag called `{tag}`.",
                colour=discord.Colour.red(),
            )

            if view and view.interaction:
                return await view.interaction.edit_original_response(embed=embed, view=None)
            else:
                return await ctx.reply(embed=embed)

        if tag_data.is_user and not user_tags_allowed:
            embed = discord.Embed(
                title=f"{ctx.bot.error_emoji} Not Allowed",
                description="A server admin has disabled user tags in this server.",
                colour=discord.Colour.red(),
            )
            if view and view.interaction:
                return await view.interaction.edit_original_response(embed=embed, view=None)
            else:
                return await ctx.reply(embed=embed)

        if view and view.interaction:
            await view.interaction.edit_original_response(
                embed=None,
                view=None,
                content=tag_data.content,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        else:
            await ctx.reply(
                content=tag_data.content, allowed_mentions=discord.AllowedMentions.none()
            )

    # List tags command
    @tags_group.command(
        name="list", aliases=["viewall"], description="View a list of all server or user tags."
    )
    @commands.cooldown(1, 3)
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(mode="Whether to view server or user tags.")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Server Tag", value="server"),
            app_commands.Choice(name="User Tag", value="user"),
        ]
    )
    async def view_all_tags(
        self, ctx: commands.Context["TitaniumBot"], mode: Literal["server", "user"] = "user"
    ):
        if mode == "server" and not self.__server_tag_available(ctx):
            embed = discord.Embed(
                title=f"{ctx.bot.error_emoji} Not Available",
                description="Server tags are only available in servers with Titanium.",
                colour=discord.Colour.red(),
            )
            return await ctx.reply(embed=embed)

        if mode == "server" and ctx.guild:
            stmt = select(Tag).where(Tag.guild_id == ctx.guild.id)
        else:
            stmt = select(Tag).where(Tag.owner_id == ctx.author.id, Tag.is_user)

        async with get_session() as session:
            results = await session.execute(stmt)
            tags = results.scalars().all()

        tags = list(tags)
        tags.sort(key=lambda x: x.name)

        tag_pages: list[discord.Embed] = []
        current_page_tags: list[str] = []

        for tag in tags:
            current_page_tags.append(f"`{tag.name}`")

            if len(current_page_tags) == 15:
                tag_pages.append(
                    discord.Embed(
                        title=f"{mode.capitalize()} Tags",
                        description=f"There are `{len(tags)}` tags. To manage tags, use the `/tag-settings` slash commands.\n\n"
                        + "\n".join(current_page_tags),
                        colour=discord.Colour.light_grey(),
                    ).set_author(
                        name=ctx.guild.name
                        if mode == "server" and ctx.guild
                        else f"@{ctx.author.name}",
                        icon_url=ctx.guild.icon
                        if mode == "server" and ctx.guild
                        else ctx.author.display_avatar,
                    )
                )
                current_page_tags = []

        if len(current_page_tags) > 0:
            tag_pages.append(
                discord.Embed(
                    title=f"{mode.capitalize()} Tags",
                    description=f"There are `{len(tags)}` tags. To manage tags, use the `/tag-settings` slash commands.\n\n"
                    + "\n".join(current_page_tags),
                    colour=discord.Colour.light_grey(),
                ).set_author(
                    name=ctx.guild.name
                    if mode == "server" and ctx.guild
                    else f"@{ctx.author.name}",
                    icon_url=ctx.guild.icon
                    if mode == "server" and ctx.guild
                    else ctx.author.display_avatar,
                )
            )

        if not tag_pages:
            embed = discord.Embed(
                title=f"{ctx.bot.error_emoji} No Tags Found",
                description="Looks like you don't have any tags yet! To manage tags, use the `/tag-settings` slash commands.",
                colour=discord.Colour.red(),
            )
            return await ctx.reply(embed=embed)

        if len(tag_pages) > 1:
            view = PaginationView(embeds=tag_pages, timeout=1200)
            await ctx.reply(embed=tag_pages[0], view=view)
        else:
            await ctx.reply(
                embed=tag_pages[0].set_footer(
                    text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar
                )
            )


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(TagCommandsCog(bot))

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Any, Literal

import discord
from discord import app_commands
from discord.ext import commands
from rapidfuzz import fuzz, process
from sqlalchemy import select

from lib.embeds.general import cancelled
from lib.helpers.validation import is_valid_uuid
from lib.sql.sql import GuildSettings, Tag, get_session
from lib.views.pagination import PaginationView

if TYPE_CHECKING:
    from main import TitaniumBot


class TagOptionView(discord.ui.View):
    def __init__(
        self,
        original_user: discord.User | discord.Member,
        timeout: float = 60.0,
        ephemeral: bool = False,
    ):
        super().__init__(timeout=timeout)

        self.value = None
        self.timed_out = False
        self.original_user = original_user
        self.interaction: discord.Interaction | None = None
        self.ephemeral = ephemeral

    async def on_timeout(self) -> None:
        self.timed_out = True

    async def interaction_check(self, interaction: discord.Interaction["TitaniumBot"]) -> bool:
        if interaction.user.id != self.original_user.id:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Not Allowed",
                description="Only the user who sent the command can interact with this button.",
                colour=discord.Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False

        return True

    @discord.ui.button(label="Server Tag")
    async def server(
        self, interaction: discord.Interaction["TitaniumBot"], button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=self.ephemeral)

        self.value = True
        self.interaction = interaction
        self.stop()

    @discord.ui.button(label="User Tag")
    async def user(
        self, interaction: discord.Interaction["TitaniumBot"], button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=self.ephemeral)

        self.value = False
        self.interaction = interaction
        self.stop()


async def tag_autocomplete_base(
    bot: TitaniumBot, interaction: discord.Interaction["TitaniumBot"], current: str, verify: bool
) -> list[app_commands.Choice[str]]:

    server_tags_allowed = verify
    user_tags_allowed = True

    if server_tags_allowed and interaction.guild:
        config = await bot.fetch_guild_config(interaction.guild.id)
        if config and config.tag_settings and not config.tag_settings.allow_user_tags:
            user_tags_allowed = False

    server_tags = []
    user_tags = []

    async with get_session() as session:
        if server_tags_allowed and interaction.guild:
            stmt = (
                select(Tag)
                .where(Tag.guild_id == interaction.guild.id)
                .order_by(Tag.amount_used.desc())
            )
            results = await session.execute(stmt)
            server_tags = results.scalars().all()

        if user_tags_allowed:
            stmt = (
                select(Tag)
                .where(Tag.owner_id == interaction.user.id, Tag.is_user)
                .order_by(Tag.amount_used.desc())
            )
            results = await session.execute(stmt)
            user_tags = results.scalars().all()

    if not current:
        results = [
            app_commands.Choice(
                name="Start typing to search for a server or user tag, or select a frequently used tag below",
                value="",
            )
        ]

        tags: list[Tag] = []
        tags.extend(server_tags[:3])
        tags.extend(user_tags[:3])

        for tag in tags:
            results.append(
                app_commands.Choice(
                    name=f"{'User' if tag.is_user else 'Server'}: {tag.name}", value=str(tag.id)
                )
            )

        return results

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
        self.logger: logging.Logger = logging.getLogger("tags")

    def __server_tag_available(
        self,
        ctx: commands.Context["TitaniumBot"] | discord.Interaction["TitaniumBot"],
        config: GuildSettings | None,
    ) -> bool:
        author = ctx.author if isinstance(ctx, commands.Context) else ctx.user
        return bool(
            ctx.guild
            and isinstance(author, discord.Member)
            and ctx.guild.id in [role.id for role in author.roles]
            and config
            and config.tags_enabled
        )

    async def push_tag_usage(self, tag: Tag) -> None:
        async with get_session() as session:
            session_tag = await session.get(Tag, tag.id)
            if not session_tag:
                return
            session_tag.amount_used += 1

    async def command_not_found_hook(
        self, ctx: commands.Context["TitaniumBot"], error: Any
    ) -> bool:
        config = await self.bot.fetch_guild_config(ctx.guild.id) if ctx.guild else None
        if not self.__server_tag_available(ctx, config) or not ctx.guild:
            self.logger.debug("Server tags unavailable")
            return False

        if not config or (
            not config.tags_enabled
            or not config.tag_settings
            or not config.tag_settings.prefix_fallback
        ):
            self.logger.debug("Prefix fallback disabled")
            return False

        self.logger.debug(f"Searching tag: {ctx.invoked_with}")
        for tag in config.tag_settings.tags:
            if not (tag.name == ctx.invoked_with or str(tag.id) == ctx.invoked_with):
                continue

            self.logger.debug(f"Found tag: {tag.name}")
            await ctx.reply(content=tag.content, allowed_mentions=discord.AllowedMentions.none())
            await self.push_tag_usage(tag)

            # Send analytics manually
            # The command technically wasn't found so no analytics will be sent otherwise
            embed = discord.Embed(
                title=f"`@{ctx.author.name}` ran a tag command",
                description=f"`{ctx.clean_prefix}{tag.name}`",
                timestamp=ctx.message.created_at,
            )
            embed.add_field(name="User", value=f"{ctx.author.mention} (`{ctx.author.id}`)")
            if self.bot.user:
                embed.set_author(
                    name=f"{self.bot.user.name}#{self.bot.user.discriminator}",
                    icon_url=self.bot.user.display_avatar,
                )

            webhook_url = os.getenv("ANALYTICS_WEBHOOK")
            if webhook_url:
                self.logger.debug("Sending analytics")
                webhook = discord.Webhook.from_url(
                    webhook_url,
                    client=self.bot,
                )
                await webhook.send(embed=embed)

            return True

        self.logger.debug("No tags found, skipping")
        return False

    async def tag_autocomplete(
        self, interaction: discord.Interaction["TitaniumBot"], current: str
    ) -> list[app_commands.Choice[str]]:
        config = (
            await self.bot.fetch_guild_config(interaction.guild_id)
            if interaction.guild_id and interaction.is_guild_integration()
            else None
        )
        return await tag_autocomplete_base(
            bot=self.bot,
            interaction=interaction,
            current=current,
            verify=self.__server_tag_available(interaction, config),
        )

    # Use tag command
    @commands.hybrid_group(
        name="tag", aliases=["tags"], fallback="use", description="Send a server or user tag."
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        tag="The tag to send.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.autocomplete(tag=tag_autocomplete)
    @commands.cooldown(1, 3)
    async def tags_group(
        self, ctx: commands.Context["TitaniumBot"], tag: str, ephemeral: bool = False
    ):
        await ctx.defer(ephemeral=ephemeral)

        if not tag:
            embed = discord.Embed(
                title=f"{ctx.bot.error_emoji} Enter a tag name",
                description="Please enter a tag name when sending the command.",
                colour=discord.Colour.red(),
            )
            return await ctx.reply(embed=embed, ephemeral=ephemeral)

        config = (
            await self.bot.fetch_guild_config(ctx.guild.id)
            if ctx.guild and (ctx.interaction and ctx.interaction.is_guild_integration())
            else None
        )
        user_tags_allowed = True
        server_tags_allowed = self.__server_tag_available(ctx, config)

        if server_tags_allowed and ctx.guild:
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

            view = TagOptionView(original_user=ctx.author, ephemeral=ephemeral)
            await ctx.reply(embed=embed, view=view, ephemeral=ephemeral)
            timed_out = await view.wait()

            if not view.interaction:
                raise RuntimeError("Impossible: interaction is missing")

            if timed_out or view.value is None:
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
                description=f"Couldn't find a tag called `{tag}`. Create and manage tags with the `/settings` command.",
                colour=discord.Colour.red(),
            )

            if view and view.interaction:
                return await view.interaction.edit_original_response(embed=embed, view=None)
            else:
                return await ctx.reply(embed=embed, ephemeral=ephemeral)

        if tag_data.is_user and not user_tags_allowed:
            embed = discord.Embed(
                title=f"{ctx.bot.error_emoji} Not Allowed",
                description="A server admin has disabled user tags in this server.",
                colour=discord.Colour.red(),
            )
            if view and view.interaction:
                return await view.interaction.edit_original_response(embed=embed, view=None)
            else:
                return await ctx.reply(embed=embed, ephemeral=ephemeral)

        if view and view.interaction:
            await view.interaction.edit_original_response(
                embed=None,
                view=None,
                content=tag_data.content,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            await self.push_tag_usage(tag_data)
        else:
            await ctx.reply(
                content=tag_data.content,
                allowed_mentions=discord.AllowedMentions.none(),
                ephemeral=ephemeral,
            )
            await self.push_tag_usage(tag_data)

    # List tags command
    @tags_group.command(
        name="list", aliases=["viewall"], description="View a list of all server or user tags."
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        mode="Whether to view server or user tags.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Server Tag", value="server"),
            app_commands.Choice(name="User Tag", value="user"),
        ]
    )
    @commands.cooldown(1, 5)
    async def view_all_tags(
        self,
        ctx: commands.Context["TitaniumBot"],
        mode: Literal["server", "user"] = "user",
        ephemeral: bool = False,
    ):
        await ctx.defer(ephemeral=ephemeral)

        config = (
            await self.bot.fetch_guild_config(ctx.guild.id)
            if ctx.guild and (ctx.interaction and ctx.interaction.is_guild_integration())
            else None
        )
        if mode == "server" and not self.__server_tag_available(ctx, config):
            embed = discord.Embed(
                title=f"{ctx.bot.error_emoji} Not Available",
                description="Server tags are only available in servers with Titanium and the tags module enabled.",
                colour=discord.Colour.red(),
            )
            return await ctx.reply(embed=embed, ephemeral=ephemeral)

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
                    description=f"There are `{len(tags)}` tags. To manage tags, use the `/settings` command.\n\n"
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
                description="Looks like you don't have any tags yet! To manage tags, use the `/settings` command.",
                colour=discord.Colour.red(),
            )
            return await ctx.reply(embed=embed, ephemeral=ephemeral)

        if len(tag_pages) > 1:
            view = PaginationView(embeds=tag_pages, timeout=1200)
            await ctx.reply(embed=tag_pages[0], view=view, ephemeral=ephemeral)
        else:
            await ctx.reply(
                embed=tag_pages[0].set_footer(
                    text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar
                ),
                ephemeral=ephemeral,
            )


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(TagCommandsCog(bot))

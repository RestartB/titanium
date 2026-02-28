import importlib
import sys
from typing import TYPE_CHECKING

import discord
from discord import ButtonStyle, Colour, app_commands
from discord.ext import commands
from discord.ui import Button, View
from sqlalchemy import select

import lib.views.pagination as page_views
from lib.helpers.page_generators import generate_lb_embeds
from lib.sql.sql import LeaderboardUserStats, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class ServerCommandsCog(commands.Cog, name="Server", description="Get user information."):
    """Server related commands"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        for module_name, module in list(sys.modules.items()):
            if module_name.startswith("lib."):
                importlib.reload(module)

    @commands.hybrid_group(name="server", description="Get information about the server.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @commands.guild_only()
    async def server_group(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.defer()

        if not ctx.guild:
            raise commands.errors.NoPrivateMessage

        embed = discord.Embed(
            title="Server Info",
            colour=ctx.guild.me.accent_colour if ctx.guild.me else Colour.random(),
        )
        embed.set_author(
            name=f"{ctx.guild.name}",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        embed.add_field(name="Total Members", value=f"`{ctx.guild.member_count:,}`")
        embed.add_field(
            name="Creation Date", value=f"<t:{int(ctx.guild.created_at.timestamp())}:d>"
        )

        if ctx.guild.owner:
            embed.add_field(
                name="Owner",
                value=f"{ctx.guild.owner.mention} (`@{ctx.guild.owner.name}`)",
            )

        embed.add_field(
            name="Channels",
            value=f"`{len(ctx.guild.channels)}`",
        )
        embed.add_field(
            name="Categories",
            value=f"`{len(ctx.guild.categories)}`",
        )
        embed.add_field(
            name="Roles",
            value=f"`{len(ctx.guild.roles)}`",
        )

        embed.add_field(name="ID", value=f"`{ctx.guild.id}`")

        view = View()

        if ctx.guild.vanity_url:
            view.add_item(
                Button(
                    label="Vanity Invite",
                    url=ctx.guild.vanity_url,
                    style=ButtonStyle.url,
                )
            )

        await ctx.reply(embed=embed, view=view)

    @server_group.command(name="icon", description="Get the server's icon.")
    @commands.guild_only()
    async def server_icon(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.defer()

        if not ctx.guild:
            raise commands.errors.NoPrivateMessage

        embed = discord.Embed(
            colour=ctx.guild.me.accent_colour if ctx.guild.me else Colour.random(),
        )
        embed.set_author(
            name=f"{ctx.guild.name}'s Icon",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        if not ctx.guild.icon:
            embed.description = "This server does not have an icon."
            await ctx.reply(embed=embed)
            return

        image = ctx.guild.icon.url
        embed.set_image(url=image)

        png_url = image + "?format=png"
        jpg_url = image + "?format=jpg"
        webp_url = image + "?format=webp"
        formats = {"PNG": png_url, "JPG": jpg_url, "WEBP": webp_url}

        view = View()
        for format_name, format_url in formats.items():
            view.add_item(Button(label=f"{format_name}", url=format_url, style=ButtonStyle.link))

        await ctx.reply(embed=embed, view=view)

    @server_group.command(
        name="boosts", aliases=["boostinfo"], description="Get the server's boost information."
    )
    @commands.guild_only()
    async def server_boosts(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.defer()

        if not ctx.guild:
            raise commands.errors.NoPrivateMessage

        embed = discord.Embed(
            title="Server Boosts",
            colour=ctx.guild.me.accent_colour if ctx.guild.me else Colour.random(),
        )
        embed.set_author(
            name=f"{ctx.guild.name}",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        embed.add_field(name="Total Boosts", value=f"`{ctx.guild.premium_subscription_count}`")
        embed.add_field(name="Boost Level", value=f"`Level {ctx.guild.premium_tier}`", inline=True)

        await ctx.reply(embed=embed)

    # Message leaderboard command
    @server_group.command(
        name="messages", description="Get the amount of messages members have sent in the server."
    )
    @commands.guild_only()
    async def message_lb_command(self, ctx: commands.Context["TitaniumBot"]):
        if not ctx.guild:
            return

        await ctx.defer()

        if ctx.author.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="You have opted out of data collection and cannot use leaderboard features.",
                colour=discord.Colour.red(),
            )
            await ctx.send(embed=embed)
            return

        guild_settings = await self.bot.fetch_guild_config(ctx.guild.id)
        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_enabled
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Leaderboard Disabled",
                description="The leaderboard system is not enabled in this server.",
                colour=discord.Colour.red(),
            )
            await ctx.send(embed=embed)
            return

        async with get_session() as session:
            stmt = (
                select(LeaderboardUserStats)
                .where(LeaderboardUserStats.guild_id == ctx.guild.id)
                .order_by(LeaderboardUserStats.message_count.desc())
                .limit(1000)
            )
            result = await session.execute(stmt)
            top_users = result.scalars().all()

            if not top_users:
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} No Data",
                    description="No users have any recorded messages yet.",
                    colour=discord.Colour.red(),
                )
                await ctx.send(embed=embed)
                return

            pages = generate_lb_embeds(
                guild=ctx.guild,
                author=ctx.author,
                top_users=top_users,
                title="Messages Sent",
                attr="message_count",
            )
            view = page_views.LeaderboardReloadPageView(
                embeds=pages,
                timeout=240,
                title="Messages Sent",
                error_description="No users have any recorded messages yet.",
                sort_type=LeaderboardUserStats.message_count,
                reload_type="message_count",
                error_emoji=str(self.bot.error_emoji),
            )

            if len(pages) > 1:
                await ctx.send(embed=pages[0], view=view)
            else:
                await ctx.send(embed=pages[0])

    # Word leaderboard command
    @server_group.command(
        name="words", description="Get the amount of words members have sent in the server."
    )
    @commands.guild_only()
    async def word_lb_command(self, ctx: commands.Context["TitaniumBot"]):
        if not ctx.guild:
            return

        await ctx.defer()

        if ctx.author.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="You have opted out of data collection and cannot use leaderboard features.",
                colour=discord.Colour.red(),
            )
            await ctx.send(embed=embed)
            return

        guild_settings = await self.bot.fetch_guild_config(ctx.guild.id)
        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_enabled
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Leaderboard Disabled",
                description="The leaderboard system is not enabled in this server.",
                colour=discord.Colour.red(),
            )
            await ctx.send(embed=embed)
            return

        async with get_session() as session:
            stmt = (
                select(LeaderboardUserStats)
                .where(LeaderboardUserStats.guild_id == ctx.guild.id)
                .order_by(LeaderboardUserStats.word_count.desc())
                .limit(1000)
            )
            result = await session.execute(stmt)
            top_users = result.scalars().all()

            if not top_users:
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} No Data",
                    description="No users have any recorded words yet.",
                    colour=discord.Colour.red(),
                )
                await ctx.send(embed=embed)
                return

            pages = generate_lb_embeds(
                guild=ctx.guild,
                author=ctx.author,
                top_users=top_users,
                title="Words Sent",
                attr="word_count",
            )
            view = page_views.LeaderboardReloadPageView(
                embeds=pages,
                timeout=240,
                title="Words Sent",
                error_description="No users have any recorded words yet.",
                sort_type=LeaderboardUserStats.word_count,
                reload_type="word_count",
                error_emoji=str(self.bot.error_emoji),
            )

            if len(pages) > 1:
                await ctx.send(embed=pages[0], view=view)
            else:
                await ctx.send(embed=pages[0])

    # Attachment leaderboard command
    @server_group.command(
        name="attachments",
        description="Get the amount of attachments members have sent in the server.",
    )
    @commands.guild_only()
    async def attachment_lb_command(self, ctx: commands.Context["TitaniumBot"]):
        if not ctx.guild:
            return

        await ctx.defer()

        if ctx.author.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="You have opted out of data collection and cannot use leaderboard features.",
                colour=discord.Colour.red(),
            )
            await ctx.send(embed=embed)
            return

        guild_settings = await self.bot.fetch_guild_config(ctx.guild.id)
        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_enabled
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Leaderboard Disabled",
                description="The leaderboard system is not enabled in this server.",
                colour=discord.Colour.red(),
            )
            await ctx.send(embed=embed)
            return

        async with get_session() as session:
            stmt = (
                select(LeaderboardUserStats)
                .where(LeaderboardUserStats.guild_id == ctx.guild.id)
                .order_by(LeaderboardUserStats.attachment_count.desc())
                .limit(1000)
            )
            result = await session.execute(stmt)
            top_users = result.scalars().all()

            if not top_users:
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} No Data",
                    description="No users have any recorded attachments yet.",
                    colour=discord.Colour.red(),
                )
                await ctx.send(embed=embed)
                return

            pages = generate_lb_embeds(
                guild=ctx.guild,
                author=ctx.author,
                top_users=top_users,
                title="Attachments Sent",
                attr="attachment_count",
            )
            view = page_views.LeaderboardReloadPageView(
                embeds=pages,
                timeout=240,
                title="Attachments Sent",
                error_description="No users have any recorded attachments yet.",
                sort_type=LeaderboardUserStats.attachment_count,
                reload_type="attachment_count",
                error_emoji=str(self.bot.error_emoji),
            )

            if len(pages) > 1:
                await ctx.send(embed=pages[0], view=view)
            else:
                await ctx.send(embed=pages[0])

    # Attachment leaderboard command
    @server_group.command(
        name="swearjar",
        description="Get the amount of explicit words members have sent in the server.",
    )
    @commands.guild_only()
    async def explicit_lb_command(self, ctx: commands.Context["TitaniumBot"]):
        if not ctx.guild:
            return

        await ctx.defer()

        if ctx.author.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="You have opted out of data collection and cannot use leaderboard features.",
                colour=discord.Colour.red(),
            )
            await ctx.send(embed=embed)
            return

        guild_settings = await self.bot.fetch_guild_config(ctx.guild.id)
        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_enabled
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Leaderboard Disabled",
                description="The leaderboard system is not enabled in this server.",
                colour=discord.Colour.red(),
            )
            await ctx.send(embed=embed)
            return

        async with get_session() as session:
            stmt = (
                select(LeaderboardUserStats)
                .where(LeaderboardUserStats.guild_id == ctx.guild.id)
                .order_by(LeaderboardUserStats.explicit_count.desc())
                .limit(1000)
            )
            result = await session.execute(stmt)
            top_users = result.scalars().all()

            if not top_users:
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} No Data",
                    description="No users have said any explicit terms yet.",
                    colour=discord.Colour.red(),
                )
                await ctx.send(embed=embed)
                return

            pages = generate_lb_embeds(
                guild=ctx.guild,
                author=ctx.author,
                top_users=top_users,
                title="Swear Jar",
                attr="explicit_count",
            )
            view = page_views.LeaderboardReloadPageView(
                embeds=pages,
                timeout=240,
                title="Swear Jar",
                error_description="No users have said any explicit terms yet.",
                sort_type=LeaderboardUserStats.explicit_count,
                reload_type="explicit_count",
                error_emoji=str(self.bot.error_emoji),
            )

            if len(pages) > 1:
                await ctx.send(embed=pages[0], view=view)
            else:
                await ctx.send(embed=pages[0])


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(ServerCommandsCog(bot))

import asyncio
from io import BytesIO
from textwrap import shorten
from typing import TYPE_CHECKING, Optional

import discord
from colorthief import ColorThief
from discord import ButtonStyle, Colour, app_commands
from discord.ext import commands
from discord.ui import Button, View
from sqlalchemy import select

from lib.helpers.page_generators import generate_lb_embeds
from lib.sql.sql import LeaderboardUserStats, get_session
from lib.views.pagination import LeaderboardReloadPageView

if TYPE_CHECKING:
    from main import TitaniumBot


class ServerCommandsCog(commands.Cog, name="Server", description="Get server information."):
    """Server related commands"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    @commands.hybrid_group(name="server", description="Get information about the server.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @commands.guild_only()
    async def server_group(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.defer()

        if not ctx.guild:
            raise commands.errors.NoPrivateMessage

        embed = discord.Embed(title="Server Info", colour=Colour.light_grey())
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

        if ctx.guild.icon:
            thief = ColorThief(BytesIO(await ctx.guild.icon.read()))
            embed.colour = Colour.from_rgb(*await asyncio.to_thread(thief.get_color))

        await ctx.reply(embed=embed, view=view)

    @server_group.command(name="icon", description="Get the server's icon.")
    @commands.guild_only()
    async def server_icon(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.defer()

        if not ctx.guild:
            raise commands.errors.NoPrivateMessage

        embed = discord.Embed(colour=Colour.light_grey())
        embed.set_author(
            name=f"{ctx.guild.name}'s Icon",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        if not ctx.guild.icon:
            embed.description = "This server does not have an icon."
            await ctx.reply(embed=embed)
            return

        image = ctx.guild.icon
        embed.set_image(url=image.url)

        thief = ColorThief(BytesIO(await image.read()))
        embed.colour = Colour.from_rgb(*await asyncio.to_thread(thief.get_color))

        view = View().add_item(
            Button(label="Open in Browser", style=ButtonStyle.link, url=image.url)
        )
        await ctx.reply(embed=embed, view=view)

    @server_group.command(name="banner", description="Get the server's banner.")
    @commands.guild_only()
    async def server_banner(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.defer()

        if not ctx.guild:
            raise commands.errors.NoPrivateMessage

        embed = discord.Embed(colour=Colour.light_grey())
        embed.set_author(
            name=f"{ctx.guild.name}'s Banner",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        if not ctx.guild.banner:
            embed.description = "This server does not have an banner."
            await ctx.reply(embed=embed)
            return

        image = ctx.guild.banner
        embed.set_image(url=image.url)

        # Get dominant colour for embed
        thief = ColorThief(BytesIO(await image.read()))
        embed.colour = Colour.from_rgb(*await asyncio.to_thread(thief.get_color))

        view = View().add_item(
            Button(label="Open in Browser", style=ButtonStyle.link, url=image.url)
        )
        await ctx.reply(embed=embed, view=view)

    @server_group.command(
        name="boosts", aliases=["boostinfo"], description="Get the server's boost information."
    )
    @commands.guild_only()
    async def server_boosts(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.defer()

        if not ctx.guild:
            raise commands.errors.NoPrivateMessage

        embed = discord.Embed(title="Server Boosts", colour=Colour.purple())
        embed.set_author(
            name=f"{ctx.guild.name}",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        embed.add_field(name="Total Boosts", value=f"`{ctx.guild.premium_subscription_count}`")
        embed.add_field(name="Boost Level", value=f"`Level {ctx.guild.premium_tier}`", inline=True)

        if ctx.guild.icon:
            thief = ColorThief(BytesIO(await ctx.guild.icon.read()))
            embed.colour = Colour.from_rgb(*await asyncio.to_thread(thief.get_color))

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
                show_xp_label=False,
            )
            view = LeaderboardReloadPageView(
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
                show_xp_label=False,
            )
            view = LeaderboardReloadPageView(
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
                show_xp_label=False,
            )
            view = LeaderboardReloadPageView(
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
                show_xp_label=False,
            )
            view = LeaderboardReloadPageView(
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

    # First Message command
    @server_group.command(
        name="first-message",
        aliases=["firstmessage"],
        description="Get the first message in a channel, uses current channel by default.",
    )
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @commands.guild_only()
    @app_commands.describe(
        channel="Optional: the target channel. Defaults to the current channel.",
        ephemeral="Optional: whether to send the command output as a dismissable message only visible to you. Defaults to true.",
    )
    @app_commands.checks.cooldown(1, 5)
    async def first_message(
        self,
        ctx: commands.Context["TitaniumBot"],
        channel: Optional[discord.abc.GuildChannel] = None,
        ephemeral: bool = True,
    ) -> None:
        await ctx.defer(ephemeral=ephemeral)

        if isinstance(ctx.author, discord.User):
            raise Exception("Impossible: author is a user")

        if isinstance(ctx.me, discord.ClientUser):
            raise Exception("Impossible: bot is a user")

        if not channel:
            if not isinstance(ctx.channel, discord.abc.GuildChannel):
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} Error",
                    description="The current channel is not supported.",
                    colour=Colour.red(),
                )
                await ctx.reply(embed=embed, ephemeral=ephemeral)
                return

            channel = ctx.channel

        if not isinstance(channel, discord.abc.Messageable):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Error",
                description="The selected channel does not support messages.",
                colour=Colour.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        user_perms = channel.permissions_for(ctx.author)
        bot_perms = channel.permissions_for(ctx.me)

        if not user_perms.read_messages or not user_perms.read_message_history:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Not Allowed",
                description="You do not have permissions to read the message history of the selected channel.",
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        if not bot_perms.read_messages or not bot_perms.read_message_history:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Not Allowed",
                description="Titanium does not have permission to read the message history of the selected channel.",
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        message = None
        try:
            async for msg in channel.history(limit=1, oldest_first=True):
                message = msg
        except discord.errors.Forbidden:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Forbidden",
                description="Titanium may not have permissions to read the message history of the selected channel.",
                colour=Colour.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)

        if not message:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} No Messages",
                description="Titanium couldn't find any messages in the selected channel.",
                colour=Colour.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        embed = discord.Embed(
            title="First Message",
            description=f"{message.content if message.content else 'No content.'}",
            timestamp=message.created_at,
        )
        embed.set_author(name=f"#{shorten(channel.name, width=255)}")
        embed.set_footer(
            text=f"@{ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        if msg.author is not None and not msg.is_system():
            embed.set_author(
                name=msg.author.display_name,
                icon_url=msg.author.display_avatar.url,
            )

        view = View()
        view.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.url,
                url=msg.jump_url,
                label="Jump to Message",
            )
        )

        await ctx.reply(embed=embed, view=view, ephemeral=ephemeral)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(ServerCommandsCog(bot))

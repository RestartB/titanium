import asyncio
from io import BytesIO
from typing import TYPE_CHECKING

import discord
from colorthief import ColorThief
from discord import ButtonStyle, Colour, app_commands
from discord.ext import commands
from discord.ui import Button, View
from discord.utils import format_dt
from sqlalchemy import select

from lib.embeds.leaderboard import generate_lb_embeds
from lib.sql.sql import LeaderboardUserStats, get_session
from lib.views.pagination import LeaderboardReloadPageView

if TYPE_CHECKING:
    from main import TitaniumBot


@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
class ServerCommandsCog(
    commands.GroupCog, group_name="server", description="Server information related commands."
):
    """Server related commands"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    @app_commands.command(name="info", description="Get information about the server.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    async def server_info(
        self, interaction: discord.Interaction["TitaniumBot"], ephemeral: bool = False
    ) -> None:
        await interaction.response.defer(ephemeral=ephemeral)

        if not interaction.guild:
            raise ValueError("Guild info unavailable")

        embed = discord.Embed(title="Server Info", colour=Colour.light_grey())
        embed.set_author(
            name=f"{interaction.guild.name}",
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None,
        )
        embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
        embed.set_footer(
            text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url
        )

        embed.add_field(name="Total Members", value=f"`{interaction.guild.member_count:,}`")
        embed.add_field(
            name="Creation Date", value=format_dt(interaction.guild.created_at, style="d")
        )

        if interaction.guild.owner:
            embed.add_field(
                name="Owner",
                value=f"{interaction.guild.owner.mention} (`@{interaction.guild.owner.name}`)",
            )

        embed.add_field(
            name="Channels",
            value=f"`{len(interaction.guild.channels)}`",
        )
        embed.add_field(
            name="Categories",
            value=f"`{len(interaction.guild.categories)}`",
        )
        embed.add_field(
            name="Roles",
            value=f"`{len(interaction.guild.roles)}`",
        )

        embed.add_field(name="ID", value=f"`{interaction.guild.id}`")

        view = View()

        if interaction.guild.vanity_url:
            view.add_item(
                Button(
                    label="Vanity Invite",
                    url=interaction.guild.vanity_url,
                    style=ButtonStyle.url,
                )
            )

        if interaction.guild.icon:
            thief = ColorThief(BytesIO(await interaction.guild.icon.read()))
            embed.colour = Colour.from_rgb(*await asyncio.to_thread(thief.get_color))

        await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)

    @app_commands.command(name="icon", description="Get the server's icon.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    async def server_icon(
        self, interaction: discord.Interaction["TitaniumBot"], ephemeral: bool = False
    ) -> None:
        await interaction.response.defer(ephemeral=ephemeral)

        if not interaction.guild:
            raise ValueError("Guild info unavailable")

        embed = discord.Embed(colour=Colour.light_grey())
        embed.set_author(
            name=f"{interaction.guild.name}'s Icon",
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None,
        )
        embed.set_footer(
            text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url
        )

        if not interaction.guild.icon:
            embed.description = "This server does not have an icon."
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        image = interaction.guild.icon
        embed.set_image(url=image.url)

        thief = ColorThief(BytesIO(await image.read()))
        embed.colour = Colour.from_rgb(*await asyncio.to_thread(thief.get_color))

        view = View().add_item(
            Button(label="Open in Browser", style=ButtonStyle.link, url=image.url)
        )
        await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)

    @app_commands.command(name="banner", description="Get the server's banner.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    async def server_banner(
        self, interaction: discord.Interaction["TitaniumBot"], ephemeral: bool = False
    ) -> None:
        await interaction.response.defer(ephemeral=ephemeral)

        if not interaction.guild:
            raise ValueError("Guild info unavailable")

        embed = discord.Embed(colour=Colour.light_grey())
        embed.set_author(
            name=f"{interaction.guild.name}'s Banner",
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None,
        )
        embed.set_footer(
            text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url
        )

        if not interaction.guild.banner:
            embed.description = "This server does not have an banner."
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        image = interaction.guild.banner
        embed.set_image(url=image.url)

        # Get dominant colour for embed
        thief = ColorThief(BytesIO(await image.read()))
        embed.colour = Colour.from_rgb(*await asyncio.to_thread(thief.get_color))

        view = View().add_item(
            Button(label="Open in Browser", style=ButtonStyle.link, url=image.url)
        )
        await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)

    @app_commands.command(name="boosts", description="Get the server's boost information.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    async def server_boosts(
        self, interaction: discord.Interaction["TitaniumBot"], ephemeral: bool = False
    ) -> None:
        await interaction.response.defer(ephemeral=ephemeral)

        if not interaction.guild:
            raise ValueError("Guild info unavailable")

        embed = discord.Embed(title="Server Boosts", colour=Colour.purple())
        embed.set_author(
            name=f"{interaction.guild.name}",
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None,
        )
        embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
        embed.set_footer(
            text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url
        )

        embed.add_field(
            name="Total Boosts", value=f"`{interaction.guild.premium_subscription_count}`"
        )
        embed.add_field(
            name="Boost Level", value=f"`Level {interaction.guild.premium_tier}`", inline=True
        )

        if interaction.guild.icon:
            thief = ColorThief(BytesIO(await interaction.guild.icon.read()))
            embed.colour = Colour.from_rgb(*await asyncio.to_thread(thief.get_color))

        await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    # Message leaderboard command
    @app_commands.command(
        name="messages", description="Get the amount of messages members have sent in the server."
    )
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    async def message_lb_command(
        self, interaction: discord.Interaction["TitaniumBot"], ephemeral: bool = False
    ):
        if not interaction.guild:
            return

        await interaction.response.defer(ephemeral=ephemeral)

        if interaction.user.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="You have opted out of data collection and cannot use leaderboard features.",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        guild_settings = await self.bot.fetch_guild_config(interaction.guild.id)
        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_enabled
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Leaderboard Disabled",
                description="The leaderboard system is disabled in this server. Ask a server admin to turn it on using the `/settings` command or the Titanium Dashboard.",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        async with get_session() as session:
            stmt = (
                select(LeaderboardUserStats)
                .where(LeaderboardUserStats.guild_id == interaction.guild.id)
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
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                return

            pages = generate_lb_embeds(
                guild=interaction.guild,
                author=interaction.user,
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

            await interaction.followup.send(embed=pages[0], view=view, ephemeral=ephemeral)

    # Word leaderboard command
    @app_commands.command(
        name="words", description="Get the amount of words members have sent in the server."
    )
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    @app_commands.checks.cooldown(1, 5)
    async def word_lb_command(
        self, interaction: discord.Interaction["TitaniumBot"], ephemeral: bool = False
    ):
        if not interaction.guild:
            return

        await interaction.response.defer(ephemeral=ephemeral)

        if interaction.user.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="You have opted out of data collection and cannot use leaderboard features.",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        guild_settings = await self.bot.fetch_guild_config(interaction.guild.id)
        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_enabled
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Leaderboard Disabled",
                description="The leaderboard system is disabled in this server. Ask a server admin to turn it on using the `/settings` command or the Titanium Dashboard.",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        async with get_session() as session:
            stmt = (
                select(LeaderboardUserStats)
                .where(
                    LeaderboardUserStats.guild_id == interaction.guild.id,
                    LeaderboardUserStats.word_count > 0,
                )
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
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                return

            pages = generate_lb_embeds(
                guild=interaction.guild,
                author=interaction.user,
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

            await interaction.followup.send(embed=pages[0], view=view, ephemeral=ephemeral)

    # Attachment leaderboard command
    @app_commands.command(
        name="attachments",
        description="Get the amount of attachments members have sent in the server.",
    )
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    @app_commands.checks.cooldown(1, 5)
    async def attachment_lb_command(
        self, interaction: discord.Interaction["TitaniumBot"], ephemeral: bool = False
    ):
        if not interaction.guild:
            return

        await interaction.response.defer(ephemeral=ephemeral)

        if interaction.user.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="You have opted out of data collection and cannot use leaderboard features.",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        guild_settings = await self.bot.fetch_guild_config(interaction.guild.id)
        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_enabled
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Leaderboard Disabled",
                description="The leaderboard system is disabled in this server. Ask a server admin to turn it on using the `/settings` command or the Titanium Dashboard.",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        async with get_session() as session:
            stmt = (
                select(LeaderboardUserStats)
                .where(
                    LeaderboardUserStats.guild_id == interaction.guild.id,
                    LeaderboardUserStats.attachment_count > 0,
                )
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
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                return

            pages = generate_lb_embeds(
                guild=interaction.guild,
                author=interaction.user,
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

            await interaction.followup.send(embed=pages[0], view=view, ephemeral=ephemeral)

    # VC leaderboard command
    @app_commands.command(
        name="vc", description="Get the amount of time that users have spent in VC in the server."
    )
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    @app_commands.checks.cooldown(1, 5)
    async def vc_lb_command(
        self, interaction: discord.Interaction["TitaniumBot"], ephemeral: bool = False
    ):
        if not interaction.guild:
            return

        await interaction.response.defer(ephemeral=ephemeral)

        if interaction.user.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="You have opted out of data collection and cannot use leaderboard features.",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        guild_settings = await self.bot.fetch_guild_config(interaction.guild.id)
        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_enabled
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Leaderboard Disabled",
                description="The leaderboard system is disabled in this server. Ask a server admin to turn it on using the `/settings` command or the Titanium Dashboard.",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        async with get_session() as session:
            stmt = (
                select(LeaderboardUserStats)
                .where(
                    LeaderboardUserStats.guild_id == interaction.guild.id,
                    LeaderboardUserStats.vc_minutes > 0,
                )
                .order_by(LeaderboardUserStats.vc_minutes.desc())
                .limit(1000)
            )
            result = await session.execute(stmt)
            top_users = result.scalars().all()

            if not top_users:
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} No Data",
                    description="No users have any recorded VC time yet.",
                    colour=discord.Colour.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                return

            pages = generate_lb_embeds(
                guild=interaction.guild,
                author=interaction.user,
                top_users=top_users,
                title="Voice Chat Time",
                attr="vc_minutes",
                show_xp_label=False,
            )
            view = LeaderboardReloadPageView(
                embeds=pages,
                timeout=240,
                title="Voice Chat Time",
                error_description="No users have any recorded VC time yet.",
                sort_type=LeaderboardUserStats.vc_minutes,
                reload_type="vc_minutes",
                error_emoji=str(self.bot.error_emoji),
            )

            await interaction.followup.send(embed=pages[0], view=view, ephemeral=ephemeral)

    # Attachment leaderboard command
    @app_commands.command(
        name="swearjar",
        description="Get the amount of explicit words members have sent in the server.",
    )
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    @app_commands.checks.cooldown(1, 5)
    async def explicit_lb_command(
        self, interaction: discord.Interaction["TitaniumBot"], ephemeral: bool = False
    ):
        if not interaction.guild:
            return

        await interaction.response.defer(ephemeral=ephemeral)

        if interaction.user.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="You have opted out of data collection and cannot use leaderboard features.",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        guild_settings = await self.bot.fetch_guild_config(interaction.guild.id)
        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_enabled
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Leaderboard Disabled",
                description="The leaderboard system is disabled in this server. Ask a server admin to turn it on using the `/settings` command or the Titanium Dashboard.",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        async with get_session() as session:
            stmt = (
                select(LeaderboardUserStats)
                .where(
                    LeaderboardUserStats.guild_id == interaction.guild.id,
                    LeaderboardUserStats.explicit_count > 0,
                )
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
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                return

            pages = generate_lb_embeds(
                guild=interaction.guild,
                author=interaction.user,
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

            await interaction.followup.send(embed=pages[0], view=view, ephemeral=ephemeral)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(ServerCommandsCog(bot))

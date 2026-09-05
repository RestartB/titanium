from typing import TYPE_CHECKING

import discord
from discord import ButtonStyle, Embed, Member, User, app_commands
from discord.ext import commands
from discord.ui import Button, View
from discord.utils import format_dt

if TYPE_CHECKING:
    from main import TitaniumBot


class UserCommandsCog(commands.Cog, name="Users", description="Get user information."):
    """User related commands"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    @app_commands.command(name="user", description="Get information about a user.")
    @app_commands.describe(
        user="Optional: the user to get information about. Defaults to yourself.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.checks.cooldown(1, 3)
    async def user(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        user: User | Member | None = None,
        ephemeral: bool = False,
    ) -> None:
        await interaction.response.defer(ephemeral=ephemeral)

        user = user or interaction.user
        in_guild = isinstance(user, Member)

        fetched_user = await interaction.client.fetch_user(user.id)
        banner = fetched_user.banner
        accent_colour = fetched_user.accent_colour

        embed = Embed(title="User Info", colour=accent_colour)
        embed.set_author(
            name=f"{user.display_name} (@{user.name})",
            icon_url=user.display_avatar.url,
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        if banner is not None:
            embed.set_image(url=banner.url)

        embed.add_field(name="ID", value=f"`{user.id}`")
        embed.add_field(
            name="Joined Discord",
            value=f"{format_dt(user.created_at, style='R')} ({format_dt(user.created_at)})",
        )

        join_date = user.joined_at if in_guild and user.joined_at else None
        if join_date:
            embed.add_field(
                name="Joined Server",
                value=f"{format_dt(join_date, style='R')} ({format_dt(join_date)})",
            )

        if in_guild and interaction.guild and len(user.roles) > 0:
            embed.add_field(
                name="Roles",
                value=", ".join(
                    role.mention for role in user.roles if role.id != interaction.guild.id
                )
                or "No Roles",
            )

        if in_guild and len(user.roles) > 0:
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )
        elif in_guild:
            embed.set_footer(
                text=f"@{interaction.user.name} - add Titanium to the server to get roles",
                icon_url=interaction.user.display_avatar.url,
            )
        else:
            embed.set_footer(
                text=f"@{interaction.user.name} - user isn't in the server, showing limited info",
                icon_url=interaction.user.display_avatar.url,
            )

        view = View()
        view.add_item(
            discord.ui.Button(
                label="User URL",
                style=discord.ButtonStyle.url,
                url=f"https://discord.com/users/{user.id}",
                row=0,
            )
        )
        view.add_item(
            discord.ui.Button(
                label="Open PFP in Browser",
                style=discord.ButtonStyle.url,
                url=user.display_avatar.url,
                row=0,
            )
        )

        # Send Embed
        await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)

    @app_commands.command(name="pfp", description="Get a user's profile picture.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        user="Optional: the user to get the PFP of. Defaults to yourself.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.checks.cooldown(1, 3)
    async def pfp(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        user: User | Member | None,
        ephemeral: bool = False,
    ) -> None:
        await interaction.response.defer(ephemeral=ephemeral)

        user = user or interaction.user
        user = await interaction.client.fetch_user(user.id)

        embed = Embed(colour=user.accent_colour)
        embed.set_author(
            name=f"@{user.name}'s PFP",
            icon_url=user.display_avatar.url,
        )
        embed.set_footer(
            text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url
        )

        url = user.avatar.url if user.avatar else user.default_avatar.url
        embed.set_image(url=url)

        view = View().add_item(Button(label="Open in Browser", style=ButtonStyle.link, url=url))
        await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)

    @app_commands.command(name="server-pfp", description="Get a user's server profile picture.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.describe(
        user="Optional: the user to get the PFP of. Defaults to yourself.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.checks.cooldown(1, 3)
    async def server_pfp(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        user: Member | None = None,
        ephemeral: bool = False,
    ) -> None:
        await interaction.response.defer(ephemeral=ephemeral)

        if not user:
            user = interaction.user if isinstance(interaction.user, Member) else None

        if not user:
            raise RuntimeError("Impossible: member object not returned")

        embed = Embed(colour=user.accent_colour)
        embed.set_author(
            name=f"@{user.name}'s Server PFP",
            icon_url=user.display_avatar.url,
        )
        embed.set_footer(
            text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url
        )

        if user.guild_avatar:
            embed.set_image(url=user.guild_avatar.url)
            view = View().add_item(
                Button(label="Open in Browser", style=ButtonStyle.link, url=user.guild_avatar.url)
            )

            await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)
        else:
            embed.description = (
                f"{self.bot.error_emoji} {user.mention} does not have a server profile picture."
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    @app_commands.command(name="banner", description="Get the banner of a user.")
    @app_commands.describe(
        user="Optional: the user to get the banner of. Defaults to yourself.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.checks.cooldown(1, 3)
    async def banner(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        user: Member | User | None,
        ephemeral: bool = False,
    ) -> None:
        await interaction.response.defer(ephemeral=ephemeral)

        user = user or interaction.user
        user = await interaction.client.fetch_user(user.id)
        banner = user.banner.url if user.banner else None

        embed = Embed(colour=user.accent_colour)
        embed.set_author(
            name=f"@{user.name}'s Banner",
            icon_url=user.display_avatar.url,
        )
        embed.set_footer(
            text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url
        )

        if banner:
            embed.set_image(url=banner)
            view = View().add_item(
                Button(label="Open in Browser", style=ButtonStyle.link, url=banner)
            )

            await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)
        else:
            embed.description = f"{self.bot.error_emoji} {user.mention} does not have a banner."
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(UserCommandsCog(bot))

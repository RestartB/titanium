import discord
import discord.ext
from discord import Color, app_commands
from discord.ext import commands
from discord.ui import View


class UserUtils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    context = discord.app_commands.AppCommandContext(
        guild=True, dm_channel=True, private_channel=True
    )
    installs = discord.app_commands.AppInstallationType(guild=True, user=True)
    userGroup = app_commands.Group(
        name="user",
        description="User related commands.",
        allowed_contexts=context,
        allowed_installs=installs,
    )

    # User Info command
    @userGroup.command(name="info", description="Get info about a user.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    async def server_info(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        # Temp fix! See below for info.
        user = await interaction.client.fetch_user(user.id)

        try:
            member = await interaction.guild.fetch_member(user.id)
            in_guild = True
        except discord.errors.NotFound:
            member = user
            in_guild = False

        embed = discord.Embed(
            title="User Info",
            color=(
                user.accent_color if user.accent_color is not None else Color.random()
            ),
        )
        embed.set_author(
            name=f"{member.display_name} (@{member.name})",
            icon_url=member.display_avatar.url,
        )

        # FIXME - Temp fix!
        # We need to use the user object to get the banner. This should work with the member object...
        # ... but discord.py has a bug where the banner always returns None with member. This is a workaround.
        # This can be changed to display_banner when discord.py fixes the bug. Conclusion: fuck discord.py.
        if user.banner is not None:
            embed.set_image(url=user.banner.url)

        creation_date = int(member.created_at.timestamp())
        join_date = int(member.joined_at.timestamp()) if in_guild else None

        embed.add_field(name="ID", value=member.id)

        # Other info
        embed.add_field(
            name="Joined Discord",
            value=f"<t:{creation_date}:R> (<t:{creation_date}:f>)",
        )
        (
            embed.add_field(
                name="Joined Server", value=f"<t:{join_date}:R> (<t:{join_date}:f>)"
            )
            if in_guild
            else None
        )

        if not interaction.is_guild_integration():
            embed.set_footer(
                text=f"@{interaction.user.name} - add Titanium to the server for more info.",
                icon_url=interaction.user.display_avatar.url,
            )
        elif in_guild:
            roles = []

            for role in member.roles:
                roles.append(role.mention)

            embed.add_field(name="Roles", value=", ".join(roles))

            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )
        elif not in_guild:
            embed.set_footer(
                text=f"@{interaction.user.name} - user is not in the server, showing limited info.",
                icon_url=interaction.user.display_avatar.url,
            )

        embed.set_thumbnail(url=member.display_avatar.url)

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

    # PFP command
    @userGroup.command(name="pfp", description="Show a user's PFP.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="The target user.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    async def pfp(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        embed = discord.Embed(
            title="PFP",
            color=(
                user.accent_color if user.accent_color is not None else Color.random()
            ),
        )

        embed.set_image(url=user.display_avatar.url)
        embed.set_author(
            name=f"{user.display_name} (@{user.name})", icon_url=user.display_avatar.url
        )
        embed.set_footer(
            text=f"@{interaction.user.name}",
            icon_url=interaction.user.display_avatar.url,
        )

        view = View()
        view.add_item(
            discord.ui.Button(
                label="Open in Browser",
                style=discord.ButtonStyle.url,
                url=user.display_avatar.url,
                row=0,
            )
        )

        # Send Embed
        await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)

    # Banner command
    @userGroup.command(name="banner", description="Show a user's banner.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="The target user.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    async def banner(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        user = await interaction.client.fetch_user(user.id)
        if user.banner is None:
            embed = discord.Embed(
                title="Banner",
                description="This user does not have a banner.",
                color=(
                    user.accent_color if user.accent_color is not None else Color.red()
                ),
            )

            embed.set_author(
                name=f"{user.display_name} (@{user.name})",
                icon_url=user.display_avatar.url,
            )
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )

            # Send Embed
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        else:
            embed = discord.Embed(
                title="Banner",
                color=(
                    user.accent_color
                    if user.accent_color is not None
                    else Color.random()
                ),
            )

            embed.set_image(url=user.banner.url)
            embed.set_author(
                name=f"{user.display_name} (@{user.name})",
                icon_url=user.display_avatar.url,
            )
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )

            view = View()
            view.add_item(
                discord.ui.Button(
                    label="Open in Browser",
                    style=discord.ButtonStyle.url,
                    url=user.banner.url,
                    row=0,
                )
            )

            # Send Embed
            await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)


async def setup(bot):
    await bot.add_cog(UserUtils(bot))

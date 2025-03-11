import discord
import discord.ext
from discord import Color, app_commands
from discord.ext import commands
from discord.ui import View


class ServerUtils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    context = discord.app_commands.AppCommandContext(
        guild=True, dm_channel=False, private_channel=False
    )
    serverGroup = app_commands.Group(
        name="server", description="Server related commands.", allowed_contexts=context
    )

    # Server Icon command
    @serverGroup.command(name="icon", description="Show the server's icon.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    async def server_icon(
        self, interaction: discord.Interaction, ephemeral: bool = False
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        # Handle no icon
        if interaction.guild.icon is not None:
            embed = discord.Embed(title="Server Icon", color=Color.random())
            embed.set_image(url=interaction.guild.icon.url)
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )
            embed.set_author(
                name=interaction.guild.name,
                icon_url=(
                    interaction.guild.icon.url
                    if interaction.guild.icon is not None
                    else None
                ),
            )

            view = View()
            view.add_item(
                discord.ui.Button(
                    label="Open in Browser",
                    style=discord.ButtonStyle.url,
                    url=interaction.guild.icon.url,
                    row=0,
                )
            )

            # Send Embed
            await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)
        else:
            embed = discord.Embed(title="Server has no icon!", color=Color.random())
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    # Server Banner command
    @serverGroup.command(name="banner", description="Show the server's banner.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    async def server_banner(
        self, interaction: discord.Interaction, ephemeral: bool = False
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        # Handle no banner
        if interaction.guild.banner is not None:
            embed = discord.Embed(title="Server Banner", color=Color.random())
            embed.set_image(url=interaction.guild.banner.url)
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )
            embed.set_author(
                name=interaction.guild.name,
                icon_url=(
                    interaction.guild.icon.url
                    if interaction.guild.icon is not None
                    else None
                ),
            )

            view = View()
            view.add_item(
                discord.ui.Button(
                    label="Open in Browser",
                    style=discord.ButtonStyle.url,
                    url=interaction.guild.banner.url,
                    row=0,
                )
            )

            # Send Embed
            await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)
        else:
            embed = discord.Embed(title="Server has no banner!", color=Color.random())
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    # Server Info command
    @serverGroup.command(name="info", description="Get info about the server.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    async def server_info(
        self, interaction: discord.Interaction, ephemeral: bool = False
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        embed = discord.Embed(
            title="Server Info",
            color=Color.random(),
        )

        embed.set_author(
            name=interaction.guild.name,
            icon_url=(
                interaction.guild.icon.url
                if interaction.guild.icon is not None
                else None
            ),
        )

        # Member count
        embed.add_field(name="Total Members", value=interaction.guild.member_count)

        # Creation date
        embed.add_field(
            name="Creation Date",
            value=f"<t:{int(interaction.guild.created_at.timestamp())}:d>",
        )

        # Owner
        try:
            embed.add_field(name="Owner", value=interaction.guild.owner.mention)
        except AttributeError:
            embed.add_field(name="Owner", value="Unknown")

        # Channel counts
        embed.add_field(
            name="Text Channels", value=len(interaction.guild.text_channels)
        )
        embed.add_field(
            name="Voice Channels", value=len(interaction.guild.voice_channels)
        )
        embed.add_field(name="Categories", value=len(interaction.guild.categories))

        embed.add_field(name="Server ID", value=interaction.guild.id)

        view = View()

        # Skip button when there's no vanity invite
        try:
            if interaction.guild.vanity_url is not None:
                view.add_item(
                    discord.ui.Button(
                        style=discord.ButtonStyle.url,
                        url=interaction.guild.vanity_url,
                        label="Vanity Invite",
                    )
                )
        except Exception:
            pass

        # Handle no icon
        try:
            (
                embed.set_thumbnail(url=interaction.guild.icon.url)
                if interaction.guild.icon is not None
                else None
            )
        except AttributeError:
            pass

        embed.set_footer(
            text=f"@{interaction.user.name}",
            icon_url=interaction.user.display_avatar.url,
        )

        # Send Embed
        await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)

    # Server Info command
    @serverGroup.command(
        name="boosts", description="Get info about this server's boosts."
    )
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    async def server_boost(
        self, interaction: discord.Interaction, ephemeral: bool = False
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        embed = discord.Embed(title="Server Boosts", color=Color.random())

        embed.set_author(
            name=interaction.guild.name,
            icon_url=(
                interaction.guild.icon.url
                if interaction.guild.icon is not None
                else None
            ),
        )

        # Boost counts
        embed.add_field(
            name="Total Boosts", value=interaction.guild.premium_subscription_count
        )
        embed.add_field(
            name="Level", value=f"Level {interaction.guild.premium_tier}", inline=True
        )

        embed.set_footer(
            text=f"@{interaction.user.name}",
            icon_url=interaction.user.display_avatar.url,
        )

        # Send Embed
        await interaction.followup.send(embed=embed, ephemeral=ephemeral)


async def setup(bot):
    await bot.add_cog(ServerUtils(bot))

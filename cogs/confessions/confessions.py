from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from discord import Colour, Embed, app_commands
from discord.ext import commands
from discord.ui import Button, View
from discord.utils import format_dt

from lib.classes.guild_logger import GuildLogger
from lib.embeds.general import guild_only, invalid_duration
from lib.helpers.duration import DurationTransformer
from lib.helpers.hybrid import SlashCommandOnly
from lib.logic.polls import create_anonymous_poll
from lib.views.polls import CloseNowButton, DeletePollButton, VoteButton

if TYPE_CHECKING:
    from main import TitaniumBot


class ConfessionCog(commands.Cog, name="Confession", description="Anonymous message commands."):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot: TitaniumBot = bot

    async def cog_load(self) -> None:
        self.bot.add_dynamic_items(VoteButton, CloseNowButton, DeletePollButton)

    @commands.command(name="anonymous", description="Please use the slash command version instead.")
    async def confession_prefix(self, ctx: commands.Context["TitaniumBot"]) -> None:
        raise SlashCommandOnly

    context = discord.app_commands.AppCommandContext(
        guild=True, dm_channel=False, private_channel=False
    )
    installs = discord.app_commands.AppInstallationType(guild=True, user=False)
    default_permissions = discord.Permissions(view_channel=True, send_messages=True)
    confession_group = app_commands.Group(
        name="anonymous",
        description="Create anonymous confessions and polls.",
        allowed_contexts=context,
        allowed_installs=installs,
        default_permissions=default_permissions,
    )

    async def interaction_check(self, interaction: discord.Interaction["TitaniumBot"]) -> bool:
        if not interaction.guild:
            raise ValueError("Guild only command but no guild available")

        guild_settings = await self.bot.fetch_guild_config(interaction.guild.id)
        if not guild_settings or not guild_settings.confessions_enabled:
            await interaction.response.send_message(
                embed=Embed(
                    colour=Colour.red(),
                    title=f"{self.bot.error_emoji} Confessions Disabled",
                    description="The confession module is disabled. Ask a server admin to turn it on using the `/settings` command or the Titanium Dashboard.",
                ),
                ephemeral=True,
            )
            return False

        return True

    @confession_group.command(name="confession", description="Send an anonymous confession.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(view_channel=True, send_messages=True)
    @app_commands.checks.bot_has_permissions(view_channel=True, send_messages=True)
    @app_commands.describe(
        message="Your message to include in the confession.",
        image="Optional: add an image to include with the confession.",
    )
    @app_commands.checks.cooldown(1, 10)
    async def confession(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        message: str,
        image: discord.Attachment | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None or not interaction.is_guild_integration():
            return

        if image and (not image.content_type or not image.content_type.startswith("image/")):
            await interaction.followup.send(
                embed=Embed(
                    colour=Colour.red(),
                    title=f"{self.bot.error_emoji} Invalid File",
                    description="The attached file must be an image.",
                ),
                ephemeral=True,
            )
            return

        if not isinstance(interaction.channel, discord.abc.Messageable):
            await interaction.followup.send(
                embed=Embed(
                    colour=Colour.red(),
                    title=f"{self.bot.error_emoji} Invalid Channel",
                    description="Confessions cannot be sent from this channel type. Please use a different channel.",
                ),
                ephemeral=True,
            )
            return

        guild_settings = await self.bot.fetch_guild_config(interaction.guild.id)
        if not guild_settings or not guild_settings.confessions_settings:
            raise RuntimeError("No config returned")

        channel = interaction.channel
        if (
            not guild_settings.confessions_settings.confessions_in_channel
            and guild_settings.confessions_settings.confessions_channel_id
        ):
            channel = interaction.guild.get_channel(
                guild_settings.confessions_settings.confessions_channel_id
            )

        if not channel:
            await interaction.followup.send(
                embed=Embed(
                    colour=Colour.red(),
                    title=f"{self.bot.error_emoji} Channel Not Found",
                    description=(
                        "The confession channel is not set or could not be found. Ask a server admin to configure it using the Titanium Dashboard."
                    ),
                ),
                ephemeral=True,
            )
            return

        if not isinstance(channel, discord.abc.Messageable):
            await interaction.followup.send(
                embed=Embed(
                    colour=Colour.red(),
                    title=f"{self.bot.error_emoji} Invalid Channel",
                    description="Titanium can't send to the configured confession channel. Please ask a server admin to set a valid channel using the Titanium Dashboard.",
                ),
                ephemeral=True,
            )
            return

        if not channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.followup.send(
                embed=Embed(
                    colour=Colour.red(),
                    title=f"{self.bot.error_emoji} Invalid Permissions",
                    description="Titanium doesn't have permission to send to the configured confession channel. Please ask a server admin to give Titanium send message permissions in the selected channel.",
                ),
                ephemeral=True,
            )
            return

        embed = Embed(
            title="Anonymous Confession",
            description=message,
            colour=Colour.light_grey(),
            timestamp=interaction.created_at,
        )
        if image and guild_settings.confessions_settings.attachments_allowed:
            embed.set_image(url=image.url)

        conf_msg = await channel.send(embed=embed)

        if isinstance(channel, discord.abc.GuildChannel):
            logger = GuildLogger(self.bot, interaction.guild)
            await logger.titanium_confession(
                interaction=interaction,
                confession_channel=channel,
                message=message,
                image=(
                    image
                    if image and guild_settings.confessions_settings.attachments_allowed
                    else None
                ),
            )

        embed = Embed(
            title=f"{self.bot.success_emoji} Sent",
            description="Your confession has been sent.",
            colour=Colour.green(),
        )

        if image and not guild_settings.confessions_settings.attachments_allowed:
            embed.add_field(
                name="Note",
                value=f"{interaction.client.info_emoji} Attachments in anonymous messages are disabled in this server. Ask a server admin to enable them in the Titanium Dashboard.",
            )

        await interaction.followup.send(
            embed=embed,
            view=View().add_item(
                Button(
                    label="View Confession",
                    url=conf_msg.jump_url,
                    style=discord.ButtonStyle.url,
                )
            ),
            ephemeral=True,
        )

    @confession_group.command(
        name="poll", description="Send an anonymous poll with up to 5 options, and an image."
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(view_channel=True, send_messages=True, send_polls=True)
    @app_commands.checks.bot_has_permissions(view_channel=True, send_messages=True)
    @app_commands.describe(
        title="The title of the poll.",
        duration="The duration to wait before ending the poll.",
        choice1="The first choice. Use the optional arguments to provide up to 4 more choices.",
        image_or_video="Optional: add an image or video to display alongside the title.",
        show_live_results="Optional: show live results while the poll is open. Defaults to true.",
    )
    @app_commands.checks.cooldown(1, 10)
    async def anonymous_poll(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        title: str,
        duration: app_commands.Transform[timedelta | None, DurationTransformer],
        choice1: app_commands.Range[str, 1, 100],
        choice2: app_commands.Range[str, 1, 100] | None = None,
        choice3: app_commands.Range[str, 1, 100] | None = None,
        choice4: app_commands.Range[str, 1, 100] | None = None,
        choice5: app_commands.Range[str, 1, 100] | None = None,
        image_or_video: discord.Attachment | None = None,
        show_live_results: bool = True,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="You have opted out of data collection and cannot use this feature.",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if image_or_video and (
            not image_or_video.content_type
            or (
                not image_or_video.content_type.startswith("image/")
                and not image_or_video.content_type.startswith("video/")
            )
        ):
            await interaction.followup.send(
                embed=Embed(
                    colour=Colour.red(),
                    title=f"{self.bot.error_emoji} Invalid File",
                    description="The attached file must be an image.",
                ),
                ephemeral=True,
            )
            return

        if (
            not interaction.channel_id
            or not interaction.channel
            or not interaction.guild_id
            or not interaction.guild
            or not isinstance(interaction.channel, discord.abc.GuildChannel)
        ):
            await interaction.followup.send(embed=guild_only(self.bot), ephemeral=True)
            return

        if not isinstance(interaction.channel, discord.abc.Messageable):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Error",
                description="The current channel does not support messages.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if not interaction.channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.followup.send(
                embed=Embed(
                    colour=Colour.red(),
                    title=f"{self.bot.error_emoji} Invalid Permissions",
                    description="Titanium doesn't have permission to send messages in this channel. Please ask a server admin to give Titanium send message permissions in this channel.",
                ),
                ephemeral=True,
            )
            return

        if not duration:
            await interaction.followup.send(embed=invalid_duration(self.bot), ephemeral=True)
            return

        guild_settings = await self.bot.fetch_guild_config(interaction.guild.id)
        if not guild_settings or not guild_settings.confessions_settings:
            raise RuntimeError("No config returned")

        if not guild_settings.confessions_settings.polls_enabled:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Polls Disabled",
                description="Anonymous Polls are disabled in this server. Ask a server admin to enable them in the Titanium Dashboard.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        choices = [choice1, choice2, choice3, choice4, choice5]
        choices = [choice for choice in choices if choice is not None]
        closing_time = interaction.created_at + duration

        await create_anonymous_poll(
            bot=self.bot,
            channel=interaction.channel,
            creator=interaction.user,
            title=title,
            choices=choices,
            closing_time=closing_time,
            attachment=(
                image_or_video
                if image_or_video and guild_settings.confessions_settings.attachments_allowed
                else None
            ),
            show_live_results=show_live_results,
        )

        embed = Embed(
            title=f"{self.bot.success_emoji} Created",
            description=f"Your poll has been created. It will close {format_dt(closing_time, style='R')} ({format_dt(closing_time)}), or when you press the close / delete button.",
            colour=Colour.green(),
        )

        if image_or_video and not guild_settings.confessions_settings.attachments_allowed:
            embed.add_field(
                name="Note",
                value=f"{interaction.client.info_emoji} Attachments in anonymous messages are disabled in this server. Ask a server admin to enable them in the Titanium Dashboard.",
            )

        await interaction.followup.send(
            embed=embed,
            ephemeral=True,
        )


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(ConfessionCog(bot))

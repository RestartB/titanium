import re
from io import BytesIO
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from lib.classes.quote_config import QuoteData
from lib.enums.images import ImageFormats
from lib.helpers.hybrid import defer
from lib.logic.quote import create_quote_image
from lib.views.quote import QuoteView

if TYPE_CHECKING:
    from main import TitaniumBot


class QuoteCommandsCog(
    commands.Cog, name="Quotes", description="Generate quote images from messages or custom input."
):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot: TitaniumBot = bot

        # Quote option
        self.quote_ctx = app_commands.ContextMenu(
            name="Quote This",
            callback=self.quote_callback,
            allowed_contexts=discord.app_commands.AppCommandContext(
                guild=True, dm_channel=True, private_channel=True
            ),
            allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True),
        )

        self.bot.tree.add_command(self.quote_ctx)

    @app_commands.checks.cooldown(1, 5)
    async def quote_callback(
        self, interaction: discord.Interaction["TitaniumBot"], message: discord.Message
    ):
        await interaction.response.defer()

        if message.clean_content == "":
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Nothing to quote",
                description="Nothing to quote, there is no content in this message.",
                colour=discord.Colour.red(),
            )

            await interaction.followup.send(
                embed=embed,
            )

            return
        elif message.is_system():
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Nothing to quote",
                description="You cannot quote this message, as it is a system message.",
                colour=discord.Colour.red(),
            )

            await interaction.followup.send(
                embed=embed,
            )

            return

        pfp_data = BytesIO()
        await message.author.display_avatar.save(pfp_data)

        data = QuoteData(
            content=message.clean_content,
            user=message.author,
            runner_user=interaction.user,
            output_format=ImageFormats.GIF,
            pfp_data=pfp_data,
        )

        file = await create_quote_image(data=data)

        view = QuoteView(bot=self.bot, data=data)
        view.add_item(
            discord.ui.Button(
                label="Jump to Message", style=discord.ButtonStyle.link, url=message.jump_url
            )
        )

        await interaction.followup.send(file=file, view=view)

    @commands.hybrid_command(
        name="quote",
        description="Create a quote image. To quote messages, right click the message, click apps, then Quote This.",
    )
    @app_commands.describe(
        user="The user to quote.",
        content="The content to quote. To quote messages, right click the message, click apps, then Quote This.",
        output_format="Optional: the format to use. Defaults to GIF.",
        fade="Optional: whether to apply a fade to the user's PFP. Defaults to true.",
        nickname="Optional: whether to show the user's nickname. Defaults to false.",
        light_mode="Optional: whether to start with light mode. Defaults to false.",
        bw_mode="Optional: whether to start with black and white mode. Defaults to false.",
        spoiler="Optional: whether to send the image as a spoiler. Defaults to false.",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.checks.cooldown(1, 5)
    async def custom_quote(
        self,
        ctx: commands.Context["TitaniumBot"],
        user: discord.User,
        *,
        content: str,
        output_format: ImageFormats | None = None,
        fade: bool = True,
        nickname: bool = False,
        light_mode: bool = False,
        bw_mode: bool = False,
        spoiler: bool = False,
    ):
        async with defer(ctx):
            pfp_data = BytesIO()
            await user.display_avatar.save(pfp_data)

            data = QuoteData(
                content=content,
                user=user,
                runner_user=ctx.author,
                output_format=output_format if output_format else ImageFormats.GIF,
                pfp_data=pfp_data,
                nickname=nickname,
                fade=fade,
                light_mode=light_mode,
                bw_mode=bw_mode,
                spoiler=spoiler,
                custom_quote=True,
            )

            # adapted from built in discord.py message.clean_content
            guild = ctx.guild
            if guild:

                def resolve_member(id: int) -> str:
                    member = guild.get_member(id)
                    return f"@{member.display_name if member else 'unknown-user'}"

                def resolve_channel(id: int) -> str:
                    channel = guild.get_channel(id)
                    return f"#{channel.name if channel else 'deleted-channel'}"

                def resolve_role(id: int) -> str:
                    role = guild.get_role(id)
                    return f"@{role.name if role else 'deleted-role'}"
            else:

                def resolve_member(id: int) -> str:
                    user = self.bot.get_user(id)
                    return f"@{user.name if user else 'unknown-user'}"

                def resolve_channel(id: int) -> str:
                    return "#unknown-channel"

                def resolve_role(id: int) -> str:
                    return "@unknown-role"

            transforms = {
                "@": resolve_member,
                "@!": resolve_member,
                "#": resolve_channel,
                "@&": resolve_role,
            }

            def repl(match: re.Match) -> str:
                type = match[1]
                id = int(match[2])
                transformed = transforms[type](id)
                return transformed

            data.content = re.sub(r"<(@[!&]?|#)([0-9]{15,20})>", repl, data.content)

            file = await create_quote_image(data)
            view = QuoteView(bot=self.bot, data=data)

            if output_format:
                view.remove_item(view.png_button)

            await ctx.reply(file=file, view=view)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(QuoteCommandsCog(bot))

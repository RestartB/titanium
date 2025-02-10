import discord
from discord import Color
from discord.ext import commands
from discord.ui import View


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Status Update
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        self.bot: commands.Bot

        try:
            embed = discord.Embed(
                title="Welcome to Titanium!",
                description="Titanium is your open source, multi purpose Discord bot. To see all of my commands, type `/`, then look through the list.",
                color=Color.green(),
            )
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            embed.add_field(
                name="Tips",
                value="""1. Use slash commands!
2. Enable the leaderboard! It allows you to track how many messages, words and attachments are being sent.
3. Enable the fireboard! It allows your members to copy a message to the fireboard channel when it gets enough reactions.""",
                inline=False,
            )
            embed.add_field(
                name="Feedback",
                value="Enjoy the bot? Drop a star on my GitHub repo! (it's free and helps me a ton!) Have a suggestion or has something gone wrong? Submit a GitHub issue and I'll take a look.",
                inline=False,
            )

            view = View()
            view.add_item(
                discord.ui.Button(
                    label="Website",
                    style=discord.ButtonStyle.url,
                    url="https://titaniumbot.me",
                )
            )
            view.add_item(
                discord.ui.Button(
                    label="Source Code",
                    style=discord.ButtonStyle.url,
                    url="https://github.com/restartb/titanium",
                )
            )
            view.add_item(
                discord.ui.Button(
                    label="Privacy Policy",
                    style=discord.ButtonStyle.url,
                    url="https://github.com/RestartB/titanium/blob/main/Privacy.md",
                )
            )
            view.add_item(
                discord.ui.Button(
                    label="Support Server",
                    style=discord.ButtonStyle.url,
                    url="https://discord.gg/FKc8gZUmhM",
                )
            )
            view.add_item(
                discord.ui.Button(
                    label="Bot Status",
                    style=discord.ButtonStyle.url,
                    url="https://status.titaniumbot.me/",
                )
            )

            if guild.system_channel is not None:
                if guild.system_channel.permissions_for(guild.me).send_messages:
                    await guild.system_channel.send(embed=embed, view=view)
                    return

            for channel in guild.channels:
                if channel.permissions_for(guild.me).send_messages:
                    await channel.send(embed=embed, view=view)
                    return
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(Welcome(bot))

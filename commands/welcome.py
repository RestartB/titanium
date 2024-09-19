import discord
from discord import Color
from discord.ext import commands

class welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    # Status Update
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        self.bot: commands.Bot
        
        try:
            embed = discord.Embed(title = "Welcome to Titanium!", description = "Titanium is an open source, multi purpose Discord bot. To see all of my commands, type `/`, then look through the list.", color=Color.green())
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            embed.add_field(name = "Tips", value = """1. Use slash commands!
2. Enable the leaderboard! It allows you to track how many messages, words and attachments are being sent.
3. Enable the fireboard! It allows your members to copy a message to the fireboard channel when it gets enough reactions.""", inline = False)
            embed.add_field(name = "Feedback", value = "Enjoy the bot? Drop a star on my GitHub repo! (it's free and helps me a ton!) Have a suggestion or has something gone wrong? Submit a GitHub issue and I'll take a look. https://github.com/restartb/titanium", inline = False)
            
            if guild.system_channel is not None:
                if guild.system_channel.permissions_for(guild.me).send_messages:
                    await guild.system_channel.send(embed = embed)
                    return
            
            for channel in guild.channels:
                if channel.permissions_for(guild.me).send_messages:
                    await channel.send(embed = embed)
                    return
        except Exception:
            pass

async def setup(bot):
    await bot.add_cog(welcome(bot))

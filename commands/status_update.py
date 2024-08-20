import discord
from discord.ext import commands
import asyncio

class status_update(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    # Listen for Messages
    @commands.Cog.listener()
    async def on_ready(self):
        members = 0
        
        for guild in self.bot.guilds:
            members += guild.member_count

        await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f"{members} users in {len(self.bot.guilds)} servers - / to see commands"))

        await asyncio.sleep(86400)

async def setup(bot):
    await bot.add_cog(status_update(bot))
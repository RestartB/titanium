import discord
from discord import app_commands, Color
from discord.ext import commands
from discord.ui import View
import asyncio
import random

class misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    funGroup = app_commands.Group(name="fun", description="Various fun commands.")
    
    # 8 Ball command
    @funGroup.command(name = "8ball", description = "Get an answer from the mystical 8 ball.")
    async def ball(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer()

        ball_list = ["It is certain.", "It is decidedly so.", "Without a doubt.", "Yes, definitely.", "You may rely on it.", "As I see it, yes.", "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.", "Reply hazy, try again.", "Ask again later.", "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.", "Don't count on it.", "My reply is no.", "My sources say no.", "Outlook not so good.", "Very doubtful."]
        
        # Truncate question if longer than 1024 characters
        if len(question) > 1024:
            question_trunc = question[:1021] + "..."
        else:
            question_trunc = question

        embed = discord.Embed(title = "Rolling...", color = Color.random())
        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)

        await interaction.followup.send(embed = embed)

        await asyncio.sleep(random.randint(2,4))

        embed = discord.Embed(title = "8 Ball", color = Color.random())
        embed.add_field(name = "Your Question", value = question_trunc, inline = False)
        embed.add_field(name = "8 Ball's Response", value = random.choice(ball_list))
        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)

        await interaction.edit_original_response(embed = embed)
    
    # Fish Command
    @funGroup.command(name = "fish", description = "Fish!")
    @app_commands.checks.cooldown(1,5)
    async def fish(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(title = "Fish!", color = Color.random())
        file = discord.File(f"{self.bot.path}{self.bot.pathtype}content{self.bot.pathtype}video_file{self.bot.pathtype}fish.mp4", filename = "fish.mp4")
        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
        await interaction.followup.send(embed = embed, file = file)

    # First Message command
    @app_commands.command(name = "first-message", description = "Get the first message in a channel, uses current channel by default.")
    async def first_message(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        await interaction.response.defer(ephemeral=True)
        
        # Send initial embed
        embed = discord.Embed(title = "Loading...", color = Color.orange())
        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
        await interaction.followup.send(embed = embed, ephemeral = True)

        try:
            if channel == None:
                channel = interaction.channel
            async for msg in channel.history(limit = 1, oldest_first = True):
                embed = discord.Embed(title = f"#{channel.name} - First Message", description=f"{msg.content}", color = Color.random())
                embed.set_footer(text = f"{msg.author.name} - {(msg.created_at).hour}:{(msg.created_at).minute} {(msg.created_at).day}/{(msg.created_at).month}/{(msg.created_at).year} UTC", icon_url = msg.author.avatar.url)
                view = View()
                view.add_item(discord.ui.Button(style = discord.ButtonStyle.url, url = msg.jump_url, label = "Jump to Message"))
                await interaction.edit_original_response(embed=embed, view=view)
        except discord.errors.Forbidden:
            embed = discord.Embed(title = "Forbidden", description = "The bot may not have permissions to view messages in the selected channel.", color = Color.red())
            await interaction.edit_original_response(embed=embed)
        except Exception:
            embed = discord.Embed(title = "Error", description = "**An error has occurred.\n\nSolutions**\n- Is the channel a text channel?\n- Has a message been sent here yet?\n- Try again later.", color = Color.red())
            await interaction.edit_original_response(embed=embed)
    
    # PFP command
    @app_commands.command(name = "pfp", description = "Show a user's PFP.")
    async def pfp(self, interaction: discord.Interaction, user: discord.User):
        await interaction.response.defer()
        # Idea: set embed colour to user's banner colour'
        embed = discord.Embed(title = f"PFP - {user.name}", color = Color.random())
        embed.set_image(url = user.avatar.url)
        embed.set_footer(text = f"Requested by {interaction.user.name} - right click or long press to save image", icon_url = interaction.user.avatar.url)
        # Send Embed
        await interaction.followup.send(embed = embed)
    
    
        
async def setup(bot):
    await bot.add_cog(misc(bot))
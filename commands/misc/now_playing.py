import discord
from discord import Color, app_commands
from discord.ext import commands
from discord.ui import View

import utils.spotify_elements as elements

from spotipy.oauth2 import SpotifyClientCredentials
import spotipy

import string
from colorthief import ColorThief
import random
import aiohttp
import os
from urllib.parse import quote_plus


class NowPlaying(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.auth_manager = SpotifyClientCredentials(client_id = self.bot.tokens['spotify-api-id'], client_secret = self.bot.tokens['spotify-api-secret'])
        self.sp = spotipy.Spotify(auth_manager=self.auth_manager)
    
    # Now Playing command
    @app_commands.command(name = "now-playing", description = "Show current activity / now playing status.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user = "Optional: the user to show the activity of. If not provided, it will show your own activity.")
    async def nowPlaying(self, interaction: discord.Interaction, user: discord.User = None):
        if user is None:
            user = interaction.user
        
        # Check if Titanium is in a mutual guild with the user
        if user.mutual_guilds is None: 
            # Send error message - no mutual guilds
            await interaction.response.defer(ephemeral=True)
            embed = discord.Embed(title = "No Mutual Guilds", description="Titanium must be in a mutual guild with the user to be able to see their status.", color = Color.red())

            await interaction.followup.send(embed=embed, ephemeral=True)
            return 0
        else:
            # Get member from mutual guild
            await interaction.response.defer()
            
            member: discord.Member = user.mutual_guilds[0].get_member(user.id)

        # Check if user has an activity
        if member.activity is None:
            embed = discord.Embed(title = "No Activity", description=f"{user.mention} is currently not doing any activites.", color = Color.red())

            await interaction.followup.send(embed=embed)
        else:
            # Iterate through activities
            for activity in member.activities:
                # Pick first activity that is not a CustomActivity
                if isinstance(activity, discord.CustomActivity):
                    # Check if it is the only activity
                    if len(member.activities) == 1:
                        embed = discord.Embed(title = "No Activity", description=f"{user.mention} is currently not doing any activites.", color = Color.red())

                        await interaction.followup.send(embed=embed)
                    else:
                        pass
                else:
                    break
            
            # Check if activity is Spotify
            if isinstance(activity, discord.Spotify): # Spotify
                item = self.sp.track(activity.track_id)
                
                await elements.song(self, item=item, interaction=interaction)
            else: # Other
                # Set Activity String
                if activity.type == discord.ActivityType.playing:
                    activityType = "Playing"
                elif activity.type == discord.ActivityType.streaming:
                    activityType = "Streaming"
                elif activity.type == discord.ActivityType.listening:
                    activityType = "Listening"
                elif activity.type == discord.ActivityType.watching:
                    activityType = "Watching"
                elif activity.type == discord.ActivityType.custom:
                    activityType = "Custom"
                else:
                    activityType = ""
                
                # Select colour
                if activity.large_image_url is not None:
                    color = Color.from_rgb(r=255, g=255, b=255)
                else:
                    color = Color.random()
                
                if activity.details:
                    # Create Embed
                    embed = discord.Embed(title = f"{activity.details}", description=activity.state, color=Color.random())
                    embed.set_author(name=f"{activityType}{(" to " if activityType == "Listening" else " - ") if activity.small_image_text is not None else ''}{activity.small_image_text}", icon_url=activity.small_image_url)

                    embed.set_footer(text=f"@{user.name} - {activity.name}", icon_url=user.display_avatar.url)
                    embed.set_thumbnail(url=activity.large_image_url)

                    # Create View
                    view = View()
                    
                    if activity.url is not None:
                        view.add_item(discord.ui.Button(url=activity.url, label="View Activity", style=discord.ButtonStyle.url))
                    
                    try:
                        view.add_item(discord.ui.Button(url=f'https://www.google.com/search?q={quote_plus(activity.details)}+{quote_plus(activity.state)}+{quote_plus(activity.small_image_text)}', label="Search on Google", style=discord.ButtonStyle.url))
                    except Exception:
                        pass
                    
                    # Send Embed
                    await interaction.followup.send(embed=embed, view=view)
                else:
                    # Create Embed
                    embed = discord.Embed(title = f"{activityType}{(' to' if activityType == 'Listening' else '')}", description=activity.name, color=Color.random())

                    embed.set_author(name=f"@{user.name}", icon_url=user.display_avatar.url)
                    embed.set_thumbnail(url=activity.large_image_url)

                    # Create View
                    view = View()
                    
                    if activity.url is not None:
                        view.add_item(discord.ui.Button(url=activity.url, label="View Activity", style=discord.ButtonStyle.url))
                    
                    # Send Embed
                    await interaction.followup.send(embed=embed, view=view)

                letters = string.ascii_lowercase
                filename = ''.join(random.choice(letters) for i in range(8))

                async with aiohttp.ClientSession() as session:
                    async with session.get(activity.large_image_url) as request:
                        file = open(f'{filename}.jpg', 'wb')
                        async for chunk in request.content.iter_chunked(10):
                            file.write(chunk)
                        file.close()
                        
                color_thief = ColorThief(f'{filename}.jpg')
                dominant_color = color_thief.get_color()

                os.remove(f'{filename}.jpg')

                embed.color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2])

                await interaction.edit_original_response(embed=embed)

async def setup(bot):
    await bot.add_cog(NowPlaying(bot))

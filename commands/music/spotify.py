import os
import random
import string

import aiohttp
import discord
import spotipy
from colorthief import ColorThief
from discord import Color, app_commands
from discord.ext import commands
from discord.ui import Select, View
from spotipy.oauth2 import SpotifyClientCredentials

import utils.spotify_elements as elements


class spotify(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auth_manager = SpotifyClientCredentials(client_id = self.bot.spotify_id, client_secret = self.bot.spotify_secret)
        self.sp = spotipy.Spotify(auth_manager=self.auth_manager)

    context = discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True)
    installs = discord.app_commands.AppInstallationType(guild=True, user=True)
    spotifyGroup = app_commands.Group(name="spotify", description="Spotify related commands.", allowed_contexts=context, allowed_installs=installs)
    
    # Spotify Search command
    @spotifyGroup.command(name = "search", description = "Search Spotify.")
    @app_commands.checks.cooldown(1, 10)
    @app_commands.choices(search_type=[
            app_commands.Choice(name="Song", value="song"),
            app_commands.Choice(name="Artist", value="artist"),
            app_commands.Choice(name="Album", value="album"),
            ])
    @app_commands.describe(search_type = "The type of media you are searching for. Supported types are song, artist and album.")
    @app_commands.describe(search = "What you are searching for.")
    @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissable message only visible to you. Defaults to false.")
    async def spotify_search(self, interaction: discord.Interaction, search_type: app_commands.Choice[str], search: str, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        
        options_list = []
        
        if search_type.value == "song":
            # Search Spotify
            result = self.sp.search(search, type = 'track', limit = 5)

            # Check if result is blank
            if len(result['tracks']['items']) == 0:
                embed = discord.Embed(title = "Error", description="No results were found.", color = Color.red())
                await interaction.edit_original_response(embed = embed)
            else:
                # Sort through request data
                i = 0
                for item in result['tracks']['items']:   
                    if item['explicit'] == True:
                        if len(item['name']) > 86:
                            label = item['name'][:86] + "... (Explicit)"
                        else:
                            label = item['name'] + " (Explicit)"
                    else:
                        if len(item['name']) > 100:
                            label = item['name'][:97] + "..."
                        else:
                            label = item['name']
                    
                    artist_string = ""
                    
                    for artist in item['artists']:
                        if artist_string == "":
                            artist_string = artist['name']
                        else:
                            artist_string += f", {artist['name']}"
                    
                    if len(f"{artist_string} - {item['album']['name']}") > 100:
                        description = f"{artist_string} - {item['album']['name']}"[:97] + "..."
                    else:
                        description = f"{artist_string} - {item['album']['name']}"
                    
                    options_list.append(discord.SelectOption(label = label, description = description, value = i))
                    i += 1
                
                # Define options
                select = Select(options = options_list)

                embed = discord.Embed(title = "Select Song", description = f'Showing {len(result["tracks"]["items"])} results for "{search}"', color = Color.random())
                embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)

                # Response to user selection
                async def response(interaction: discord.Interaction):
                    await interaction.response.defer(ephemeral=ephemeral)
                    
                    # Find unique ID of selection in the list
                    item = result['tracks']['items'][int(select.values[0])]

                    await elements.song(self=self, item=item, interaction=interaction, ephemeral=ephemeral)
            # Set up list with provided values
            select.callback = response
            view = View()
            view.add_item(select)

            # Edit initial message to show dropdown
            await interaction.edit_original_response(embed = embed, view = view)
        elif search_type.value == "artist":
            # Search Spotify
            result = self.sp.search(search, type = 'artist', limit = 5)

            # Check if result is blank
            if len(result['artists']['items']) == 0:
                embed = discord.Embed(title = "Error", description="No results were found.", color = Color.red())
                await interaction.edit_original_response(embed = embed)
            else:
                # Sort through request data
                i = 0
                for item in result['artists']['items']:
                    if len(item['name']) > 100:
                        title = item['name'][:97] + "..."
                    else:
                        title = item['name']
                    
                    options_list.append(discord.SelectOption(label = title, value = i))
                    i += 1
                
                # Define options
                select = Select(options=options_list)

                embed = discord.Embed(title = "Select Artist", description = f'Showing {len(result["artists"]["items"])} results for "{search}"', color = Color.random())
                embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)

                # Response to user selection
                async def response(interaction: discord.Interaction):
                    await interaction.response.defer(ephemeral=ephemeral)
                    
                    item = result['artists']['items'][int(select.values[0])]

                    result_info = self.sp.artist(item['id'])

                    result_top_tracks = self.sp.artist_top_tracks(item['id'])
                    
                    await elements.artist(self=self, item=result_info, top_tracks=result_top_tracks, interaction=interaction, ephemeral=ephemeral)
                # Set up list with provided values
                select.callback = response
                view = View()
                view.add_item(select)

                # Edit initial message to show dropdown
                await interaction.edit_original_response(embed = embed, view = view)
        elif search_type.value == "album":
            # Search Spotify
            result = self.sp.search(search, type = 'album', limit = 5)
            
            # Check if result is blank
            if len(result['albums']['items']) == 0:
                embed = discord.Embed(title = "Error", description="No results were found.", color = Color.red())
                await interaction.edit_original_response(embed = embed)
            else:
                # Sort through request data
                i = 0
                for item in result['albums']['items']:
                    artist_string = ""
                    for artist in item['artists']:
                        if artist_string == "":
                            artist_string = artist['name'].replace('*', '-') 
                        else:
                            artist_string += f", {artist['name']}".replace('*', '-')
                    
                    if len(item['name']) > 100:
                        title = item['name'][:97] + "..."
                    else:
                        title = item['name']
                    
                    if len(artist_string) > 100:
                        description = artist_string[:97] + "..."
                    else:
                        description = artist_string
                    
                    options_list.append(discord.SelectOption(label = title, description = description, value = i))
                    i += 1
                
                # Define options
                select = Select(options=options_list)

                embed = discord.Embed(title = "Select Album", description = f'Showing {len(result["albums"]["items"])} results for "{search}"', color = Color.random())
                embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)

                # Response to user selection
                async def response(interaction: discord.Interaction):
                    await interaction.response.defer(ephemeral=ephemeral)
                    
                    item = result['albums']['items'][int(select.values[0])]

                    result_info = self.sp.album(item['id'])
                    
                    await elements.album(self=self, item=result_info, interaction=interaction, ephemeral=ephemeral)
                
                # Set up list with provided values
                select.callback = response
                view = View()
                view.add_item(select)
                
                # Edit initial message to show dropdown
                await interaction.edit_original_response(embed = embed, view = view)

    # Spotify Image command
    @spotifyGroup.command(name = "image", description = "Get high quality album art from a Spotify URL.")
    @app_commands.describe(url = "The target Spotify URL. Song, album, playlist and spotify.link URLs are supported.")
    @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissable message only visible to you. Defaults to false.")
    @app_commands.checks.cooldown(1, 10)
    async def spotify_image(self, interaction: discord.Interaction, url: str, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        
        if "spotify.link" in url:
            try:  
                url = url.replace('www.', '').replace('http://', '').replace('https://', '').rstrip('/')
                url = f"https://{url}"
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as request:
                        url = str(request.url)
                    
                url_expanded = True
            except Exception as error:
                print("[SPOTIMG] Error while expanding URL.")
                print(error)
                if interaction.user.id in self.bot.dev_ids:
                    embed = discord.Embed(title = "Error occurred while expanding URL.", description = error, color = Color.red())
                    embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                    await interaction.followup.send(embed = embed, ephemeral=ephemeral)
                    return
                else:
                    embed = discord.Embed(title = "Error occurred while expanding URL.", description = "A **spotify.link** was detected, but we could not expand it. Is it valid?\n\nIf you are sure the URL is valid and supported, please try again later or message <@563372552643149825> for assistance.", color = Color.red())
                    embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                    await interaction.followup.send(embed = embed, ephemeral=ephemeral)
                    return
        else:
            url_expanded = False
        
        embed = discord.Embed(title = "Loading...", description = f"{self.bot.loading_emoji} Getting images...", color = Color.orange())
        embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
        await interaction.followup.send(embed = embed, ephemeral=ephemeral)

        artist_string = ""

        try:
            if "track" in url:
                result = self.sp.track(url)
                
                for artist in result['artists']:
                    if artist_string == "":
                        artist_string = artist['name'] 
                    else:
                        artist_string += f", {artist['name']}"

                if result["album"]["images"] != None:
                    image_url = result["album"]["images"][0]["url"]

                    letters = string.ascii_lowercase
                    filename = ''.join(random.choice(letters) for i in range(8))

                    async with aiohttp.ClientSession() as session:
                        async with session.get(image_url) as request:
                            file = open(f'{filename}.jpg', 'wb')
                            async for chunk in request.content.iter_chunked(10):
                                file.write(chunk)
                            file.close()
                            
                    color_thief = ColorThief(f'{filename}.jpg')
                    dominant_color = color_thief.get_color()

                    os.remove(f'{filename}.jpg')
                    
                    if result["album"]["images"][0]['height'] == None or result["album"]["images"][0]['width'] == None:
                        embed = discord.Embed(title = f"{result['name']} ({artist_string}) - Album Art", description = "Viewing highest quality (Resolution unknown)", color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]))
                    else:
                        embed = discord.Embed(title = f"{result['name']} ({artist_string}) - Album Art", description = f"Viewing highest quality ({result['album']['images'][0]['width']}x{result['album']['images'][0]['height']})", color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]))
                    
                    embed.set_image(url = result["album"]["images"][0]["url"])
                    embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                    
                    view = View()
                    view.add_item(discord.ui.Button(label="Download", style=discord.ButtonStyle.url, url=result["images"][0]["url"]))
                    
                    await interaction.edit_original_response(embed = embed, view = view)
                else:
                    embed = discord.Embed(title = "No album art available.", color = Color.red())
                    embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                    await interaction.edit_original_response(embed = embed)
            elif "album" in url:
                result = self.sp.album(url)
                
                image_url = result["images"][0]["url"]

                # Generate random filename
                letters = string.ascii_lowercase
                filename = ''.join(random.choice(letters) for i in range(8))

                # Save image
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as request:
                        file = open(f'{filename}.jpg', 'wb')
                        async for chunk in request.content.iter_chunked(10):
                            file.write(chunk)
                        file.close()
                        
                # Get dominant colour for embed
                color_thief = ColorThief(f'{filename}.jpg')
                dominant_color = color_thief.get_color()

                # Remove file when done
                os.remove(f'{filename}.jpg')

                for artist in result['artists']:
                    if artist_string == "":
                        artist_string = artist['name'] 
                    else:
                        artist_string += f", {artist['name']}"

                if result["images"] != None:
                    if result["images"][0]['height'] == None or result["images"][0]['width'] == None:
                        embed = discord.Embed(title = f"{result['name']} ({artist_string}) - Album Art", description = "Viewing highest quality (Resolution unknown)", color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]))
                    else:
                        embed = discord.Embed(title = f"{result['name']} ({artist_string}) - Album Art", description = f"Viewing highest quality ({result['images'][0]['width']}x{result['images'][0]['height']})", color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]))
                    embed.set_image(url = result["images"][0]["url"])
                    embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                    
                    view = View()
                    view.add_item(discord.ui.Button(label="Download", style=discord.ButtonStyle.url, url=result["images"][0]["url"]))
                    
                    await interaction.edit_original_response(embed = embed, view = view)
                else:
                    embed = discord.Embed(title = "No album art available.", color = Color.red)
                    embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                    await interaction.edit_original_response(embed = embed)
            # Playlist URL
            elif "playlist" in url:
                # Search playlist on Spotify
                result = self.sp.playlist(url, market="GB")

                image_url = result["images"][0]["url"]

                # Generate random filename
                letters = string.ascii_lowercase
                filename = ''.join(random.choice(letters) for i in range(8))

                # Save image
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as request:
                        file = open(f'{filename}.jpg', 'wb')
                        async for chunk in request.content.iter_chunked(10):
                            file.write(chunk)
                        file.close()
                        
                # Get dominant colour for embed
                color_thief = ColorThief(f'{filename}.jpg')
                dominant_color = color_thief.get_color()

                # Remove file when done
                os.remove(f'{filename}.jpg')

                if result["images"] != None:
                    if result["images"][0]['height'] == None or result["images"][0]['width'] == None:
                        embed = discord.Embed(title = f"{result['name']} - {result['owner']['display_name']} (Playlist) - Cover Art", description = "Viewing highest quality (Resolution unknown)", color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]))
                    else:
                        embed = discord.Embed(title = f"{result['name']} - {result['owner']['display_name']} (Playlist) - Cover Art", description = f"Viewing highest quality ({result['images'][0]['width']}x{result['images'][0]['height']})", color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]))
                    embed.set_image(url = result["images"][0]["url"])
                    embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                    
                    view = View()
                    view.add_item(discord.ui.Button(label="Download", style=discord.ButtonStyle.url, url=result["images"][0]["url"]))
                    
                    await interaction.edit_original_response(embed = embed, view = view)
                else:
                    embed = discord.Embed(title = "No cover art available.", color = Color.red)
                    embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                    await interaction.edit_original_response(embed = embed)
            else:
                embed = discord.Embed(title = "Error", description = "Error while searching URL. Is it a valid and supported Spotify URL?", color = Color.red())
                embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                await interaction.edit_original_response(embed = embed)
        except spotipy.exceptions.SpotifyException:
            embed = discord.Embed(title = "Error", description = "Error while searching URL. Is it a valid and supported Spotify URL?", color = Color.red())
            embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
            await interaction.edit_original_response(embed = embed)

async def setup(bot):
    await bot.add_cog(spotify(bot))
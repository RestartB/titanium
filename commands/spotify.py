import discord
from discord import app_commands, Color, ButtonStyle
from discord.ext import commands
from discord.ui import View, Select
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from urllib.parse import quote
import random
import aiohttp
import string
from colorthief import ColorThief
import os

class spotify(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auth_manager = SpotifyClientCredentials(client_id = self.bot.spotify_id, client_secret = self.bot.spotify_secret)
        self.sp = spotipy.Spotify(auth_manager=self.auth_manager)

    # Spotify Search command
    @app_commands.command(name = "spotify", description = "Search Spotify.")
    @app_commands.checks.cooldown(1, 10)
    @app_commands.choices(search_type=[
            app_commands.Choice(name="Song", value="song"),
            app_commands.Choice(name="Artist", value="artist"),
            app_commands.Choice(name="Album", value="album"),
            ])
    @app_commands.describe(search_type = "The type of media you are searching for. Supported types are song, artist and album.")
    @app_commands.describe(search = "What you are searching for.")
    async def spotify_search(self, interaction: discord.Interaction, search_type: app_commands.Choice[str], search: str):
        await interaction.response.defer()

        options_list = []
        
        # Send initial embed
        embed = discord.Embed(title = "Please wait...", color = Color.orange())
        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
        await interaction.followup.send(embed = embed)
        
        try:
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
                                artist_string = f"{artist_string}, {artist['name']}"
                        
                        if len(f"{artist_string} - {item['album']['name']}") > 100:
                            description = f"{artist_string} - {item['album']['name']}"[:97] + "..."
                        else:
                            description = f"{artist_string} - {item['album']['name']}"
                        
                        options_list.append(discord.SelectOption(label = label, description = description, value = i))
                        i += 1
                    
                    # Define options
                    select = Select(options = options_list)

                    embed = discord.Embed(title = "Select Song", description = f'Showing {len(result["tracks"]["items"])} results for "{search}"', color = Color.random())
                    embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)

                    # Response to user selection
                    async def response(interaction: discord.Interaction):
                        await interaction.response.defer()
                        
                        # Find unique ID of selection in the list
                        item = result['tracks']['items'][int(select.values[0])]
                        
                        image_url = item['album']['images'][0]['url']

                        embed = discord.Embed(title = "Please wait...", color = Color.orange())
                        await interaction.edit_original_response(embed = embed, view = None)
                        
                        artist_string = ""
                        for artist in item['artists']:
                            if artist_string == "":
                                artist_string = artist['name']
                            else:
                                artist_string = f"{artist_string}, {artist['name']}"
                        
                        # Set up new embed
                        if item['explicit'] == True:
                            embed = discord.Embed(title = f"{item['name']} (Explicit)", color = Color.from_rgb(r = 255, g = 255, b = 255))
                        else:
                            embed = discord.Embed(title = item['name'], color = Color.from_rgb(r = 255, g = 255, b = 255))
                        embed.set_thumbnail(url = item['album']['images'][0]['url'])
                        embed.add_field(name = "Artists", value = artist_string, inline = True)
                        embed.add_field(name = "Album", value = item['album']['name'], inline = True)
                        embed.set_footer(text = "Getting colour information...")

                        # Define View
                        view = View()
                        
                        seconds, item['duration_ms'] = divmod(item['duration_ms'], 1000)
                        minutes, seconds = divmod(seconds, 60)

                        # Add Open in Spotify button
                        spotify_button = discord.ui.Button(label=f'Play on Spotify ({int(minutes):02d}:{int(seconds):02d})', style=discord.ButtonStyle.url, url=item['external_urls']['spotify'], row = 0)
                        view.add_item(spotify_button)

                        # Add song.link button                
                        songlink_button = discord.ui.Button(label="Other Streaming Services", style=discord.ButtonStyle.url, url=f"https://song.link/{item["external_urls"]["spotify"]}", row = 1)
                        view.add_item(songlink_button)
                        
                        # Add Search on YT Music button
                        ytm_button = discord.ui.Button(label='Search on YT Music', style=discord.ButtonStyle.url, url=f'https://music.youtube.com/search?q={(quote(item["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}', row = 1)
                        view.add_item(ytm_button)

                        # Add Search on Google button
                        google_button = discord.ui.Button(label='Search on Google', style=discord.ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(item["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}', row = 1)
                        view.add_item(google_button)
                        
                        # Send new embed
                        await interaction.edit_original_response(embed = embed, view = view)

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
                        dominant_color = color_thief.get_color(quality=1)

                        # Remove file when done
                        os.remove(f'{filename}.jpg')

                        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                        embed.color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2])

                        await interaction.edit_original_response(embed = embed)

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
                        options_list.append(discord.SelectOption(label = item['name'], value = i))
                        i += 1
                    
                    # Define options
                    select = Select(options=options_list)

                    embed = discord.Embed(title = "Select Artist", description = f'Showing {len(result["artists"]["items"])} results for "{search}"', color = Color.random())
                    embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)

                    # Response to user selection
                    async def response(interaction: discord.Interaction):
                        await interaction.response.defer()
                        
                        embed = discord.Embed(title = "Please wait...", color = Color.orange())
                        await interaction.edit_original_response(embed = embed, view = None)
                        
                        item = result['artists']['items'][int(select.values[0])]

                        result_info = self.sp.artist(item['id'])

                        result_top_tracks = self.sp.artist_top_tracks(item['id'])
                        
                        image_url = result_info["images"][0]["url"]
                        
                        embed = discord.Embed(title = f"{result_info['name']}", color = Color.from_rgb(r = 255, g = 255, b = 255))
                        embed.add_field(name = "Followers", value = f"{result_info['followers']['total']:,}")
                        embed.set_thumbnail(url = result_info["images"][0]["url"])
                        embed.set_footer(text = "Getting colour information...")

                        topsong_string = ""
                        for i in range(0,5):
                            artist_string = ""
                            for artist in result_top_tracks['tracks'][i]['artists']:
                                if artist_string == "":
                                    artist_string = artist['name'].replace('*', '-') 
                                else:
                                    artist_string = f"{artist_string}, {artist['name']}".replace('*', '-')
                                    
                            # Hide artist string from song listing if there is only one artist
                            if len(result_top_tracks['tracks'][i]['artists']) == 1:
                                if topsong_string == "":
                                    topsong_string = f"**{i + 1}: {result_top_tracks['tracks'][i]['name'].replace('*', '-')}**"
                                else:
                                    topsong_string = f"{topsong_string}\n**{i + 1}: {result_top_tracks['tracks'][i]['name'].replace('*', '-')}**"
                            else:
                                if topsong_string == "":
                                    topsong_string = f"**{i + 1}: {result_top_tracks['tracks'][i]['name'].replace('*', '-')}** - {artist_string}"
                                else:
                                    topsong_string = f"{topsong_string}\n**{i + 1}: {result_top_tracks['tracks'][i]['name'].replace('*', '-')}** - {artist_string}"
                        
                        embed.add_field(name = "Top Songs", value = topsong_string, inline = False)

                        view = View()
                        
                        # Add Open in Spotify button
                        spotify_button = discord.ui.Button(label=f'Show on Spotify', style=discord.ButtonStyle.url, url=result_info["external_urls"]["spotify"], row = 0)
                        view.add_item(spotify_button)

                        # Add song.link button                
                        songlink_button = discord.ui.Button(label="Other Streaming Services", style=discord.ButtonStyle.url, url=f"https://song.link/{result_info['external_urls']['spotify']}", row = 1)
                        view.add_item(songlink_button)

                        # Add Search on YT Music button
                        ytm_button = discord.ui.Button(label='Search on YT Music', style=discord.ButtonStyle.url, url=f'https://music.youtube.com/search?q={(quote(result_info["name"])).replace("%2B", "+")}', row = 1)
                        view.add_item(ytm_button)

                        # Add Search on Google button
                        google_button = discord.ui.Button(label='Search on Google', style=discord.ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(result_info["name"])).replace("%2B", "+")}', row = 1)
                        view.add_item(google_button)

                        await interaction.edit_original_response(embed = embed, view = view)

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
                        dominant_color = color_thief.get_color(quality=1)

                        # Remove file when done
                        os.remove(f'{filename}.jpg')

                        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                        embed.color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2])

                        await interaction.edit_original_response(embed = embed)
                    
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
                                artist_string = artist_string + ", " + artist['name'].replace('*', '-')
                        
                        options_list.append(discord.SelectOption(label = item['name'], description = artist_string, value = i))
                        i += 1
                    
                    # Define options
                    select = Select(options=options_list)

                    embed = discord.Embed(title = "Select Album", description = f'Showing {len(result["albums"]["items"])} results for "{search}"', color = Color.random())
                    embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)

                    # Response to user selection
                    async def response(interaction: discord.Interaction):
                        await interaction.response.defer()
                        
                        embed = discord.Embed(title = "Please wait...", color = Color.orange())
                        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                        await interaction.edit_original_response(embed = embed, view = None)
                        
                        item = result['albums']['items'][int(select.values[0])]

                        result_info = self.sp.album(item['id'])
                        
                        image_url = result_info["images"][0]["url"]
                        
                        songlist_string = ""
                        for i in range(len(result_info['tracks']['items'])):
                            artist_string = ""
                            for artist in result_info['tracks']['items'][i]['artists']:
                                if artist_string == "":
                                    artist_string = artist['name'].replace('*', '-') 
                                else:
                                    artist_string = artist_string + ", " + artist['name'].replace('*', '-')
                                    
                            # Hide artist string from song listing if there is only one artist
                            if len(result_info['tracks']['items'][i]['artists']) == 1:
                                if songlist_string == "":
                                    songlist_string = f"**{i + 1}: {result_info['tracks']['items'][i]['name'].replace('*', '-')}**"
                                else:
                                    songlist_string = f"{songlist_string}\n**{i + 1}: {result_info['tracks']['items'][i]['name'].replace('*', '-')}**"
                            else:
                                if songlist_string == "":
                                    songlist_string = f"**{i + 1}: {result_info['tracks']['items'][i]['name'].replace('*', '-')}** - {artist_string}"
                                else:
                                    songlist_string = f"{songlist_string}\n**{i + 1}: {result_info['tracks']['items'][i]['name'].replace('*', '-')}** - {artist_string}"

                        artist_string = ""
                        for artist in result_info['artists']:
                            if artist_string == "":
                                artist_string = artist['name'].replace('*', '-') 
                            else:
                                artist_string = artist_string + ", " + artist['name'].replace('*', '-')
                        
                        embed = discord.Embed(title = f"{result_info['name']} - {artist_string}", description = songlist_string, color = Color.from_rgb(r = 255, g = 255, b = 255))
                        embed.set_footer(text = "Getting colour information...")

                        embed.set_thumbnail(url = result_info["images"][0]["url"])

                        view = View()
                        
                        # Add Open in Spotify button
                        spotify_button = discord.ui.Button(label=f'Show on Spotify', style=discord.ButtonStyle.url, url=result_info["external_urls"]["spotify"], row = 0)
                        view.add_item(spotify_button)

                        # Add song.link button                
                        songlink_button = discord.ui.Button(label="Other Streaming Services", style=discord.ButtonStyle.url, url=f"https://song.link/{result_info['external_urls']['spotify']}", row = 1)
                        view.add_item(songlink_button)

                        # Add Search on YT Music button
                        ytm_button = discord.ui.Button(label='Search on YT Music', style=discord.ButtonStyle.url, url=f'https://music.youtube.com/search?q={(quote(result_info["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}', row = 1)
                        view.add_item(ytm_button)

                        # Add Search on Google button
                        google_button = discord.ui.Button(label='Search on Google', style=discord.ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(result_info["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}', row = 1)
                        view.add_item(google_button)

                        await interaction.edit_original_response(embed = embed, view = view)

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
                        dominant_color = color_thief.get_color(quality=1)

                        # Remove file when done
                        os.remove(f'{filename}.jpg')

                        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                        embed.color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2])

                        await interaction.edit_original_response(embed = embed)
                    
                    # Set up list with provided values
                    select.callback = response
                    view = View()
                    view.add_item(select)

                    # Edit initial message to show dropdown
                    await interaction.edit_original_response(embed = embed, view = view)
        except Exception as error:
            await interaction.response.defer(ephemeral = True)
            embed = discord.Embed(title = "Spotify - Error", description = "An unknown error has occurred. The error has been logged.")
            print("[SPOTIFY] Error has occurred. Error below:")
            print(error)
            await interaction.edit_original_response(embed = embed, view = None, ephemeral = True)

    # Spotify Image command
    @app_commands.command(name = "spotify-image", description = "Get album art from a Spotify URL.")
    @app_commands.describe(url = "The target Spotify URL. Song, album, playlist and spotify.link URLs are supported.")
    @app_commands.checks.cooldown(1, 10)
    async def spotify_image(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()
        
        if "spotify.link" in url:
            try:
                embed = discord.Embed(title = "Expanding URL...", color = Color.orange())
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                await interaction.followup.send(embed = embed)
                
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
                    embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                    await interaction.edit_original_response(embed = embed)
                    return
                else:
                    embed = discord.Embed(title = "Error occurred while expanding URL.", description = "A **spotify.link** was detected, but we could not expand it. Is it valid?\n\nIf you are sure the URL is valid and supported, please try again later or message <@563372552643149825> for assistance.", color = Color.red())
                    embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                    await interaction.edit_original_response(embed = embed)
                    return
        
        embed = discord.Embed(title = "Getting images...", color = Color.orange())
        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
        if url_expanded == True:
                await interaction.edit_original_response(embed = embed)
        else:
            await interaction.followup.send(embed = embed)

        artist_string = ""

        try:
            if "track" in url:
                result = self.sp.track(url)
                
                for artist in result['artists']:
                    if artist_string == "":
                        artist_string = artist['name'] 
                    else:
                        artist_string = f"{artist_string}, {artist['name']}"

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
                    dominant_color = color_thief.get_color(quality=1)

                    os.remove(f'{filename}.jpg')
                    
                    if result["album"]["images"][0]['height'] == None or result["album"]["images"][0]['width'] == None:
                        embed = discord.Embed(title = f"{result['name']} ({artist_string}) - Album Art", description = "Viewing highest quality (Resolution unknown)", color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]))
                    else:
                        embed = discord.Embed(title = f"{result['name']} ({artist_string}) - Album Art", description = f"Viewing highest quality ({result['album']['images'][0]['width']}x{result['album']['images'][0]['height']})", color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]))
                    
                    embed.set_image(url = result["album"]["images"][0]["url"])
                    embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                    await interaction.edit_original_response(embed = embed)
                else:
                    embed = discord.Embed(title = "No album art available.", color = Color.red())
                    embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
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
                dominant_color = color_thief.get_color(quality=1)

                # Remove file when done
                os.remove(f'{filename}.jpg')

                for artist in result['artists']:
                    if artist_string == "":
                        artist_string = artist['name'] 
                    else:
                        artist_string = f"{artist_string}, {artist['name']}"

                if result["images"] != None:
                    if result["images"][0]['height'] == None or result["images"][0]['width'] == None:
                        embed = discord.Embed(title = f"{result['name']} ({artist_string}) - Album Art", description = "Viewing highest quality (Resolution unknown)", color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]))
                    else:
                        embed = discord.Embed(title = f"{result['name']} ({artist_string}) - Album Art", description = f"Viewing highest quality ({result['images'][0]['width']}x{result['images'][0]['height']})", color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]))
                    embed.set_image(url = result["images"][0]["url"])
                    embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                    await interaction.edit_original_response(embed = embed)
                else:
                    embed = discord.Embed(title = "No album art available.", color = Color.red)
                    embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                    await interaction.edit_original_response(embed = embed)
        except Exception:
            embed = discord.Embed(title = "Unexpected Error", description = "Please try again later or message <@563372552643149825> for assistance.", color = Color.red())
            embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
            await interaction.edit_original_response(embed = embed, view = None)

async def setup(bot):
    await bot.add_cog(spotify(bot))
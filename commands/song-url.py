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

class song_url(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auth_manager = SpotifyClientCredentials(client_id = self.bot.spotify_id, client_secret = self.bot.spotify_secret)
        self.sp = spotipy.Spotify(auth_manager=self.auth_manager)
    
    # Song URL command
    @app_commands.command(name = "song-url", description = "Get info about a song link.")
    @app_commands.describe(url = "The target URL. Run /song-link-help for supported link types.")
    @app_commands.checks.cooldown(1, 15)
    async def spotify_url(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()

        embed = discord.Embed(title = "Please wait...", description = "For non Spotify links, this may take a moment. Hold tight!", color = Color.orange())
        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
        await interaction.followup.send(embed = embed)
        
        artist_string = ""

        if not("spotify" in url):
            try:
                processed_source = quote(url, safe='()*!\'')
                request_url = f"https://api.song.link/v1-alpha.1/links?url={processed_source}&userCountry=GB"
                
                # Send request to song.link
                async with aiohttp.ClientSession() as session:
                    async with session.get(request_url) as request:
                        request_data = await request.json()
                        request_status = request.status
                
                if request_status == 400:
                    embed = discord.Embed(title = "Invalid Link", description = "The link entered is not valid. Please ensure you are sending a valid link.", color = Color.red())
                    embed.add_field(name = "Supported URLs", value = "**Spotify:** Song, Artist, Album, Playlist, `spotify.link`\n**Others (Apple Music, YouTube, etc.):** Song Only")
                    embed.set_footer(text = f"Requested by {interaction.user.name} - powered by song.link", icon_url = interaction.user.avatar.url)
                    await interaction.edit_original_response(embed = embed)
                    return
                if not(request_status <= 200 or request_status >= 299) or (request_data['linksByPlatform']['spotify']['url'] == None):
                    embed = discord.Embed(title = "An error has occurred.", description = "An error has occurred while searching the URL.\n\n**Solutions:**\n1. Check the URL is a valid song URL.\n2. Try again later.", color = Color.red())
                    embed.add_field(name = "Supported URLs", value = "**Spotify:** Song, Artist, Album, Playlist, `spotify.link`\n**Others (Apple Music, YouTube, etc.):** Song")
                    if interaction.user.id in self.bot.dev_ids:
                        embed.add_field(name = "Error Code (Dev)", value = request_status)
                    embed.set_footer(text = f"Requested by {interaction.user.name} - powered by song.link", icon_url = interaction.user.avatar.url)
                    await interaction.edit_original_response(embed = embed)
                    return
                elif request_data['entitiesByUniqueId'][request_data['entityUniqueId']]['type'] != 'song':
                    embed = discord.Embed(title = "Unsupported Link Type", description = f"{request_data['entitiesByUniqueId'][request_data['entityUniqueId']]['type']} link types from this service are unsupported.", color = Color.red())
                    embed.add_field(name = "Supported URLs", value = "**Spotify:** Song, Artist, Album, Playlist, `spotify.link`\n**Others (Apple Music, YouTube, etc.):** Song")
                    embed.set_footer(text = f"Requested by {interaction.user.name} - powered by song.link", icon_url = interaction.user.avatar.url)
                    await interaction.edit_original_response(embed = embed)
                    return
                else:
                    url = request_data['linksByPlatform']['spotify']['url']
            except Exception:
                embed = discord.Embed(title = "Unexpected Error", description = "Please try again later or message <@563372552643149825> for assistance.", color = Color.red())
                await interaction.edit_original_response(embed = embed)
        
            # Set Platform Strings
            if request_data['entitiesByUniqueId'][request_data['entityUniqueId']]['apiProvider'] == "amazon":
                platform = "Play on Amazon Music"
                platform_api = request_data['entitiesByUniqueId'][request_data['entityUniqueId']]['apiProvider']
            elif request_data['entitiesByUniqueId'][request_data['entityUniqueId']]['apiProvider'] == "itunes":
                platform = "Play on Apple Music"
                platform_api = "appleMusic"
            elif request_data['entitiesByUniqueId'][request_data['entityUniqueId']]['apiProvider'] == "soundcloud":
                platform = "Play on SoundCloud"
                platform_api = request_data['entitiesByUniqueId'][request_data['entityUniqueId']]['apiProvider']
            elif request_data['entitiesByUniqueId'][request_data['entityUniqueId']]['apiProvider'] == "youtube":
                platform = "Play on YouTube"
                platform_api = request_data['entitiesByUniqueId'][request_data['entityUniqueId']]['apiProvider']
            else:
                platform = f"Play on {request_data['entitiesByUniqueId'][request_data['entityUniqueId']]['apiProvider'].title()}"
        else:
            platform = "spotify"
        
        try:
            if "spotify.link" in url:
                try:
                    embed = discord.Embed(title = "Expanding URL...", color = Color.orange())
                    embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                    await interaction.edit_original_response(embed = embed)
                    
                    url = url.replace('www.', '').replace('http://', '').replace('https://', '').rstrip('/')
                    url = f"https://{url}"
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as request:
                            url = str(request.url)
                except Exception as error:
                    print("[SPOTURL] Error while expanding URL.")
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
            
            if "track" in url:
                result = self.sp.track(url)
                
                image_url = result["album"]["images"][0]["url"]

                if result['explicit'] == True:
                    embed = discord.Embed(title = f"{result['name']} (Explicit)", color = Color.from_rgb(r = 255, g = 255, b = 255))
                else:
                    embed = discord.Embed(title = f"{result['name']}", color = Color.from_rgb(r = 255, g = 255, b = 255))

                for artist in result['artists']:
                    if artist_string == "":
                        artist_string = artist['name'].replace('*', '-')
                    else:
                        artist_string = f"{artist_string}, {artist['name']}".replace('*', '-')
                
                embed.add_field(name = "Artists", value = artist_string, inline = True)
                embed.add_field(name = "Album", value = result['album']["name"], inline = True)
                embed.set_thumbnail(url = result["album"]["images"][0]["url"])
                embed.set_footer(text = "Getting colour information...")

                view = View()
                            
                seconds, result['duration_ms'] = divmod(result['duration_ms'], 1000)
                minutes, seconds = divmod(seconds, 60)

                # Add Open in Spotify button
                spotify_button = discord.ui.Button(label=f'Play on Spotify ({int(minutes):02d}:{int(seconds):02d})', style=discord.ButtonStyle.url, url=result["external_urls"]["spotify"], row = 0)
                view.add_item(spotify_button)

                # Show OG Platform button if OG platform isn't Spotify
                if platform != "spotify":
                    ogservice_button = discord.ui.Button(label=platform, style=discord.ButtonStyle.url, url=request_data['linksByPlatform'][platform_api]['url'], row = 0)
                    view.add_item(ogservice_button)

                if platform != "spotify":
                    songlink_button = discord.ui.Button(label="Global Link", style=discord.ButtonStyle.url, url=request_data['pageUrl'], row = 0)
                    view.add_item(songlink_button)
                
                # Add Search on YT Music button
                ytm_button = discord.ui.Button(label='Search on YT Music', style=discord.ButtonStyle.url, url=f'https://music.youtube.com/search?q={(quote(result["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}', row = 1)
                view.add_item(ytm_button)

                # Add Search on Google button
                google_button = discord.ui.Button(label='Search on Google', style=discord.ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(result["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}', row = 1)
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

                embed.set_footer(text = f"Requested by {interaction.user.name} - powered by song.link", icon_url = interaction.user.avatar.url)
                embed.color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2])

                await interaction.edit_original_response(embed = embed)
            elif "artist" in url:
                # Fetch artist info
                result_info = self.sp.artist(url)

                # Fetch artist top songs
                result_top_tracks = self.sp.artist_top_tracks(url)
                
                image_url = result_info["images"][0]["url"]

                embed = discord.Embed(title = "Parsing info...", color = Color.orange())
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                await interaction.edit_original_response(embed = embed)
                
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
            elif "album" in url:
                # Fetch artist info
                result_info = self.sp.album(url)
                
                image_url = result_info["images"][0]["url"]

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
                
                embed = discord.Embed(title = "Parsing info...", color = Color.orange())
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                await interaction.edit_original_response(embed = embed)
                
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
            elif "playlist" in url:
                # Search playlist on Spotify
                result_info = self.sp.playlist(url, market="GB")
                
                # Variables
                i = 0
                pages = []
                pageStr = ""

                embed = discord.Embed(title = "Getting images...", color = Color.orange())
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                await interaction.edit_original_response(embed = embed)
                
                # Get image URL
                image_url = result_info["images"][0]["url"]

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

                embed = discord.Embed(title = "Parsing info...", color = Color.orange())
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                await interaction.edit_original_response(embed = embed)
                
                # Work through all tracks in playlist, adding them to a page
                for playlist_item in result_info['tracks']['items']:
                    i += 1
                    artist_string = ""

                    # Check if item is a track, podcast, unavailable in current reigon or unknown
                    if playlist_item['track'] == None:
                        # Item type is unavailable in the GB reigon
                        # If there's nothing in the current page, make a new one
                        if pageStr == "":
                            pageStr = f"**{i}:** *(Media Unavailable)*"
                        # Else, add string to existing page
                        else:
                            pageStr = f"{pageStr}\n**{i}:** *(Media Unavailable)*"
                    elif playlist_item['track']['type'] == "track":
                        # Item is a track
                        # Work through all artists of item
                        for artist in playlist_item['track']['artists']:
                            # If there is no artists already in the artist string
                            if artist_string == "":
                                # We set the artist string to the artist we're currently on
                                artist_string = artist['name'].replace("*", "-")
                            else:
                                # Else, we add the current artist to the existing artist string
                                artist_string = f"{artist_string}, {artist['name']}".replace("*", "-")
                        
                        # If there's nothing in the current page, make a new one
                        if pageStr == "":
                            pageStr = f"**{i}: {playlist_item['track']['name'].replace('*', '-')}** - {artist_string}"
                        # Else, add string to existing page
                        else:
                            pageStr = f"{pageStr}\n**{i}: {playlist_item['track']['name'].replace('*', '-')}** - {artist_string}"
                    elif playlist_item['track']['type'] == "episode":
                        # Item is a podcast
                        if pageStr == "":
                            pageStr = f"**{i}: {playlist_item['track']['album']['name'].replace('*', '-')}** - {playlist_item['track']['name'].replace('*', '-')} (Podcast)"
                        else:
                            pageStr = f"{pageStr}\n**{i}: {playlist_item['track']['album']['name'].replace('*', '-')}** - {playlist_item['track']['name'].replace('*', '-')} (Podcast)"
                    else:
                        # Item type is unknown / unsupported
                        # If there's nothing in the current page, make a new one
                        if pageStr == "":
                            pageStr = f"**{i}:** *(Unknown Media Type)*"
                        # Else, add string to existing page
                        else:
                            pageStr = f"{pageStr}\n**{i}:** *(Unknown Media Type)*"

                    # If there's 25 items in the current page, we split it into a new page
                    if i % 25 == 0:
                        pages.append(pageStr)
                        pageStr = ""

                # If there is still data in pageStr, add it to a new page
                if pageStr != "":
                    pages.append(pageStr)
                    pageStr = ""

                # If there are more than 100 items in the playlist, we add a notice to the final page
                if result_info['tracks']['total'] > 100:
                    pages[-1] = f"{pages[-1]}\n\n**+{result_info['tracks']['total'] - 100} items**"

                # Define page view
                class PlaylistPagesController(View):
                    def __init__(self, pages):
                        super().__init__()
                        self.page = 0
                        self.pages = pages
                        spotify_button = discord.ui.Button(label=f'Show on Spotify', style=discord.ButtonStyle.url, url=result_info["external_urls"]["spotify"])
                        self.add_item(spotify_button)
                
                    @discord.ui.button(label="<", style=ButtonStyle.green, custom_id="prev")
                    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        if self.page > 0:
                            self.page -= 1
                        else:
                            self.page = len(self.pages) - 1
                        embed = discord.Embed(title = f"{result_info['name']} (Playlist)", description = f"by {result_info['owner']['display_name']} - {result_info['tracks']['total']} items\n\n{self.pages[self.page]}", color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]))
                        embed.set_thumbnail(url = result_info['images'][0]['url'])
                        embed.set_footer(text = f"Requested by {interaction.user.name} - Page {self.page + 1}/{len(pages)}", icon_url = interaction.user.avatar.url)
                        await interaction.response.edit_message(embed = embed)

                    @discord.ui.button(label=">", style=ButtonStyle.green, custom_id="next")
                    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        if self.page < len(self.pages) - 1:
                            self.page += 1
                        else:
                            self.page = 0
                        embed = discord.Embed(title = f"{result_info['name']} (Playlist)", description = f"by {result_info['owner']['display_name']} - {result_info['tracks']['total']} items\n\n{self.pages[self.page]}", color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]))
                        embed.set_thumbnail(url = result_info['images'][0]['url'])
                        embed.set_footer(text = f"Requested by {interaction.user.name} - Page {self.page + 1}/{len(pages)}", icon_url = interaction.user.avatar.url)
                        await interaction.response.edit_message(embed = embed)

                embed = discord.Embed(title = f"{result_info['name']} (Playlist)", description = f"by {result_info['owner']['display_name']} - {result_info['tracks']['total']} items\n\n{pages[0]}", color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]))
                embed.set_thumbnail(url = result_info['images'][0]['url'])
                embed.set_footer(text = f"Requested by {interaction.user.name} - Page 1/{len(pages)}", icon_url = interaction.user.avatar.url)
                
                # If there's only 1 page, make embed without page buttons
                if len(pages) == 1:
                    # Add Open in Spotify button
                    view = View()
                    spotify_button = discord.ui.Button(label=f'Show on Spotify', style=discord.ButtonStyle.url, url=result_info["external_urls"]["spotify"])
                    view.add_item(spotify_button)
                    
                    await interaction.edit_original_response(embed = embed, view = view)
                # Else, make embed with page buttons
                else:
                    await interaction.edit_original_response(embed = embed, view = PlaylistPagesController(pages))
            else:
                embed = discord.Embed(title = "Spotify - Error", description = "Error while searching URL. Is it a valid and supported Spotify URL?", color = Color.red())
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                await interaction.edit_original_response(embed = embed)
                return
        except Exception:
            embed = discord.Embed(title = "Spotify - Error", description = "Error while searching URL. Is it a valid and supported Spotify URL?", color = Color.red())
            await interaction.edit_original_response(embed = embed)

async def setup(bot):
    await bot.add_cog(song_url(bot))
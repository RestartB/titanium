import discord
from discord import app_commands, Color, ButtonStyle
from discord.ext import commands
from discord.ui import View, Select
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from urllib.parse import quote

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
    async def spotify_search(self, interaction: discord.Interaction, search_type: app_commands.Choice[str], search: str):
        await interaction.response.defer()

        options_list = []
        
        try:
            if search_type.value == "song":
                # Send initial embed
                embed = discord.Embed(title = "Searching...", color = Color.orange())
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                await interaction.followup.send(embed = embed)

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

                    embed = discord.Embed(title = "Select Song", description = f'Found {len(result["tracks"]["items"])} results for "{search}"', color = Color.random())
                    embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)

                    # Response to user selection
                    async def response(interaction: discord.Interaction):
                        await interaction.response.defer()
                        # Find unique ID of selection in the list
                        item = result['tracks']['items'][int(select.values[0])]

                        artist_string = ""
                        for artist in item['artists']:
                            if artist_string == "":
                                artist_string = artist['name']
                            else:
                                artist_string = f"{artist_string}, {artist['name']}"

                        # Set up new embed
                        if item['explicit'] == True:
                            embed = discord.Embed(title = f"{item['name']} (Explicit)", color = Color.random())
                        else:
                            embed = discord.Embed(title = item['name'], color = Color.random())
                        embed.set_thumbnail(url = item['album']['images'][0]['url'])
                        embed.add_field(name = "Artists", value = artist_string, inline = True)
                        embed.add_field(name = "Album", value = item['album']['name'], inline = True)
                        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)

                        # Define View
                        view = View()
                        
                        seconds, item['duration_ms'] = divmod(item['duration_ms'], 1000)
                        minutes, seconds = divmod(seconds, 60)

                        # Add Open in Spotify button
                        spotify_button = discord.ui.Button(label=f'Play on Spotify ({int(minutes):02d}:{int(seconds):02d})', style=discord.ButtonStyle.url, url=item['external_urls']['spotify'])
                        view.add_item(spotify_button)
                        
                        # Add Search on YT Music button
                        ytm_button = discord.ui.Button(label='Search on YT Music', style=discord.ButtonStyle.url, url=f'https://music.youtube.com/search?q={(quote(item["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}')
                        view.add_item(ytm_button)

                        # Add Search on Google button
                        google_button = discord.ui.Button(label='Search on Google', style=discord.ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(item["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}')
                        view.add_item(google_button)
                        
                        # Send new embed
                        await interaction.edit_original_response(embed = embed, view = view)
                        
                    # Set up list with provided values
                    select.callback = response
                    view = View()
                    view.add_item(select)

                    # Edit initial message to show dropdown
                    await interaction.edit_original_response(embed = embed, view = view)
            elif search_type.value == "artist":
                # Send initial embed
                embed = discord.Embed(title = "Searching...", color = Color.orange())
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                await interaction.followup.send(embed = embed)

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

                    embed = discord.Embed(title = "Select Artist", description = f'Found {len(result["artists"]["items"])} results for "{search}"', color = Color.random())
                    embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)

                    # Response to user selection
                    async def response(interaction: discord.Interaction):
                        await interaction.response.defer()
                        
                        item = result['artists']['items'][int(select.values[0])]

                        result_info = self.sp.artist(item['id'])

                        result_top_tracks = self.sp.artist_top_tracks(item['id'])

                        embed = discord.Embed(title = f"{result_info['name']}")
                        embed.add_field(name = "Followers", value = f"{result_info['followers']['total']:,}")
                        embed.set_thumbnail(url = result_info["images"][0]["url"])

                        topsong_string = ""
                        for i in range(0,5):
                            artist_string = ""
                            for artist in result_top_tracks['tracks'][i]['artists']:
                                if artist_string == "":
                                    artist_string = artist['name'] 
                                else:
                                    artist_string = f"{artist_string}, {artist['name']}"
                                    
                            if topsong_string == "":
                                topsong_string = f"**{i + 1}: {result_top_tracks['tracks'][i]['name']}** - {artist_string}"
                            else:
                                topsong_string = f"{topsong_string}\n**{i + 1}: {result_top_tracks['tracks'][i]['name']}** - {artist_string}"
                        
                        embed.add_field(name = "Top Songs", value = topsong_string, inline = False)

                        view = View()
                        
                        # Add Open in Spotify button
                        spotify_button = discord.ui.Button(label=f'Show on Spotify', style=discord.ButtonStyle.url, url=result_info["external_urls"]["spotify"])
                        view.add_item(spotify_button)

                        # Add Search on YT Music button
                        ytm_button = discord.ui.Button(label='Search on YT Music', style=discord.ButtonStyle.url, url=f'https://music.youtube.com/search?q={(quote(result_info["name"])).replace("%2B", "+")}')
                        view.add_item(ytm_button)

                        # Add Search on Google button
                        google_button = discord.ui.Button(label='Search on Google', style=discord.ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(result_info["name"])).replace("%2B", "+")}')
                        view.add_item(google_button)

                        await interaction.edit_original_response(embed = embed, view = view)
                    
                    # Set up list with provided values
                    select.callback = response
                    view = View()
                    view.add_item(select)

                    # Edit initial message to show dropdown
                    await interaction.edit_original_response(embed = embed, view = view)
            elif search_type.value == "album":
                # Send initial embed
                embed = discord.Embed(title = "Searching...", color = Color.orange())
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                await interaction.followup.send(embed = embed)

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
                        options_list.append(discord.SelectOption(label = item['name'], value = i))
                        i += 1
                    
                    # Define options
                    select = Select(options=options_list)

                    embed = discord.Embed(title = "Select Album", description = f'Found {len(result["albums"]["items"])} results for "{search}"', color = Color.random())
                    embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)

                    # Response to user selection
                    async def response(interaction: discord.Interaction):
                        await interaction.response.defer()
                        
                        item = result['albums']['items'][int(select.values[0])]

                        result_info = self.sp.album(item['id'])

                        songlist_string = ""
                        for i in range(len(result_info['tracks']['items'])):
                            artist_string = ""
                            for artist in result_info['tracks']['items'][i]['artists']:
                                if artist_string == "":
                                    artist_string = artist['name'] 
                                else:
                                    artist_string = artist_string + ", " + artist['name']
                                    
                            if songlist_string == "":
                                songlist_string = f"**{i + 1}: {result_info['tracks']['items'][i]['name']}** - {artist_string}"
                            else:
                                songlist_string = f"{songlist_string}\n**{i + 1}: {result_info['tracks']['items'][i]['name']}** - {artist_string}"

                        artist_string = ""
                        for artist in result_info['artists']:
                            if artist_string == "":
                                artist_string = artist['name'] 
                            else:
                                artist_string = artist_string + ", " + artist['name']
                        
                        embed = discord.Embed(title = f"{result_info['name']} - {artist_string}", description = songlist_string, color = Color.random())
                        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)

                        embed.set_thumbnail(url = result_info["images"][0]["url"])

                        view = View()
                        
                        # Add Open in Spotify button
                        spotify_button = discord.ui.Button(label=f'Show on Spotify', style=discord.ButtonStyle.url, url=result_info["external_urls"]["spotify"])
                        view.add_item(spotify_button)

                        # Add Search on YT Music button
                        ytm_button = discord.ui.Button(label='Search on YT Music', style=discord.ButtonStyle.url, url=f'https://music.youtube.com/search?q={(quote(result_info["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}')
                        view.add_item(ytm_button)

                        # Add Search on Google button
                        google_button = discord.ui.Button(label='Search on Google', style=discord.ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(result_info["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}')
                        view.add_item(google_button)

                        await interaction.edit_original_response(embed = embed, view = view)
                    
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

    # Spotify URL command
    @app_commands.command(name = "spotify_url", description = "Get info about a Spotify song, artist, album or playlist.")
    @app_commands.checks.cooldown(1, 10)
    async def spotify_url(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()
        
        embed = discord.Embed(title = "Searching...", color = Color.orange())
        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
        await interaction.followup.send(embed = embed)

        artist_string = ""

        try:
            if "track" in url:
                result = self.sp.track(url)
                
                if result['explicit'] == True:
                    embed = discord.Embed(title = f"{result['name']} (Explicit)", color = Color.random())
                else:
                    embed = discord.Embed(title = f"{result['name']}", color = Color.random())

                for artist in result['artists']:
                    if artist_string == "":
                        artist_string = artist['name']
                    else:
                        artist_string = f"{artist_string}, {artist['name']}"
                
                embed.add_field(name = "Artists", value = artist_string, inline = True)
                embed.add_field(name = "Album", value = result['album']["name"], inline = True)
                embed.set_thumbnail(url = result["album"]["images"][0]["url"])
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)

                view = View()
                            
                seconds, result['duration_ms'] = divmod(result['duration_ms'], 1000)
                minutes, seconds = divmod(seconds, 60)

                # Add Open in Spotify button
                spotify_button = discord.ui.Button(label=f'Play on Spotify ({int(minutes):02d}:{int(seconds):02d})', style=discord.ButtonStyle.url, url=result["external_urls"]["spotify"])
                view.add_item(spotify_button)
                
                # Add Search on YT Music button
                ytm_button = discord.ui.Button(label='Search on YT Music', style=discord.ButtonStyle.url, url=f'https://music.youtube.com/search?q={(quote(result["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}')
                view.add_item(ytm_button)

                # Add Search on Google button
                google_button = discord.ui.Button(label='Search on Google', style=discord.ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(result["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}')
                view.add_item(google_button)
                
                # Send new embed
                await interaction.edit_original_response(embed = embed, view = view)
            elif "artist" in url:
                # Fetch artist info
                result_info = self.sp.artist(url)

                # Fetch artist top songs
                result_top_tracks = self.sp.artist_top_tracks(url)

                embed = discord.Embed(title = f"{result_info['name']}", color = Color.random())
                embed.add_field(name = "Followers", value = f"{result_info['followers']['total']:,}")
                embed.set_thumbnail(url = result_info["images"][0]["url"])
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                
                topsong_string = ""
                for i in range(0,5):
                    artist_string = ""
                    for artist in result_top_tracks['tracks'][i]['artists']:
                        if artist_string == "":
                            artist_string = artist['name'] 
                        else:
                            artist_string = f"{artist_string}, {artist['name']}"
                            
                    if topsong_string == "":
                        topsong_string = f"**{i + 1}: {result_top_tracks['tracks'][i]['name']}** - {artist_string}"
                    else:
                        topsong_string = f"{topsong_string}\n**{i + 1}: {result_top_tracks['tracks'][i]['name']}** - {artist_string}"
                
                embed.add_field(name = "Top Songs", value = topsong_string, inline = False)

                view = View()
                
                # Add Open in Spotify button
                spotify_button = discord.ui.Button(label=f'Show on Spotify', style=discord.ButtonStyle.url, url=result_info["external_urls"]["spotify"])
                view.add_item(spotify_button)

                # Add Search on YT Music button
                ytm_button = discord.ui.Button(label='Search on YT Music', style=discord.ButtonStyle.url, url=f'https://music.youtube.com/search?q={(quote(result_info["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}')
                view.add_item(ytm_button)

                # Add Search on Google button
                google_button = discord.ui.Button(label='Search on Google', style=discord.ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(result_info["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}')
                view.add_item(google_button)

                await interaction.edit_original_response(embed = embed, view = view)
            elif "album" in url:
                # Fetch artist info
                result_info = self.sp.album(url)

                songlist_string = ""
                for i in range(len(result_info['tracks']['items'])):
                    artist_string = ""
                    for artist in result_info['tracks']['items'][i]['artists']:
                        if artist_string == "":
                            artist_string = artist['name'] 
                        else:
                            artist_string = artist_string + ", " + artist['name']
                            
                    if songlist_string == "":
                        songlist_string = f"**{i + 1}: {result_info['tracks']['items'][i]['name']}** - {artist_string}"
                    else:
                        songlist_string = f"{songlist_string}\n**{i + 1}: {result_info['tracks']['items'][i]['name']}** - {artist_string}"

                artist_string = ""
                for artist in result_info['artists']:
                    if artist_string == "":
                        artist_string = artist['name'] 
                    else:
                        artist_string = artist_string + ", " + artist['name']
                
                embed = discord.Embed(title = f"{result_info['name']} - {artist_string}", description = songlist_string, color = Color.random())
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)

                embed.set_thumbnail(url = result_info["images"][0]["url"])

                view = View()
                
                # Add Open in Spotify button
                spotify_button = discord.ui.Button(label=f'Show on Spotify', style=discord.ButtonStyle.url, url=result_info["external_urls"]["spotify"])
                view.add_item(spotify_button)

                # Add Search on YT Music button
                ytm_button = discord.ui.Button(label='Search on YT Music', style=discord.ButtonStyle.url, url=f'https://music.youtube.com/search?q={(quote(result_info["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}')
                view.add_item(ytm_button)

                # Add Search on Google button
                google_button = discord.ui.Button(label='Search on Google', style=discord.ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(result_info["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}')
                view.add_item(google_button)

                await interaction.edit_original_response(embed = embed, view = view)
            elif "playlist" in url:
                # Search playlist on Spotify
                result_info = self.sp.playlist(url, market="GB")
                
                # Variables
                i = 0
                pages = []
                pageStr = ""

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
                                artist_string = artist['name']
                            else:
                                # Else, we add the current artist to the existing artist string
                                artist_string = f"{artist_string}, {artist['name']}"
                        
                        # If there's nothing in the current page, make a new one
                        if pageStr == "":
                            pageStr = f"**{i}: {playlist_item['track']['name']}** - {artist_string}"
                        # Else, add string to existing page
                        else:
                            pageStr = f"{pageStr}\n**{i}: {playlist_item['track']['name']}** - {artist_string}"
                    elif playlist_item['track']['type'] == "episode":
                        # Item is a podcast
                        if pageStr == "":
                            pageStr = f"**{i}: {playlist_item['track']['album']['name']}** - {playlist_item['track']['name']} (Podcast)"
                        else:
                            pageStr = f"{pageStr}\n**{i}: {playlist_item['track']['album']['name']}** - {playlist_item['track']['name']} (Podcast)"
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
                        embed = discord.Embed(title = f"{result_info['name']} (Playlist)", description = f"by {result_info['owner']['display_name']} - {result_info['tracks']['total']} items\n\n{self.pages[self.page]}", color = Color.random())
                        embed.set_thumbnail(url = result_info['images'][0]['url'])
                        embed.set_footer(text = f"Requested by {interaction.user.name} - Page {self.page + 1}/{len(pages)}", icon_url = interaction.user.avatar.url)
                        await interaction.response.edit_message(embed = embed)

                    @discord.ui.button(label=">", style=ButtonStyle.green, custom_id="next")
                    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        if self.page < len(self.pages) - 1:
                            self.page += 1
                        else:
                            self.page = 0
                        embed = discord.Embed(title = f"{result_info['name']} (Playlist)", description = f"by {result_info['owner']['display_name']} - {result_info['tracks']['total']} items\n\n{self.pages[self.page]}", color = Color.random())
                        embed.set_thumbnail(url = result_info['images'][0]['url'])
                        embed.set_footer(text = f"Requested by {interaction.user.name} - Page {self.page + 1}/{len(pages)}")
                        await interaction.response.edit_message(embed = embed)

                embed = discord.Embed(title = f"{result_info['name']} (Playlist)", description = f"by {result_info['owner']['display_name']} - {result_info['tracks']['total']} items\n\n{pages[0]}", color = Color.random())
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
        except Exception:
            embed = discord.Embed(title = "Spotify - Error", description = "Error while searching URL. Is it a valid and supported Spotify URL?", color = Color.red())
            await interaction.edit_original_response(embed = embed)

    # Spotify Image command
    @app_commands.command(name = "spotify_image", description = "Get album art from a Spotify URL.")
    @app_commands.checks.cooldown(1, 10)
    async def spotify_image(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()
        
        embed = discord.Embed(title = "Searching...", color = Color.orange())
        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
        await interaction.followup.send(embed = embed)

        artist_string = ""

        if "track" in url:
            result = self.sp.track(url)
            
            for artist in result['artists']:
                if artist_string == "":
                    artist_string = artist['name'] 
                else:
                    artist_string = f"{artist_string}, {artist['name']}"

            if result["album"]["images"] != None:
                if result["album"]["images"][0]['height'] == None or result["album"]["images"][0]['width'] == None:
                    embed = discord.Embed(title = f"{result['name']} ({artist_string}) - Album Art", description = "Viewing highest quality (Resolution unknown)")
                else:
                    embed = discord.Embed(title = f"{result['name']} ({artist_string}) - Album Art", description = f"Viewing highest quality ({result['album']['images'][0]['width']}x{result['album']['images'][0]['height']})")
                
                embed.set_image(url = result["album"]["images"][0]["url"])
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                await interaction.edit_original_response(embed = embed)
            else:
                embed = discord.Embed(title = "No album art available.", color = Color.red)
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                await interaction.edit_original_response(embed = embed)
        elif "album" in url:
            result = self.sp.album(url)
            
            for artist in result['artists']:
                if artist_string == "":
                    artist_string = artist['name'] 
                else:
                    artist_string = f"{artist_string}, {artist['name']}"

            if result["images"] != None:
                if result["images"][0]['height'] == None or result["images"][0]['width'] == None:
                    embed = discord.Embed(title = f"{result['name']} ({artist_string}) - Album Art", description = "Viewing highest quality (Resolution unknown)")
                else:
                    embed = discord.Embed(title = f"{result['name']} ({artist_string}) - Album Art", description = f"Viewing highest quality ({result['images'][0]['width']}x{result['images'][0]['height']})")
                embed.set_image(url = result["images"][0]["url"])
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                await interaction.edit_original_response(embed = embed)
            else:
                embed = discord.Embed(title = "No album art available.", color = Color.red)
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                await interaction.edit_original_response(embed = embed)

async def setup(bot):
    await bot.add_cog(spotify(bot))
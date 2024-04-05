import discord
from discord import app_commands, Color, ButtonStyle
from discord.ext import commands
from discord.ui import Select, View
import aiohttp
from urllib.parse import quote

class music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Lyrics command
    @app_commands.command(name = "lyrics", description = "Find Lyrics to a song.")
    @app_commands.checks.cooldown(1, 10)
    async def lyrics(self, interaction: discord.Interaction, search: str):
        try:    
            await interaction.response.defer()

            # Define lists
            options = []
            song_list = []
            artist_list = []
            album_list = []
            id_list = []
            lyrics_list = []

            # Clean up user input
            search = search.replace(" ", "%20")
            search = search.lower()

            # Send initial embed
            embed = discord.Embed(title = "Searching...", color = Color.orange())
            embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
            await interaction.followup.send(embed = embed)

            # Create URL
            request_url = f"https://lrclib.net/api/search?q={search}"

            # Change %20 back to " "
            search = search.replace("%20", " ")

            # Send request to LRCLib
            async with aiohttp.ClientSession() as session:
                async with session.get(request_url) as request:
                    request_data = await request.json()
            
            # Check if result is blank
            if request_data == []:
                embed = discord.Embed(title = "Error", description="No results were found.", color = Color.red())
                await interaction.edit_original_response(embed = embed)
            else:
                # Sort through request data, add required info to lists
                for song in request_data:
                    song_list.append(song['name'])
                    artist_list.append(song['artistName'])
                    album_list.append(song['albumName'])
                    id_list.append(song['id'])
                    lyrics_list.append(song['plainLyrics'])

                # Generate dropdown values
                if len(song_list) > 5:
                    embed = discord.Embed(title = "Select Song", description = f'Found 5 results for "{search}"', color = Color.random())
                    embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                    for i in range(0,5):
                        # Handle strings being too long
                        if len(song_list[i]) > 100:
                            song_name = song_list[i][:97] + "..."
                        else:
                            song_name = song_list[i]
                        if len(f"{artist_list[i]} - {album_list[i]}") > 100:
                            list_description = f"{artist_list[i]} - {album_list[i]}"[:97] + "..."
                        else:
                            list_description = f"{artist_list[i]} - {album_list[i]}"
                        options.append(discord.SelectOption(label = song_name, description = list_description, value = id_list[i]))
                else:
                    embed = discord.Embed(title = "Select Song", description = f'Found {len(song_list)} results for "{search}"', color = Color.random())
                    embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                    for i in range(0, len(song_list)):
                        # Handle strings being too long
                        if len(song_list[i]) > 100:
                            song_name = song_list[i][:97] + "..."
                        else:
                            song_name = song_list[i]
                        if len(f"{artist_list[i]} - {album_list[i]}") > 100:
                            list_description = f"{artist_list[i]} - {album_list[i]}"[:97] + "..."
                        else:
                            list_description = f"{artist_list[i]} - {album_list[i]}"
                        options.append(discord.SelectOption(label = song_name, description = list_description, value = id_list[i]))

                # Define options
                select = Select(options=options)

                # Response to user selection
                async def response(interaction: discord.Interaction):
                    await interaction.response.defer()
                    # Find unique ID of selection in the list
                    list_place = id_list.index(int(select.values[0]))
                    
                    try:
                        lyrics_split = lyrics_list[list_place].split("\n\n")

                        paged_lyrics = []
                        current_page = ""

                        for paragraph in lyrics_split:
                            if len(paragraph) + len(current_page) < 2200:
                                current_page = current_page + "\n\n" + paragraph
                            else:
                                paged_lyrics.append(current_page)
                                current_page = ""
                                current_page = current_page + paragraph

                        paged_lyrics.append(current_page)

                        # Create lyric embed
                        embed = discord.Embed(title = f"{song_list[list_place]} - {artist_list[list_place]}", description = paged_lyrics[0], color = Color.random())
                        
                        class PaginationView(View):
                            def __init__(self, pages):
                                super().__init__()
                                self.page = 0
                                self.pages = pages
                                google_button = discord.ui.Button(label='Search on Google', style=discord.ButtonStyle.url, url=f'https://www.google.com/search?q={song_list[list_place].replace(" ", "+")}+{artist_list[list_place].replace(" ", "+")}')
                                self.add_item(google_button)
                        
                            @discord.ui.button(label="<", style=ButtonStyle.green, custom_id="prev")
                            async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                                if self.page > 0:
                                    self.page -= 1
                                else:
                                    self.page = len(self.pages) - 1
                                embed = discord.Embed(title = f"{song_list[list_place]} - {artist_list[list_place]}", description = self.pages[self.page], color = Color.random())
                                embed.set_footer(text = f"Page {self.page + 1}/{len(paged_lyrics)}")
                                await interaction.response.edit_message(embed = embed)

                            @discord.ui.button(label=">", style=ButtonStyle.green, custom_id="next")
                            async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                                if self.page < len(self.pages) - 1:
                                    self.page += 1
                                else:
                                    self.page = 0
                                embed = discord.Embed(title = f"{song_list[list_place]} - {artist_list[list_place]}", description = self.pages[self.page], color = Color.random())
                                embed.set_footer(text = f"Page {self.page + 1}/{len(paged_lyrics)}")
                                await interaction.response.edit_message(embed = embed)

                        if len(paged_lyrics) == 1:
                            google_button = discord.ui.Button(label='Search on Google', style=discord.ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(song_list[list_place])).replace("%2B", "+")}+{(quote(artist_list[list_place])).replace("%2B", "+")}')
                            view = View()
                            view.add_item(google_button)
                            embed.set_footer(text = f"Lryics - Page 1/1")
                            await interaction.edit_original_response(embed = embed, view = view)
                        else:
                            embed.set_footer(text = f"Lyrics - Page 1/{len(paged_lyrics)}")
                            await interaction.edit_original_response(embed = embed, view = PaginationView(paged_lyrics))
                    except AttributeError:
                        google_button = discord.ui.Button(label='Search on Google', style=discord.ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(song_list[list_place])).replace("%2B", "+")}+{(quote(artist_list[list_place])).replace("%2B", "+")}')
                        view = View()
                        view.add_item(google_button)
                        embed = discord.Embed(title = f"{song_list[list_place]} - {artist_list[list_place]}", description = "The song has no lyrics.", color = Color.red())
                        await interaction.edit_original_response(embed = embed, view = view)
                
                # Set up list with provided values
                select.callback = response
                view = View()
                view.add_item(select)

                # Edit initial message to show dropdown
                await interaction.edit_original_response(embed = embed, view = view)
        except Exception as error:
            embed = discord.Embed(title = "Lyrics - Error", description = "An unknown error has occurred. The error has been logged.")
            print("[LYRICS] Error has occurred. Error below:")
            print(error)
            await interaction.edit_original_response(embed = embed, view = None, ephemeral = True)
    
    # Global Song URL command
    @app_commands.command(name = "song-global-url", description = "Get links for many streaming platforms based on a URL.")
    @app_commands.checks.cooldown(1, 10)
    async def song_global_url(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()

        embed = discord.Embed(title = "Searching...", color = Color.orange())
        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
        await interaction.followup.send(embed = embed)
        
        try:
            processed_source = quote(url, safe='()*!\'')
            request_url = f"https://api.song.link/v1-alpha.1/links?url={processed_source}&userCountry=GB"
            
            # Send request to song.link
            async with aiohttp.ClientSession() as session:
                async with session.get(request_url) as request:
                    request_data = await request.json()
                    request_status = request.status
            
            if not(request_status <= 200 or request_status >= 299):
                embed = discord.Embed(title = "An error has occurred.", description = "An error has occurred while finding song URLs.\n\n**Solutions:**\n1. Check the URL is a valid song URL.\n2. Check the URL is not for a playlist, album or artist.\n3. Try again later.", color = Color.red())
                if interaction.user.id in self.bot.dev_ids:
                    embed.add_field(name = "Error Code (Dev)", value = request_status)
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                await interaction.edit_original_response(embed = embed)
            else:
                embed = discord.Embed(title = f"{request_data['entitiesByUniqueId'][request_data['entityUniqueId']]['title']} ({request_data['entitiesByUniqueId'][request_data['entityUniqueId']]['type']})", color = Color.random())
                embed.add_field(name = "Artists", value = request_data['entitiesByUniqueId'][request_data['entityUniqueId']]['artistName'])
                if request_data['entitiesByUniqueId'][request_data['entityUniqueId']]['thumbnailUrl'] != None:
                    embed.set_thumbnail(url = request_data['entitiesByUniqueId'][request_data['entityUniqueId']]['thumbnailUrl'])
                
                view = View()

                for link_type in request_data['linksByPlatform']:
                    if link_type == "amazonMusic":
                        amazon_button = discord.ui.Button(style = discord.ButtonStyle.url, url = request_data['linksByPlatform'][link_type]['url'], label = "Amazon Music", row = 0)
                        view.add_item(amazon_button)
                    elif link_type == "appleMusic":
                        am_button = discord.ui.Button(style = discord.ButtonStyle.url, url = request_data['linksByPlatform'][link_type]['url'], label = "Apple Music", row = 0)
                        view.add_item(am_button)
                    elif link_type == "spotify":
                        spotify_button = discord.ui.Button(style = discord.ButtonStyle.url, url = request_data['linksByPlatform'][link_type]['url'], label = "Spotify", row = 0)
                        view.add_item(spotify_button)
                    elif link_type == "tidal":
                        tidal_button = discord.ui.Button(style = discord.ButtonStyle.url, url = request_data['linksByPlatform'][link_type]['url'], label = "Tidal", row = 0)
                        view.add_item(tidal_button)
                    elif link_type == "youtube":
                        yt_button = discord.ui.Button(style = discord.ButtonStyle.url, url = request_data['linksByPlatform'][link_type]['url'], label = "YouTube", row = 1)
                        view.add_item(yt_button)
                    elif link_type == "youtubeMusic":
                        ytm_button = discord.ui.Button(style = discord.ButtonStyle.url, url = request_data['linksByPlatform'][link_type]['url'], label = "YouTube Music", row = 1)
                        view.add_item(ytm_button)

                await interaction.edit_original_response(embed = embed, view = view)
        except Exception:
            embed = discord.Embed(title = "Unexpected Error", description = "Please try again later or message <@563372552643149825> for assistance.", color = Color.red())
            await interaction.edit_original_response(embed = embed, view = None)
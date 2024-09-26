from urllib.parse import quote

import aiohttp
import discord
from discord import ButtonStyle, Color, app_commands
from discord.ext import commands
from discord.ui import View

class music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Lyrics command
    @app_commands.command(name = "lyrics", description = "Find Lyrics to a song.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(search = "The song you're seaching for.")
    @app_commands.describe(longer_pages = "Optional: allows a max of 4096 characters per page instead of 1000. Defaults to false.")
    @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissable message only visible to you. Defaults to false.")
    @app_commands.checks.cooldown(1, 10)
    async def lyrics(self, interaction: discord.Interaction, search: str, longer_pages: bool = False, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)

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
            await interaction.followup.send(embed = embed, ephemeral=ephemeral)
        else:
            # Sort through request data, add required info to lists
            for song in request_data:
                song_list.append(song['name'])
                artist_list.append(song['artistName'])
                album_list.append(song['albumName'])
                id_list.append(song['id'])
                lyrics_list.append(song['plainLyrics'])

            # Generate dropdown values
            # Limit to 5 options
            if len(song_list) > 5:
                embed = discord.Embed(title = "Select Song", description = f'Found {len(song_list)} results, showing 5 results for "{search}".\n\nCan\u0027t find what you\u0027re looking for? Try to be more specific with your query, for example, specifying the author.', color = Color.orange())
                embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                
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
                embed = discord.Embed(title = "Select Song", description = f'Found {len(song_list)} results, {len(song_list)} showing results for "{search}".\n\nCan\u0027t find what you\u0027re looking for? Try to be more specific with your query, for example, specifying the author.', color = Color.orange())
                embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                
                # Add each song's option
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

            # Song select view
            class songSelectView(View):
                def __init__(self, options: list):
                    super().__init__(timeout = 120) # 2 minute timeout

                    self.msg = discord.WebhookMessage
                    
                    dropdownInstance = dropdown(options)
                    self.add_item(dropdownInstance)
                    
                    # Pass in view's self to allow it to be stopped
                    dropdownInstance.viewSelf = self
                    dropdownInstance.msg = self.msg
                            
                async def on_timeout(self) -> None:
                    for item in self.children:
                        item.disabled = True

                    await self.msg.edit(view=self)
            
            # Song select dropdown class
            class dropdown(discord.ui.Select):
                def __init__(self, options: list):
                    super().__init__(placeholder="Select Song", min_values=1, max_values=1, options=options)

                    self.viewSelf: View
                    self.msg: discord.WebhookMessage
                
                # Callback
                async def callback(self, interaction: discord.Interaction):
                    await interaction.response.defer(ephemeral=ephemeral)
                    
                    # Stop dropdown view
                    self.viewSelf.stop()
                    
                    # Find unique ID of selection in the list
                    list_place = id_list.index(int(self.values[0]))
                    
                    try:
                        lyrics_split = lyrics_list[list_place].split("\n\n")

                        pages = []
                        current_page = ""

                        # Page split
                        for paragraph in lyrics_split:
                            if longer_pages == True:
                                if len(paragraph) + len(current_page) < 4096:
                                    current_page = current_page + "\n\n" + paragraph
                                else:
                                    pages.append(current_page)
                                    current_page = ""
                                    current_page = current_page + paragraph
                            else:
                                if len(paragraph) + len(current_page) < 1000:
                                    current_page = current_page + "\n\n" + paragraph
                                else:
                                    pages.append(current_page)
                                    current_page = ""
                                    current_page = current_page + paragraph

                        # Add any remaining contents
                        if current_page != "":
                            pages.append(current_page)

                        # Create lyric embed
                        embed = discord.Embed(title = f"Lyrics: {song_list[list_place]} - {artist_list[list_place]}", description = pages[0], color = Color.random())

                        if len(pages) == 1: # One page - send embed without page controller
                            google_button = discord.ui.Button(label='Search on Google', style=ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(song_list[list_place])).replace("%2B", "+")}+{(quote(artist_list[list_place])).replace("%2B", "+")}')
                            
                            view = View()
                            view.add_item(google_button)
                            
                            embed.set_footer(text = f"lrclib.net - Page 1/1")
                            
                            await interaction.edit_original_response(embed = embed, view = view)
                        else: # Multiple pages - send embed with page controller
                            embed.set_footer(text = f"lrclib.net - Page 1/{len(pages)}")
                            pagesInstance = lyricPages(pages, list_place)
                            await interaction.edit_original_response(embed = embed, view = pagesInstance)

                            # Pass through interaction to get original sender ID - used for lock button
                            pagesInstance.interaction = interaction
                            
                            # Pass through message - used for timeout edit, currently broken
                            pagesInstance.msg = self.msg
                    except AttributeError: # No lyrics
                        google_button = discord.ui.Button(label='Search on Google', style=ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(song_list[list_place])).replace("%2B", "+")}+{(quote(artist_list[list_place])).replace("%2B", "+")}')
                        
                        view = View()
                        view.add_item(google_button)
                        
                        embed = discord.Embed(title = f"{song_list[list_place]} - {artist_list[list_place]}", description = "The song has no lyrics.", color = Color.red())
                        embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                        
                        await interaction.edit_original_response(embed = embed, view = view)
            
            # Lyrics Page view
            class lyricPages(View):
                def __init__(self, pages: list, list_place: int):
                    super().__init__(timeout = 1200) # 30 minute timeout
                    
                    self.page = 0
                    self.pages: list = pages
                    self.list_place: int = list_place

                    self.interaction: discord.Interaction
                    self.msg: discord.Message

                    self.locked = False
                    
                    google_button = discord.ui.Button(label='Search on Google', style=ButtonStyle.url, url=f'https://www.google.com/search?q={song_list[list_place].replace(" ", "+")}+{artist_list[list_place].replace(" ", "+")}')
                    self.add_item(google_button)

                    # First and previous buttons will always start disabled
                    for item in self.children:
                        if item.custom_id == "first" or item.custom_id == "prev":
                            item.disabled = True
                
                # Disable all buttons on timeout
                async def on_timeout(self) -> None:
                    for item in self.children:
                        if item.style != ButtonStyle.url:
                            item.disabled = True

                    # Edit message with disabled view
                    await self.msg.edit(view=self)
            
                # Block others from controlling when lock is active
                async def interaction_check(self, interaction: discord.Interaction):
                    if interaction.user.id != self.interaction.user.id:
                        if self.locked:
                            embed = discord.Embed(title = "Error", description = "This command is locked. Only the owner can control it.", color=Color.red())
                            await interaction.response.send_message(embed = embed, ephemeral = True, delete_after=5)
                        else:
                            return True
                    else:
                        return True
                
                # First page
                @discord.ui.button(emoji="⏮️", style=ButtonStyle.red, custom_id="first")
                async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.page = 0

                    for item in self.children:
                        item.disabled = False
                        
                        if item.custom_id == "first" or item.custom_id == "prev":
                            item.disabled = True
                    
                    embed = discord.Embed(title = f"Lyrics: {song_list[self.list_place]} - {artist_list[self.list_place]}", description = self.pages[self.page], color = Color.random())
                    embed.set_footer(text = f"lrclib.net - Page {self.page + 1}/{len(self.pages)}")
                    
                    await interaction.response.edit_message(embed = embed, view = self)
                
                # Previous page
                @discord.ui.button(emoji="⏪", style=ButtonStyle.gray, custom_id="prev")
                async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if self.page - 1 == 0:
                        self.page -= 1

                        for item in self.children:
                            item.disabled = False

                            if item.custom_id == "first" or item.custom_id == "prev":
                                item.disabled = True
                    else:
                        self.page -= 1

                        for item in self.children:
                            item.disabled = False
                    
                    embed = discord.Embed(title = f"Lyrics: {song_list[self.list_place]} - {artist_list[self.list_place]}", description = self.pages[self.page], color = Color.random())
                    embed.set_footer(text = f"lrclib.net - Page {self.page + 1}/{len(self.pages)}")
                    
                    await interaction.response.edit_message(embed = embed, view = self)
                
                # Lock / unlock button
                @discord.ui.button(emoji="🔓", style=ButtonStyle.green, custom_id="lock")
                async def lock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id == self.interaction.user.id:
                        self.locked = not self.locked

                        if self.locked == True:
                            button.emoji = "🔒"
                            button.style = ButtonStyle.red
                        else:
                            button.emoji = "🔓"
                            button.style = ButtonStyle.green
                        
                        await interaction.response.edit_message(view = self)
                    else:
                        embed = discord.Embed(title = "Error", description = "Only the command runner can toggle the page controls lock.", color=Color.red())
                        await interaction.response.send_message(embed = embed, ephemeral = True, delete_after=5)

                # Next page
                @discord.ui.button(emoji="⏩", style=ButtonStyle.gray, custom_id="next")
                async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if (self.page + 1) == (len(self.pages) - 1):
                        self.page += 1

                        for item in self.children:
                            item.disabled = False
                            
                            if item.custom_id == "next" or item.custom_id == "last":
                                item.disabled = True
                    else:
                        self.page += 1

                        for item in self.children:
                            item.disabled = False
                    
                    embed = discord.Embed(title = f"Lyrics: {song_list[self.list_place]} - {artist_list[self.list_place]}", description = self.pages[self.page], color = Color.random())
                    embed.set_footer(text = f"lrclib.net - Page {self.page + 1}/{len(self.pages)}")
                    
                    await interaction.response.edit_message(embed = embed, view = self)
                
                # Last page
                @discord.ui.button(emoji="⏭️", style=ButtonStyle.green, custom_id="last")
                async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.page = len(self.pages) - 1

                    for item in self.children:
                        item.disabled = False

                        if item.custom_id == "next" or item.custom_id == "last":
                            item.disabled = True
                    
                    embed = discord.Embed(title = f"Lyrics: {song_list[self.list_place]} - {artist_list[self.list_place]}", description = self.pages[self.page], color = Color.random())
                    embed.set_footer(text = f"lrclib.net - Page {self.page + 1}/{len(self.pages)}")
                    
                    await interaction.response.edit_message(embed = embed, view = self)
            
            songSelectViewInstance = songSelectView(options)
            
            # Edit initial message to show dropdown
            msg = await interaction.followup.send(embed = embed, view = songSelectViewInstance, ephemeral=ephemeral, wait=True)
            songSelectViewInstance.msg = msg

async def setup(bot):
    await bot.add_cog(music(bot))
import discord
from discord import Color, ButtonStyle
from discord.ext import commands
from discord.ui import View
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from urllib.parse import quote
import asyncio
import re

class spotify_autoembed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auth_manager = SpotifyClientCredentials(client_id = self.bot.spotify_id, client_secret = self.bot.spotify_secret)
        self.sp = spotipy.Spotify(auth_manager=self.auth_manager)
    
    # Spotify Embed Autosender
    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore bots
        if message.author.bot != True:
            # Check if there is a Spotify link in the message
            if "https://open.spotify.com/" in message.content:
                messageTargetURLs = []
                i = 0

                # Extract only URLs, put them in messageAllURLs list
                urlRegex = r"\b((?:https?://)?(?:(?:www\.)?(?:[\da-z\.-]+)\.(?:[a-z]{2,6})|(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)|(?:(?:[0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,7}:|(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}|(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}|(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}|(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:(?:(?::[0-9a-fA-F]{1,4}){1,6})|:(?:(?::[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(?::[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(?:ffff(?::0{1,4}){0,1}:){0,1}(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])|(?:[0-9a-fA-F]{1,4}:){1,4}:(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])))(?::[0-9]{1,4}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])?(?:/[\w\.-]*)*/?)\b"
                messageAllURLs = re.findall(urlRegex, message.content)

                # Add Spotify URLs to messageTargetURLs, while ignoring irrelevant URLs
                for url in messageAllURLs:
                    if "https://open.spotify.com/" in url:
                        messageTargetURLs.append(url)

                # Work through all URLs
                for url in messageTargetURLs:
                    i += 1
                    artist_string = ""
                    # Catch any uncaught errors
                    # try:
                    # Identify URL type
                    if "track" in url:
                        # Track URL
                        # Query information from Spotify
                        result = self.sp.track(url)

                        # If song is explicit...
                        if result['explicit'] == True:
                            # We add an explicit tag and generate the Discord Embed with title
                            embed = discord.Embed(title = f"{result['name']} (Explicit) (Song)")
                        # Else...
                        else:
                            # We just generate the Discord Embed with title
                            embed = discord.Embed(title = f"{result['name']} (Song)")

                        # Add all artists for song to comma separated string
                        # Example: artist1, artist2, artist3
                        for artist in result['artists']:
                            if artist_string == "":
                                artist_string = artist['name']
                            else:
                                artist_string = f"{artist_string}, {artist['name']}"
                        
                        # Populate embed with information
                        embed.add_field(name = "Artists", value = artist_string, inline = True)
                        embed.add_field(name = "Album", value = result['album']["name"], inline = True)
                        embed.set_thumbnail(url = result["album"]["images"][0]["url"])
                        embed.set_footer(text = f"Message by {message.author.name} - Link {i}/{len(messageTargetURLs)}", icon_url = message.author.avatar.url)

                        # Define view
                        view = View()
                                    
                        # Work out song length in sec:min
                        seconds, result['duration_ms'] = divmod(result['duration_ms'], 1000)
                        minutes, seconds = divmod(seconds, 60)

                        # Add Dismiss Embed Button
                        async def deleteCallback(interaction: discord.Interaction):
                            await interaction.response.defer()
                            
                            # If attempt is from message creator...
                            if interaction.user.id == message.author.id:
                                # We delete the message
                                await msg.delete()
                            # Else...
                            else:
                                # Display permission error that deletes after 3 seconds
                                embed = discord.Embed(title = f"Error", description = f"{interaction.user.mention}, you are not the message OP.", color = Color.red())
                                await message.channel.send(embed = embed, delete_after=3)
                        
                        # Add Dismiss button, define callback as deleteCallback
                        delete_button = discord.ui.Button(label=f'Dismiss Embed', style=discord.ButtonStyle.red)
                        delete_button.callback = deleteCallback
                        view.add_item(delete_button)
                        
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
                        msg = await message.reply(embed = embed, view = view, mention_author = False)
                    elif "artist" in url:
                        # Artist URL
                        # Fetch artist info
                        result_info = self.sp.artist(url)

                        # Fetch artist top songs
                        result_top_tracks = self.sp.artist_top_tracks(url)

                        # Create embed, populate it with information
                        embed = discord.Embed(title = f"{result_info['name']} (Artist)")
                        embed.add_field(name = "Followers", value = f"{result_info['followers']['total']:,}")
                        embed.set_thumbnail(url = result_info["images"][0]["url"])
                        embed.set_footer(text = f"Message by {message.author.name} - Link {i}/{len(messageTargetURLs)}", icon_url = message.author.avatar.url)
                        
                        topsong_string = ""
                        for i in range(0,5):
                            # Add all artists for song to comma separated string
                            # Example: artist1, artist2, artist3
                            artist_string = ""
                            for artist in result_top_tracks['tracks'][i]['artists']:
                                if artist_string == "":
                                    artist_string = artist['name'] 
                                else:
                                    artist_string = f"{artist_string}, {artist['name']}"
                                    
                            # Add each song to a new line in topsong_string
                            # If string is empty...
                            if topsong_string == "":
                                # Set topsong_string to song
                                topsong_string = f"**{i + 1}: {result_top_tracks['tracks'][i]['name']}** - {artist_string}"
                            else:
                                # Add current song to topsong_string, separated with new line
                                topsong_string = f"{topsong_string}\n**{i + 1}: {result_top_tracks['tracks'][i]['name']}** - {artist_string}"
                        
                        # Add top songs to embed
                        embed.add_field(name = "Top Songs", value = topsong_string, inline = False)

                        # Define view
                        view = View()
                        
                        # Dismiss Button callback
                        async def deleteCallback(interaction: discord.Interaction):
                            await interaction.response.defer()
                            
                            # If attempt is from message creator...
                            if interaction.user.id == message.author.id:
                                # We delete the message
                                await msg.delete()
                            # Else...
                            else:
                                # Display permission error that deletes after 3 seconds
                                embed = discord.Embed(title = f"Error", description = f"{interaction.user.mention}, you are not the message OP.", color = Color.red())
                                await message.channel.send(embed = embed, delete_after=3)
                        
                        # Add Dismiss button, define callback as deleteCallback
                        delete_button = discord.ui.Button(label=f'Dismiss Embed', style=discord.ButtonStyle.red)
                        delete_button.callback = deleteCallback
                        view.add_item(delete_button)
                        
                        # Add Open in Spotify button
                        spotify_button = discord.ui.Button(label=f'Show on Spotify', style=discord.ButtonStyle.url, url=result_info["external_urls"]["spotify"])
                        view.add_item(spotify_button)

                        # Add Search on YT Music button
                        ytm_button = discord.ui.Button(label='Search on YT Music', style=discord.ButtonStyle.url, url=f'https://music.youtube.com/search?q={(quote(result_info["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}')
                        view.add_item(ytm_button)

                        # Add Search on Google button
                        google_button = discord.ui.Button(label='Search on Google', style=discord.ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(result_info["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}')
                        view.add_item(google_button)

                        msg = await message.reply(embed = embed, view = view, mention_author = False)
                    elif "album" in url:
                        # Album URL
                        # Fetch artist info
                        result_info = self.sp.album(url)

                        songlist_string = ""
                        # Work through all songs in album
                        for i in range(len(result_info['tracks']['items'])):
                            # Add all artists for song to comma separated string
                            # Example: artist1, artist2, artist3
                            artist_string = ""
                            for artist in result_info['tracks']['items'][i]['artists']:
                                if artist_string == "":
                                    artist_string = artist['name'] 
                                else:
                                    artist_string = f"{artist_string}, {artist['name']}"
                                    
                            # Add song listing to song list
                            if songlist_string == "":
                                songlist_string = f"**{i + 1}: {result_info['tracks']['items'][i]['name']}** - {artist_string}"
                            else:
                                songlist_string = f"{songlist_string}\n**{i + 1}: {result_info['tracks']['items'][i]['name']}** - {artist_string}"

                        # Add all artists for album to comma separated string
                        # Example: artist1, artist2, artist3
                        artist_string = ""
                        for artist in result_info['artists']:
                            if artist_string == "":
                                artist_string = artist['name'] 
                            else:
                                artist_string = artist_string + ", " + artist['name']
                        
                        # Create embed, populate it with information
                        embed = discord.Embed(title = f"{result_info['name']} - {artist_string} (Album)", description = songlist_string)
                        embed.set_thumbnail(url = result_info["images"][0]["url"])
                        embed.set_footer(text = f"Message by {message.author.name} - Link {i}/{len(messageTargetURLs)}", icon_url = message.author.avatar.url)

                        view = View()

                        # Add Dismiss Embed Button
                        async def deleteCallback(interaction: discord.Interaction):
                            await interaction.response.defer()
                            
                            # If attempt is from message creator...
                            if interaction.user.id == message.author.id:
                                # We delete the message
                                await msg.delete()
                            # Else...
                            else:
                                # Display permission error that deletes after 3 seconds
                                embed = discord.Embed(title = f"Error", description = f"{interaction.user.mention}, you are not the message OP.", color = Color.red())
                                await message.channel.send(embed = embed, delete_after=3)
                        
                        # Add Dismiss button, define callback as deleteCallback
                        delete_button = discord.ui.Button(label=f'Dismiss Embed', style=discord.ButtonStyle.red)
                        delete_button.callback = deleteCallback
                        view.add_item(delete_button)
                        
                        # Add Open in Spotify button
                        spotify_button = discord.ui.Button(label=f'Show on Spotify', style=discord.ButtonStyle.url, url=result_info["external_urls"]["spotify"])
                        view.add_item(spotify_button)

                        # Add Search on YT Music button
                        ytm_button = discord.ui.Button(label='Search on YT Music', style=discord.ButtonStyle.url, url=f'https://music.youtube.com/search?q={(quote(result_info["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}')
                        view.add_item(ytm_button)

                        # Add Search on Google button
                        google_button = discord.ui.Button(label='Search on Google', style=discord.ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(result_info["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}')
                        view.add_item(google_button)

                        msg = await message.reply(embed = embed, view = view, mention_author = False)
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
                            # Init
                            def __init__(self, pages):
                                super().__init__()
                                self.page = 0
                                self.pages = pages
                                
                                # Add Dismiss Embed Button
                                async def deleteCallback(interaction: discord.Interaction):
                                    await interaction.response.defer()
                                    
                                    # If attempt is from message creator...
                                    if interaction.user.id == message.author.id:
                                        # We delete the message
                                        await msg.delete()
                                    # Else...
                                    else:
                                        # Display permission error that deletes after 3 seconds
                                        embed = discord.Embed(title = f"Error", description = f"{interaction.user.mention}, you are not the message OP.", color = Color.red())
                                        await message.channel.send(embed = embed, delete_after=3)
                                
                                # Add Dismiss button, define callback as deleteCallback
                                delete_button = discord.ui.Button(label=f'Dismiss Embed', style=discord.ButtonStyle.red)
                                delete_button.callback = deleteCallback
                                view.add_item(delete_button)
                        
                            # Previous page button
                            @discord.ui.button(label="<", style=ButtonStyle.green, custom_id="prev")
                            async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                                await interaction.response.defer()
                                if self.page > 0:
                                    self.page -= 1
                                else:
                                    self.page = len(self.pages) - 1
                                embed = discord.Embed(title = f"{result_info['name']} (Playlist)", description = f"by {result_info['owner']['display_name']} - {result_info['tracks']['total']} items\n\n{self.pages[self.page]}", color = Color.random())
                                embed.set_thumbnail(url = result_info['images'][0]['url'])
                                embed.set_footer(text = f"Requested by {interaction.user.name} - Page {self.page + 1}/{len(pages)}", icon_url = message.author.avatar.url)
                                await msg.edit(embed = embed)

                            # Next page button
                            @discord.ui.button(label=">", style=ButtonStyle.green, custom_id="next")
                            async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                                await interaction.response.defer()
                                if self.page < len(self.pages) - 1:
                                    self.page += 1
                                else:
                                    self.page = 0
                                embed = discord.Embed(title = f"{result_info['name']} (Playlist)", description = f"by {result_info['owner']['display_name']} - {result_info['tracks']['total']} items\n\n{self.pages[self.page]}", color = Color.random())
                                embed.set_thumbnail(url = result_info['images'][0]['url'])
                                embed.set_footer(text = f"Message by {message.author.name} - Page {self.page + 1}/{len(pages)}", icon_url = message.author.avatar.url)
                                await msg.edit(embed = embed)

                        # Create embed, populate it with information
                        embed = discord.Embed(title = f"{result_info['name']} (Playlist)", description = f"by {result_info['owner']['display_name']} - {result_info['tracks']['total']} items\n\n{pages[0]}", color = Color.random())
                        embed.set_thumbnail(url = result_info['images'][0]['url'])
                        embed.set_footer(text = f"Message by {message.author.name} - Page 1/{len(pages)}", icon_url = message.author.avatar.url)
                        
                        # If there's only 1 page, make embed without page buttons
                        if len(pages) == 1:
                            # Add Open in Spotify button
                            view = View()
                            spotify_button = discord.ui.Button(label=f'Show on Spotify', style=discord.ButtonStyle.url, url=result_info["external_urls"]["spotify"])
                            view.add_item(spotify_button)
                            
                            msg = await message.reply(embed = embed, view = view)
                        # Else, make embed with page buttons
                        else:
                            msg = await message.reply(embed = embed, view = PlaylistPagesController(pages))     
                    else:
                        pass
                    # except Exception:
                    #     pass
                    await asyncio.sleep(2)

async def setup(bot):
    await bot.add_cog(spotify_autoembed(bot))
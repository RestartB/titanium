import os
import random
import string
from urllib.parse import quote
from utils.escape_markdown import escape_markdown as escape

import aiohttp
import discord
import spotipy
from colorthief import ColorThief
from discord import Color
from discord.ui import View


# Song parse function
async def song(self, item: spotipy.Spotify.track, interaction: discord.Interaction, add_button_url: str = None, add_button_text: str = None, cached: bool = False, ephemeral: bool = False):
    """
    Handle Spotify song embeds.
    """
    
    image_url = item['album']['images'][0]['url']

    artist_img = self.sp.artist(item["artists"][0]["external_urls"]["spotify"])["images"][0]["url"]
    
    artist_string = ""
    for artist in item['artists']:
        if artist_string == "":
            artist_string = artist['name']
        else:
            artist_string += f", {artist['name']}"
    
    explicit = item['explicit']

    # Set up new embed
    embed = discord.Embed(title = f"{item['name']}{f' {self.bot.explicit_emoji}' if explicit else ''}", description=f"on **[{await escape(item['album']['name'])}](<{item['album']['external_urls']['spotify']}>) • {item['album']['release_date'].split('-', 1)[0]}**", color = Color.from_rgb(r = 255, g = 255, b = 255))
    
    embed.set_thumbnail(url = item['album']['images'][0]['url'])
    embed.set_author(name = artist_string, url=item["artists"][0]["external_urls"]["spotify"], icon_url=artist_img)
    embed.set_footer(text = f"Getting colour information...{' • Cached Result' if cached else ''}")

    class spotifyButtonsMenu(View):
        def __init__(self, bot):
            super().__init__(timeout=30)

            self.bot = bot
            self.interaction: discord.Interaction
            self.ogMsg: discord.WebhookMessage
            
            if not(add_button_url == None or add_button_text == None):
                # Add additional button                
                add_button = discord.ui.Button(label=add_button_text, style=discord.ButtonStyle.url, url=add_button_url, row = 0)
                self.add_item(add_button)

            songlink_button = discord.ui.Button(label="Other Streaming Services", style=discord.ButtonStyle.url, url=f"https://song.link/{item['external_urls']['spotify']}", row = 0)
            self.add_item(songlink_button)

            google_button = discord.ui.Button(label='Search on Google', style=discord.ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(item["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}', row = 0)
            self.add_item(google_button)

        async def on_timeout(self) -> None:
            try:
                await self.ogMsg.delete()
            except (discord.errors.NotFound, discord.HTTPException, discord.Forbidden):
                pass
        
        async def interaction_check(self, interaction: discord.Interaction):
            if interaction.user.id != self.interaction.user.id:
                embed = discord.Embed(title = "Error", description = "You can only control a menu that you have requested.", color=Color.red())
                await interaction.response.send_message(embed = embed, delete_after=5, ephemeral=True)
            else:
                return True
        
        @discord.ui.button(label='Album Art', style=discord.ButtonStyle.gray, row = 1)
        async def art(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer(ephemeral=ephemeral)
            
            if item["album"]["images"] != None:
                image_url = item["album"]["images"][0]["url"]

                if item["album"]["images"][0]['height'] == None or item["album"]["images"][0]['width'] == None:
                    embed = discord.Embed(title = f"{item['name']} ({artist_string}) - Album Art", description = "Viewing highest quality (Resolution unknown)", color = Color.from_rgb(r = 255, g = 255, b = 255))
                    embed.set_footer(text = "Getting colour information...")
                else:
                    embed = discord.Embed(title = f"{item['name']} ({artist_string}) - Album Art", description = f"Viewing highest quality ({item['album']['images'][0]['width']}x{item['album']['images'][0]['height']})", color = Color.from_rgb(r = 255, g = 255, b = 255))
                    embed.set_footer(text = "Getting colour information...")
                
                embed.set_image(url = item["album"]["images"][0]["url"])
                
                view = View()
                view.add_item(discord.ui.Button(label="Download", style=discord.ButtonStyle.url, url=item["album"]["images"][0]["url"]))
                    
                await interaction.edit_original_response(embed = embed, view = view)

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

                if item["album"]["images"][0]['height'] == None or item["album"]["images"][0]['width'] == None:
                    embed = discord.Embed(title = f"{item['name']} ({artist_string}) - Album Art", description = "Viewing highest quality (Resolution unknown)", color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]))
                    embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                else:
                    embed = discord.Embed(title = f"{item['name']} ({artist_string}) - Album Art", description = f"Viewing highest quality ({item['album']['images'][0]['width']}x{item['album']['images'][0]['height']})", color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]))
                    embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                
                embed.set_image(url = item["album"]["images"][0]["url"])
                await interaction.edit_original_response(embed = embed)
            else:
                embed = discord.Embed(title = "No album art available.", color = Color.red())
                embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                await interaction.edit_original_response(embed = embed)
            
            self.stop()
        
        @discord.ui.button(label='Close', style = discord.ButtonStyle.red, row = 1)
        async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer(ephemeral=ephemeral)
            
            await interaction.delete_original_response()
    
    class spotifyEmbedView(View):
        def __init__(self, bot):
            super().__init__(timeout=None)

            self.bot = bot.bot
            self.interaction: discord.Interaction

            seconds, item['duration_ms'] = divmod(item['duration_ms'], 1000)
            minutes, seconds = divmod(seconds, 60)

            # Add Open in Spotify button
            spotify_button = discord.ui.Button(label=f'Play on Spotify ({int(minutes):02d}:{int(seconds):02d})', style=discord.ButtonStyle.url, url=item['external_urls']['spotify'], row = 0)
            self.add_item(spotify_button)
        
        async def on_timeout(self) -> None:
            for item in self.children:
                if item.style != discord.ButtonStyle.url:
                    item.disabled = True

            await self.interaction.edit_original_response(view=self)
        
        @discord.ui.button(label=f'Menu', style=discord.ButtonStyle.gray, row = 0)
        async def menu(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer(ephemeral=ephemeral)
            
            menuInstance = spotifyButtonsMenu(self.bot)
            ogMsg = await interaction.followup.send(view=menuInstance, wait=True, ephemeral=ephemeral)

            menuInstance.interaction = interaction
            menuInstance.ogMsg = ogMsg

    viewInstance = spotifyEmbedView(self)
    
    try:
        # Detect if embed already exists
        (await interaction.original_response()).embeds[0]

        await interaction.edit_original_response(embed = embed, view = viewInstance)
    except IndexError:
        # Send new embed
        await interaction.followup.send(embed = embed, view = viewInstance, ephemeral=ephemeral)

    viewInstance.interaction = interaction

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

    embed.set_footer(text = f"@{interaction.user.name}{' • Cached Result' if cached else ''}", icon_url = interaction.user.display_avatar.url)
    embed.color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2])

    await interaction.edit_original_response(embed = embed)

# Artist parse function
async def artist(self, item: spotipy.Spotify.artist, top_tracks: spotipy.Spotify.artist_top_tracks, interaction: discord.Interaction, add_button_url: str = None, add_button_text: str = None, ephemeral: bool = False):
    """
    Handle Spotify artist embeds.
    """
    
    image_url = item["images"][0]["url"]
                        
    embed = discord.Embed(title = f"{item['name']}", color = Color.from_rgb(r = 255, g = 255, b = 255))
    embed.add_field(name = "Followers", value = f"{item['followers']['total']:,}")
    embed.set_thumbnail(url = item["images"][0]["url"])
    embed.set_footer(text = "Getting colour information...")

    topsong_string = ""
    for i in range(0,5):
        artist_string = ""
        for artist in top_tracks['tracks'][i]['artists']:
            if artist_string == "":
                artist_string = await escape(artist['name'])
            else:
                artist_string += f", {await escape(artist['name'])}"
                
        # Hide artist string from song listing if there is only one artist
        if len(top_tracks['tracks'][i]['artists']) == 1:
            if topsong_string == "":
                topsong_string = f"{i + 1}. **{await escape(top_tracks['tracks'][i]['name'])}**"
            else:
                topsong_string += f"\n{i + 1}. **{await escape(top_tracks['tracks'][i]['name'])}**"
        else:
            if topsong_string == "":
                topsong_string = f"{i + 1}. **{await escape(top_tracks['tracks'][i]['name'])}** - {artist_string}"
            else:
                topsong_string += f"\n{i + 1}. **{await escape(top_tracks['tracks'][i]['name'])}** - {artist_string}"
    
    embed.add_field(name = "Top Songs", value = topsong_string, inline = False)

    class spotifyButtonsMenu(View):
        def __init__(self, bot):
            super().__init__(timeout=30)

            self.bot = bot
            self.interaction: discord.Interaction
            self.ogMsg: discord.WebhookMessage
            
            if not(add_button_url == None or add_button_text == None):
                # Add additional button                
                add_button = discord.ui.Button(label=add_button_text, style=discord.ButtonStyle.url, url=add_button_url, row = 0)
                self.add_item(add_button)

            google_button = discord.ui.Button(label='Search on Google', style=discord.ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(item["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}', row = 0)
            self.add_item(google_button)

        async def on_timeout(self) -> None:
            try:
                await self.ogMsg.delete()
            except (discord.errors.NotFound, discord.HTTPException, discord.Forbidden):
                pass
        
        async def interaction_check(self, interaction: discord.Interaction):
            if interaction.user.id != self.interaction.user.id:
                embed = discord.Embed(title = "Error", description = "You can only control a menu that you have requested.", color=Color.red())
                await interaction.response.send_message(embed = embed, delete_after=5, ephemeral=True)
            else:
                return True
        
        @discord.ui.button(label='Close', style = discord.ButtonStyle.red, row = 1)
        async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer(ephemeral=ephemeral)
            
            await interaction.delete_original_response()
    
    class spotifyEmbedView(View):
        def __init__(self, bot):
            super().__init__(timeout=None)

            self.bot = bot.bot
            self.interaction: discord.Interaction

            # Add Open in Spotify button
            spotify_button = discord.ui.Button(label=f'Show on Spotify', style=discord.ButtonStyle.url, url=item['external_urls']['spotify'], row = 0)
            self.add_item(spotify_button)
        
        async def on_timeout(self) -> None:
            for item in self.children:
                if item.style != discord.ButtonStyle.url:
                    item.disabled = True

            await self.interaction.edit_original_response(view=self)
        
        @discord.ui.button(label=f'Menu', style=discord.ButtonStyle.gray, row = 0)
        async def menu(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer(ephemeral=ephemeral)
            
            menuInstance = spotifyButtonsMenu(self.bot)
            ogMsg = await interaction.followup.send(view=menuInstance, wait=True, ephemeral=ephemeral)

            menuInstance.interaction = interaction
            menuInstance.ogMsg = ogMsg

    viewInstance = spotifyEmbedView(self)
    
    try:
        # Detect if embed already exists
        (await interaction.original_response()).embeds[0]

        await interaction.edit_original_response(embed = embed, view = viewInstance)
    except IndexError:
        # Send new embed
        await interaction.followup.send(embed = embed, view = viewInstance, ephemeral=ephemeral)

    viewInstance.interaction = interaction

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

    embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
    embed.color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2])

    await interaction.edit_original_response(embed = embed)

# Album parse function
async def album(self, item: spotipy.Spotify.album, interaction: discord.Interaction, add_button_url: str = None, add_button_text: str = None, cached: bool = False, ephemeral: bool = False):
    """
    Handle Spotify album embeds.
    """
    
    image_url = item["images"][0]["url"]
    artist_img = self.sp.artist(item["artists"][0]["external_urls"]["spotify"])["images"][0]["url"]
                        
    songlist_string = f"*Released **{item['release_date']}***\n"

    for i in range(len(item['tracks']['items'])):
        artist_string = ""
        for artist in item['tracks']['items'][i]['artists']:
            if artist_string == "":
                artist_string = await escape(artist['name'])
            else:
                artist_string += ", " + await escape(artist['name'])
                
        # Hide artist string from song listing if there is only one artist
        if len(item['tracks']['items'][i]['artists']) == 1:
            songlist_string += f"\n{i + 1}. **{await escape(item['tracks']['items'][i]['name'])}**"
        else:
            songlist_string += f"\n{i + 1}. **{await escape(item['tracks']['items'][i]['name'])}** - {artist_string}"

    artist_string = ""
    for artist in item['artists']:
        if artist_string == "":
            artist_string = await escape(artist['name'])
        else:
            artist_string = artist_string + ", " + await escape(artist['name'])
    
    embed = discord.Embed(title = f"{item['name']}", description = songlist_string, color = Color.from_rgb(r = 255, g = 255, b = 255))
    embed.set_footer(text = f"Getting colour information...{' • Cached Result' if cached else ''}")

    embed.set_thumbnail(url = item["images"][0]["url"])
    embed.set_author(name=artist_string, url=item["artists"][0]["external_urls"]["spotify"], icon_url=artist_img)

    class spotifyButtonsMenu(View):
        def __init__(self, bot):
            super().__init__(timeout=30)

            self.bot = bot
            self.interaction: discord.Interaction
            self.ogMsg: discord.WebhookMessage
            
            if not(add_button_url == None or add_button_text == None):
                # Add additional button                
                add_button = discord.ui.Button(label=add_button_text, style=discord.ButtonStyle.url, url=add_button_url, row = 0)
                self.add_item(add_button)
        
            # Add song.link button                
            songlink_button = discord.ui.Button(label="Other Streaming Services", style=discord.ButtonStyle.url, url=f"https://song.link/{item['external_urls']['spotify']}", row = 0)
            self.add_item(songlink_button)

            # Add Search on Google button
            google_button = discord.ui.Button(label='Search on Google', style=discord.ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(item["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}', row = 0)
            self.add_item(google_button)

        async def on_timeout(self) -> None:
            try:
                await self.ogMsg.delete()
            except (discord.errors.NotFound, discord.HTTPException, discord.Forbidden):
                pass
        
        async def interaction_check(self, interaction: discord.Interaction):
            if interaction.user.id != self.interaction.user.id:
                embed = discord.Embed(title = "Error", description = "You can only control a menu that you have requested.", color=Color.red())
                await interaction.response.send_message(embed = embed, delete_after=5, ephemeral=True)
            else:
                return True
        
        @discord.ui.button(label='Album Art', style=discord.ButtonStyle.gray, row = 1)
        async def art(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer(ephemeral=ephemeral)
            
            if item["images"] != None:
                image_url = item["images"][0]["url"]

                if item["images"][0]['height'] == None or item["images"][0]['width'] == None:
                    embed = discord.Embed(title = f"{item['name']} ({artist_string}) - Album Art", description = "Viewing highest quality (Resolution unknown)", color = Color.from_rgb(r = 255, g = 255, b = 255))
                    embed.set_footer(text = "Getting colour information...")
                else:
                    embed = discord.Embed(title = f"{item['name']} ({artist_string}) - Album Art", description = f"Viewing highest quality ({item['images'][0]['width']}x{item['images'][0]['height']})", color = Color.from_rgb(r = 255, g = 255, b = 255))
                    embed.set_footer(text = "Getting colour information...")
                
                embed.set_image(url = item["images"][0]["url"])
                
                view = View()
                view.add_item(discord.ui.Button(label="Download", style=discord.ButtonStyle.url, url=item["images"][0]["url"]))
                    
                await interaction.edit_original_response(embed = embed, view = view)

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

                if item["images"][0]['height'] == None or item["images"][0]['width'] == None:
                    embed = discord.Embed(title = f"{item['name']} ({artist_string}) - Album Art", description = "Viewing highest quality (Resolution unknown)", color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]))
                    embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                else:
                    embed = discord.Embed(title = f"{item['name']} ({artist_string}) - Album Art", description = f"Viewing highest quality ({item['images'][0]['width']}x{item['images'][0]['height']})", color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]))
                    embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                
                embed.set_image(url = item["images"][0]["url"])
                await interaction.edit_original_response(embed = embed)
            else:
                embed = discord.Embed(title = "No album art available.", color = Color.red())
                embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                await interaction.edit_original_response(embed = embed)
            
            self.stop()
        
        @discord.ui.button(label='Close', style = discord.ButtonStyle.red, row = 1)
        async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer(ephemeral=ephemeral)
            
            await interaction.delete_original_response()
    
    class spotifyEmbedView(View):
        def __init__(self, bot):
            super().__init__(timeout=None)

            self.bot = bot.bot
            self.interaction: discord.Interaction

            # Add Open in Spotify button
            spotify_button = discord.ui.Button(label=f'Play on Spotify', style=discord.ButtonStyle.url, url=item['external_urls']['spotify'], row = 0)
            self.add_item(spotify_button)
        
        async def on_timeout(self) -> None:
            for item in self.children:
                if item.style != discord.ButtonStyle.url:
                    item.disabled = True

            await self.interaction.edit_original_response(view=self)
        
        @discord.ui.button(label=f'Menu', style=discord.ButtonStyle.gray, row = 0)
        async def menu(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer(ephemeral=ephemeral)
            
            menuInstance = spotifyButtonsMenu(self.bot)
            ogMsg = await interaction.followup.send(view=menuInstance, wait=True, ephemeral=ephemeral)

            menuInstance.interaction = interaction
            menuInstance.ogMsg = ogMsg

    viewInstance = spotifyEmbedView(self)
    
    try:
        # Detect if embed already exists
        (await interaction.original_response()).embeds[0]

        await interaction.edit_original_response(embed = embed, view = viewInstance)
    except IndexError:
        # Send new embed
        await interaction.followup.send(embed = embed, view = viewInstance, ephemeral=ephemeral)

    viewInstance.interaction = interaction

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

    embed.set_footer(text = f"@{interaction.user.name}{' • Cached Result' if cached else ''}", icon_url = interaction.user.display_avatar.url)
    embed.color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2])

    await interaction.edit_original_response(embed = embed)

async def playlist():
    pass
import discord
from discord import Color
from discord.ui import View, Select
from urllib.parse import quote
import random
import aiohttp
import string
from colorthief import ColorThief
import os

# Song parse function
async def song(self, item: dict, interaction: discord.Interaction, compact: bool):
    """
    Handle Spotify song embeds.
    """
       
    image_url = item['album']['images'][0]['url']
    
    artist_string = ""
    for artist in item['artists']:
        if artist_string == "":
            artist_string = artist['name']
        else:
            artist_string += f", {artist['name']}"
    
    # Set up new embed
    if item['explicit'] == True:
        embed = discord.Embed(title = f"{item['name']} (Explicit)", color = Color.from_rgb(r = 255, g = 255, b = 255))
    else:
        embed = discord.Embed(title = item['name'], color = Color.from_rgb(r = 255, g = 255, b = 255))
    embed.set_thumbnail(url = item['album']['images'][0]['url'])
    embed.add_field(name = "Artists", value = artist_string, inline = compact)
    embed.add_field(name = "Album", value = item['album']['name'], inline = compact)
    embed.set_footer(text = "Getting colour information...")
    
    # Define View
    view = View(timeout=1800)
    
    seconds, item['duration_ms'] = divmod(item['duration_ms'], 1000)
    minutes, seconds = divmod(seconds, 60)

    # Add Open in Spotify button
    spotify_button = discord.ui.Button(label=f'Play on Spotify ({int(minutes):02d}:{int(seconds):02d})', style=discord.ButtonStyle.url, url=item['external_urls']['spotify'], row = 0)
    view.add_item(spotify_button)

    # More Button Callback
    async def more_callback(interaction: discord.Interaction):
        await interaction.response.defer()

        view = View(timeout=300)

        # Add song.link button                
        songlink_button = discord.ui.Button(label="Other Streaming Services", style=discord.ButtonStyle.url, url=f"https://song.link/{item['external_urls']['spotify']}", row = 1)
        view.add_item(songlink_button)

        # Add Search on Google button
        google_button = discord.ui.Button(label='Search on Google', style=discord.ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(item["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}', row = 1)
        view.add_item(google_button)

        # Album Art Callback
        async def art_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            
            embed = discord.Embed(title = "Getting images...", color = Color.orange())
            embed = discord.Embed(title = "Loading...", description = f"{self.bot.loading_emoji} Getting images...", color = Color.orange())
            embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
            await interaction.edit_original_response(embed = embed, view = None)
            
            if item["album"]["images"] != None:
                image_url = item["album"]["images"][0]["url"]

                if item["album"]["images"][0]['height'] == None or item["album"]["images"][0]['width'] == None:
                    embed = discord.Embed(title = f"{item['name']} ({artist_string}) - Album Art", description = "Viewing highest quality (Resolution unknown)", color = Color.from_rgb(r = 255, g = 255, b = 255))
                    embed.set_footer(text = "Getting colour information...")
                else:
                    embed = discord.Embed(title = f"{item['name']} ({artist_string}) - Album Art", description = f"Viewing highest quality ({item['album']['images'][0]['width']}x{item['album']['images'][0]['height']})", color = Color.from_rgb(r = 255, g = 255, b = 255))
                    embed.set_footer(text = "Getting colour information...")
                
                embed.set_image(url = item["album"]["images"][0]["url"])
                await interaction.edit_original_response(embed = embed)

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

                if item["album"]["images"][0]['height'] == None or item["album"]["images"][0]['width'] == None:
                    embed = discord.Embed(title = f"{item['name']} ({artist_string}) - Album Art", description = "Viewing highest quality (Resolution unknown)", color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]))
                    embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                else:
                    embed = discord.Embed(title = f"{item['name']} ({artist_string}) - Album Art", description = f"Viewing highest quality ({item['album']['images'][0]['width']}x{item['album']['images'][0]['height']})", color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]))
                    embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                
                embed.set_image(url = item["album"]["images"][0]["url"])
                await interaction.edit_original_response(embed = embed)
            else:
                embed = discord.Embed(title = "No album art available.", color = Color.red())
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                await interaction.edit_original_response(embed = embed)
        
        # Add Album Art button
        art_button = discord.ui.Button(label='Album Art', style=discord.ButtonStyle.gray, row = 2)
        art_button.callback = art_callback
        view.add_item(art_button)

        # Close Button Callback
        async def delete_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            
            await msg.delete()
        
        # Add Close button
        close_button = discord.ui.Button(label='Close', style = discord.ButtonStyle.red, row = 2)
        close_button.callback = delete_callback
        view.add_item(close_button)

        msg = await interaction.followup.send(view = view)
    
    # Add More Options button
    more_button = discord.ui.Button(label=f'More', style=discord.ButtonStyle.gray, row = 0)
    more_button.callback = more_callback
    view.add_item(more_button)

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

# Artist parse function
async def artist(item: dict, top_tracks: dict, interaction: discord.Interaction):
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
                artist_string = artist['name'].replace('*', '-') 
            else:
                artist_string += f", {artist['name']}".replace('*', '-')
                
        # Hide artist string from song listing if there is only one artist
        if len(top_tracks['tracks'][i]['artists']) == 1:
            if topsong_string == "":
                topsong_string = f"{i + 1}. **{top_tracks['tracks'][i]['name'].replace('*', '-')}**"
            else:
                topsong_string += f"\n{i + 1}. **{top_tracks['tracks'][i]['name'].replace('*', '-')}**"
        else:
            if topsong_string == "":
                topsong_string = f"{i + 1}. **{top_tracks['tracks'][i]['name'].replace('*', '-')}** - {artist_string}"
            else:
                topsong_string += f"\n{i + 1}. **{top_tracks['tracks'][i]['name'].replace('*', '-')}** - {artist_string}"
    
    embed.add_field(name = "Top Songs", value = topsong_string, inline = False)

    view = View(timeout=1800)
    
    # Add Open in Spotify button
    spotify_button = discord.ui.Button(label=f'Show on Spotify', style=discord.ButtonStyle.url, url=item['external_urls']['spotify'], row = 0)
    view.add_item(spotify_button)

    # More Button Callback
    async def more_callback(interaction: discord.Interaction):
        await interaction.response.defer()

        view = View(timeout=300)

        # Add Search on Google button
        google_button = discord.ui.Button(label='Search on Google', style=discord.ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(item["name"])).replace("%2B", "+")}', row = 1)
        view.add_item(google_button)

        # Close Button Callback
        async def delete_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            
            await msg.delete()
        
        # Add Close button
        close_button = discord.ui.Button(label='Close', style = discord.ButtonStyle.red, row = 1)
        close_button.callback = delete_callback
        view.add_item(close_button)

        msg = await interaction.followup.send(view = view)
    
    # Add More Options button
    more_button = discord.ui.Button(label=f'More', style=discord.ButtonStyle.gray, row = 0)
    more_button.callback = more_callback
    view.add_item(more_button)

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

# Album parse function
async def album(self, item: dict, interaction: discord.Interaction):
    """
    Handle Spotify album embeds.
    """
    
    image_url = item["images"][0]["url"]
                        
    songlist_string = ""
    for i in range(len(item['tracks']['items'])):
        artist_string = ""
        for artist in item['tracks']['items'][i]['artists']:
            if artist_string == "":
                artist_string = artist['name'].replace('*', '-') 
            else:
                artist_string += ", " + artist['name'].replace('*', '-')
                
        # Hide artist string from song listing if there is only one artist
        if len(item['tracks']['items'][i]['artists']) == 1:
            if songlist_string == "":
                songlist_string = f"{i + 1}. **{item['tracks']['items'][i]['name'].replace('*', '-')}**"
            else:
                songlist_string += f"\n{i + 1}. **{item['tracks']['items'][i]['name'].replace('*', '-')}**"
        else:
            if songlist_string == "":
                songlist_string = f"{i + 1}. **{item['tracks']['items'][i]['name'].replace('*', '-')}** - {artist_string}"
            else:
                songlist_string += f"\n{i + 1}. **{item['tracks']['items'][i]['name'].replace('*', '-')}** - {artist_string}"

    artist_string = ""
    for artist in item['artists']:
        if artist_string == "":
            artist_string = artist['name'].replace('*', '-') 
        else:
            artist_string = artist_string + ", " + artist['name'].replace('*', '-')
    
    embed = discord.Embed(title = f"{item['name']} - {artist_string}", description = songlist_string, color = Color.from_rgb(r = 255, g = 255, b = 255))
    embed.set_footer(text = "Getting colour information...")

    embed.set_thumbnail(url = item["images"][0]["url"])

    view = View(timeout=1800)
    
    # Add Open in Spotify button
    spotify_button = discord.ui.Button(label=f'Show on Spotify', style=discord.ButtonStyle.url, url=item['external_urls']['spotify'], row = 0)
    view.add_item(spotify_button)

    # More Button Callback
    async def more_callback(interaction: discord.Interaction):
        await interaction.response.defer()

        view = View()

        # Add song.link button                
        songlink_button = discord.ui.Button(label="Other Streaming Services", style=discord.ButtonStyle.url, url=f"https://song.link/{item['external_urls']['spotify']}", row = 1)
        view.add_item(songlink_button)

        # Add Search on Google button
        google_button = discord.ui.Button(label='Search on Google', style=discord.ButtonStyle.url, url=f'https://www.google.com/search?q={(quote(item["name"])).replace("%2B", "+")}+{(quote(artist_string)).replace("%2B", "+")}', row = 1)
        view.add_item(google_button)

        # Album Art Callback
        async def art_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            
            embed = discord.Embed(title = "Loading...", description = f"{self.bot.loading_emoji} Getting images...", color = Color.orange())
            embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
            await interaction.edit_original_response(embed = embed, view = None)
            
            if item["images"] != None:
                image_url = item["images"][0]["url"]

                if item["images"][0]['height'] == None or item["images"][0]['width'] == None:
                    embed = discord.Embed(title = f"{item['name']} ({artist_string}) - Album Art", description = "Viewing highest quality (Resolution unknown)", color = Color.from_rgb(r = 255, g = 255, b = 255))
                    embed.set_footer(text = "Getting colour information...")
                else:
                    embed = discord.Embed(title = f"{item['name']} ({artist_string}) - Album Art", description = f"Viewing highest quality ({item['images'][0]['width']}x{item['images'][0]['height']})", color = Color.from_rgb(r = 255, g = 255, b = 255))
                    embed.set_footer(text = "Getting colour information...")
                
                embed.set_image(url = item["images"][0]["url"])
                await interaction.edit_original_response(embed = embed)

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

                if item["images"][0]['height'] == None or item["images"][0]['width'] == None:
                    embed = discord.Embed(title = f"{item['name']} ({artist_string}) - Album Art", description = "Viewing highest quality (Resolution unknown)", color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]))
                    embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                else:
                    embed = discord.Embed(title = f"{item['name']} ({artist_string}) - Album Art", description = f"Viewing highest quality ({item['images'][0]['width']}x{item['images'][0]['height']})", color = Color.from_rgb(r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]))
                    embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                
                embed.set_image(url = item["images"][0]["url"])
                await interaction.edit_original_response(embed = embed)
            else:
                embed = discord.Embed(title = "No album art available.", color = Color.red())
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                await interaction.edit_original_response(embed = embed)
        
        # Add Album Art button
        art_button = discord.ui.Button(label='Album Art', style=discord.ButtonStyle.gray, row = 2)
        art_button.callback = art_callback
        view.add_item(art_button)

        # Close Button Callback
        async def delete_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            
            await msg.delete()
        
        # Add Close button
        close_button = discord.ui.Button(label='Close', style = discord.ButtonStyle.red, row = 2)
        close_button.callback = delete_callback
        view.add_item(close_button)

        msg = await interaction.followup.send(view = view)
    
    # Add More Options button
    more_button = discord.ui.Button(label=f'More', style=discord.ButtonStyle.gray, row = 0)
    more_button.callback = more_callback
    view.add_item(more_button)

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

def playlist():
    pass
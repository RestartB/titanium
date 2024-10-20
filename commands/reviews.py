import aiohttp
import discord
from discord import ButtonStyle, Color, app_commands
from discord.ext import commands
from discord.ui import View


class reviewCom(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    context = discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True)
    installs = discord.app_commands.AppInstallationType(guild=True, user=True)
    reviewGroup = app_commands.Group(name="reviews", description="Review a user on ReviewDB.", allowed_contexts=context, allowed_installs=installs)
    
    # Review view command
    @reviewGroup.command(name = "user", description = "See a user's reviews on ReviewDB.")
    @app_commands.checks.cooldown(1, 10)
    @app_commands.describe(user = "The user you want to see the reviews of.")
    @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissable message only visible to you. Defaults to false.")
    async def reviewView(self, interaction: discord.Interaction, user: discord.User, ephemeral: bool = False):
        try:    
            await interaction.response.defer(ephemeral=ephemeral)

            # Create URL
            request_url = f"https://manti.vendicated.dev/api/reviewdb/users/{user.id}/reviews"

            # Send request to ReviewDB
            async with aiohttp.ClientSession() as session:
                async with session.get(request_url) as request:
                    reviews = await request.json()
            
            reviewCount = reviews["reviewCount"]
            reviews = reviews["reviews"]
            
            i = 0
            prettyReview = 0
            pageList = []
            pages = []

            # Create pages
            for review in reviews:
                i += 1
            
                if pageList == []:
                    pageList.append([review, prettyReview])
                else:
                    pageList.append([review, prettyReview])
                
                prettyReview += 1

                # If there's 4 items in the current page, we split it into a new page
                if i % 4 == 0:
                    pages.append(pageList)
                    pageList = []
            
            # Add a page if remaining contents isn't empty
            if pageList != []:
                pages.append(pageList)
            
            class pageView(View):
                def __init__(self, pages):
                    super().__init__(timeout = 900)
                    self.page = 0
                    self.pages = pages

                    self.locked = False

                    self.interaction: discord.Interaction
                    self.message: discord.WebhookMessage

                    for item in self.children:
                        if item.custom_id == "first" or item.custom_id == "prev":
                            item.disabled = True
            
                # View timeout
                async def on_timeout(self) -> None:
                    for item in self.children:
                        item.disabled = True

                    await self.message.edit(view=self)
                
                # Page lock
                async def interaction_check(self, interaction: discord.Interaction):
                    if interaction.user.id != self.interaction.user.id:
                        if self.locked:
                            embed = discord.Embed(title = "Error", description = "This command is locked. Only the owner can control it.", color=Color.red())
                            await interaction.response.send_message(embed = embed, ephemeral=True, delete_after=5)
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
                    
                    embed = discord.Embed(title = f"ReviewDB User Reviews", description = f"There are **{reviewCount} reviews** for this user.", color = Color.random())
                    embed.set_author(name=user.name, url=f"https://discord.com/users/{user.id}", icon_url=user.display_avatar.url)
                    
                    i = 1
                    for item in self.pages[self.page]:
                        if item[0]["id"] == 0:
                            reviewContent = item[0]["comment"]
                            
                            embed.add_field(name = "System", value = reviewContent, inline = False)
                        else:
                            reviewTimestamp = item[0]["timestamp"]
                            
                            # Handle strings being too long
                            if len(item[0]["comment"]) > 1024:
                                reviewContent = item[0]["comment"][:1021] + "..."
                            else:
                                reviewContent = item[0]["comment"]
                            
                            embed.add_field(name = f"{item[1]}. @{item[0]['sender']['username']} - <t:{reviewTimestamp}:d>", value = reviewContent, inline = False)

                            i += 1

                    embed.set_footer(text = f"Currently controlling: {interaction.user.name} - Page {self.page + 1}/{len(self.pages)}", icon_url = interaction.user.display_avatar.url)
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

                    embed = discord.Embed(title = f"ReviewDB User Reviews", description = f"There are **{reviewCount} reviews** for this user.", color = Color.random())
                    embed.set_author(name=user.name, url=f"https://discord.com/users/{user.id}", icon_url=user.display_avatar.url)

                    i = 1
                    for item in self.pages[self.page]:
                        if item[0]["id"] == 0:
                            reviewContent = item[0]["comment"]
                            
                            embed.add_field(name = "System", value = reviewContent, inline = False)
                        else:
                            reviewTimestamp = item[0]["timestamp"]
                            
                            # Handle strings being too long
                            if len(item[0]["comment"]) > 1024:
                                reviewContent = item[0]["comment"][:1021] + "..."
                            else:
                                reviewContent = item[0]["comment"]
                            
                            embed.add_field(name = f"{item[1]}. @{item[0]['sender']['username']} - <t:{reviewTimestamp}:d>", value = reviewContent, inline = False)

                            i += 1

                    embed.set_footer(text = f"Currently controlling: {interaction.user.name} - Page {self.page + 1}/{len(self.pages)}", icon_url = interaction.user.display_avatar.url)
                    await interaction.response.edit_message(embed = embed, view = self)

                # Lock / unlock toggle
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
                        await interaction.response.send_message(embed = embed, delete_after=5)
                
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
                    
                    embed = discord.Embed(title = f"ReviewDB User Reviews", description = f"There are **{reviewCount} reviews** for this user.", color = Color.random())
                    embed.set_author(name=user.name, url=f"https://discord.com/users/{user.id}", icon_url=user.display_avatar.url)

                    i = 1
                    for item in self.pages[self.page]:
                        if item[0]["id"] == 0:
                            reviewContent = item[0]["comment"]
                    
                            embed.add_field(name = "System", value = reviewContent, inline = False)
                        else:
                            reviewTimestamp = item[0]["timestamp"]
                            
                            # Handle strings being too long
                            if len(item[0]["comment"]) > 1024:
                                reviewContent = item[0]["comment"][:1021] + "..."
                            else:
                                reviewContent = item[0]["comment"]
                            
                            embed.add_field(name = f"{item[1]}. @{item[0]['sender']['username']} - <t:{reviewTimestamp}:d>", value = reviewContent, inline = False)

                            i += 1

                    embed.set_footer(text = f"Currently controlling: {interaction.user.name} - Page {self.page + 1}/{len(self.pages)}", icon_url = interaction.user.display_avatar.url)
                    await interaction.response.edit_message(embed = embed, view = self)
                
                # Last page button
                @discord.ui.button(emoji="⏭️", style=ButtonStyle.green, custom_id="last")
                async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.page = len(self.pages) - 1

                    for item in self.children:
                        item.disabled = False

                        if item.custom_id == "next" or item.custom_id == "last":
                            item.disabled = True
                    
                    embed = discord.Embed(title = f"ReviewDB User Reviews", description = f"There are **{reviewCount} reviews** for this user.", color = Color.random())
                    embed.set_author(name=user.name, url=f"https://discord.com/users/{user.id}", icon_url=user.display_avatar.url)

                    i = 1
                    for item in self.pages[self.page]:
                        if item[0]["id"] == 0:
                            reviewContent = item[0]["comment"]
                    
                            embed.add_field(name = "System", value = reviewContent, inline = False)
                        else:
                            reviewTimestamp = item[0]["timestamp"]
                            
                            # Handle strings being too long
                            if len(item[0]["comment"]) > 1024:
                                reviewContent = item[0]["comment"][:1021] + "..."
                            else:
                                reviewContent = item[0]["comment"]
                            
                            embed.add_field(name = f"{item[1]}. @{item[0]['sender']['username']} - <t:{reviewTimestamp}:d>", value = reviewContent, inline = False)

                            i += 1

                    embed.set_footer(text = f"Currently controlling: {interaction.user.name} - Page {self.page + 1}/{len(self.pages)}", icon_url = interaction.user.display_avatar.url)
                    await interaction.response.edit_message(embed = embed, view = self)

            embed = discord.Embed(title = f"ReviewDB User Reviews", description = f"There are **{reviewCount} reviews** for this user.", color = Color.random())
            embed.set_author(name=user.name, url=f"https://discord.com/users/{user.id}", icon_url=user.display_avatar.url)
            
            if not(len(pages) == 0):
                # Reviews exist
                i = 1
                for item in pages[0]:
                    if int(item[0]["id"]) == 0:
                        reviewContent = item[0]["comment"]
                        
                        embed.add_field(name = "System", value = reviewContent, inline = False)
                    else:
                        reviewTimestamp = item[0]["timestamp"]
                            
                        # Handle strings being too long
                        if len(item[0]["comment"]) > 1024:
                            reviewContent = item[0]["comment"][:1021] + "..."
                        else:
                            reviewContent = item[0]["comment"]
                        
                        embed.add_field(name = f"{item[1]}. @{item[0]['sender']['username']} - <t:{reviewTimestamp}:d>", value = reviewContent, inline = False)

                        i += 1
                
                embed.set_footer(text = f"Currently controlling: {interaction.user.name} - Page 1/{len(pages)}", icon_url = interaction.user.display_avatar.url)
                
                if len(pages) == 1:
                    await interaction.followup.send(embed = embed, ephemeral=ephemeral)
                else:
                    msg = await interaction.followup.send(embed = embed, view = pageView(pages), ephemeral=ephemeral, wait=True)

                    pageView.interaction = interaction
                    pageView.message = msg
            else:
                embed = discord.Embed(title = "ReviewDB User Reviews", description="This user has no reviews!", color = Color.red())
                embed.set_author(name=user.name, url=f"https://discord.com/users/{user.id}", icon_url=user.display_avatar.url)
            
                await interaction.followup.send(embed = embed, ephemeral=ephemeral)
        except discord.errors.HTTPException as e:
            if "automod" in str(e).lower():
                embed = discord.Embed(title = "Error", description = "Message has been blocked by server AutoMod policies. Server admins may have been notified.", color = Color.red())
                embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                await interaction.followup.send(embed = embed, ephemeral=ephemeral)
            else:
                embed = discord.Embed(title = "Error", description = "Couldn't send the message. AutoMod may have been triggered.", color = Color.red())
                embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                await interaction.followup.send(embed = embed, ephemeral=ephemeral)
    
    # Review view command
    @reviewGroup.command(name = "server", description = "See the current server's reviews on ReviewDB.")
    @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissable message only visible to you. Defaults to false.")
    @app_commands.checks.cooldown(1, 10)
    async def reviewServerView(self, interaction: discord.Interaction, server_id: int = 0, ephemeral: bool = False):
        try:    
            await interaction.response.defer(ephemeral=ephemeral)
            
            if interaction.guild == None:
                embed = discord.Embed(title = "Error", description = "This is not a guild!", color = Color.red())
                embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                
                await interaction.followup.send(embed = embed, ephemeral=ephemeral)
            
            # Create URL
            if server_id == 0:
                request_url = f"https://manti.vendicated.dev/api/reviewdb/users/{interaction.guild.id}/reviews"
            else:
                request_url = f"https://manti.vendicated.dev/api/reviewdb/users/{int(server_id)}/reviews"

            # Send request to ReviewDB
            async with aiohttp.ClientSession() as session:
                async with session.get(request_url) as request:
                    reviews = await request.json()
            
            reviewCount = reviews["reviewCount"]
            reviews = reviews["reviews"]
            
            i = 0
            prettyReview = 0
            pageList = []
            pages = []

            for review in reviews:
                i += 1
            
                if pageList == []:
                    pageList.append([review, prettyReview])
                else:
                    pageList.append([review, prettyReview])
                
                prettyReview += 1

                # If there's 4 items in the current page, we split it into a new page
                if i % 4 == 0:
                    pages.append(pageList)
                    pageList = []
            
            if pageList != []:
                pages.append(pageList)
            
            class pageView(View):
                def __init__(self, pages):
                    super().__init__(timeout = 900)
                    self.page = 0
                    self.pages = pages

                    self.interaction: discord.Interaction
                    self.message: discord.WebhookMessage
                    
                    self.locked = False

                    for item in self.children:
                        if item.custom_id == "first" or item.custom_id == "prev":
                            item.disabled = True
            
                async def on_timeout(self) -> None:
                    for item in self.children:
                        item.disabled = True

                    await self.message.edit(view=self)
                
                async def interaction_check(self, interaction: discord.Interaction):
                    if interaction.server.id != self.interaction.server.id:
                        if self.locked:
                            embed = discord.Embed(title = "Error", description = "This command is locked. Only the owner can control it.", color=Color.red())
                            await interaction.response.send_message(embed = embed, ephemeral=True, delete_after=5)
                        else:
                            return True
                    else:
                        return True
                
                @discord.ui.button(emoji="⏮️", style=ButtonStyle.red, custom_id="first")
                async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.page = 0

                    for item in self.children:
                        item.disabled = False
                        
                        if item.custom_id == "first" or item.custom_id == "prev":
                            item.disabled = True
                    
                    embed = discord.Embed(title = f"ReviewDB Server Reviews", description = f"There are **{reviewCount} reviews** for this server.", color = Color.random())
                    embed.set_author(name=interaction.guild.name, icon_url=(interaction.guild.icon.url if interaction.guild.icon is not None else ""))
                    
                    i = 1
                    for item in self.pages[self.page]:
                        if item[0]["id"] == 0:
                            reviewContent = item[0]["comment"]
                            
                            embed.add_field(name = "System", value = reviewContent, inline = False)
                        else:
                            reviewTimestamp = item[0]["timestamp"]
                            
                            # Handle strings being too long
                            if len(item[0]["comment"]) > 1024:
                                reviewContent = item[0]["comment"][:1021] + "..."
                            else:
                                reviewContent = item[0]["comment"]
                            
                            embed.add_field(name = f"{item[1]}. @{item[0]['sender']['username']} - <t:{reviewTimestamp}:d>", value = reviewContent, inline = False)

                            i += 1

                    embed.set_footer(text = f"Currently controlling: {interaction.user.name} - Page {self.page + 1}/{len(self.pages)}", icon_url = interaction.user.display_avatar.url)
                    await interaction.response.edit_message(embed = embed, view = self)
                
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

                    embed = discord.Embed(title = f"ReviewDB Server Reviews", description = f"There are **{reviewCount} reviews** for this server.", color = Color.random())
                    embed.set_author(name=interaction.guild.name, icon_url=(interaction.guild.icon.url if interaction.guild.icon is not None else ""))

                    i = 1
                    for item in self.pages[self.page]:
                        if item[0]["id"] == 0:
                            reviewContent = item[0]["comment"]
                            
                            embed.add_field(name = "System", value = reviewContent, inline = False)
                        else:
                            reviewTimestamp = item[0]["timestamp"]
                            
                            # Handle strings being too long
                            if len(item[0]["comment"]) > 1024:
                                reviewContent = item[0]["comment"][:1021] + "..."
                            else:
                                reviewContent = item[0]["comment"]
                            
                            embed.add_field(name = f"{item[1]}. @{item[0]['sender']['username']} - <t:{reviewTimestamp}:d>", value = reviewContent, inline = False)

                            i += 1

                    embed.set_footer(text = f"Currently controlling: {interaction.user.name} - Page {self.page + 1}/{len(self.pages)}", icon_url = interaction.user.display_avatar.url)
                    await interaction.response.edit_message(embed = embed, view = self)

                @discord.ui.button(emoji="🔓", style=ButtonStyle.green, custom_id="lock")
                async def lock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.server.id == self.interaction.server.id:
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
                        await interaction.response.send_message(embed = embed, delete_after=5)
                
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
                    
                    embed = discord.Embed(title = f"ReviewDB Server Reviews", description = f"There are **{reviewCount} reviews** for this server.", color = Color.random())
                    embed.set_author(name=interaction.guild.name, icon_url=(interaction.guild.icon.url if interaction.guild.icon is not None else ""))

                    i = 1
                    for item in self.pages[self.page]:
                        if item[0]["id"] == 0:
                            reviewContent = item[0]["comment"]
                    
                            embed.add_field(name = "System", value = reviewContent, inline = False)
                        else:
                            reviewTimestamp = item[0]["timestamp"]
                            
                            # Handle strings being too long
                            if len(item[0]["comment"]) > 1024:
                                reviewContent = item[0]["comment"][:1021] + "..."
                            else:
                                reviewContent = item[0]["comment"]
                            
                            embed.add_field(name = f"{item[1]}. @{item[0]['sender']['username']} - <t:{reviewTimestamp}:d>", value = reviewContent, inline = False)

                            i += 1

                    embed.set_footer(text = f"Currently controlling: {interaction.user.name} - Page {self.page + 1}/{len(self.pages)}", icon_url = interaction.user.display_avatar.url)
                    await interaction.response.edit_message(embed = embed, view = self)
                
                @discord.ui.button(emoji="⏭️", style=ButtonStyle.green, custom_id="last")
                async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.page = len(self.pages) - 1

                    for item in self.children:
                        item.disabled = False

                        if item.custom_id == "next" or item.custom_id == "last":
                            item.disabled = True
                    
                    embed = discord.Embed(title = f"ReviewDB Server Reviews", description = f"There are **{reviewCount} reviews** for this server.", color = Color.random())
                    embed.set_author(name=interaction.guild.name, icon_url=(interaction.guild.icon.url if interaction.guild.icon is not None else ""))

                    i = 1
                    for item in self.pages[self.page]:
                        if item[0]["id"] == 0:
                            reviewContent = item[0]["comment"]
                    
                            embed.add_field(name = "System", value = reviewContent, inline = False)
                        else:
                            reviewTimestamp = item[0]["timestamp"]
                            
                            # Handle strings being too long
                            if len(item[0]["comment"]) > 1024:
                                reviewContent = item[0]["comment"][:1021] + "..."
                            else:
                                reviewContent = item[0]["comment"]
                            
                            embed.add_field(name = f"{item[1]}. @{item[0]['sender']['username']} - <t:{reviewTimestamp}:d>", value = reviewContent, inline = False)

                            i += 1

                    embed.set_footer(text = f"Currently controlling: {interaction.user.name} - Page {self.page + 1}/{len(self.pages)}", icon_url = interaction.user.display_avatar.url)
                    await interaction.response.edit_message(embed = embed, view = self)

            embed = discord.Embed(title = f"ReviewDB Server Reviews", description = f"There are **{reviewCount} reviews** for this server.", color = Color.random())
            embed.set_author(name=interaction.guild.name, icon_url=(interaction.guild.icon.url if interaction.guild.icon is not None else ""))
            
            if not(len(pages) == 0):
                i = 1
                for item in pages[0]:
                    if int(item[0]["id"]) == 0:
                        reviewContent = item[0]["comment"]
                        
                        embed.add_field(name = "System", value = reviewContent, inline = False)
                    else:
                        reviewTimestamp = item[0]["timestamp"]
                            
                        # Handle strings being too long
                        if len(item[0]["comment"]) > 1024:
                            reviewContent = item[0]["comment"][:1021] + "..."
                        else:
                            reviewContent = item[0]["comment"]
                        
                        embed.add_field(name = f"{item[1]}. @{item[0]['sender']['username']} - <t:{reviewTimestamp}:d>", value = reviewContent, inline = False)

                        i += 1
                
                embed.set_footer(text = f"Currently controlling: {interaction.user.name} - Page 1/{len(pages)}", icon_url = interaction.user.display_avatar.url)
                
                if len(pages) == 1:
                    await interaction.followup.send(embed = embed, ephemeral=ephemeral)
                else:
                    await interaction.followup.send(embed = embed, view = pageView(pages), ephemeral=ephemeral)

                    pageView.interaction = interaction
                    pageView.message = await interaction.original_response()
            else:
                embed = discord.Embed(title = "ReviewDB Server Reviews", description="This server has no reviews!", color = Color.red())
                embed.set_author(name=interaction.guild.name, icon_url=(interaction.guild.icon.url if interaction.guild.icon is not None else ""))
            
                await interaction.followup.send(embed = embed, ephemeral=ephemeral)
        except discord.errors.HTTPException as e:
            if "automod" in str(e).lower():
                embed = discord.Embed(title = "Error", description = "Message has been blocked by server AutoMod policies. Server admins may have been notified.", color = Color.red())
                embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                await interaction.followup.send(embed = embed, ephemeral=ephemeral)
            else:
                embed = discord.Embed(title = "Error", description = "Couldn't send the message. AutoMod may have been triggered.", color = Color.red())
                embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                await interaction.followup.send(embed = embed, ephemeral=ephemeral)

async def setup(bot):
    await bot.add_cog(reviewCom(bot))

import aiohttp
import discord
import wikipedia
from discord import ButtonStyle, Color, app_commands
from discord.ext import commands
from discord.ui import View


class web_search(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    context = discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True)
    installs = discord.app_commands.AppInstallationType(guild=True, user=True)
    searchGroup = app_commands.Group(name="search", description="Search the web using various services.", allowed_contexts=context, allowed_installs=installs)

    # Urban Dictionary command
    @searchGroup.command(name = "urban-dictionary", description = "Search Urban Dictionary. Warning: content is mostly unmoderated and may be inappropriate!")
    @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissable message only visible to you. Defaults to false.")
    @app_commands.checks.cooldown(1,10)
    async def urban_dict(self, interaction: discord.Interaction, query: str, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)

        embed_list = []

        try:
            query = query.replace(" ", "%20")
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.urbandictionary.com/v0/define?term={query}") as request:
                    request_data = await request.json()

            item_list = []

            if len(request_data['list']) != 0:
                for item in request_data['list']:
                    item_list.append(item)
                
                class UrbanDictPageView(View):
                    def __init__(self, pages):
                        super().__init__(timeout = 900)
                        
                        self.page = 0
                        self.pages = pages

                        self.locked = False

                        for item in self.children:
                            if item.custom_id == "first" or item.custom_id == "prev":
                                item.disabled = True
                
                    async def on_timeout(self) -> None:
                        for item in self.children:
                            item.disabled = True

                        await self.message.edit(view=self)
                    
                    async def interaction_check(self, interaction: discord.Interaction):
                        if interaction.user.id != self.interaction.user.id:
                            if self.locked:
                                embed = discord.Embed(title = "Error", description = "This command is locked. Only the owner can control it.", color=Color.red())
                                await interaction.response.send_message(embed = embed, ephemeral=True, delete_after=5)
                            else:
                                return True
                        else:
                            return True
                    
                    @discord.ui.button(emoji="⏮️", style=ButtonStyle.red, custom_id="first")
                    async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        embed_list.pop()

                        self.page = 0

                        for item in self.children:
                            item.disabled = False
                            
                            if item.custom_id == "first" or item.custom_id == "prev":
                                item.disabled = True
                        
                        embed = discord.Embed(title = f"{self.pages[self.page]['word']} (Urban Dictionary)", description = f"**Author: {self.pages[self.page]['author']}**\n\n||{(self.pages[self.page]['definition'].replace('[', '')).replace(']', '')}||", url = self.pages[self.page]['permalink'], color = Color.random())
                        
                        embed.set_footer(text = f"@{interaction.user.name} - Page {self.page + 1}/{len(item_list)}", icon_url = interaction.user.display_avatar.url)
                        embed_list.append(embed)
                        
                        await interaction.response.edit_message(embeds = embed_list, view = self)
                    
                    @discord.ui.button(emoji="⏪", style=ButtonStyle.gray, custom_id="prev")
                    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        embed_list.pop()
                        
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
                        
                        embed = discord.Embed(title = f"{self.pages[self.page]['word']} (Urban Dictionary)", description = f"**Author: {self.pages[self.page]['author']}**\n\n||{(self.pages[self.page]['definition'].replace('[', '')).replace(']', '')}||", url = self.pages[self.page]['permalink'], color = Color.random())
                        
                        embed.set_footer(text = f"@{interaction.user.name} - Page {self.page + 1}/{len(item_list)}", icon_url = interaction.user.display_avatar.url)
                        embed_list.append(embed)
                        
                        await interaction.response.edit_message(embeds = embed_list, view = self)

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
                    
                    @discord.ui.button(emoji="⏩", style=ButtonStyle.gray, custom_id="next")
                    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        embed_list.pop()
                        
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
                        
                        embed = discord.Embed(title = f"{self.pages[self.page]['word']} (Urban Dictionary)", description = f"**Author: {self.pages[self.page]['author']}**\n\n||{(self.pages[self.page]['definition'].replace('[', '')).replace(']', '')}||", url = self.pages[self.page]['permalink'], color = Color.random())
                        
                        embed.set_footer(text = f"@{interaction.user.name} - Page {self.page + 1}/{len(item_list)}", icon_url = interaction.user.display_avatar.url)
                        embed_list.append(embed)
                        
                        await interaction.response.edit_message(embeds = embed_list, view = self)
                    
                    @discord.ui.button(emoji="⏭️", style=ButtonStyle.green, custom_id="last")
                    async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        embed_list.pop()
                        
                        self.page = len(self.pages) - 1

                        for item in self.children:
                            item.disabled = False

                            if item.custom_id == "next" or item.custom_id == "last":
                                item.disabled = True
                        
                        embed = discord.Embed(title = f"{self.pages[self.page]['word']} (Urban Dictionary)", description = f"**Author: {self.pages[self.page]['author']}**\n\n||{(self.pages[self.page]['definition'].replace('[', '')).replace(']', '')}||", url = self.pages[self.page]['permalink'], color = Color.random())
                        
                        embed.set_footer(text = f"@{interaction.user.name} - Page {self.page + 1}/{len(item_list)}", icon_url = interaction.user.display_avatar.url)
                        embed_list.append(embed)
                        
                        await interaction.response.edit_message(embeds = embed_list, view = self)

                embed = discord.Embed(title = "Content Warning", description = "Urban Dictionary has very little moderation and content may be inappropriate! View at your own risk.", color = Color.orange())
                embed_list.append(embed)
                
                embed = discord.Embed(title = f"{item_list[0]['word']} (Urban Dictionary)", description = f"**Author: {item_list[0]['author']}**\n\n||{(item_list[0]['definition'].replace('[', '')).replace(']', '')}||", url = item_list[0]['permalink'], color = Color.random())
                embed.set_footer(text = f"@{interaction.user.name} - Page 1/{len(item_list)}", icon_url = interaction.user.display_avatar.url)
                embed_list.append(embed)
                
                if len(item_list) == 1:
                    await interaction.followup.send(embeds = embed_list, ephemeral=ephemeral)
                else:
                    await interaction.followup.send(embeds = embed_list, view = UrbanDictPageView(item_list), ephemeral=ephemeral)

                    UrbanDictPageView.interaction = interaction
                    UrbanDictPageView.message = await interaction.original_response()
            else:
                embed = discord.Embed(title = "No results found.", color = Color.red())
                embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        except discord.errors.HTTPException as e:
            if "automod" in str(e).lower():
                embed = discord.Embed(title = "Error", description = "Message has been blocked by server AutoMod policies. Server admins may have been notified.", color = Color.red())
                embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            else:
                embed = discord.Embed(title = "Error", description = "Couldn't send the message.", color = Color.red())
                embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    # Wikipedia command
    @searchGroup.command(name = "wikipedia", description = "Search Wikipedia for information.")
    @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissable message only visible to you. Defaults to false.")
    @app_commands.checks.cooldown(1, 5)
    async def wiki(self, interaction: discord.Interaction, search: str, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        
        try:
            page = wikipedia.page(search)
            
            embed = discord.Embed(title = f"Search: {search}", color=Color.from_rgb(r = 255, g = 255, b = 255))
            embed.add_field(name = f"{page.title}", value = wikipedia.summary(search, sentences = 3))
            embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
            embed.set_author(name = "Wikipedia", icon_url = "https://upload.wikimedia.org/wikipedia/en/thumb/8/80/Wikipedia-logo-v2.svg/1200px-Wikipedia-logo-v2.svg.png")
            
            view = View()
            view.add_item(discord.ui.Button(label = "Read More", style = discord.ButtonStyle.url, url = page.url))
            
            await interaction.followup.send(embed = embed, view = view, ephemeral=ephemeral)
        except wikipedia.exceptions.PageError:
            embed = discord.Embed(title = "Error", description = f"No page was found on Wikipedia matching {search}. Try another search.", color = Color.red())
            embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
            embed.set_author(name = "Wikipedia", icon_url = "https://upload.wikimedia.org/wikipedia/en/thumb/8/80/Wikipedia-logo-v2.svg/1200px-Wikipedia-logo-v2.svg.png")
            
            await interaction.followup.send(embed = embed, ephemeral=ephemeral)
        except wikipedia.exceptions.DisambiguationError as error:
            embed = discord.Embed(title = "Please be more specific with your query.", description=error, color = Color.red())
            embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
            embed.set_author(name = "Wikipedia", icon_url = "https://upload.wikimedia.org/wikipedia/en/thumb/8/80/Wikipedia-logo-v2.svg/1200px-Wikipedia-logo-v2.svg.png")
            
            await interaction.followup.send(embed = embed, ephemeral=ephemeral)
        except discord.errors.HTTPException as e:
            if "automod" in str(e).lower():
                embed = discord.Embed(title = "Error", description = "Message has been blocked by server AutoMod policies.", color = Color.red())
                embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                await interaction.followup.send(embed = embed, ephemeral=ephemeral)
            else:
                embed = discord.Embed(title = "Error", description = "Couldn't send the message. AutoMod may have been triggered.", color = Color.red())
                embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
                await interaction.followup.send(embed = embed, ephemeral=ephemeral)

async def setup(bot):
    await bot.add_cog(web_search(bot))
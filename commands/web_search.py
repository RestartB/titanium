import discord
from discord import app_commands, Color, ButtonStyle
from discord.ext import commands
from discord.ui import View
import aiohttp
import wikipedia

class web_search(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    context = discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True)
    installs = discord.app_commands.AppInstallationType(guild=True, user=True)
    searchGroup = app_commands.Group(name="search", description="Search the web using various services.", allowed_contexts=context, allowed_installs=installs)
    
    # Equation Solver command (broken)
    # @searchGroup.command(name = "equation-solver", description= "Solve an equation or expression.")
    # @app_commands.checks.cooldown(1, 10)
    # async def self(interaction: discord.Interaction, equation: str):
    #     await interaction.response.defer()
        
    #     try:
    #         # Send request to mathjs
    #         request_url = f"http://api.mathjs.org/v4/?expr={equation.replace(' ', '%20')}"
    #         request = requests.get(request_url)
    #         request_data = request.json()

    #         # Generate embed
    #         embed = discord.Embed(title = "Equation Solver")
    #         embed.add_field(name = "Equation / Expression", value = equation)
    #         embed.add_field(name = "Solution", value = request_data)
    #         embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)

    #         # Edit loading message with new embed
    #         await interaction.edit_original_response(embed = embed)
    #     except Exception:
    #         embed = discord.Embed(title = "Error", description = "An error has occurred. Solutions:\n\n**1.** Is the expression / equation valid?\n**2.** Are you using any forbidden characters?\n**3.** Try again later.")
    #         embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
    #         await interaction.edit_original_response(embed = embed)

    # Urban Dictionary command
    @searchGroup.command(name = "urban-dictionary", description = "Search Urban Dictionary. Warning: content is mostly unmoderated and may be inappropriate!")
    @app_commands.checks.cooldown(1,10)
    async def urban_dict(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        embed = discord.Embed(title = "Searching...", color = Color.orange())
        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
        await interaction.followup.send(embed = embed)

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
                        super().__init__(timeout = None)
                        self.page = 0
                        self.pages = pages
                
                    @discord.ui.button(label="<", style=ButtonStyle.green, custom_id="prev")
                    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        embed_list.pop()
                        if self.page > 0:
                            self.page -= 1
                        else:
                            self.page = len(self.pages) - 1
                        embed = discord.Embed(title = f"{self.pages[self.page]['word']} (Urban Dictionary)", description = f"**Author: {self.pages[self.page]['author']}**\n\n||{(self.pages[self.page]['definition'].replace('[', '')).replace(']', '')}||", color = Color.random())
                        embed.set_footer(text = f"Requested by {interaction.user.name} - Page {self.page + 1}/{len(item_list)}", icon_url = interaction.user.avatar.url)
                        embed_list.append(embed)
                        await interaction.response.edit_message(embeds = embed_list)

                    @discord.ui.button(label=">", style=ButtonStyle.green, custom_id="next")
                    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        embed_list.pop()
                        if self.page < len(self.pages) - 1:
                            self.page += 1
                        else:
                            self.page = 0
                        embed = discord.Embed(title = f"{self.pages[self.page]['word']} (Urban Dictionary)", description = f"**Author: {self.pages[self.page]['author']}**\n\n||{(self.pages[self.page]['definition'].replace('[', '')).replace(']', '')}||", color = Color.random())
                        embed.set_footer(text = f"Requested by {interaction.user.name} - Page {self.page + 1}/{len(item_list)}", icon_url = interaction.user.avatar.url)
                        embed_list.append(embed)
                        await interaction.response.edit_message(embeds = embed_list)

                embed = discord.Embed(title = "Content Warning", description = "Urban Dictionary has very little moderation and content may be inappropriate! View at your own risk.", color = Color.orange())
                embed_list.append(embed)
                
                embed = discord.Embed(title = f"{item_list[0]['word']} (Urban Dictionary)", description = f"**Author: {item_list[0]['author']}**\n\n||{(item_list[0]['definition'].replace('[', '')).replace(']', '')}||", color = Color.random())
                embed.set_footer(text = f"Requested by {interaction.user.name} - Page 1/{len(item_list)}", icon_url = interaction.user.avatar.url)
                embed_list.append(embed)
                
                if len(item_list) == 1:
                    await interaction.edit_original_response(embeds = embed_list)
                else:
                    await interaction.edit_original_response(embeds = embed_list, view = UrbanDictPageView(item_list))
            else:
                embed = discord.Embed(title = "No results found.", color = Color.red())
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                await interaction.edit_original_response(embed = embed)
        except Exception:
            embed = discord.Embed(title = "An error has occurred.", description = "Please try again later or message <@563372552643149825> for assistance.", color = Color.red())
            embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
            await interaction.edit_original_response(embed = embed, view = None)

    # Wikipedia command
    @searchGroup.command(name = "wikipedia", description = "Search Wikipedia for information.")
    @app_commands.checks.cooldown(1, 5)
    async def wiki(self, interaction: discord.Interaction, search: str):
        await interaction.response.defer()
        embed = discord.Embed(title = "Loading...", color = Color.orange())
        await interaction.followup.send(embed = embed)
        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
        try:
            page = wikipedia.page(search)
            embed = discord.Embed(title = f"Search: {search}", color=Color.from_rgb(r = 255, g = 255, b = 255))
            embed.add_field(name = f"{page.title}", value = wikipedia.summary(search, sentences = 3))
            embed.set_footer(text = "Wikipedia", icon_url = "https://upload.wikimedia.org/wikipedia/en/thumb/8/80/Wikipedia-logo-v2.svg/1200px-Wikipedia-logo-v2.svg.png")
            view = View()
            view.add_item(discord.ui.Button(label = "Read More", style = discord.ButtonStyle.url, url = page.url))
            await interaction.edit_original_response(embed = embed, view = view)
        except wikipedia.exceptions.PageError:
            embed = discord.Embed(title = "Error", description = f"No page was found on Wikipedia matching {search}. Try another search.", color = Color.red())
            embed.set_footer(text = "Wikipedia", icon_url = "https://upload.wikimedia.org/wikipedia/en/thumb/8/80/Wikipedia-logo-v2.svg/1200px-Wikipedia-logo-v2.svg.png")
            await interaction.edit_original_response(embed = embed)
        except wikipedia.exceptions.DisambiguationError as error:
            embed = discord.Embed(title = "Please be more specific with your query.", color = Color.red())
            embed.add_field(name = "Information", value = error)
            embed.set_footer(text = "Wikipedia", icon_url = "https://upload.wikimedia.org/wikipedia/en/thumb/8/80/Wikipedia-logo-v2.svg/1200px-Wikipedia-logo-v2.svg.png")
            await interaction.edit_original_response(embed = embed)
        except Exception:
            embed = discord.Embed(title = "An error has occurred.", description = "Please try again later or message <@563372552643149825> for assistance.", color = Color.red())
            embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
            await interaction.edit_original_response(embed = embed, view = None)

async def setup(bot):
    await bot.add_cog(web_search(bot))
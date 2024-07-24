import discord
from discord import app_commands, Color, ButtonStyle
from discord.ext import commands
from discord.ui import Select, View
import aiohttp
from urllib.parse import quote
import json

class reviewCom(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Reviews command
    @app_commands.command(name = "reviews", description = "See a user's reviews on ReviewDB.")
    @app_commands.checks.cooldown(1, 10)
    @app_commands.describe(user = "The user you want to see the reviews of.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def reviews(self, interaction: discord.Interaction, user: discord.User):
        try:    
            await interaction.response.defer()

            embed = discord.Embed(title = "Loading...", color = Color.orange())
            embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
            await interaction.followup.send(embed = embed)

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
                    super().__init__(timeout = 43200)
                    self.page = 0
                    self.pages = pages
            
                @discord.ui.button(label="<", style=discord.ButtonStyle.green, custom_id="prev")
                async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if self.page > 0:
                        self.page -= 1
                    else:
                        self.page = len(self.pages) - 1

                    embed = discord.Embed(title = f"review.db User Reviews", description = f"There are **{reviewCount} reviews** for this user.", color = Color.random())
                    embed.set_author(name=user.name, url=f"https://discord.com/users/{user.id}", icon_url=user.avatar.url)

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

                    embed.set_footer(text = f"Currently controlling: {interaction.user.name} - Page {self.page + 1}/{len(self.pages)}", icon_url = interaction.user.avatar.url)
                    await interaction.response.edit_message(embed = embed)

                @discord.ui.button(label=">", style=discord.ButtonStyle.green, custom_id="next")
                async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if self.page < len(self.pages) - 1:
                        self.page += 1
                    else:
                        self.page = 0
                    
                    embed = discord.Embed(title = f"review.db User Reviews", description = f"There are **{reviewCount} reviews** for this user.", color = Color.random())
                    embed.set_author(name=user.name, url=f"https://discord.com/users/{user.id}", icon_url=user.avatar.url)

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

                    embed.set_footer(text = f"Currently controlling: {interaction.user.name} - Page {self.page + 1}/{len(self.pages)}", icon_url = interaction.user.avatar.url)
                    await interaction.response.edit_message(embed = embed)

            embed = discord.Embed(title = f"review.db User Reviews", description = f"There are **{reviewCount} reviews** for this user.", color = Color.random())
            embed.set_author(name=user.name, url=f"https://discord.com/users/{user.id}", icon_url=user.avatar.url)
            
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
                
                embed.set_footer(text = f"Currently controlling: {interaction.user.name} - Page 1/{len(pages)}", icon_url = interaction.user.avatar.url)
                
                if len(pages) == 1:
                    await interaction.edit_original_response(embed = embed)
                else:
                    await interaction.edit_original_response(embed = embed, view = pageView(pages))
            else:
                embed = discord.Embed(title = "review.db User Reviews", description="This user has no reviews!", color = Color.red())
                embed.set_author(name=user.name, url=f"https://discord.com/users/{user.id}", icon_url=user.avatar.url)
            
                await interaction.edit_original_response(embed = embed)
        except discord.errors.HTTPException as e:
            if "automod" in str(e).lower():
                embed = discord.Embed(title = "Error", description = "Message has been blocked by server AutoMod policies.", color = Color.red())
                await interaction.edit_original_response(embed = embed, view = None)
            else:
                embed = discord.Embed(title = "Error", description = "Couldn't send the message. AutoMod may have been triggered.", color = Color.red())
                await interaction.edit_original_response(embed = embed, view = None)
        except Exception:
            embed = discord.Embed(title = "Unexpected Error", description = "Please try again later or message <@563372552643149825> for assistance.", color = Color.red())
            await interaction.edit_original_response(embed = embed, view = None)

async def setup(bot):
    await bot.add_cog(reviewCom(bot))
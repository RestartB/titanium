import asqlite
import discord
from discord import ButtonStyle, Color, app_commands
from discord.ext import commands
from discord.ui import View
from thefuzz import process


class Tags(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    def __init__(self, bot):
        self.bot = bot
        self.tagsPool: asqlite.Pool = bot.tagsPool
        self.tags: dict = {}
        
        self.bot.loop.create_task(self.setup())
        self.bot.loop.create_task(self.getTagLists())
    
    # Setup function
    async def setup(self):
        async with self.tagsPool.acquire() as sql:
            print("[TAGS] Setting up tags table...")
            
            # Create table if it doesn't exist
            await sql.execute("CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY, creatorID INTEGER, name TEXT, content TEXT)")
            await sql.commit()
        
        print("[TAGS] Tags table setup complete.")

    # List refresh function
    async def getTagLists(self):
        async with self.tagsPool.acquire() as sql:
            # Get all tags
            tags = await sql.fetchall("SELECT * FROM tags")

            for tag in tags:
                if tag[1] not in self.tags:
                    self.tags[tag[1]] = {}
                
                self.tags[tag[1]][tag[2]] = tag[3]
    
    context = discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True)
    installs = discord.app_commands.AppInstallationType(guild=True, user=True)
    tagsGroup = app_commands.Group(name="tags", description="Create quick responses with tags.", allowed_contexts=context, allowed_installs=installs)
    
    # Tags List command
    @tagsGroup.command(name = "list", description = "View your tags.")
    async def tagsList(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id not in self.tags:
            myTags = []
        else:
            def format_tag_content(content: str) -> str:
                if content.startswith('https://cdn.discordapp.com/'):
                    return '`[Attachment]`'
                return f"`{content[:30]}...`" if len(content) > 30 else f'`{content}`'
            
            myTags = (
                f"{key} ({format_tag_content(self.tags[interaction.user.id][key])})"
                for key in self.tags[interaction.user.id].keys()
            )
        
        if myTags == []:
            embed = discord.Embed(title = "Tags", description = "You don't have any tags.", color = Color.red())
            await interaction.followup.send(embed = embed, ephemeral=True)
        else:
            pages = []
            pageStr = ""
            i = 0

            for tag in myTags:
                i += 1
                
                if pageStr == "":
                    pageStr += f"{i}. {tag}"
                else:
                    pageStr += f"\n{i}. {tag}"

                # If there's 10 items in the current page, we split it into a new page
                if i % 10 == 0:
                    pages.append(pageStr)
                    pageStr = ""

            if pageStr != "":
                pages.append(pageStr)
            
            class Leaderboard(View):
                def __init__(self, pages):
                    super().__init__(timeout = 900)
                    self.page = 0
                    self.pages = pages

                    self.msgID: int

                    for item in self.children:
                        if item.custom_id == "first" or item.custom_id == "prev":
                            item.disabled = True

                # Timeout
                async def on_timeout(self) -> None:
                    try:
                        for item in self.children:
                            item.disabled = True
                        
                        msg = await interaction.channel.fetch_message(self.msgID)
                        await msg.edit(view = self)
                    except Exception:
                        pass
                
                @discord.ui.button(emoji="⏮️", style=ButtonStyle.red, custom_id="first")
                async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.page = 0

                    for item in self.children:
                        item.disabled = False
                        
                        if item.custom_id == "first" or item.custom_id == "prev":
                            item.disabled = True
                    
                    embed = discord.Embed(title = f"Tags", description = self.pages[self.page], color = Color.random())
                    embed.set_footer(text = f"Page {self.page + 1}/{len(self.pages)}", icon_url = interaction.user.display_avatar.url)

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
                    
                    embed = discord.Embed(title = f"Tags", description = self.pages[self.page], color = Color.random())
                    embed.set_footer(text = f"Page {self.page + 1}/{len(self.pages)}", icon_url = interaction.user.display_avatar.url)

                    await interaction.response.edit_message(embed = embed, view = self)

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

                    embed = discord.Embed(title = f"Tags", description = self.pages[self.page], color = Color.red())
                    embed.set_footer(text = f"Page {self.page + 1}/{len(self.pages)}", icon_url = interaction.user.display_avatar.url)

                    await interaction.response.edit_message(embed = embed, view = self)
                
                @discord.ui.button(emoji="⏭️", style=ButtonStyle.green, custom_id="last")
                async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.page = len(self.pages) - 1

                    for item in self.children:
                        item.disabled = False

                        if item.custom_id == "next" or item.custom_id == "last":
                            item.disabled = True
                    
                    embed = discord.Embed(title = f"Tags", description = self.pages[self.page], color = Color.random())
                    embed.set_footer(text = f"Page {self.page + 1}/{len(self.pages)}", icon_url = interaction.user.display_avatar.url)

                    await interaction.response.edit_message(embed = embed, view = self)

            embed = discord.Embed(title = f"Tags", description=pages[0], color = Color.random())
            embed.set_footer(text = f"Page 1/{len(pages)}", icon_url = interaction.user.display_avatar.url)
            
            if len(pages) == 1:
                await interaction.followup.send(embed = embed, ephemeral=True)
            else:
                webhook = await interaction.followup.send(embed = embed, view = Leaderboard(pages), ephemeral=True, wait=True)

                Leaderboard.msgID = webhook.id
    
    async def tagAutocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        if interaction.user.id not in self.tags or self.tags[interaction.user.id] == []:
            return []
        else:
            if current == "":
                # Sort by name alphabetically, show first 25
                sorted = list(self.tags[interaction.user.id].keys())[:25]

                return [
                    app_commands.Choice(name=value, value=value)
                    for value in sorted
                ]
            else:
                matches = process.extract(current.lower(), list(self.tags[interaction.user.id].keys()), limit=10)
                
                return [
                    app_commands.Choice(name=match[0], value=match[0])
                    for match in matches if match[1] >= 60
                ]
    
    # Tags Use command
    @tagsGroup.command(name = "use", description = "Use a tag.")
    @app_commands.autocomplete(tag=tagAutocomplete)
    async def tagsList(self, interaction: discord.Interaction, tag: str, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)

        tag = tag.lower()
        
        # Check if tag name is in list
        if interaction.user.id in self.tags and tag not in list(self.tags[interaction.user.id].keys()):
            embed = discord.Embed(title = "Error", description = "That tag doesn't exist.", color = Color.red())
            await interaction.followup.send(embed = embed, ephemeral=ephemeral)
        else:
            await interaction.followup.send(self.tags[interaction.user.id][tag], ephemeral=ephemeral)

    # Tags Create command
    @tagsGroup.command(name = "create", description = "Create a new tag.")
    @app_commands.describe(name = "The name of the tag. Max 100 characters.")
    @app_commands.describe(content = "The content of the tag. Overridden by attachment if you add one.")
    @app_commands.describe(attachment = "Optional: quickly add an attachment to the tag. Overrides content.")
    async def tagsCreate(self, interaction: discord.Interaction, name: str, content: str = None, attachment: discord.Attachment = None):
        await interaction.response.defer(ephemeral=True)

        name = name.lower()
        
        if len(name) > 100:
            embed = discord.Embed(title = "Error", description = "Tag name is too long.", color = Color.red())
            await interaction.followup.send(embed = embed, ephemeral=True)
        elif interaction.user.id in self.tags and name in list(self.tags[interaction.user.id].keys()):
            embed = discord.Embed(title = "Error", description = "That tag already exists.", color = Color.red())
            await interaction.followup.send(embed = embed, ephemeral=True)
        else:
            if content is None and attachment is None:
                embed = discord.Embed(title = "Error", description = "You must provide content or an attachment.", color = Color.red())
                await interaction.followup.send(embed = embed, ephemeral=True)
            else:
                if attachment is not None:
                    async with self.tagsPool.acquire() as sql:
                        await sql.execute("INSERT INTO tags (creatorID, name, content) VALUES (?, ?, ?)", (interaction.user.id, name, attachment.url))
                    
                    if interaction.user.id not in self.tags:
                        self.tags[interaction.user.id] = {}
                    
                    self.tags[interaction.user.id][name] = attachment.url
                else:
                    async with self.tagsPool.acquire() as sql:
                        await sql.execute("INSERT INTO tags (creatorID, name, content) VALUES (?, ?, ?)", (interaction.user.id, name, content))
                    
                    if interaction.user.id not in self.tags:
                        self.tags[interaction.user.id] = {}
                    
                    self.tags[interaction.user.id][name] = content
                
                embed = discord.Embed(title = "Success", description = "Tag created.", color = Color.green())
                await interaction.followup.send(embed = embed, ephemeral=True)
    
    # Tags Delete command
    @tagsGroup.command(name = "delete", description = "Delete a tag.")
    @app_commands.describe(tag = "The tag to delete.")
    @app_commands.autocomplete(tag=tagAutocomplete)
    async def tagsDelete(self, interaction: discord.Interaction, tag: str):
        await interaction.response.defer(ephemeral=True)

        tag = tag.lower()
        
        if interaction.user.id in self.tags and tag not in list(self.tags[interaction.user.id].keys()):
            embed = discord.Embed(title = "Error", description = "That tag doesn't exist.", color = Color.red())
            await interaction.followup.send(embed = embed, ephemeral=True)
        else:
            async with self.tagsPool.acquire() as sql:
                await sql.execute("DELETE FROM tags WHERE creatorID = ? AND name = ?", (interaction.user.id, tag,))
            
            del self.tags[interaction.user.id][tag]
            
            embed = discord.Embed(title = "Success", description = "Tag deleted.", color = Color.green())
            await interaction.followup.send(embed = embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Tags(bot))

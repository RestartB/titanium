import asqlite
import discord
from discord import ButtonStyle, Color, app_commands
from discord.ext import commands
from discord.ui import View
from thefuzz import process


# Tag Create Form
class TagCreateModal(discord.ui.Modal, title="Create Tag"):
    def __init__(self):
        super().__init__(timeout=10)

    name = discord.ui.TextInput(
        label="Name", placeholder="The name of your new tag.", style=discord.TextStyle.short, required=True, max_length=100
    )
    content = discord.ui.TextInput(
        label="Content",
        placeholder="If you have added an attachment, leave this blank.",
        style=discord.TextStyle.paragraph,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        self.stop()
        return

# Tag Edit Form
class TagEditModal(discord.ui.Modal, title="Edit Selected Tag"):
    def __init__(self):
        super().__init__(timeout=10)

    name = discord.ui.TextInput(
        label="New Name", placeholder="If you do not want to set a new name, leave this blank.", style=discord.TextStyle.short, required=False, max_length=100
    )
    content = discord.ui.TextInput(
        label="Content",
        placeholder="If you have added an attachment, leave this blank.",
        style=discord.TextStyle.paragraph,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        self.stop()
        return

class Tags(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tags_pool: asqlite.Pool = bot.tags_pool
        self.tags: dict = {}

        self.bot.loop.create_task(self.setup())
        self.bot.loop.create_task(self.get_tag_lists())

    # Setup function
    async def setup(self):
        async with self.tags_pool.acquire() as sql:
            # Create table if it doesn't exist
            await sql.execute(
                "CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY, creatorID INTEGER, name TEXT, content TEXT)"
            )
            await sql.commit()

    # List refresh function
    async def get_tag_lists(self):
        async with self.tags_pool.acquire() as sql:
            # Get all tags
            tags = await sql.fetchall("SELECT * FROM tags")

            for tag in tags:
                if tag[1] not in self.tags:
                    self.tags[tag[1]] = {}

                self.tags[tag[1]][tag[2]] = tag[3]

    context = discord.app_commands.AppCommandContext(
        guild=True, dm_channel=True, private_channel=True
    )
    installs = discord.app_commands.AppInstallationType(guild=True, user=True)
    tagsGroup = app_commands.Group(
        name="tags",
        description="Create quick responses with tags.",
        allowed_contexts=context,
        allowed_installs=installs,
    )

    # Tags List command
    @tagsGroup.command(name="list", description="View your tags.")
    async def tags_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id not in self.tags:
            my_tags = []
        else:

            def format_tag_content(content: str) -> str:
                if content.startswith("https://cdn.discordapp.com/"):
                    return "`[Attachment]`"
                return f"`{content[:30]}...`" if len(content) > 30 else f"`{content}`"

            my_tags = (
                f"{key} ({format_tag_content(self.tags[interaction.user.id][key])})"
                for key in self.tags[interaction.user.id].keys()
            )

        if my_tags == []:
            embed = discord.Embed(
                title="Tags", description="You don't have any tags.", color=Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            pages = []
            page_str = ""
            i = 0

            for tag in my_tags:
                i += 1

                if page_str == "":
                    page_str += f"{i}. {tag}"
                else:
                    page_str += f"\n{i}. {tag}"

                # If there's 10 items in the current page, we split it into a new page
                if i % 10 == 0:
                    pages.append(page_str)
                    page_str = ""

            if page_str != "":
                pages.append(page_str)

            class Leaderboard(View):
                def __init__(self, pages):
                    super().__init__(timeout=900)
                    self.page = 0
                    self.pages = pages

                    self.msg_id: int

                    for item in self.children:
                        if item.custom_id == "first" or item.custom_id == "prev":
                            item.disabled = True

                # Timeout
                async def on_timeout(self) -> None:
                    try:
                        for item in self.children:
                            item.disabled = True

                        msg = await interaction.channel.fetch_message(self.msg_id)
                        await msg.edit(view=self)
                    except Exception:
                        pass

                @discord.ui.button(emoji="⏮️", style=ButtonStyle.red, custom_id="first")
                async def first_button(
                    self, interaction: discord.Interaction, button: discord.ui.Button
                ):
                    self.page = 0

                    for item in self.children:
                        item.disabled = False

                        if item.custom_id == "first" or item.custom_id == "prev":
                            item.disabled = True

                    embed = discord.Embed(
                        title="Tags",
                        description=self.pages[self.page],
                        color=Color.random(),
                    )
                    embed.set_footer(
                        text=f"Page {self.page + 1}/{len(self.pages)}",
                        icon_url=interaction.user.display_avatar.url,
                    )

                    await interaction.response.edit_message(embed=embed, view=self)

                @discord.ui.button(emoji="⏪", style=ButtonStyle.gray, custom_id="prev")
                async def prev_button(
                    self, interaction: discord.Interaction, button: discord.ui.Button
                ):
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

                    embed = discord.Embed(
                        title="Tags",
                        description=self.pages[self.page],
                        color=Color.random(),
                    )
                    embed.set_footer(
                        text=f"Page {self.page + 1}/{len(self.pages)}",
                        icon_url=interaction.user.display_avatar.url,
                    )

                    await interaction.response.edit_message(embed=embed, view=self)

                @discord.ui.button(emoji="⏩", style=ButtonStyle.gray, custom_id="next")
                async def next_button(
                    self, interaction: discord.Interaction, button: discord.ui.Button
                ):
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

                    embed = discord.Embed(
                        title="Tags",
                        description=self.pages[self.page],
                        color=Color.red(),
                    )
                    embed.set_footer(
                        text=f"Page {self.page + 1}/{len(self.pages)}",
                        icon_url=interaction.user.display_avatar.url,
                    )

                    await interaction.response.edit_message(embed=embed, view=self)

                @discord.ui.button(emoji="⏭️", style=ButtonStyle.green, custom_id="last")
                async def last_button(
                    self, interaction: discord.Interaction, button: discord.ui.Button
                ):
                    self.page = len(self.pages) - 1

                    for item in self.children:
                        item.disabled = False

                        if item.custom_id == "next" or item.custom_id == "last":
                            item.disabled = True

                    embed = discord.Embed(
                        title="Tags",
                        description=self.pages[self.page],
                        color=Color.random(),
                    )
                    embed.set_footer(
                        text=f"Page {self.page + 1}/{len(self.pages)}",
                        icon_url=interaction.user.display_avatar.url,
                    )

                    await interaction.response.edit_message(embed=embed, view=self)

            embed = discord.Embed(
                title="Tags", description=pages[0], color=Color.random()
            )
            embed.set_footer(
                text=f"Page 1/{len(pages)}",
                icon_url=interaction.user.display_avatar.url,
            )

            if len(pages) == 1:
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                webhook = await interaction.followup.send(
                    embed=embed, view=Leaderboard(pages), ephemeral=True, wait=True
                )

                Leaderboard.msg_id = webhook.id

    async def tag_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if interaction.user.id not in self.tags or self.tags[interaction.user.id] == []:
            return []
        else:
            if current == "":
                # Sort by name alphabetically, show first 25
                sorted = list(self.tags[interaction.user.id].keys())[:25]

                return [
                    app_commands.Choice(name=value, value=value) for value in sorted
                ]
            else:
                matches = process.extract(
                    current.lower(),
                    list(self.tags[interaction.user.id].keys()),
                    limit=10,
                )

                return [
                    app_commands.Choice(name=match[0], value=match[0])
                    for match in matches
                    if match[1] >= 60
                ]

    # Tags Use command
    @tagsGroup.command(name="use", description="Use a tag.")
    @app_commands.autocomplete(tag=tag_autocomplete)
    async def tags_use(
        self, interaction: discord.Interaction, tag: str, ephemeral: bool = False
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        tag = tag.lower()

        # Check if tag name is in list
        if interaction.user.id in self.tags and tag not in list(
            self.tags[interaction.user.id].keys()
        ):
            embed = discord.Embed(
                title="Error", description="That tag doesn't exist.", color=Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        else:
            await interaction.followup.send(
                self.tags[interaction.user.id][tag], ephemeral=ephemeral
            )

    # Tags Create command
    @tagsGroup.command(name="create", description="Create a new tag.")
    @app_commands.describe(
        attachment="Optional: quickly add an attachment to the tag. Overrides content."
    )
    async def tags_create(
        self,
        interaction: discord.Interaction,
        attachment: discord.Attachment = None,
    ):
        tagModal = TagCreateModal()
        await interaction.response.send_modal(tagModal)
        await tagModal.wait()

        name = tagModal.name.value.lower()

        if name == "":
            return
        else:
            if interaction.user.id in self.tags and name in list(
                self.tags[interaction.user.id].keys()
            ):
                embed = discord.Embed(
                    title="Error", description="That tag already exists.", color=Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                if tagModal.content.value == "" and attachment is None:
                    embed = discord.Embed(
                        title="Error",
                        description="You must provide content or an attachment.",
                        color=Color.red(),
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    if attachment is not None:
                        async with self.tags_pool.acquire() as sql:
                            await sql.execute(
                                "INSERT INTO tags (creatorID, name, content) VALUES (?, ?, ?)",
                                (interaction.user.id, name, attachment.url),
                            )

                        if interaction.user.id not in self.tags:
                            self.tags[interaction.user.id] = {}

                        self.tags[interaction.user.id][name] = attachment.url
                    else:
                        async with self.tags_pool.acquire() as sql:
                            await sql.execute(
                                "INSERT INTO tags (creatorID, name, content) VALUES (?, ?, ?)",
                                (interaction.user.id, name, tagModal.content.value),
                            )

                        if interaction.user.id not in self.tags:
                            self.tags[interaction.user.id] = {}

                        self.tags[interaction.user.id][name] = tagModal.content.value

                    embed = discord.Embed(
                        title="Success", description="Tag created.", color=Color.green()
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)

    # Tags Edit command
    @tagsGroup.command(name="edit", description="Edit a tag.")
    @app_commands.describe(tag="The tag to edit.")
    @app_commands.describe(
        attachment="Optional: quickly add an attachment to the tag. Overrides content."
    )
    @app_commands.autocomplete(tag=tag_autocomplete)
    async def tags_edit(
        self,
        interaction: discord.Interaction,
        tag: str,
        attachment: discord.Attachment = None,
    ):
        tag = tag.lower()

        if interaction.user.id not in self.tags or tag not in list(
            self.tags[interaction.user.id].keys()
        ):
            embed = discord.Embed(
                title="Error", description="That tag doesn't exist.", color=Color.red()
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        else:
            tagModal = TagCreateModal()
            await interaction.response.send_modal(tagModal)
            await tagModal.wait()

            name = tagModal.name.value.lower()
            
            if name == "" and tagModal.content.value == "" and attachment is None:
                embed = discord.Embed(
                    title="Error",
                    description="You must provide a new name, new content or a new attachment.",
                    color=Color.red(),
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            else:
                # Name Checks
                if name != "":
                    if len(name) > 100:
                        embed = discord.Embed(
                            title="Error",
                            description="New tag name is too long.",
                            color=Color.red(),
                        )
                        
                        await interaction.followup.send(embed=embed, ephemeral=True)
                        return
                    else:
                        if name in list(self.tags[interaction.user.id].keys()):
                            embed = discord.Embed(
                                title="Error",
                                description="New tag name is already in use.",
                                color=Color.red(),
                            )
                            
                            await interaction.followup.send(embed=embed, ephemeral=True)
                            return
                
                # Update Attachment / Content
                if attachment is not None: # Attachment
                    async with self.tags_pool.acquire() as sql:
                        await sql.execute(
                            "UPDATE tags SET content = ? WHERE creatorID = ? AND name = ?",
                            (
                                attachment.url,
                                interaction.user.id,
                                tag,
                            ),
                        )

                    if interaction.user.id not in self.tags:
                        self.tags[interaction.user.id] = {}

                    self.tags[interaction.user.id][tag] = attachment.url
                else: # Content
                    async with self.tags_pool.acquire() as sql:
                        await sql.execute(
                            "UPDATE tags SET content = ? WHERE creatorID = ? AND name = ?",
                            (
                                tagModal.content.value,
                                interaction.user.id,
                                tag,
                            ),
                        )

                    if interaction.user.id not in self.tags:
                        self.tags[interaction.user.id] = {}

                    self.tags[interaction.user.id][tag] = tagModal.content.value

                # Update Name
                if name != "":
                    async with self.tags_pool.acquire() as sql:
                        await sql.execute(
                            "UPDATE tags SET name = ? WHERE creatorID = ? AND name = ?",
                            (
                                name,
                                interaction.user.id,
                                tag,
                            ),
                        )

                    self.tags[interaction.user.id][name] = self.tags[
                        interaction.user.id
                    ][tag]
                    del self.tags[interaction.user.id][tag]
                
                embed = discord.Embed(
                    title="Success", description="Tag updated.", color=Color.green()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

    # Tags Delete command
    @tagsGroup.command(name="delete", description="Delete a tag.")
    @app_commands.describe(tag="The tag to delete.")
    @app_commands.autocomplete(tag=tag_autocomplete)
    async def tags_delete(self, interaction: discord.Interaction, tag: str):
        await interaction.response.defer(ephemeral=True)

        tag = tag.lower()

        if interaction.user.id in self.tags and tag not in list(
            self.tags[interaction.user.id].keys()
        ):
            embed = discord.Embed(
                title="Error", description="That tag doesn't exist.", color=Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            async with self.tags_pool.acquire() as sql:
                await sql.execute(
                    "DELETE FROM tags WHERE creatorID = ? AND name = ?",
                    (
                        interaction.user.id,
                        tag,
                    ),
                )

            del self.tags[interaction.user.id][tag]

            embed = discord.Embed(
                title="Success", description="Tag deleted.", color=Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Tags(bot))

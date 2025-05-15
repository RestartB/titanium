import asqlite
import discord
from discord import ButtonStyle, Color, app_commands
from discord.ext import commands
from discord.ui import View
from thefuzz import process


# Tag Create Form
class TagCreateModal(discord.ui.Modal, title="Create Tag"):
    def __init__(self):
        super().__init__(timeout=600)

    name = discord.ui.TextInput(
        label="Name",
        placeholder="The name of the new tag.",
        style=discord.TextStyle.short,
        required=True,
        max_length=100,
    )
    content = discord.ui.TextInput(
        label="Content",
        placeholder="If you have added an attachment, leave this blank.",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=2000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        self.stop()
        return


# Tag Edit Form
class TagEditModal(discord.ui.Modal, title="Edit Selected Tag"):
    def __init__(self):
        super().__init__(timeout=600)

    name = discord.ui.TextInput(
        label="New Name",
        placeholder="If you do not want to set a new name, leave this blank.",
        style=discord.TextStyle.short,
        required=False,
        max_length=100,
    )
    content = discord.ui.TextInput(
        label="Content",
        placeholder="If you have added an attachment, leave this blank.",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=2000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        self.stop()
        return


class ServerTags(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tags_pool: asqlite.Pool = bot.tags_pool
        self.tags: dict = {}

        self.bot.loop.create_task(self.get_tag_lists())

    # List refresh function
    async def get_tag_lists(self):
        async with self.tags_pool.acquire() as sql:
            # Get all tags
            tags = await sql.fetchall("SELECT * FROM tags")

            for tag in tags:
                if tag[1] not in self.tags:
                    self.tags[tag[1]] = {}

                self.tags[tag[1]][tag[2]] = tag[3]

    async def server_tag_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if not interaction.is_guild_integration():
            return [
                app_commands.Choice(
                    name="Titanium is not in this server, so you can't use server tags here. Please use user tags instead.",
                    value="",
                ),
            ]
        else:
            try:
                if self.tags[interaction.guild_id] == []:
                    return []
                else:
                    if current == "":
                        # Sort by name alphabetically, show first 25
                        sorted = list(self.tags[interaction.guild_id].keys())[:25]

                        return [
                            app_commands.Choice(name=value, value=value)
                            for value in sorted
                        ]
                    else:
                        matches = process.extract(
                            current.lower(),
                            list(self.tags[interaction.guild_id].keys()),
                            limit=10,
                        )

                        return [
                            app_commands.Choice(name=match[0], value=match[0])
                            for match in matches
                            if match[1] >= 60
                        ]
            except KeyError:
                return []

    # Server Tags Use command
    @app_commands.command(name="server-tag", description="Use a server tag.")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.checks.cooldown(1, 5)
    @app_commands.autocomplete(tag=server_tag_autocomplete)
    async def server_tags_use(
        self, interaction: discord.Interaction, tag: str, ephemeral: bool = False
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        tag = tag.lower()

        if not interaction.is_guild_integration():
            embed = discord.Embed(
                title="Error",
                description="Titanium is not in this server, so you can't use server tags here. Please use user tags instead.",
                color=Color.red(),
            )

            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        try:
            # Check if tag name is in list
            if tag not in list(self.tags[interaction.guild_id].keys()):
                embed = discord.Embed(
                    title="Error",
                    description="That tag doesn't exist.",
                    color=Color.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            else:
                await interaction.followup.send(
                    self.tags[interaction.guild_id][tag],
                    ephemeral=ephemeral,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
        except KeyError:
            embed = discord.Embed(
                title="Error",
                description="That tag doesn't exist.",
                color=Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    context = discord.app_commands.AppCommandContext(
        guild=True, dm_channel=False, private_channel=False
    )
    installs = discord.app_commands.AppInstallationType(guild=True, user=False)
    permissions = discord.Permissions(manage_guild=True)
    tagsGroup = app_commands.Group(
        name="server-tags",
        description="Server Tags - manage server wide tags.",
        allowed_contexts=context,
        allowed_installs=installs,
        default_permissions=permissions,
    )

    # Tags List command
    @tagsGroup.command(name="list", description="View the server's tags.")
    @app_commands.checks.cooldown(1, 5)
    async def tags_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if interaction.guild_id not in self.tags:
            my_tags = []
        else:

            def format_tag_content(content: str) -> str:
                if content.startswith("https://cdn.discordapp.com/"):
                    return "`[Attachment]`"
                return f"`{content[:30]}...`" if len(content) > 30 else f"`{content}`"

            my_tags = (
                f"{key} ({format_tag_content(self.tags[interaction.guild_id][key])})"
                for key in self.tags[interaction.guild_id].keys()
            )

        if my_tags == []:
            embed = discord.Embed(
                title="Tags",
                description="The server don't have any tags.",
                color=Color.red(),
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

    # Tags Create command
    @tagsGroup.command(name="create", description="Create a new tag.")
    @app_commands.checks.cooldown(1, 5)
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
            if interaction.guild_id in self.tags and name in list(
                self.tags[interaction.guild_id].keys()
            ):
                embed = discord.Embed(
                    title="Error",
                    description="That tag already exists.",
                    color=Color.red(),
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
                    if len(tagModal.content.value) > 2000:
                        embed = discord.Embed(
                            title="Error",
                            description="Tag content is too long.",
                            color=Color.red(),
                        )
                        await interaction.followup.send(embed=embed, ephemeral=True)
                    else:
                        if attachment is not None:
                            async with self.tags_pool.acquire() as sql:
                                await sql.execute(
                                    "INSERT INTO tags (creatorID, name, content) VALUES (?, ?, ?)",
                                    (interaction.guild_id, name, attachment.url),
                                )

                            if interaction.guild_id not in self.tags:
                                self.tags[interaction.guild_id] = {}

                            self.tags[interaction.guild_id][name] = attachment.url
                        else:
                            async with self.tags_pool.acquire() as sql:
                                await sql.execute(
                                    "INSERT INTO tags (creatorID, name, content) VALUES (?, ?, ?)",
                                    (interaction.guild_id, name, tagModal.content.value),
                                )

                            if interaction.guild_id not in self.tags:
                                self.tags[interaction.guild_id] = {}

                            self.tags[interaction.guild_id][name] = tagModal.content.value

                        embed = discord.Embed(
                            title="Success", description="Tag created.", color=Color.green()
                        )
                        await interaction.followup.send(embed=embed, ephemeral=True)

    # Tags Edit command
    @tagsGroup.command(name="edit", description="Edit a tag.")
    @app_commands.checks.cooldown(1, 5)
    @app_commands.describe(tag="The tag to edit.")
    @app_commands.describe(
        attachment="Optional: quickly add an attachment to the tag. Overrides content."
    )
    @app_commands.autocomplete(tag=server_tag_autocomplete)
    async def tags_edit(
        self,
        interaction: discord.Interaction,
        tag: str,
        attachment: discord.Attachment = None,
    ):
        tag = tag.lower()

        if interaction.guild_id not in self.tags or tag not in list(
            self.tags[interaction.guild_id].keys()
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
                        if name in list(self.tags[interaction.guild_id].keys()):
                            embed = discord.Embed(
                                title="Error",
                                description="New tag name is already in use.",
                                color=Color.red(),
                            )

                            await interaction.followup.send(embed=embed, ephemeral=True)
                            return

                if len(tagModal.content.value) > 2000:
                    embed = discord.Embed(
                        title="Error",
                        description="Tag content is too long.",
                        color=Color.red(),
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
                
                # Update Attachment / Content
                if attachment is not None:  # Attachment
                    async with self.tags_pool.acquire() as sql:
                        await sql.execute(
                            "UPDATE tags SET content = ? WHERE creatorID = ? AND name = ?",
                            (
                                attachment.url,
                                interaction.guild_id,
                                tag,
                            ),
                        )

                    if interaction.guild_id not in self.tags:
                        self.tags[interaction.guild_id] = {}

                    self.tags[interaction.guild_id][tag] = attachment.url
                else:  # Content
                    async with self.tags_pool.acquire() as sql:
                        await sql.execute(
                            "UPDATE tags SET content = ? WHERE creatorID = ? AND name = ?",
                            (
                                tagModal.content.value,
                                interaction.guild_id,
                                tag,
                            ),
                        )

                    if interaction.guild_id not in self.tags:
                        self.tags[interaction.guild_id] = {}

                    self.tags[interaction.guild_id][tag] = tagModal.content.value

                # Update Name
                if name != "":
                    async with self.tags_pool.acquire() as sql:
                        await sql.execute(
                            "UPDATE tags SET name = ? WHERE creatorID = ? AND name = ?",
                            (
                                name,
                                interaction.guild_id,
                                tag,
                            ),
                        )

                    self.tags[interaction.guild_id][name] = self.tags[
                        interaction.guild_id
                    ][tag]
                    del self.tags[interaction.guild_id][tag]

                embed = discord.Embed(
                    title="Success", description="Tag updated.", color=Color.green()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

    # Tags Delete command
    @tagsGroup.command(name="delete", description="Delete a tag.")
    @app_commands.checks.cooldown(1, 5)
    @app_commands.describe(tag="The tag to delete.")
    @app_commands.autocomplete(tag=server_tag_autocomplete)
    async def tags_delete(self, interaction: discord.Interaction, tag: str):
        await interaction.response.defer(ephemeral=True)

        tag = tag.lower()

        if interaction.guild_id in self.tags and tag not in list(
            self.tags[interaction.guild_id].keys()
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
                        interaction.guild_id,
                        tag,
                    ),
                )

            del self.tags[interaction.guild_id][tag]

            embed = discord.Embed(
                title="Success", description="Tag deleted.", color=Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(ServerTags(bot))

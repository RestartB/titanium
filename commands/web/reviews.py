import aiohttp
import discord
from discord import ButtonStyle, Color, app_commands
from discord.ext import commands
from discord.ui import View


class Reviews(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    context = discord.app_commands.AppCommandContext(
        guild=True, dm_channel=True, private_channel=True
    )
    installs = discord.app_commands.AppInstallationType(guild=True, user=True)
    reviewGroup = app_commands.Group(
        name="reviews",
        description="Review a user on ReviewDB.",
        allowed_contexts=context,
        allowed_installs=installs,
    )

    # Review view command
    @reviewGroup.command(name="user", description="See a user's reviews on ReviewDB.")
    @app_commands.checks.cooldown(1, 10)
    @app_commands.describe(user="The user you want to see the reviews of.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    async def user_reviews(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        ephemeral: bool = False,
    ):
        try:
            await interaction.response.defer(ephemeral=ephemeral)

            # Create URL
            request_url = (
                f"https://manti.vendicated.dev/api/reviewdb/users/{user.id}/reviews"
            )

            # Send request to ReviewDB
            async with aiohttp.ClientSession() as session:
                async with session.get(request_url) as request:
                    reviews = await request.json()

            review_count = reviews["review_count"]
            reviews = reviews["reviews"]

            i = 0
            pretty_review = 0
            page_list = []
            pages = []

            # Create pages
            for review in reviews:
                i += 1

                if page_list == []:
                    page_list.append([review, pretty_review])
                else:
                    page_list.append([review, pretty_review])

                pretty_review += 1

                # If there's 4 items in the current page, we split it into a new page
                if i % 4 == 0:
                    pages.append(page_list)
                    page_list = []

            # Add a page if remaining contents isn't empty
            if page_list != []:
                pages.append(page_list)

            class PageView(View):
                def __init__(self, pages):
                    super().__init__(timeout=900)
                    self.page = 0
                    self.pages = pages

                    self.locked = False

                    self.user_id: int
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

                # Page lock
                async def interaction_check(self, interaction: discord.Interaction):
                    if interaction.user.id != self.user_id:
                        if self.locked:
                            embed = discord.Embed(
                                title="Error",
                                description="This command is locked. Only the owner can control it.",
                                color=Color.red(),
                            )
                            await interaction.response.send_message(
                                embed=embed, ephemeral=True
                            )
                        else:
                            return True
                    else:
                        return True

                # First page
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
                        title="ReviewDB User Reviews",
                        description=f"There are **{review_count} reviews** for this user.",
                        color=Color.random(),
                    )
                    embed.set_author(
                        name=user.name,
                        url=f"https://discord.com/users/{user.id}",
                        icon_url=user.display_avatar.url,
                    )

                    i = 1
                    for item in self.pages[self.page]:
                        if item[0]["id"] == 0:
                            review_content = item[0]["comment"]

                            embed.add_field(
                                name="System", value=review_content, inline=False
                            )
                        else:
                            review_timestamp = item[0]["timestamp"]

                            # Handle strings being too long
                            if len(item[0]["comment"]) > 1024:
                                review_content = item[0]["comment"][:1021] + "..."
                            else:
                                review_content = item[0]["comment"]

                            embed.add_field(
                                name=f"{item[1]}. @{item[0]['sender']['username']} - <t:{review_timestamp}:d>",
                                value=review_content,
                                inline=False,
                            )

                            i += 1

                    embed.set_footer(
                        text=f"Controlling: @{interaction.user.name} - Page {self.page + 1}/{len(self.pages)}",
                        icon_url=interaction.user.display_avatar.url,
                    )
                    await interaction.response.edit_message(embed=embed, view=self)

                # Previous page
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
                        title="ReviewDB User Reviews",
                        description=f"There are **{review_count} reviews** for this user.",
                        color=Color.random(),
                    )
                    embed.set_author(
                        name=user.name,
                        url=f"https://discord.com/users/{user.id}",
                        icon_url=user.display_avatar.url,
                    )

                    i = 1
                    for item in self.pages[self.page]:
                        if item[0]["id"] == 0:
                            review_content = item[0]["comment"]

                            embed.add_field(
                                name="System", value=review_content, inline=False
                            )
                        else:
                            review_timestamp = item[0]["timestamp"]

                            # Handle strings being too long
                            if len(item[0]["comment"]) > 1024:
                                review_content = item[0]["comment"][:1021] + "..."
                            else:
                                review_content = item[0]["comment"]

                            embed.add_field(
                                name=f"{item[1]}. @{item[0]['sender']['username']} - <t:{review_timestamp}:d>",
                                value=review_content,
                                inline=False,
                            )

                            i += 1

                    embed.set_footer(
                        text=f"Controlling: @{interaction.user.name} - Page {self.page + 1}/{len(self.pages)}",
                        icon_url=interaction.user.display_avatar.url,
                    )
                    await interaction.response.edit_message(embed=embed, view=self)

                # Lock / unlock toggle
                @discord.ui.button(
                    emoji="🔓", style=ButtonStyle.green, custom_id="lock"
                )
                async def lock_button(
                    self, interaction: discord.Interaction, button: discord.ui.Button
                ):
                    if interaction.user.id == self.user_id:
                        self.locked = not self.locked

                        if self.locked:
                            button.emoji = "🔒"
                            button.style = ButtonStyle.red
                        else:
                            button.emoji = "🔓"
                            button.style = ButtonStyle.green

                        await interaction.response.edit_message(view=self)
                    else:
                        embed = discord.Embed(
                            title="Error",
                            description="Only the command runner can toggle the page controls lock.",
                            color=Color.red(),
                        )
                        await interaction.response.send_message(
                            embed=embed, ephemeral=True
                        )

                # Next page
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
                        title="ReviewDB User Reviews",
                        description=f"There are **{review_count} reviews** for this user.",
                        color=Color.random(),
                    )
                    embed.set_author(
                        name=user.name,
                        url=f"https://discord.com/users/{user.id}",
                        icon_url=user.display_avatar.url,
                    )

                    i = 1
                    for item in self.pages[self.page]:
                        if item[0]["id"] == 0:
                            review_content = item[0]["comment"]

                            embed.add_field(
                                name="System", value=review_content, inline=False
                            )
                        else:
                            review_timestamp = item[0]["timestamp"]

                            # Handle strings being too long
                            if len(item[0]["comment"]) > 1024:
                                review_content = item[0]["comment"][:1021] + "..."
                            else:
                                review_content = item[0]["comment"]

                            embed.add_field(
                                name=f"{item[1]}. @{item[0]['sender']['username']} - <t:{review_timestamp}:d>",
                                value=review_content,
                                inline=False,
                            )

                            i += 1

                    embed.set_footer(
                        text=f"Controlling: @{interaction.user.name} - Page {self.page + 1}/{len(self.pages)}",
                        icon_url=interaction.user.display_avatar.url,
                    )
                    await interaction.response.edit_message(embed=embed, view=self)

                # Last page button
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
                        title="ReviewDB User Reviews",
                        description=f"There are **{review_count} reviews** for this user.",
                        color=Color.random(),
                    )
                    embed.set_author(
                        name=user.name,
                        url=f"https://discord.com/users/{user.id}",
                        icon_url=user.display_avatar.url,
                    )

                    i = 1
                    for item in self.pages[self.page]:
                        if item[0]["id"] == 0:
                            review_content = item[0]["comment"]

                            embed.add_field(
                                name="System", value=review_content, inline=False
                            )
                        else:
                            review_timestamp = item[0]["timestamp"]

                            # Handle strings being too long
                            if len(item[0]["comment"]) > 1024:
                                review_content = item[0]["comment"][:1021] + "..."
                            else:
                                review_content = item[0]["comment"]

                            embed.add_field(
                                name=f"{item[1]}. @{item[0]['sender']['username']} - <t:{review_timestamp}:d>",
                                value=review_content,
                                inline=False,
                            )

                            i += 1

                    embed.set_footer(
                        text=f"Controlling: @{interaction.user.name} - Page {self.page + 1}/{len(self.pages)}",
                        icon_url=interaction.user.display_avatar.url,
                    )
                    await interaction.response.edit_message(embed=embed, view=self)

            embed = discord.Embed(
                title="ReviewDB User Reviews",
                description=f"There are **{review_count} reviews** for this user.",
                color=Color.random(),
            )
            embed.set_author(
                name=user.name,
                url=f"https://discord.com/users/{user.id}",
                icon_url=user.display_avatar.url,
            )

            if not (len(pages) == 0):
                # Reviews exist
                i = 1
                for item in pages[0]:
                    if int(item[0]["id"]) == 0:
                        review_content = item[0]["comment"]

                        embed.add_field(
                            name="System", value=review_content, inline=False
                        )
                    else:
                        review_timestamp = item[0]["timestamp"]

                        # Handle strings being too long
                        if len(item[0]["comment"]) > 1024:
                            review_content = item[0]["comment"][:1021] + "..."
                        else:
                            review_content = item[0]["comment"]

                        embed.add_field(
                            name=f"{item[1]}. @{item[0]['sender']['username']} - <t:{review_timestamp}:d>",
                            value=review_content,
                            inline=False,
                        )

                        i += 1

                embed.set_footer(
                    text=f"Controlling: @{interaction.user.name} - Page 1/{len(pages)}",
                    icon_url=interaction.user.display_avatar.url,
                )

                if len(pages) == 1:
                    await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                else:
                    page_view_instance = PageView(pages)

                    webhook = await interaction.followup.send(
                        embed=embed,
                        view=page_view_instance,
                        ephemeral=ephemeral,
                        wait=True,
                    )

                    page_view_instance.user_id = interaction.user.id
                    page_view_instance.msg_id = webhook.id
            else:
                embed = discord.Embed(
                    title="ReviewDB User Reviews",
                    description="This user has no reviews!",
                    color=Color.red(),
                )
                embed.set_author(
                    name=user.name,
                    url=f"https://discord.com/users/{user.id}",
                    icon_url=user.display_avatar.url,
                )

                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        except discord.errors.HTTPException as e:
            if "automod" in str(e).lower():
                embed = discord.Embed(
                    title="Error",
                    description="Message has been blocked by server AutoMod policies. Server admins may have been notified.",
                    color=Color.red(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            else:
                embed = discord.Embed(
                    title="Error",
                    description="Couldn't send the message. AutoMod may have been triggered.",
                    color=Color.red(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    # Server review view command
    @reviewGroup.command(
        name="server", description="See the current server's reviews on ReviewDB."
    )
    @app_commands.describe(
        server_id="Optional: specify the ID of the server you would like to view. Defaults to the current server."
    )
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    @app_commands.checks.cooldown(1, 10)
    async def server_reviews(
        self,
        interaction: discord.Interaction,
        server_id: str = "",
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        try:
            if interaction.guild is None:
                if server_id == "":
                    embed = discord.Embed(
                        title="Error",
                        description="Please specify a server ID.",
                        color=Color.red(),
                    )
                    embed.set_footer(
                        text=f"@{interaction.user.name}",
                        icon_url=interaction.user.display_avatar.url,
                    )

                    await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                    return
                else:
                    try:
                        server_id = int(server_id)
                        guild = await self.bot.fetch_guild(server_id)
                    except ValueError:
                        embed = discord.Embed(
                            title="Error",
                            description="Invalid server ID.",
                            color=Color.red(),
                        )
                        embed.set_footer(
                            text=f"@{interaction.user.name}",
                            icon_url=interaction.user.display_avatar.url,
                        )

                        await interaction.followup.send(
                            embed=embed, ephemeral=ephemeral
                        )
                        return
                    except discord.errors.NotFound:
                        embed = discord.Embed(
                            title="Error",
                            description="Server not found.",
                            color=Color.red(),
                        )
                        embed.set_footer(
                            text=f"@{interaction.user.name}",
                            icon_url=interaction.user.display_avatar.url,
                        )

                        await interaction.followup.send(
                            embed=embed, ephemeral=ephemeral
                        )
                        return
            else:
                guild = interaction.guild

            request_url = (
                f"https://manti.vendicated.dev/api/reviewdb/users/{guild.id}/reviews"
            )

            # Send request to ReviewDB
            async with aiohttp.ClientSession() as session:
                async with session.get(request_url) as request:
                    reviews = await request.json()

            review_count = reviews["review_count"]
            reviews = reviews["reviews"]

            i = 0
            pretty_review = 0
            page_list = []
            pages = []

            for review in reviews:
                i += 1

                if page_list == []:
                    page_list.append([review, pretty_review])
                else:
                    page_list.append([review, pretty_review])

                pretty_review += 1

                # If there's 4 items in the current page, we split it into a new page
                if i % 4 == 0:
                    pages.append(page_list)
                    page_list = []

            if page_list != []:
                pages.append(page_list)

            class PageView(View):
                def __init__(self, pages):
                    super().__init__(timeout=900)
                    self.page = 0
                    self.pages = pages

                    self.user_id: int
                    self.msg_id: int

                    self.locked = False

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

                async def interaction_check(self, interaction: discord.Interaction):
                    if interaction.user.id != self.user_id:
                        if self.locked:
                            embed = discord.Embed(
                                title="Error",
                                description="This command is locked. Only the owner can control it.",
                                color=Color.red(),
                            )
                            await interaction.response.send_message(
                                embed=embed, ephemeral=True
                            )
                        else:
                            return True
                    else:
                        return True

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
                        title="ReviewDB Server Reviews",
                        description=f"There are **{review_count} reviews** for this server.",
                        color=Color.random(),
                    )
                    embed.set_author(
                        name=guild.name,
                        icon_url=(guild.icon.url if guild.icon is not None else ""),
                    )

                    i = 1
                    for item in self.pages[self.page]:
                        if item[0]["id"] == 0:
                            review_content = item[0]["comment"]

                            embed.add_field(
                                name="System", value=review_content, inline=False
                            )
                        else:
                            review_timestamp = item[0]["timestamp"]

                            # Handle strings being too long
                            if len(item[0]["comment"]) > 1024:
                                review_content = item[0]["comment"][:1021] + "..."
                            else:
                                review_content = item[0]["comment"]

                            embed.add_field(
                                name=f"{item[1]}. @{item[0]['sender']['username']} - <t:{review_timestamp}:d>",
                                value=review_content,
                                inline=False,
                            )

                            i += 1

                    embed.set_footer(
                        text=f"Controlling: @{interaction.user.name} - Page {self.page + 1}/{len(self.pages)}",
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
                        title="ReviewDB Server Reviews",
                        description=f"There are **{review_count} reviews** for this server.",
                        color=Color.random(),
                    )
                    embed.set_author(
                        name=guild.name,
                        icon_url=(guild.icon.url if guild.icon is not None else ""),
                    )

                    i = 1
                    for item in self.pages[self.page]:
                        if item[0]["id"] == 0:
                            review_content = item[0]["comment"]

                            embed.add_field(
                                name="System", value=review_content, inline=False
                            )
                        else:
                            review_timestamp = item[0]["timestamp"]

                            # Handle strings being too long
                            if len(item[0]["comment"]) > 1024:
                                review_content = item[0]["comment"][:1021] + "..."
                            else:
                                review_content = item[0]["comment"]

                            embed.add_field(
                                name=f"{item[1]}. @{item[0]['sender']['username']} - <t:{review_timestamp}:d>",
                                value=review_content,
                                inline=False,
                            )

                            i += 1

                    embed.set_footer(
                        text=f"Controlling: @{interaction.user.name} - Page {self.page + 1}/{len(self.pages)}",
                        icon_url=interaction.user.display_avatar.url,
                    )
                    await interaction.response.edit_message(embed=embed, view=self)

                @discord.ui.button(
                    emoji="🔓", style=ButtonStyle.green, custom_id="lock"
                )
                async def lock_button(
                    self, interaction: discord.Interaction, button: discord.ui.Button
                ):
                    if interaction.user.id == self.user_id:
                        self.locked = not self.locked

                        if self.locked:
                            button.emoji = "🔒"
                            button.style = ButtonStyle.red
                        else:
                            button.emoji = "🔓"
                            button.style = ButtonStyle.green

                        await interaction.response.edit_message(view=self)
                    else:
                        embed = discord.Embed(
                            title="Error",
                            description="Only the command runner can toggle the page controls lock.",
                            color=Color.red(),
                        )
                        await interaction.response.send_message(
                            embed=embed, ephemeral=True
                        )

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
                        title="ReviewDB Server Reviews",
                        description=f"There are **{review_count} reviews** for this server.",
                        color=Color.random(),
                    )
                    embed.set_author(
                        name=guild.name,
                        icon_url=(guild.icon.url if guild.icon is not None else ""),
                    )

                    i = 1
                    for item in self.pages[self.page]:
                        if item[0]["id"] == 0:
                            review_content = item[0]["comment"]

                            embed.add_field(
                                name="System", value=review_content, inline=False
                            )
                        else:
                            review_timestamp = item[0]["timestamp"]

                            # Handle strings being too long
                            if len(item[0]["comment"]) > 1024:
                                review_content = item[0]["comment"][:1021] + "..."
                            else:
                                review_content = item[0]["comment"]

                            embed.add_field(
                                name=f"{item[1]}. @{item[0]['sender']['username']} - <t:{review_timestamp}:d>",
                                value=review_content,
                                inline=False,
                            )

                            i += 1

                    embed.set_footer(
                        text=f"Controlling: @{interaction.user.name} - Page {self.page + 1}/{len(self.pages)}",
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
                        title="ReviewDB Server Reviews",
                        description=f"There are **{review_count} reviews** for this server.",
                        color=Color.random(),
                    )
                    embed.set_author(
                        name=guild.name,
                        icon_url=(guild.icon.url if guild.icon is not None else ""),
                    )

                    i = 1
                    for item in self.pages[self.page]:
                        if item[0]["id"] == 0:
                            review_content = item[0]["comment"]

                            embed.add_field(
                                name="System", value=review_content, inline=False
                            )
                        else:
                            review_timestamp = item[0]["timestamp"]

                            # Handle strings being too long
                            if len(item[0]["comment"]) > 1024:
                                review_content = item[0]["comment"][:1021] + "..."
                            else:
                                review_content = item[0]["comment"]

                            embed.add_field(
                                name=f"{item[1]}. @{item[0]['sender']['username']} - <t:{review_timestamp}:d>",
                                value=review_content,
                                inline=False,
                            )

                            i += 1

                    embed.set_footer(
                        text=f"Controlling: @{interaction.user.name} - Page {self.page + 1}/{len(self.pages)}",
                        icon_url=interaction.user.display_avatar.url,
                    )
                    await interaction.response.edit_message(embed=embed, view=self)

            embed = discord.Embed(
                title="ReviewDB Server Reviews",
                description=f"There are **{review_count} reviews** for this server.",
                color=Color.random(),
            )
            embed.set_author(
                name=guild.name,
                icon_url=(guild.icon.url if guild.icon is not None else ""),
            )

            if not (len(pages) == 0):
                i = 1
                for item in pages[0]:
                    if int(item[0]["id"]) == 0:
                        review_content = item[0]["comment"]

                        embed.add_field(
                            name="System", value=review_content, inline=False
                        )
                    else:
                        review_timestamp = item[0]["timestamp"]

                        # Handle strings being too long
                        if len(item[0]["comment"]) > 1024:
                            review_content = item[0]["comment"][:1021] + "..."
                        else:
                            review_content = item[0]["comment"]

                        embed.add_field(
                            name=f"{item[1]}. @{item[0]['sender']['username']} - <t:{review_timestamp}:d>",
                            value=review_content,
                            inline=False,
                        )

                        i += 1

                embed.set_footer(
                    text=f"Controlling: @{interaction.user.name} - Page 1/{len(pages)}",
                    icon_url=interaction.user.display_avatar.url,
                )

                if len(pages) == 1:
                    await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                else:
                    page_view_instance = PageView(pages)

                    webhook = await interaction.followup.send(
                        embed=embed,
                        view=page_view_instance,
                        ephemeral=ephemeral,
                        wait=True,
                    )

                    page_view_instance.user_id = interaction.user.id
                    page_view_instance.msg_id = webhook.id
            else:
                embed = discord.Embed(
                    title="ReviewDB Server Reviews",
                    description="This server has no reviews!",
                    color=Color.red(),
                )
                embed.set_author(
                    name=guild.name,
                    icon_url=(guild.icon.url if guild.icon is not None else ""),
                )

                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        except discord.errors.HTTPException as e:
            if "automod" in str(e).lower():
                embed = discord.Embed(
                    title="Error",
                    description="Message has been blocked by server AutoMod policies. Server admins may have been notified.",
                    color=Color.red(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            else:
                embed = discord.Embed(
                    title="Error",
                    description="Couldn't send the message. AutoMod may have been triggered.",
                    color=Color.red(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)


async def setup(bot):
    await bot.add_cog(Reviews(bot))

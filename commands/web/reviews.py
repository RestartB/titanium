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

    async def generate_user_review_embed(
        interaction: discord.Interaction,
        user: discord.Member | discord.User,
        page: list,
        current_page: int,
        page_count: int,
        review_count: int,
    ) -> discord.Embed:
        embed = discord.Embed(
            title="ReviewDB User Reviews",
            description=f"There {'are' if review_count > 1 else 'is'} **{review_count} review{'s' if review_count > 1 else ''}** for this user.",
            color=Color.random(),
        )

        embed.set_author(
            name=user.name,
            url=f"https://discord.com/users/{user.id}",
            icon_url=user.display_avatar.url,
        )

        embed.set_footer(
            text=f"Controlling: @{interaction.user.name} • Page {current_page + 1}/{page_count}",
            icon_url=interaction.user.display_avatar.url,
        )

        for review in page:
            i = review[0]
            review = review[1]

            embed.add_field(
                name=f"{i}. @{review['sender']['username']} - <t:{review['timestamp']}:d>",
                value=f"{review['comment'] if len(review['comment']) <= 1024 else review['comment'][:1021] + '...'}",
                inline=False,
            )

        return embed

    async def generate_server_review_embed(
        interaction: discord.Interaction,
        guild: discord.Guild,
        page: list,
        current_page: int,
        page_count: int,
        review_count: int,
    ) -> discord.Embed:
        embed = discord.Embed(
            title="ReviewDB Server Reviews",
            description=f"There {'are' if review_count > 1 else 'is'} **{review_count} review{'s' if review_count > 1 else ''}** for this server.",
            color=Color.random(),
        )

        embed.set_author(
            name=guild.name,
            icon_url=(guild.icon.url if guild.icon is not None else None),
        )

        embed.set_footer(
            text=f"Controlling: @{interaction.user.name} • Page {current_page + 1}/{page_count}",
            icon_url=interaction.user.display_avatar.url,
        )

        for review in page:
            i = review[0]
            review = review[1]

            embed.add_field(
                name=f"{i}. @{review['sender']['username']} - <t:{review['timestamp']}:d>",
                value=f"{review['comment'] if len(review['comment']) <= 1024 else review['comment'][:1021] + '...'}",
                inline=False,
            )

        return embed

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
        await interaction.response.defer(ephemeral=ephemeral)

        review_list = []

        # Send request to ReviewDB
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://manti.vendicated.dev/api/reviewdb/users/{user.id}/reviews?offset=0"
            ) as request:
                review_response = await request.json()

        for review in review_response["reviews"][1:]:
            review_list.append(review)

        while True:
            if not review_response["success"]:
                embed = discord.Embed(
                    title="Error",
                    description="ReviewDB has encountered an error. Titanium will not continue. Please try again later.",
                    color=Color.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)

                return
            else:
                if review_response["hasNextPage"]:
                    # Send request to ReviewDB
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"https://manti.vendicated.dev/api/reviewdb/users/{user.id}/reviews?offset={len(review_list)}"
                        ) as request:
                            review_response = await request.json()

                    for review in review_response["reviews"]:
                        review_list.append(review)
                else:
                    break

        review_amount = len(review_list)
        page = []
        pages = []

        # Create pages of 4 items
        for i, review in enumerate(review_list):
            i += 1

            if len(page) == 4:
                pages.append(page)
                page = []

            page.append([i, review])

        if page != []:
            pages.append(page)

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

                await interaction.response.edit_message(
                    embed=await Reviews.generate_user_review_embed(
                        interaction,
                        user,
                        self.pages[self.page],
                        self.page,
                        len(self.pages),
                        review_amount,
                    ),
                    view=self,
                )

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

                await interaction.response.edit_message(
                    embed=await Reviews.generate_user_review_embed(
                        interaction,
                        user,
                        self.pages[self.page],
                        self.page,
                        len(self.pages),
                        review_amount,
                    ),
                    view=self,
                )

            # Lock / unlock toggle
            @discord.ui.button(emoji="🔓", style=ButtonStyle.green, custom_id="lock")
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
                    await interaction.response.send_message(embed=embed, ephemeral=True)

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

                await interaction.response.edit_message(
                    embed=await Reviews.generate_user_review_embed(
                        interaction,
                        user,
                        self.pages[self.page],
                        self.page,
                        len(self.pages),
                        review_amount,
                    ),
                    view=self,
                )

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

                await interaction.response.edit_message(
                    embed=await Reviews.generate_user_review_embed(
                        interaction,
                        user,
                        self.pages[self.page],
                        self.page,
                        len(self.pages),
                        review_amount,
                    ),
                    view=self,
                )

        if len(pages) != 0:
            if len(pages) == 1:
                await interaction.followup.send(
                    embed=await Reviews.generate_user_review_embed(
                        interaction, user, pages[0], 0, len(pages), review_amount
                    ),
                    ephemeral=ephemeral,
                )
            else:
                page_view_instance = PageView(pages)

                webhook = await interaction.followup.send(
                    embed=await Reviews.generate_user_review_embed(
                        interaction, user, pages[0], 0, len(pages), review_amount
                    ),
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

    # Server review view command
    @reviewGroup.command(
        name="server", description="See the current server's reviews on ReviewDB."
    )
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    @app_commands.checks.cooldown(1, 10)
    async def server_reviews(
        self,
        interaction: discord.Interaction,
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        if interaction.guild is not None:
            guild = interaction.guild
        else:
            embed = discord.Embed(
                title="Error",
                description="This command can only be used in a server.",
                color=Color.red(),
            )

            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        review_list = []

        # Send request to ReviewDB
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://manti.vendicated.dev/api/reviewdb/users/{guild.id}/reviews?offset=0"
            ) as request:
                review_response = await request.json()

        for review in review_response["reviews"][1:]:
            review_list.append(review)

        while True:
            if not review_response["success"]:
                embed = discord.Embed(
                    title="Error",
                    description="ReviewDB has encountered an error. Titanium will not continue. Please try again later.",
                    color=Color.red(),
                )

                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                return
            else:
                if review_response["hasNextPage"]:
                    # Send request to ReviewDB
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"https://manti.vendicated.dev/api/reviewdb/users/{guild.id}/reviews?offset={len(review_list)}"
                        ) as request:
                            review_response = await request.json()

                    for review in review_response["reviews"]:
                        review_list.append(review)
                else:
                    break

        review_amount = len(review_list)
        page = []
        pages = []

        # Create pages of 4 items
        for i, review in enumerate(review_list):
            i += 1

            if len(page) == 4:
                pages.append(page)
                page = []

            page.append([i, review])

        if page != []:
            pages.append(page)

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

                await interaction.response.edit_message(
                    embed=await Reviews.generate_server_review_embed(
                        interaction,
                        guild,
                        self.pages[self.page],
                        self.page,
                        len(self.pages),
                        review_amount,
                    ),
                    view=self,
                )

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

                await interaction.response.edit_message(
                    embed=await Reviews.generate_server_review_embed(
                        interaction,
                        guild,
                        self.pages[self.page],
                        self.page,
                        len(self.pages),
                        review_amount,
                    ),
                    view=self,
                )

            # Lock / unlock toggle
            @discord.ui.button(emoji="🔓", style=ButtonStyle.green, custom_id="lock")
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
                    await interaction.response.send_message(embed=embed, ephemeral=True)

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

                await interaction.response.edit_message(
                    embed=await Reviews.generate_server_review_embed(
                        interaction,
                        guild,
                        self.pages[self.page],
                        self.page,
                        len(self.pages),
                        review_amount,
                    ),
                    view=self,
                )

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

                await interaction.response.edit_message(
                    embed=await Reviews.generate_server_review_embed(
                        interaction,
                        guild,
                        self.pages[self.page],
                        self.page,
                        len(self.pages),
                        review_amount,
                    ),
                    view=self,
                )

        if len(pages) != 0:
            if len(pages) == 1:
                await interaction.followup.send(
                    embed=await Reviews.generate_server_review_embed(
                        interaction, guild, pages[0], 0, len(pages), review_amount
                    ),
                    ephemeral=ephemeral,
                )
            else:
                page_view_instance = PageView(pages)

                webhook = await interaction.followup.send(
                    embed=await Reviews.generate_server_review_embed(
                        interaction, guild, pages[0], 0, len(pages), review_amount
                    ),
                    view=page_view_instance,
                    ephemeral=ephemeral,
                    wait=True,
                )

                page_view_instance.user_id = interaction.user.id
                page_view_instance.msg_id = webhook.id
        else:
            embed = discord.Embed(
                title="ReviewDB Server Reviews",
                description="This user has no reviews!",
                color=Color.red(),
            )
            embed.set_author(
                name=guild.name,
                icon_url=(guild.icon.url if guild.icon is not None else None),
            )

            await interaction.followup.send(embed=embed, ephemeral=ephemeral)


async def setup(bot):
    await bot.add_cog(Reviews(bot))

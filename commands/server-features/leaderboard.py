import logging

import asqlite
import discord
import discord.ext
from discord import ButtonStyle, Color, app_commands
from discord.ext import commands
from discord.ui import View


class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lb_pool: asqlite.Pool = bot.lb_pool
        self.bot.loop.create_task(self.sql_setup())

    async def sql_setup(self):
        async with self.lb_pool.acquire() as sql:
            if (
                await sql.fetchone(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='optOut';"
                )
                is None
            ):
                await sql.execute("CREATE TABLE optOut (userID int)")
                await sql.commit()

            self.opt_out_list = []
            raw_opt_out_list = await sql.fetchall("SELECT userID FROM optOut;")

            for id in raw_opt_out_list:
                self.opt_out_list.append(id[0])

            if (
                await sql.fetchone(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='settings';"
                )
                is None
            ):
                # Assuming this is an old version without settings table, perform migration
                logging.debug(
                    "[LB] Migrating old database to add settings table - this is normal on first run."
                )
                await sql.execute("CREATE TABLE settings (id int, deleteOnLeave int)")

                # Get all tables that aren't opt out or settings
                tables = await sql.fetchall(
                    "SELECT name FROM sqlite_master WHERE type='table' AND NOT name IN ('optOut', 'settings');"
                )

                for table in tables:
                    # Create settings for each table
                    await sql.execute(
                        "INSERT INTO settings (id, deleteOnLeave) VALUES (?, 0);",
                        (int(table[0]),),
                    )

                await sql.commit()
                logging.debug("[LB] Migration complete. Settings table created.")

    # Refresh opt out list function
    async def refresh_opt_out_list(self):
        try:
            async with self.lb_pool.acquire() as sql:
                await sql.execute("DELETE FROM optOut;")
                await sql.commit()

                for id in self.opt_out_list:
                    await sql.execute("INSERT INTO optOut (userID) VALUES (?)", (id,))

            return True, ""
        except Exception as e:
            return False, e

    # Listen for Messages
    @commands.Cog.listener()
    async def on_message(self, message):
        # Catch possible errors
        try:
            # Stop if this is a DM
            if message.guild is None:
                return

            # Check if user is Bot
            if not message.author.bot:
                if message.author.id not in self.opt_out_list:
                    async with self.lb_pool.acquire() as sql:
                        # Check if server is in DB
                        if (
                            await sql.fetchone(
                                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{str(message.guild.id)}';"
                            )
                            is not None
                        ):
                            # Check if user is already on leaderboard
                            if (
                                await sql.fetchone(
                                    f"SELECT userMention FROM '{message.guild.id}' WHERE userMention = '{message.author.mention}';"
                                )
                                is not None
                            ):
                                # User is on the leaderboard, update their values
                                await sql.execute(
                                    f"UPDATE '{message.guild.id}' SET messageCount = messageCount + 1, wordCount = wordCount + {len((message.content).split())}, attachmentCount = attachmentCount + {len(message.attachments)} WHERE userMention = ?",
                                    (message.author.mention),
                                )
                            else:
                                # User is not on leaderboard, add them to the leaderboard
                                await sql.execute(
                                    f"INSERT INTO '{message.guild.id}' (userMention, messageCount, wordCount, attachmentCount) VALUES (?, 1, {len((message.content).split())}, {len(message.attachments)})",
                                    (message.author.mention),
                                )

                            # Commit to DB
                            await sql.commit()
                        else:
                            pass
                else:
                    pass
            else:
                pass
        except Exception as error:
            logging.error("Error occurred while logging message for leaderboard!")
            logging.error(error)

    # Listen for members leaving
    @commands.Cog.listener()
    async def on_raw_member_remove(self, payload: discord.RawMemberRemoveEvent):
        async with self.lb_pool.acquire() as sql:
            row = await sql.fetchone(
                f"SELECT * FROM settings WHERE id={payload.guild_id};"
            )
            if row is not None:
                if row[1] == 1:
                    await sql.execute(
                        f"DELETE FROM '{payload.guild_id}' WHERE userMention = ?;",
                        (payload.user.mention,),
                    )
                    await sql.commit()

    context = discord.app_commands.AppCommandContext(
        guild=True, dm_channel=False, private_channel=False
    )
    installs = discord.app_commands.AppInstallationType(guild=True, user=False)
    lbGroup = app_commands.Group(
        name="leaderboard",
        description="View the server leaderboard.",
        allowed_contexts=context,
        allowed_installs=installs,
    )

    # Leaderboard Command
    @lbGroup.command(name="view", description="View the server message leaderboard.")
    @app_commands.choices(
        sort_type=[
            app_commands.Choice(name="Messages Sent", value="messageCount"),
            app_commands.Choice(name="Words Sent", value="wordCount"),
            app_commands.Choice(name="Attachments Sent", value="attachmentCount"),
        ]
    )
    @app_commands.describe(sort_type="What to sort the leaderboard by.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    @app_commands.checks.cooldown(1, 10)
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        sort_type: app_commands.Choice[str],
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        pages = []

        i = 0
        page_str = ""

        async with self.lb_pool.acquire() as sql:
            if (
                await sql.fetchone(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{str(interaction.guild.id)}';"
                )
                is not None
            ):
                vals = await sql.fetchall(
                    f"SELECT userMention, {sort_type.value} FROM '{interaction.guild.id}' ORDER BY {sort_type.value} DESC"
                )
                if vals != []:
                    for val in vals:
                        i += 1

                        if page_str == "":
                            page_str += f"{i}. {val[0]}: {val[1]}"
                        else:
                            page_str += f"\n{i}. {val[0]}: {val[1]}"

                        # If there's 10 items in the current page, we split it into a new page
                        if i % 10 == 0:
                            pages.append(page_str)
                            page_str = ""

                    if page_str != "":
                        pages.append(page_str)
                else:
                    pages.append("No Data")

                class Leaderboard(View):
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

                    @discord.ui.button(
                        emoji="⏮️", style=ButtonStyle.red, custom_id="first"
                    )
                    async def first_button(
                        self,
                        interaction: discord.Interaction,
                        button: discord.ui.Button,
                    ):
                        self.page = 0

                        for item in self.children:
                            item.disabled = False

                            if item.custom_id == "first" or item.custom_id == "prev":
                                item.disabled = True

                        embed = discord.Embed(
                            title=f"Server Leaderboard - {sort_type.name}",
                            description=self.pages[self.page],
                            color=Color.random(),
                        )
                        embed.set_footer(
                            text=f"Controlling: @{interaction.user.name} • Page {self.page + 1}/{len(self.pages)}",
                            icon_url=interaction.user.display_avatar.url,
                        )

                        await interaction.response.edit_message(embed=embed, view=self)

                    @discord.ui.button(
                        emoji="⏪", style=ButtonStyle.gray, custom_id="prev"
                    )
                    async def prev_button(
                        self,
                        interaction: discord.Interaction,
                        button: discord.ui.Button,
                    ):
                        if self.page - 1 == 0:
                            self.page -= 1

                            for item in self.children:
                                item.disabled = False

                                if (
                                    item.custom_id == "first"
                                    or item.custom_id == "prev"
                                ):
                                    item.disabled = True
                        else:
                            self.page -= 1

                            for item in self.children:
                                item.disabled = False

                        embed = discord.Embed(
                            title=f"Server Leaderboard - {sort_type.name}",
                            description=self.pages[self.page],
                            color=Color.random(),
                        )
                        embed.set_footer(
                            text=f"Controlling: @{interaction.user.name} • Page {self.page + 1}/{len(self.pages)}",
                            icon_url=interaction.user.display_avatar.url,
                        )

                        await interaction.response.edit_message(embed=embed, view=self)

                    @discord.ui.button(
                        emoji="🔓", style=ButtonStyle.green, custom_id="lock"
                    )
                    async def lock_button(
                        self,
                        interaction: discord.Interaction,
                        button: discord.ui.Button,
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

                    @discord.ui.button(
                        emoji="⏩", style=ButtonStyle.gray, custom_id="next"
                    )
                    async def next_button(
                        self,
                        interaction: discord.Interaction,
                        button: discord.ui.Button,
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
                            title=f"Server Leaderboard - {sort_type.name}",
                            description=self.pages[self.page],
                            color=Color.red(),
                        )
                        embed.set_footer(
                            text=f"Controlling: @{interaction.user.name} • Page {self.page + 1}/{len(self.pages)}",
                            icon_url=interaction.user.display_avatar.url,
                        )

                        await interaction.response.edit_message(embed=embed, view=self)

                    @discord.ui.button(
                        emoji="⏭️", style=ButtonStyle.green, custom_id="last"
                    )
                    async def last_button(
                        self,
                        interaction: discord.Interaction,
                        button: discord.ui.Button,
                    ):
                        self.page = len(self.pages) - 1

                        for item in self.children:
                            item.disabled = False

                            if item.custom_id == "next" or item.custom_id == "last":
                                item.disabled = True

                        embed = discord.Embed(
                            title=f"Server Leaderboard - {sort_type.name}",
                            description=self.pages[self.page],
                            color=Color.random(),
                        )
                        embed.set_footer(
                            text=f"Controlling: @{interaction.user.name} • Page {self.page + 1}/{len(self.pages)}",
                            icon_url=interaction.user.display_avatar.url,
                        )

                        await interaction.response.edit_message(embed=embed, view=self)

                embed = discord.Embed(
                    title=f"Server Leaderboard - {sort_type.name}",
                    description=pages[0],
                    color=Color.random(),
                )
                embed.set_footer(
                    text=f"Controlling: @{interaction.user.name} • Page 1/{len(pages)}",
                    icon_url=interaction.user.display_avatar.url,
                )

                if len(pages) == 1:
                    await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                else:
                    webhook = await interaction.followup.send(
                        embed=embed,
                        view=Leaderboard(pages),
                        ephemeral=ephemeral,
                        wait=True,
                    )

                    Leaderboard.user_id = interaction.user.id
                    Leaderboard.msg_id = webhook.id
            else:
                embed = discord.Embed(
                    title="Not Enabled",
                    description="The message leaderboard is not enabled in this server. Ask an admin to enable it first.",
                    color=Color.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    # Opt out command
    @lbGroup.command(
        name="opt-out", description="Opt out of the leaderboard globally as a user."
    )
    async def opt_out_lb(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        async def delete_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)

            embed = discord.Embed(
                title="Opting out...",
                description=f"{self.bot.options['loading-emoji']} Please wait...",
                color=Color.orange(),
            )
            await interaction.edit_original_response(embed=embed, view=None)

            if interaction.user.id in self.opt_out_list:
                embed = discord.Embed(
                    title="Failed",
                    description="You have already opted out.",
                    color=Color.red(),
                )
                await interaction.edit_original_response(embed=embed)
            else:
                self.opt_out_list.append(interaction.user.id)
                status, error = await self.refresh_opt_out_list()

                async with self.lb_pool.acquire() as sql:
                    for server in await sql.fetchall(
                        "SELECT name FROM sqlite_master WHERE type='table' AND NOT name='optOut';"
                    ):
                        await sql.execute(
                            f"DELETE FROM '{int(server[0])}' WHERE userMention = ?;",
                            (interaction.user.mention),
                        )

                    await sql.commit()

                if not status:
                    raise error

                embed = discord.Embed(title="You have opted out.", color=Color.green())
                await interaction.edit_original_response(embed=embed)

        view = View()
        delete_button = discord.ui.Button(label="Opt Out", style=ButtonStyle.red)
        delete_button.callback = delete_callback
        view.add_item(delete_button)

        embed = discord.Embed(
            title="Are you sure?",
            description="By opting out of the leaderboard, you will be unable to contribute to the Titanium leaderboard in any server. Additionally, your data will be deleted across all Titanium leaderboards.",
            color=Color.orange(),
        )
        await interaction.followup.send(embed=embed, view=view)

    # Opt out command
    @lbGroup.command(
        name="opt-in", description="Opt back in to the leaderboard globally as a user."
    )
    async def opt_in_lb(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        async def delete_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)

            embed = discord.Embed(
                title="Opting in...",
                description=f"{self.bot.options['loading-emoji']} Please wait...",
                color=Color.orange(),
            )
            await interaction.edit_original_response(embed=embed, view=None)

            if interaction.user.id not in self.opt_out_list:
                embed = discord.Embed(
                    title="Failed",
                    description="You are already opted in.",
                    color=Color.red(),
                )
                await interaction.edit_original_response(embed=embed)
            else:
                self.opt_out_list.remove(interaction.user.id)
                status, error = await self.refresh_opt_out_list()

                if not status:
                    raise error

                embed = discord.Embed(title="You have opted in.", color=Color.green())
                await interaction.edit_original_response(embed=embed)

        view = View()
        delete_button = discord.ui.Button(label="Opt In", style=ButtonStyle.green)
        delete_button.callback = delete_callback
        view.add_item(delete_button)

        embed = discord.Embed(
            title="Are you sure?",
            description="By opting in to the leaderboard, you will be able to contribute to the Titanium leaderboard in any server again.",
            color=Color.orange(),
        )
        await interaction.followup.send(embed=embed, view=view)

    context = discord.app_commands.AppCommandContext(
        guild=True, dm_channel=False, private_channel=False
    )
    perms = discord.Permissions()
    lbCtrlGroup = app_commands.Group(
        name="lb-setup",
        description="Set up the leaderboard - server admins only.",
        allowed_contexts=context,
        default_permissions=perms,
    )

    # Enable LB command
    @lbCtrlGroup.command(name="enable", description="Enable the message leaderboard.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def enable_lb(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="Enabling...",
            description=f"{self.bot.options['loading-emoji']} Enabling the leaderboard...",
            color=Color.orange(),
        )
        await interaction.edit_original_response(embed=embed)

        async with self.lb_pool.acquire() as sql:
            if (
                await sql.fetchone(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{str(interaction.guild.id)}';"
                )
                is not None
            ):
                embed = discord.Embed(
                    title="Success",
                    description="Already enabled for this server.",
                    color=Color.green(),
                )
                await interaction.edit_original_response(embed=embed)
            else:
                await sql.execute(
                    f"CREATE TABLE '{interaction.guild.id}' (userMention text, messageCount integer, wordCount integer, attachmentCount integer)"
                )
                await sql.commit()

                embed = discord.Embed(
                    title="Success",
                    description="Enabled message leaderboard for this server.",
                    color=Color.green(),
                )
                await interaction.edit_original_response(embed=embed)

    # Disable LB command
    @lbCtrlGroup.command(name="disable", description="Disable the message leaderboard.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def disable_lb(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        async def delete_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)

            embed = discord.Embed(
                title="Disabling...",
                description=f"{self.bot.options['loading-emoji']} Disabling the leaderboard...",
                color=Color.orange(),
            )
            await interaction.edit_original_response(embed=embed, view=None)

            async with self.lb_pool.acquire() as sql:
                if (
                    await sql.fetchone(
                        f"SELECT name FROM sqlite_master WHERE type='table' AND name='{interaction.guild.id}';"
                    )
                    is None
                ):
                    embed = discord.Embed(
                        title="Failed",
                        description="Leaderboard is already disabled in this server.",
                        color=Color.red(),
                    )
                    await interaction.edit_original_response(embed=embed)
                else:
                    await sql.execute(f"DROP TABLE '{interaction.guild.id}'")
                    await sql.commit()

                    embed = discord.Embed(title="Disabled.", color=Color.green())
                    await interaction.edit_original_response(embed=embed)

        view = View()
        delete_button = discord.ui.Button(label="Delete", style=ButtonStyle.red)
        delete_button.callback = delete_callback
        view.add_item(delete_button)

        embed = discord.Embed(
            title="Are you sure?",
            description="The leaderboard will be disabled, and data for this server will be deleted!",
            color=Color.orange(),
        )
        await interaction.followup.send(embed=embed, view=view)

    # Reset LB command
    @lbCtrlGroup.command(name="reset", description="Resets the message leaderboard.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def reset_lb(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        async with self.lb_pool.acquire() as sql:
            if (
                await sql.fetchone(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{interaction.guild.id}';"
                )
                is None
            ):
                embed = discord.Embed(
                    title="Disabled",
                    description="Leaderboard is disabled in this server.",
                    color=Color.red(),
                )
                await interaction.edit_original_response(embed=embed)
            else:

                async def delete_callback(interaction: discord.Interaction):
                    await interaction.response.defer(ephemeral=True)

                    embed = discord.Embed(
                        title="Resetting...",
                        description=f"{self.bot.options['loading-emoji']} Resetting the leaderboard...",
                        color=Color.orange(),
                    )
                    await interaction.edit_original_response(embed=embed, view=None)

                    await sql.execute(f"DELETE FROM '{interaction.guild.id}';")
                    await sql.commit()

                    embed = discord.Embed(title="Reset.", color=Color.green())
                    await interaction.edit_original_response(embed=embed)

                view = View()
                delete_button = discord.ui.Button(label="Reset", style=ButtonStyle.red)
                delete_button.callback = delete_callback
                view.add_item(delete_button)

                embed = discord.Embed(
                    title="Are you sure?",
                    description="The leaderboard will be reset and all data will be removed!",
                    color=Color.orange(),
                )
                await interaction.edit_original_response(embed=embed, view=view)

    # Reset LB command
    @lbCtrlGroup.command(
        name="reset-user", description="Resets a user on the leaderboard."
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def reset_userlb(self, interaction: discord.Interaction, user: discord.User):
        await interaction.response.defer(ephemeral=True)

        async with self.lb_pool.acquire() as sql:
            if (
                await sql.fetchone(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{interaction.guild.id}';"
                )
                is None
            ):
                embed = discord.Embed(
                    title="Disabled",
                    description="Leaderboard is disabled in this server.",
                    color=Color.red(),
                )
                await interaction.edit_original_response(embed=embed)
            else:

                async def delete_callback(interaction: discord.Interaction):
                    await interaction.response.defer(ephemeral=True)

                    embed = discord.Embed(
                        title="Removing...",
                        description=f"{self.bot.options['loading-emoji']} Target: {user.mention}",
                        color=Color.orange(),
                    )
                    await interaction.edit_original_response(embed=embed, view=None)

                    await sql.execute(
                        f"DELETE FROM '{interaction.guild.id}' WHERE userMention = '{user.mention}';"
                    )
                    await sql.commit()

                    embed = discord.Embed(title="Removed.", color=Color.green())
                    await interaction.edit_original_response(embed=embed)

                view = View()
                delete_button = discord.ui.Button(label="Remove", style=ButtonStyle.red)
                delete_button.callback = delete_callback
                view.add_item(delete_button)

                embed = discord.Embed(
                    title="Are you sure?",
                    description=f"Are you sure you want to remove {user.mention} from the leaderboard?",
                    color=Color.orange(),
                )
                await interaction.edit_original_response(embed=embed, view=view)

    # Toggle auto delete command
    @lbCtrlGroup.command(
        name="delete-on-leave",
        description="Toggle whether to delete users from the leaderboard when they leave.",
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def toggle_delete_on_leave(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        async with self.lb_pool.acquire() as sql:
            row = await sql.fetchone(
                "SELECT * FROM settings WHERE id=?;", (interaction.guild.id,)
            )
            if row is None:
                embed = discord.Embed(
                    title="Failed",
                    description="Leaderboard is disabled in this server.",
                    color=Color.red(),
                )
            else:
                if row[1] == 0:
                    await sql.execute(
                        "UPDATE settings SET deleteOnLeave = 1 WHERE id = ?;",
                        (interaction.guild.id,),
                    )
                    await sql.commit()

                    embed = discord.Embed(
                        title="Success",
                        description="Titanium will now try to delete users from the leaderboard when they leave the server.",
                        color=Color.green(),
                    )
                else:
                    await sql.execute(
                        "UPDATE settings SET deleteOnLeave = 0 WHERE id = ?;",
                        (interaction.guild.id,),
                    )
                    await sql.commit()

                    embed = discord.Embed(
                        title="Success",
                        description="Titanium will no longer delete users from the leaderboard when they leave the server.",
                        color=Color.green(),
                    )

            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Leaderboard(bot))

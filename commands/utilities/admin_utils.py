import asyncio
import datetime
import logging
import os
import traceback
from typing import TYPE_CHECKING

import discord
import discord.ext
import discord.ext.commands
from discord import ButtonStyle, Color, app_commands
from discord.ext import commands
from discord.ui import View

import utils.return_ctrlguild as ctrl

if TYPE_CHECKING:
    from commands.automated.status_update import StatusUpdate


class CogUtils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot: discord.ext.commands.Bot

    context = discord.app_commands.AppCommandContext(
        guild=True, dm_channel=True, private_channel=False
    )
    perms = discord.Permissions()

    target = ctrl.return_ctrlguild()
    adminGroup = app_commands.Group(
        name="admin",
        description="Control the bot. (admin only)",
        allowed_contexts=context,
        guild_ids=[target],
        default_permissions=perms,
    )

    async def interaction_check(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if await self.bot.is_owner(interaction.user):
            return True
        else:
            embed = discord.Embed(
                title="You do not have permission to run this command.",
                color=Color.red(),
            )
            await interaction.followup.send(embed=embed)

            return False

    # Load cog command
    @adminGroup.command(name="load", description="Admin Only: load a cog.")
    async def load(self, interaction: discord.Interaction, cog: str):
        cog = f"commands.{cog.replace('\\', '/').replace('/', '.')}"

        try:
            await self.bot.load_extension(cog)

            embed = discord.Embed(title=f"Loaded {cog}!", color=Color.green())
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception:
            embed = discord.Embed(
                title="Error",
                description=f"Error while loading {cog}.\n\n```python\n{traceback.format_exc()}```",
                color=Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    # Unload cog command
    @adminGroup.command(name="unload", description="Admin Only: unload a cog.")
    async def unload(self, interaction: discord.Interaction, cog: str):
        cog = f"commands.{cog.replace('\\', '/').replace('/', '.')}"

        try:
            await self.bot.unload_extension(cog)

            embed = discord.Embed(title=f"Unloaded {cog}!", color=Color.green())
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception:
            embed = discord.Embed(
                title="Error",
                description=f"Error while unloading {cog}.\n\n```python\n{traceback.format_exc()}```",
                color=Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    # Reload cog command
    @adminGroup.command(name="reload", description="Admin Only: reload a cog.")
    async def reload(self, interaction: discord.Interaction, cog: str):
        cog = f"commands.{cog.replace('\\', '/').replace('/', '.')}"

        try:
            await self.bot.reload_extension(cog)

            embed = discord.Embed(title=f"Reloaded {cog}!", color=Color.green())
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception:
            embed = discord.Embed(
                title="Error",
                description=f"Error while reloading {cog}.\n\n```python\n{traceback.format_exc()}```",
                color=Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    # Tree sync command
    @adminGroup.command(name="sync", description="Admin Only: sync the command tree.")
    async def tree_sync(self, interaction: discord.Interaction):
        # Loading prompt
        embed = discord.Embed(
            title="Syncing tree...",
            description=f"{self.bot.options['loading-emoji']} This may take a moment.",
            color=Color.orange(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

        # Control Server Sync
        logging.info(
            f"[INIT] Syncing control server command tree ({self.bot.options['control-guild']})..."
        )
        guild = await self.bot.fetch_guild(self.bot.options["control-guild"])
        sync = await self.bot.tree.sync(guild=guild)
        logging.info(
            f"[INIT] Control server command tree synced. {len(sync)} command total."
        )

        # Global Sync
        logging.info("[INIT] Syncing global command tree...")
        sync = await self.bot.tree.sync(guild=None)
        logging.info(f"[INIT] Global command tree synced. {len(sync)} commands total.")

        embed = discord.Embed(
            title="Success!",
            description=f"Tree synced. {len(sync)} commands loaded.",
            color=Color.green(),
        )
        await interaction.edit_original_response(embed=embed)

    # Enable auto status command
    @adminGroup.command(
        name="auto-status-enable", description="Admin Only: enable auto status."
    )
    async def enable_autostatus(self, interaction: discord.Interaction):
        # Start auto status task
        status_cog: "StatusUpdate" = self.bot.get_cog("StatusUpdate")

        if status_cog is not None:
            started = False

            if not status_cog.info_update.is_running():
                started = True
                status_cog.info_update.start()

            if not status_cog.status_update.is_running():
                started = True
                status_cog.status_update.start()

            if started:
                embed = discord.Embed(
                    title="Success!",
                    description="Auto status was enabled.",
                    color=Color.green(),
                )
            else:
                embed = discord.Embed(
                    title="Already Started",
                    description="Auto status is already running.",
                    color=Color.red(),
                )
        else:
            embed = discord.Embed(
                title="Error",
                description="Auto status cog does not exist.",
                color=Color.red(),
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    # Disable auto status command
    @adminGroup.command(
        name="auto-status-disable", description="Admin Only: disable auto status."
    )
    async def disable_autostatus(self, interaction: discord.Interaction):
        # Stop auto status task
        status_cog: "StatusUpdate" = self.bot.get_cog("StatusUpdate")

        if status_cog is not None:
            if (
                status_cog.status_update.is_running()
                or status_cog.info_update.is_running()
            ):
                status_cog.status_update.cancel()
                status_cog.info_update.cancel()

                # Update status
                await self.bot.change_presence(
                    activity=discord.Activity(
                        status=discord.Status.online,
                    )
                )

                embed = discord.Embed(
                    title="Success!",
                    description="Auto status was disabled and cleared.",
                    color=Color.green(),
                )
            else:
                embed = discord.Embed(
                    title="Already Stopped",
                    description="Auto status is already stopped.",
                    color=Color.red(),
                )
        else:
            embed = discord.Embed(
                title="Error",
                description="Auto status cog does not exist.",
                color=Color.red(),
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    # Set custom status command
    @adminGroup.command(
        name="custom-status", description="Admin Only: set a custom status."
    )
    async def set_custom_status(self, interaction: discord.Interaction, status: str):
        # Get auto status cog
        status_cog: "StatusUpdate" = self.bot.get_cog("StatusUpdate")

        running = False

        # Stop task if running
        if status_cog is not None:
            if (
                status_cog.status_update.is_running()
                or status_cog.info_update.is_running()
            ):
                running = True

                status_cog.status_update.cancel()
                status_cog.info_update.cancel()

        # Update status
        await self.bot.change_presence(
            activity=discord.Activity(
                status=discord.Status.online,
                type=discord.ActivityType.custom,
                name="custom",
                state=status,
            )
        )

        embed = discord.Embed(
            title="Success!",
            description=f"Custom status set to `{status}`.{' Disabled auto status.' if running else ''}",
            color=Color.green(),
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    # Clear status command
    @adminGroup.command(
        name="clear-status", description="Admin Only: clear the bot's status."
    )
    async def clear_status(self, interaction: discord.Interaction):
        # Get auto status cog
        status_cog: "StatusUpdate" = self.bot.get_cog("StatusUpdate")

        running = False

        # Stop task if running
        if status_cog is not None:
            if (
                status_cog.status_update.is_running()
                or status_cog.info_update.is_running()
            ):
                running = True

                status_cog.status_update.cancel()
                status_cog.info_update.cancel()

        # Update status
        await self.bot.change_presence(
            activity=discord.Activity(
                status=discord.Status.online,
            )
        )

        embed = discord.Embed(
            title="Success!",
            description=f"Cleared status.{' Disabled auto status.' if running else ''}",
            color=Color.green(),
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    # Clear Console command
    @adminGroup.command(
        name="clear-console", description="Admin Only: clear the console."
    )
    async def clear_console(
        self,
        interaction: discord.Interaction,
    ):
        os.system("cls" if os.name == "nt" else "clear")

        await interaction.followup.send("Cleared the console.", ephemeral=True)

    # Send Message command
    @adminGroup.command(
        name="send-message", description="Admin Only: send debug message."
    )
    async def send_message(
        self, interaction: discord.Interaction, message: str, channel_id: str, embed: bool = False
    ):
        channel = self.bot.get_channel(int(channel_id))

        if embed:
            embed = discord.Embed(
                title="Message from Bot Admin",
                description=message,
            color=Color.random(),
            )
            embed.timestamp = datetime.datetime.now()

            await channel.send(embed=embed)
        else:
            await channel.send(message)

        await interaction.followup.send(
            f"Message sent to channel ID {channel_id}.\n\nContent: {message}",
            ephemeral=True,
        )

    # Server List command
    @adminGroup.command(
        name="server-list", description="Admin Only: get a list of all server guilds."
    )
    async def server_list(self, interaction: discord.Interaction):
        page = []
        pages = []

        for i, server in enumerate(self.bot.guilds):
            page.append(
                f"{i + 1}. {server} ({server.id}) ({server.member_count} members)"
            )

            if (i + 1) % 20 == 0:
                pages.append(page)
                page = []

        if page != []:
            pages.append(page)

        class ServersPageView(View):
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
                    title="Bot Servers",
                    description="\n".join(self.pages[self.page]),
                    color=Color.random(),
                )
                embed.set_footer(text=f"Page {self.page + 1}/{len(self.pages)}")

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
                    title="Bot Servers",
                    description="\n".join(self.pages[self.page]),
                    color=Color.random(),
                )
                embed.set_footer(text=f"Page {self.page + 1}/{len(self.pages)}")

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
                    title="Bot Servers",
                    description="\n".join(self.pages[self.page]),
                    color=Color.random(),
                )
                embed.set_footer(text=f"Page {self.page + 1}/{len(self.pages)}")

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
                    title="Bot Servers",
                    description="\n".join(self.pages[self.page]),
                    color=Color.random(),
                )
                embed.set_footer(text=f"Page {self.page + 1}/{len(self.pages)}")

                await interaction.response.edit_message(embed=embed, view=self)

        embed = discord.Embed(
            title="Bot Servers", description="\n".join(pages[0]), color=Color.random()
        )
        embed.set_footer(text=f"Page 1/{len(pages)}")

        if len(pages) == 1:
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            view_instance = ServersPageView(pages)

            webhook = await interaction.followup.send(
                embed=embed, view=view_instance, wait=True, ephemeral=True
            )
            view_instance.msg_id = webhook.id

    # Error Test command
    @adminGroup.command(
        name="error-test",
        description="Admin Only: test the error handler. This WILL cause an error to occur!",
    )
    async def error_test(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Error Test", description="Error in 3 seconds...")
        await interaction.followup.send(embed=embed, ephemeral=True)

        await asyncio.sleep(3)
        raise Exception

    # Defer Test command
    @adminGroup.command(name="defer-test", description="Admin Only: test defer.")
    async def defer_test(self, interaction: discord.Interaction, seconds: int):
        await asyncio.sleep(seconds)
        await interaction.followup.send("Done.", ephemeral=True)

    # Channel Name test command
    @adminGroup.command(
        name="edit-channel",
        description="Admin Only: test editing channel names.",
    )
    async def edit_channel_name(
        self,
        interaction: discord.Interaction,
        server_id: str,
        channel_id: str,
        name: str,
    ):
        guild = self.bot.get_guild(int(server_id))
        channel = guild.get_channel(int(channel_id))

        if channel is not None:
            await channel.edit(name=name, reason="Titanium Debug")
            embed = discord.Embed(
                title="Success!",
                description=f"Channel name changed to {name}.",
                color=Color.green(),
            )

            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(CogUtils(bot))

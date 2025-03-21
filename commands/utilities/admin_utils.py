import asyncio
import datetime
import logging
import os
import traceback

import discord
import discord.ext
import discord.ext.commands
from discord import ButtonStyle, Color, app_commands
from discord.ext import commands
from discord.ui import View

import utils.return_ctrlguild as ctrl


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
        logging.info("[INIT] Syncing control server command tree...")
        guild = self.bot.get_guild(1213954608632700989)
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
        self, interaction: discord.Interaction, message: str, channel_id: str
    ):
        if interaction.user.id in self.bot.options["owner-ids"]:
            channel = self.bot.get_channel(int(channel_id))

            embed = discord.Embed(
                title="Message from Bot Admin",
                description=message,
                color=Color.random(),
            )
            embed.timestamp = datetime.datetime.now()

            await channel.send(embed=embed)

            await interaction.followup.send(
                f"Message sent to channel ID {channel_id}.\n\nContent: {message}",
                ephemeral=True,
            )
        else:
            embed = discord.Embed(
                title="You do not have permission to run this command.",
                color=Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

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

    @adminGroup.command(name="defer-test", description="Admin Only: test defer.")
    async def defer_test(self, interaction: discord.Interaction, seconds: int):
        await asyncio.sleep(seconds)
        await interaction.followup.send("Done.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(CogUtils(bot))

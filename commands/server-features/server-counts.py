import logging
import traceback
from typing import TYPE_CHECKING

import discord
from discord import Color, app_commands
from discord.ext import commands, tasks

if TYPE_CHECKING:
    from main import TitaniumBot


def human_format(num):
    if num > 9999:
        num = float("{:.3g}".format(num))
        magnitude = 0

        while abs(num) >= 1000:
            magnitude += 1
            num /= 1000.0

        return "{}{}".format(
            "{:f}".format(num).rstrip("0").rstrip("."),
            ["", "K", "M", "B", "T"][magnitude],
        )
    else:
        return f"{num:,}"


class ServerCounts(commands.Cog):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot
        self.channel_update.start()
        self.bot.loop.create_task(self.sql_setup())

    async def sql_setup(self) -> None:
        # Check if counts table exists in pool
        async with self.bot.server_counts_pool.acquire() as sql:
            if not await sql.fetchone(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='channels';"
            ):
                # Create the table if it doesn't exist
                await sql.execute(
                    "CREATE TABLE channels (server_id INT, channel_id INT, channel_name TEXT, channel_type TEXT)"
                )
                await sql.commit()

    def cog_unload(self) -> None:
        # Stop tasks on unload
        self.channel_update.cancel()

    # Info update task
    @tasks.loop(minutes=10)
    async def channel_update(self) -> None:
        await self.bot.wait_until_ready()

        async with self.bot.server_counts_pool.acquire() as sql:
            # Get servers
            servers = await sql.fetchall("SELECT DISTINCT server_id FROM channels")

            for server in servers:
                try:
                    # Get server members
                    guild = self.bot.get_guild(server[0])

                    if guild is None:
                        try:
                            guild = self.bot.fetch_guild(server[0])
                        except discord.NotFound:
                            # If the guild is not found, remove it from the database
                            await sql.execute(
                                "DELETE FROM channels WHERE server_id = ?",
                                (server[0],),
                            )

                            await sql.commit()
                            continue

                    # Get server count channels
                    channels = await sql.fetchall(
                        "SELECT * FROM channels WHERE server_id = ?",
                        (server[0],),
                    )

                    for channel in channels:
                        try:
                            channel_id: int = channel[1]
                            channel_name: str = channel[2]
                            channel_type: str = channel[3]

                            # Get the channel
                            channel = guild.get_channel(channel_id)

                            if channel is None:
                                try:
                                    channel = guild.fetch_channel(channel_id)
                                except discord.NotFound:
                                    # If the channel is not found, remove it from the database
                                    await sql.execute(
                                        "DELETE FROM channels WHERE server_id = ? AND channel_id = ?",
                                        (server[0], channel_id),
                                    )

                                    await sql.commit()
                                    continue

                            # Update the channel name with the server count
                            if channel_type == "total_members":
                                await channel.edit(
                                    name=channel_name.replace(
                                        "$VALUE$", human_format(guild.member_count)
                                    )
                                )
                            elif channel_type == "users":
                                user_count = 0

                                for member in guild.members:
                                    if not member.bot:
                                        user_count += 1

                                await channel.edit(
                                    name=channel_name.replace(
                                        "$VALUE$", human_format(user_count)
                                    )
                                )
                            elif channel_type == "bots":
                                bot_count = 0

                                for member in guild.members:
                                    if member.bot:
                                        bot_count += 1

                                await channel.edit(
                                    name=channel_name.replace(
                                        "$VALUE$", human_format(bot_count)
                                    )
                                )
                            elif channel_type == "online_members":
                                online_count = 0

                                for member in guild.members:
                                    if member.status != discord.Status.offline:
                                        online_count += 1

                                await channel.edit(
                                    name=channel_name.replace(
                                        "$VALUE$", human_format(online_count)
                                    )
                                )
                            elif channel_type == "offline_members":
                                offline_count = 0

                                for member in guild.members:
                                    if member.status == discord.Status.offline:
                                        offline_count += 1

                                await channel.edit(
                                    name=channel_name.replace(
                                        "$VALUE$", human_format(offline_count)
                                    )
                                )
                            elif channel_type == "channels":
                                channel_count = (
                                    len(guild.text_channels)
                                    + len(guild.voice_channels)
                                    + len(guild.stage_channels)
                                )

                                await channel.edit(
                                    name=channel_name.replace(
                                        "$VALUE$", human_format(channel_count)
                                    )
                                )
                        except Exception:
                            logging.error("Server Counts Update Error - Channel")
                            logging.error(traceback.format_exc())
                except Exception:
                    logging.error("Server Counts Update Error - Guild")
                    logging.error(traceback.format_exc())

    context = discord.app_commands.AppCommandContext(
        guild=True, dm_channel=False, private_channel=False
    )
    perms = discord.Permissions()
    server_counter_group = app_commands.Group(
        name="server-counters",
        description="Set up live updating server count channels.",
        allowed_contexts=context,
        default_permissions=perms,
    )

    # Add Channel command
    @server_counter_group.command(
        name="add", description="Add a live updating server count channel."
    )
    @app_commands.choices(
        channel_type=[
            app_commands.Choice(name="Total Server Members", value="total_members"),
            app_commands.Choice(name="Users", value="users"),
            app_commands.Choice(name="Bots", value="bots"),
            app_commands.Choice(name="Online Members", value="online_members"),
            app_commands.Choice(name="Offline Members", value="offline_members"),
            app_commands.Choice(name="Total Channels", value="channels"),
        ]
    )
    @app_commands.describe(
        channel_type="The type of server count channel to create.",
        channel_name="The name of the channel. Use $VALUE$ as placeholder, for example - $VALUE$ members.",
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def add_channel(
        self,
        interaction: discord.Interaction,
        channel_type: app_commands.Choice[str],
        channel_name: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        async with self.bot.server_counts_pool.acquire() as sql:
            # Update the channel name with the server count
            if channel_type.value == "total_members":
                name = channel_name.replace(
                    "$VALUE$", human_format(interaction.guild.member_count)
                )
            elif channel_type.value == "users":
                user_count = 0

                for member in interaction.guild.members:
                    if not member.bot:
                        user_count += 1

                name = channel_name.replace("$VALUE$", human_format(user_count))
            elif channel_type.value == "bots":
                bot_count = 0

                for member in interaction.guild.members:
                    if member.bot:
                        bot_count += 1

                name = channel_name.replace("$VALUE$", human_format(bot_count))
            elif channel_type.value == "online_members":
                online_count = 0

                for member in interaction.guild.members:
                    if member.status != discord.Status.offline:
                        online_count += 1

                name = channel_name.replace("$VALUE$", human_format(online_count))
            elif channel_type.value == "offline_members":
                offline_count = 0

                for member in interaction.guild.members:
                    if member.status == discord.Status.offline:
                        offline_count += 1

                name = channel_name.replace("$VALUE$", human_format(offline_count))
            elif channel_type.value == "channels":
                channel_count = (
                    len(interaction.guild.text_channels)
                    + len(interaction.guild.voice_channels)
                    + len(interaction.guild.stage_channels)
                )

                name = channel_name.replace("$VALUE$", human_format(channel_count))

            # Do not allow sending messages or connecting to the channel
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(
                    read_messages=True, send_messages=False, connect=False
                ),
            }

            # Make a new channel
            channel = await interaction.guild.create_voice_channel(
                name=name,
                overwrites=overwrites,
                reason=f"@{interaction.user.name} added server count channel",
            )

            await sql.execute(
                "INSERT INTO channels (server_id, channel_id, channel_name, channel_type) VALUES (?, ?, ?, ?)",
                (interaction.guild.id, channel.id, channel_name, channel_type.value),
            )
            await sql.commit()

            await interaction.followup.send(
                embed=discord.Embed(
                    title="Channel Created",
                    description=f"Created the {channel.mention} channel. Feel free to move it to a different place in the server list, just ensure that Titanium has permission to edit it.",
                    color=Color.green(),
                ),
                ephemeral=True,
            )

    # Remove Channel command
    @server_counter_group.command(
        name="remove", description="Remove a live updating server count channel."
    )
    @app_commands.describe(
        channel="The channel to remove.",
        delete_channel="Whether to delete the channel or just stop updating it.",
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def remove_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel,
        delete_channel: bool,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        async with self.bot.server_counts_pool.acquire() as sql:
            sql_channel = await sql.fetchone(
                "SELECT * FROM channels WHERE server_id = ? AND channel_id = ?",
                (interaction.guild.id, channel.id),
            )

            if sql_channel is None:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Not Found",
                        description=f"Titanium is not managing {channel.mention}.",
                        color=Color.red(),
                    ),
                    ephemeral=True,
                )
                return

            # Delete the channel from the database
            await sql.execute(
                "DELETE FROM channels WHERE server_id = ? AND channel_id = ?",
                (interaction.guild.id, channel.id),
            )
            await sql.commit()

            if delete_channel:
                # Delete the channel
                await channel.delete(
                    reason=f"@{interaction.user.name} removed server count channel"
                )

            await interaction.followup.send(
                embed=discord.Embed(
                    title="Channel Removed",
                    description=f"Stopped updating {'and deleted ' if delete_channel else ''}{channel.name if delete_channel else channel.mention}.",
                    color=Color.green(),
                ),
                ephemeral=True,
            )

    # Edit Channel command
    @server_counter_group.command(
        name="edit",
        description="Edit the channel name or type of a server count channel.",
    )
    @app_commands.choices(
        channel_type=[
            app_commands.Choice(name="Total Server Members", value="total_members"),
            app_commands.Choice(name="Users", value="users"),
            app_commands.Choice(name="Bots", value="bots"),
            app_commands.Choice(name="Online Members", value="online_members"),
            app_commands.Choice(name="Offline Members", value="offline_members"),
            app_commands.Choice(name="Total Channels", value="channels"),
        ]
    )
    @app_commands.describe(
        channel_type="The new server count channel type.",
        name="The new name of the channel. Use $VALUE$ as placeholder, for example - $VALUE$ members.",
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def edit_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel,
        channel_type: app_commands.Choice[str] = None,
        name: str = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        async with self.bot.server_counts_pool.acquire() as sql:
            sql_channel = await sql.fetchone(
                "SELECT * FROM channels WHERE server_id = ? AND channel_id = ?",
                (interaction.guild.id, channel.id),
            )

            if sql_channel is None:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Not Found",
                        description=f"Titanium is not managing {channel.mention}.",
                        color=Color.red(),
                    ),
                    ephemeral=True,
                )
                return
            else:
                if channel_type is None and name is None:
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="No Changes",
                            description="You must provide a new channel type or name.",
                            color=Color.red(),
                        ),
                        ephemeral=True,
                    )
                    return

                if name is not None:
                    # Update the channel name in the database
                    await sql.execute(
                        "UPDATE channels SET channel_name = ? WHERE server_id = ? AND channel_id = ?",
                        (name, interaction.guild.id, channel.id),
                    )
                    await sql.commit()

                if channel_type is not None:
                    # Update the channel type in the database
                    await sql.execute(
                        "UPDATE channels SET channel_type = ? WHERE server_id = ? AND channel_id = ?",
                        (channel_type.value, interaction.guild.id, channel.id),
                    )
                    await sql.commit()

                # Update the channel name with the server count
                if channel_type.value == "total_members":
                    name = name.replace(
                        "$VALUE$", human_format(interaction.guild.member_count)
                    )
                elif channel_type.value == "users":
                    user_count = 0

                    for member in interaction.guild.members:
                        if not member.bot:
                            user_count += 1

                    name = name.replace("$VALUE$", human_format(user_count))
                elif channel_type.value == "bots":
                    bot_count = 0

                    for member in interaction.guild.members:
                        if member.bot:
                            bot_count += 1

                    name = name.replace("$VALUE$", human_format(bot_count))
                elif channel_type.value == "online_members":
                    online_count = 0

                    for member in interaction.guild.members:
                        if member.status != discord.Status.offline:
                            online_count += 1

                    name = name.replace("$VALUE$", human_format(online_count))
                elif channel_type.value == "offline_members":
                    offline_count = 0

                    for member in interaction.guild.members:
                        if member.status == discord.Status.offline:
                            offline_count += 1

                    name = name.replace("$VALUE$", human_format(offline_count))
                elif channel_type.value == "channels":
                    channel_count = (
                        len(interaction.guild.text_channels)
                        + len(interaction.guild.voice_channels)
                        + len(interaction.guild.stage_channels)
                    )

                    name = name.replace("$VALUE$", human_format(channel_count))

                # Update the channel name
                await channel.edit(
                    name=name,
                    reason=f"@{interaction.user.name} updated server count channel",
                )

                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Channel Edited",
                        description=f"Updated {channel.mention}.",
                        color=Color.green(),
                    ),
                    ephemeral=True,
                )


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(ServerCounts(bot))

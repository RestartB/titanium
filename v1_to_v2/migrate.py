import logging
import os
import sqlite3
from typing import TYPE_CHECKING

from lib.sql.sql import (
    FireboardBoard,
    FireboardMessage,
    GuildFireboardSettings,
    ServerCounterChannel,
    get_session,
)

if TYPE_CHECKING:
    from main import TitaniumBot

"""Cog for migrating Fireboard data from v1 to v2."""


async def migrate_fireboard(bot: TitaniumBot):
    con = sqlite3.connect(os.path.join("v1_to_v2", "dbs", "fireboard.db"))
    cur = con.cursor()

    legacy_fireboard_settings = cur.execute("SELECT * FROM fireSettings").fetchall()

    for row in legacy_fireboard_settings:
        async with get_session() as session:
            server_id, reaction_amount, emoji, channel_id, ignore_bots = row

            await bot.init_guild(server_id)

            # Blacklisted things
            legacy_fireboard_role_blacklist = cur.execute(
                "SELECT roleID FROM fireRoleBlacklist WHERE serverID = ?", (server_id,)
            ).fetchall()
            legacy_fireboard_channel_blacklist = cur.execute(
                "SELECT channelID FROM fireChannelBlacklist WHERE serverID = ?", (server_id,)
            ).fetchall()

            new_fireboard_settings = await session.get(GuildFireboardSettings, server_id)
            if not new_fireboard_settings:
                new_fireboard_settings = GuildFireboardSettings(guild_id=server_id)
                session.add(new_fireboard_settings)

            new_fireboard_settings.global_ignored_roles = [
                r[0] for r in legacy_fireboard_role_blacklist
            ]
            new_fireboard_settings.global_ignored_channels = [
                c[0] for c in legacy_fireboard_channel_blacklist
            ]

            new_fireboard_board = FireboardBoard(
                guild_id=server_id,
                channel_id=channel_id,
                threshold=reaction_amount,
                reaction=emoji,
                ignore_bots=True if ignore_bots == 1 else False,
            )

            session.add(new_fireboard_board)
            await session.flush()

            # Messages
            legacy_messages = cur.execute(
                "SELECT * FROM fireMessages WHERE serverID = ?", (server_id,)
            ).fetchall()
            for message_row in legacy_messages:
                (msg_server_id, msg_id, board_msg_id, _) = message_row

                new_fireboard_message = FireboardMessage(
                    guild_id=msg_server_id,
                    message_id=msg_id,
                    fireboard_message_id=board_msg_id,
                    fireboard_id=new_fireboard_board.id,
                )
                session.add(new_fireboard_message)

    con.close()


async def migrate_server_counters(bot: TitaniumBot):
    con = sqlite3.connect(os.path.join("v1_to_v2", "dbs", "server-counts.db"))
    cur = con.cursor()

    legacy_counters = cur.execute("SELECT * FROM channels").fetchall()

    for row in legacy_counters:
        async with get_session() as session:
            (
                server_id,
                channel_id,
                channel_name,
                counter_type,
            ) = row

            await bot.init_guild(server_id)

            new_counter = ServerCounterChannel(
                id=channel_id,
                guild_id=server_id,
                count_type=counter_type.upper(),
                name=channel_name.replace("$VALUE$", "{value}"),
            )

            session.add(new_counter)
            await session.flush()

    con.close()


async def migrate_v1_to_v2(bot: TitaniumBot, init_db):
    await init_db()

    logging.info("Starting migration from v1 to v2...")

    if input("Migrate Fireboard data? (y/n) [n]: ").lower() == "y":
        await migrate_fireboard(bot)
        logging.info("Migrated Fireboard data.")

    if input("Migrate Server Counter data? (y/n) [n]: ").lower() == "y":
        await migrate_server_counters(bot)
        logging.info("Migrated Server Counter data.")

    logging.info("Migration from v1 to v2 completed.")

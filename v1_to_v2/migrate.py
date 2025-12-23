import logging
import os
import sqlite3
from typing import TYPE_CHECKING

from sqlalchemy.dialects.postgresql import insert

from lib.sql.sql import (
    FireboardBoard,
    FireboardMessage,
    GuildFireboardSettings,
    GuildLeaderboardSettings,
    LeaderboardUserStats,
    OptOutIDs,
    ServerCounterChannel,
    get_session,
)

if TYPE_CHECKING:
    from main import TitaniumBot

"""Scripts for migrating Fireboard data from v1 to v2."""


def extract_emoji_id(emoji: str) -> str:
    """Extract emoji ID from custom emoji format or return as-is for unicode"""
    if emoji.startswith("<") and emoji.endswith(">"):
        return emoji.split(":")[-1].rstrip(">")
    return emoji


async def migrate_fireboard(bot: TitaniumBot):
    with sqlite3.connect(os.path.join("v1_to_v2", "dbs", "fireboard.db")) as con:
        cur = con.cursor()

        legacy_fireboard_settings = cur.execute("SELECT * FROM fireSettings").fetchall()

        for row in legacy_fireboard_settings:
            async with get_session() as session:
                server_id, reaction_amount, emoji, channel_id, ignore_bots = row

                await bot.init_guild(server_id, refresh=False)

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
                    reaction=extract_emoji_id(emoji),
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


async def migrate_alternate_fireboard(bot: TitaniumBot, db_filename: str):
    with sqlite3.connect(os.path.join("v1_to_v2", "dbs", db_filename)) as con:
        cur = con.cursor()

        legacy_fireboard_settings = cur.execute("SELECT * FROM fireSettings").fetchall()

        for row in legacy_fireboard_settings:
            async with get_session() as session:
                server_id, reaction_amount, emoji, channel_id, ignore_bots = row

                await bot.init_guild(server_id, refresh=False)

                new_fireboard_board = FireboardBoard(
                    guild_id=server_id,
                    channel_id=channel_id,
                    threshold=reaction_amount,
                    reaction=extract_emoji_id(emoji),
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


async def migrate_server_counters(bot: TitaniumBot):
    with sqlite3.connect(os.path.join("v1_to_v2", "dbs", "server-counts.db")) as con:
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

                await bot.init_guild(server_id, refresh=False)

                new_counter = ServerCounterChannel(
                    id=channel_id,
                    guild_id=server_id,
                    count_type=counter_type.upper(),
                    name=channel_name.replace("$VALUE$", "{value}"),
                )

                session.add(new_counter)
                await session.flush()


async def migrate_leaderboard(bot: TitaniumBot):
    with sqlite3.connect(os.path.join("v1_to_v2", "dbs", "lb.db")) as con:
        cur = con.cursor()

        tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        tables = [t[0] for t in tables if t[0] not in ("settings", "optOut")]

        opt_out_ids = cur.execute("SELECT * FROM optOut").fetchall()
        async with get_session() as session:
            for (row,) in opt_out_ids:
                opt_out_entry = OptOutIDs(
                    id=int(row),
                )
                session.add(opt_out_entry)

        for table in tables:
            await bot.init_guild(int(table), refresh=False)

            settings_row = cur.execute("SELECT * FROM settings WHERE id = ?", (table,)).fetchone()
            if settings_row:
                (server_id, delete_leavers) = settings_row
                async with get_session() as session:
                    new_settings = await session.get(GuildLeaderboardSettings, int(server_id))

                    if not new_settings:
                        new_settings = GuildLeaderboardSettings(guild_id=int(server_id))
                        session.add(new_settings)

                    new_settings.delete_leavers = True if delete_leavers == 1 else False

            async with get_session() as session:
                legacy_leaderboard_entries = cur.execute(f"SELECT * FROM '{table}'").fetchall()

                for row in legacy_leaderboard_entries:
                    (user_mention, message_count, word_count, attachment_count) = row
                    user_mention: str = user_mention.lstrip("<@").rstrip(">")

                    stmt = insert(LeaderboardUserStats).values(
                        guild_id=int(table),
                        user_id=int(user_mention),
                        xp=0,
                        level=0,
                        message_count=message_count,
                        word_count=word_count,
                        attachment_count=attachment_count,
                    )
                    stmt = stmt.on_conflict_do_nothing()

                    await session.execute(stmt)


async def migrate_v1_to_v2(bot: TitaniumBot, init_db):
    await init_db()

    logging.info("Starting migration from v1 to v2...")

    if input("Migrate Fireboard data? (y/n) [n]: ").lower() == "y":
        await migrate_fireboard(bot)
        logging.info("Migrated Fireboard data.")

    if input("Migrate Server Counter data? (y/n) [n]: ").lower() == "y":
        await migrate_server_counters(bot)
        logging.info("Migrated Server Counter data.")

    if input("Migrate Leaderboard data? (y/n) [n]: ").lower() == "y":
        await migrate_leaderboard(bot)
        logging.info("Migrated Leaderboard data.")

    if input("Migrate alternate fireboard data? (y/n) [n]: ").lower() == "y":
        await migrate_alternate_fireboard(
            bot, input("Enter alternate fireboard database filename: ")
        )
        logging.info("Migrated alternate fireboard data.")

    logging.info("Migration from v1 to v2 completed.")

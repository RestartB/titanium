import json
from typing import TYPE_CHECKING

import discord
import websockets
from discord.ext import commands

if TYPE_CHECKING:
    from main import TitaniumBot


class APIWebsocket(commands.Cog):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot
        # start websocket server in the bot's loop
        self.server_task = self.bot.loop.create_task(self._run_ws_server())

    async def get_fireboard_info(self, server_id: int) -> tuple[list, list, list, list]:
        # … same as before …
        async with self.bot.fireboard_pool.acquire() as sql:
            settings = await sql.fetchone(
                "SELECT * FROM fireSettings WHERE serverID = ?", (server_id,)
            )
            messages = await sql.fetchall(
                "SELECT * FROM fireMessages WHERE serverID = ?", (server_id,)
            )
            bl_ch = await sql.fetchall(
                "SELECT channelID FROM fireChannelBlacklist WHERE serverID = ?",
                (server_id,),
            )
            bl_rl = await sql.fetchall(
                "SELECT roleID FROM fireRoleBlacklist WHERE serverID = ?",
                (server_id,),
            )
        return settings, messages, bl_ch, bl_rl

    async def _run_ws_server(self):
        async def handler(ws) -> None:
            async for raw_msg in ws:
                try:
                    req: dict = json.loads(raw_msg)

                    action = req.get("action")
                    p = req.get("params", {})

                    # mutuals
                    if action == "mutuals":
                        user = await self.bot.fetch_user(p["user_id"])
                        resp = {"mutual_guilds": [g.id for g in user.mutual_guilds]}
                    # user permissions
                    elif action == "user_perms":
                        guild = await self.bot.fetch_guild(p["server_id"])
                        member = await guild.fetch_member(p["user_id"])
                        resp = {"guild_perms": member.guild_permissions.value}
                    # server info
                    elif action == "server_info":
                        guild: discord.Guild | None = self.bot.get_guild(p["server_id"])

                        for channel in guild.channels:
                            print(channel.category.name if channel.category else None)

                        channels = [
                            {
                                "id": c.id,
                                "name": c.name,
                                "type": str(c.type),
                                "position": c.position,
                                "category_id": c.category_id if c.category else None,
                                "category_name": c.category.name
                                if c.category
                                else None,
                            }
                            for c in guild.channels
                        ]

                        print(channels)

                        roles = [
                            {
                                "id": r.id,
                                "name": r.name,
                                "position": r.position,
                                "color": r.color.to_rgb(),
                                "permissions": r.permissions.value,
                            }
                            for r in guild.roles
                        ]
                        resp = {
                            "approximate_member_count": guild.approximate_member_count,
                            "banner": str(guild.banner),
                            "id": guild.id,
                            "icon": str(guild.icon),
                            "name": guild.name,
                            "owner_id": guild.owner_id,
                            "unavailable": guild.unavailable,
                            "channels": channels,
                            "roles": roles,
                        }
                    # fireboard info
                    elif action == "fireboard_info":
                        (
                            settings,
                            messages,
                            bl_ch,
                            bl_rl,
                        ) = await self.get_fireboard_info(p["server_id"])
                        total_reacts = sum(m[3] or 0 for m in (messages or []))
                        if settings is None:
                            resp = {"enabled": False}
                        else:
                            resp = {
                                "enabled": True,
                                "config": {
                                    "reaction_requirement": settings[1],
                                    "emoji": settings[2],
                                    "channel_id": settings[3],
                                    "ignore_bots": settings[4],
                                },
                                "amount": {
                                    "messages": len(messages or []),
                                    "reactions": total_reacts,
                                },
                                "blacklist": {
                                    "channels": [c[0] for c in bl_ch],
                                    "roles": [r[0] for r in bl_rl],
                                },
                            }
                    else:
                        resp = {"error": "Unknown action"}
                except discord.Forbidden:
                    resp = {"error_code": 403, "error": "Forbidden"}
                except discord.NotFound:
                    resp = {"error_code": 404, "error": "Server not found"}
                except discord.HTTPException:
                    resp = {"error_code": 500, "error": "Discord Error"}
                # except Exception as e:
                #     resp = {"error_code": 500, "error": str(e)}
                #     traceback.print_exc()

                await ws.send(json.dumps(resp))

        server = await websockets.serve(handler, "127.0.0.1", 8765)
        await server.wait_closed()

    def cog_unload(self):
        # shut down the ws server when the cog is unloaded
        self.server_task.cancel()


async def setup(bot: "TitaniumBot"):
    await bot.add_cog(APIWebsocket(bot))

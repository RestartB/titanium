import logging
import re
from datetime import time, timezone
from typing import TYPE_CHECKING

import discord
from discord import ButtonStyle, Interaction, app_commands
from discord.ext import commands, tasks
from discord.ui import Button, View, button
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from lib.helpers.cache import get_or_fetch_member
from lib.sql.sql import RepAddHistory, UserRep, get_session
from lib.views.pagination import RepReloadPageView

if TYPE_CHECKING:
    from main import TitaniumBot


class RepView(View):
    def __init__(
        self,
        bot: TitaniumBot,
        target_member: discord.Member,
        timeout: float = 60.0,
    ):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.target_member = target_member
        self.original_message: discord.Message | None

    @button(label="Give Rep", emoji="➕", style=ButtonStyle.green)
    async def give_rep(self, interaction: Interaction["TitaniumBot"], button: Button):
        if not interaction.guild_id:
            return

        await interaction.response.defer(ephemeral=True)

        guild_config = await self.bot.fetch_guild_config(interaction.guild_id)
        if not guild_config or not guild_config.rep_enabled:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Rep Disabled",
                description="The rep system is disabled in this server. Ask a server admin to turn it on using the `/settings` command or the Titanium Dashboard.",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        async with get_session() as session:
            session.add(
                RepAddHistory(
                    user_id=interaction.user.id,
                    target_id=self.target_member.id,
                    guild_id=interaction.guild_id,
                    time=interaction.created_at,
                )
            )

            stmt = insert(UserRep).values(
                guild_id=interaction.guild_id,
                user_id=self.target_member.id,
                rep=1,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["guild_id", "user_id"],
                set_={
                    "rep": UserRep.rep + 1,
                },
            ).returning(UserRep)

            rep = (await session.execute(stmt)).scalar_one()

        await interaction.followup.send(
            embed=discord.Embed(
                title=f"{self.bot.success_emoji} Done",
                description=f"**1 rep** given to {self.target_member.mention} (`{rep.rep}` rep total)",
                colour=discord.Colour.green(),
            ),
            ephemeral=True,
        )

    @button(emoji="🗑️", style=ButtonStyle.grey)
    async def delete_button(self, interaction: Interaction["TitaniumBot"], button: Button):
        if not self.original_message:
            return

        await interaction.response.defer(ephemeral=True)

        if (
            self.original_message.author.id != interaction.user.id
            or not interaction.permissions.manage_messages
        ):
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Not Allowed",
                description="You didn't send this message. Only the message author or users with Manage Message permissions can delete the rep hint.",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        await interaction.delete_original_response()


class RepCog(commands.Cog):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.logger = logging.getLogger("rep")

    # Snapshot task
    @tasks.loop(time=time(hour=0, minute=0, tzinfo=timezone.utc))
    async def take_daily_snapshots(self) -> None:
        await self.bot.wait_until_ready()

        guild_ids = []
        for guild in self.bot.guilds:
            config = await self.bot.fetch_guild_config(guild.id, create_config=False)
            if not config or not config.rep_enabled:
                continue
            guild_ids.append(guild.id)

        for guild_id in guild_ids:
            async with get_session() as session:
                stmt = (
                    select(UserRep).where(UserRep.guild_id == guild_id).order_by(UserRep.rep.desc())
                )
                result = await session.execute(stmt)
                all_stats = result.scalars().all()

                for i, user_stat in enumerate(all_stats, start=1):
                    snapshots = user_stat.daily_snapshots or []
                    snapshots.append(i)

                    user_stat.daily_snapshots = snapshots[-30:]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # no reply / invalid reference / opted out - ignore
        if (
            not message.guild
            or not message.reference
            or not message.reference.resolved
            or isinstance(message.reference.resolved, discord.DeletedReferencedMessage)
            or message.reference.type != discord.MessageReferenceType.reply
            or message.author.id in self.bot.opt_out
        ):
            self.logger.debug("ignoring message")
            return

        # base settings
        guild_config = await self.bot.fetch_guild_config(message.guild.id)
        if (
            not guild_config
            or not guild_config.rep_enabled
            or not guild_config.rep_settings
            or not guild_config.rep_settings.rep_hint
        ):
            self.logger.debug(f"rep disabled in {message.guild.id}")
            return

        matches = []
        for check_word in ["thank you", "thx", "thanks"]:
            pattern = r"\b" + re.escape(check_word) + r"\b"
            matches.extend(re.findall(pattern, message.content, flags=re.IGNORECASE))

        if not matches:
            self.logger.debug(f"no matches ({message.content})")
            return

        referenced_message = message.reference.resolved
        referenced_author = referenced_message.author
        if isinstance(referenced_author, discord.User):
            target_member = await get_or_fetch_member(self.bot, message.guild, referenced_author.id)
            if not target_member:
                self.logger.debug(f"couldn't get user: {referenced_author.id}")
                return
        else:
            target_member = referenced_author

        if target_member.id in self.bot.opt_out:
            self.logger.debug(f"target has opted out: {target_member.id}")
            return

        view = RepView(bot=self.bot, target_member=target_member)
        await message.reply(view=view, mention_author=False, delete_after=60)

    # Member leave event
    @commands.Cog.listener()
    async def on_raw_member_remove(self, payload: discord.RawMemberRemoveEvent) -> None:
        guild_settings = await self.bot.fetch_guild_config(payload.guild_id)
        if (
            not guild_settings
            or not guild_settings.rep_settings
            or not guild_settings.rep_settings.delete_leavers
        ):
            return

        async with get_session() as session:
            stmt = (
                select(UserRep)
                .where(
                    UserRep.guild_id == payload.guild_id,
                    UserRep.user_id == payload.user.id,
                )
                .limit(1)
            )
            result = await session.execute(stmt)
            user_stats = result.scalar_one_or_none()

            if user_stats:
                await session.delete(user_stats)

            stmt = select(RepAddHistory).where(
                RepAddHistory.guild_id == payload.guild_id,
                RepAddHistory.target_id == payload.user.id,
            )
            await session.execute(stmt)

    @commands.hybrid_group(
        name="rep", fallback="view", description="Set, add, remove, and view rep for users."
    )
    @commands.guild_only()
    @app_commands.guild_install()
    @commands.cooldown(1, 3)
    async def rep_group(self, ctx: commands.Context["TitaniumBot"], member: discord.Member) -> None:
        if not ctx.guild:
            raise ValueError("Guild only command but no guild available")

        await ctx.defer()
        user = member or ctx.author

        if user.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="This user has opted out of optional data collection and cannot use rep features.",
                colour=discord.Colour.red(),
            )
            await ctx.reply(embed=embed)
            return

        async with get_session() as session:
            stmt = (
                select(UserRep)
                .where(
                    UserRep.guild_id == ctx.guild.id,
                    UserRep.user_id == user.id,
                )
                .limit(1)
            )
            result = await session.execute(stmt)
            user_stats = result.scalar_one_or_none()

            given_rep = 0
            if user != ctx.author:
                stmt = (
                    select(func.count())
                    .select_from(RepAddHistory)
                    .where(
                        RepAddHistory.guild_id == ctx.guild.id,
                        RepAddHistory.user_id == ctx.author.id,
                        RepAddHistory.target_id == user.id,
                    )
                )
                given_rep = (await session.execute(stmt)).scalar() or 0

            if not user_stats:
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} No Data",
                    description=f"**{user.display_name}** has no recorded rep.",
                    colour=discord.Colour.red(),
                )
                await ctx.reply(embed=embed)
                return

            embed = discord.Embed(
                title="Rep Info",
                description=f"{self.bot.info_emoji} You have given this user `{given_rep:,}` rep."
                if user != ctx.author
                else None,
                colour=discord.Colour.light_grey(),
            )

            embed.add_field(name="Rep", value=f"{user_stats.rep:,}", inline=True)

            embed.set_author(
                name=f"@{user.name}",
                icon_url=user.display_avatar.url,
            )
            embed.set_footer(
                text=f"@{ctx.author.name}",
                icon_url=ctx.author.display_avatar.url,
            )
            embed.set_thumbnail(
                url=user.display_avatar.url,
            )

            await ctx.reply(embed=embed)

    # Leaderboard command
    @rep_group.command(
        name="leaderboard",
        aliases=["lb", "top"],
        description="View the rep leaderboard for this server.",
    )
    @commands.cooldown(1, 5)
    async def rep_leaderboard(self, ctx: commands.Context["TitaniumBot"]):
        if not ctx.guild:
            return

        await ctx.defer()

        async with get_session() as session:
            stmt = (
                select(UserRep)
                .where(UserRep.guild_id == ctx.guild.id, UserRep.rep != 0)
                .order_by(UserRep.rep.desc())
                .limit(1000)
            )
            result = await session.execute(stmt)
            top_users = result.scalars().all()

            if not top_users:
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} No Data",
                    description="No users have any rep yet.",
                    colour=discord.Colour.red(),
                )
                await ctx.reply(embed=embed)
                return

            pages = [
                discord.Embed(
                    title="Rep Leaderboard",
                    description="\n".join(
                        [
                            f"{i * 15 + x}. <@{entry.user_id}> - `{entry.rep:,}`"
                            for x, entry in enumerate(chunk, start=1)
                        ]
                    ),
                    colour=discord.Colour.light_grey(),
                ).set_author(
                    name=ctx.guild.name,
                    icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
                )
                for i, chunk in enumerate(discord.utils.as_chunks(top_users, 15))
            ]

            pages[0].set_footer(
                text=f"Controlling: @{ctx.author.name}"
                if len(pages) > 1
                else f"@{ctx.author.name}",
                icon_url=ctx.author.display_avatar.url,
            )

            view = RepReloadPageView(embeds=pages, timeout=240, title="Rep Leaderboard")
            await ctx.reply(embed=pages[0], view=view)

    @rep_group.command(name="add", aliases=["plus"], description="Give a rep point to a user.")
    @commands.cooldown(1, 3)
    async def add_rep(self, ctx: commands.Context["TitaniumBot"], user: discord.Member) -> None:
        if not ctx.guild:
            raise ValueError("Guild only command but no guild available")

        await ctx.defer()

        if user.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="This user has opted out of optional data collection and cannot use rep features.",
                colour=discord.Colour.red(),
            )
            await ctx.reply(embed=embed)
            return

        guild_config = await self.bot.fetch_guild_config(ctx.guild.id)
        if not guild_config or not guild_config.rep_settings:
            raise ValueError("No guild config returned")

        if not guild_config.rep_enabled:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Disabled",
                description="The rep system is disabled in this server.",
                colour=discord.Colour.red(),
            )
            await ctx.reply(embed=embed)
            return

        async with get_session() as session:
            session.add(
                RepAddHistory(
                    user_id=ctx.author.id,
                    target_id=user.id,
                    guild_id=ctx.guild.id,
                )
            )

            stmt = insert(UserRep).values(
                guild_id=ctx.guild.id,
                user_id=user.id,
                rep=1,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["guild_id", "user_id"],
                set_={
                    "rep": UserRep.rep + 1,
                },
            ).returning(UserRep)

            rep = (await session.execute(stmt)).scalar_one()

        await ctx.reply(
            embed=discord.Embed(
                title=f"{self.bot.success_emoji} Done",
                description=f"**1 rep** given to {user.mention} (`{rep.rep:,}` rep total)",
                colour=discord.Colour.green(),
            ),
        )

    @rep_group.command(
        name="remove",
        aliases=["minus"],
        description="Take away rep points that you gave to a user.",
    )
    @commands.cooldown(1, 3)
    async def remove_rep(
        self, ctx: commands.Context["TitaniumBot"], user: discord.Member, amount: int
    ) -> None:
        if not ctx.guild:
            raise ValueError("Guild only command but no guild available")

        await ctx.defer()

        if user.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="This user has opted out of optional data collection and cannot use rep features.",
                colour=discord.Colour.red(),
            )
            await ctx.reply(embed=embed)
            return

        guild_config = await self.bot.fetch_guild_config(ctx.guild.id)
        if not guild_config or not guild_config.rep_settings:
            raise ValueError("No guild config returned")

        if not guild_config.rep_settings.allow_rep_remove:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Disabled",
                description="Removing user rep is disabled in this server.",
                colour=discord.Colour.red(),
            )
            await ctx.reply(embed=embed)
            return

        async with get_session() as session:
            stmt = (
                select(RepAddHistory)
                .where(
                    RepAddHistory.guild_id == ctx.guild.id,
                    RepAddHistory.user_id == ctx.author.id,
                    RepAddHistory.target_id == user.id,
                )
                .limit(amount)
            )
            history = list((await session.execute(stmt)).scalars())

            if not history:
                await ctx.reply(
                    embed=discord.Embed(
                        title=f"{self.bot.error_emoji} Nothing to Remove",
                        description="You haven't given this user any rep before, so there is nothing to remove.",
                        colour=discord.Colour.red(),
                    ),
                )
                return

            if len(history) != amount:
                await ctx.reply(
                    embed=discord.Embed(
                        title=f"{self.bot.error_emoji} Too Much Rep",
                        description=f"You have only given this user `{len(history):,}` rep, so you can't remove `{amount - len(history):,}` extra rep.",
                        colour=discord.Colour.red(),
                    ),
                )
                return

            for history_item in history:
                await session.delete(history_item)

            stmt = insert(UserRep).values(
                guild_id=ctx.guild.id,
                user_id=user.id,
                rep=0,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["guild_id", "user_id"],
                set_={
                    "rep": UserRep.rep - amount,
                },
            ).returning(UserRep)

            rep = (await session.execute(stmt)).scalar_one()

        await ctx.reply(
            embed=discord.Embed(
                title=f"{self.bot.success_emoji} Done",
                description=f"**{amount:,} rep** removed from {user.mention} (`{rep.rep:,}` rep total)",
                colour=discord.Colour.green(),
            ),
        )

    @rep_group.command(name="set", description="Manually set the rep of a user.")
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 3)
    async def set_rep(
        self, ctx: commands.Context["TitaniumBot"], user: discord.Member, amount: int
    ) -> None:
        if not ctx.guild:
            raise ValueError("Guild only command but no guild available")

        await ctx.defer()

        if user.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="This user has opted out of optional data collection and cannot use rep features.",
                colour=discord.Colour.red(),
            )
            await ctx.reply(embed=embed)
            return

        async with get_session() as session:
            stmt = insert(UserRep).values(
                guild_id=ctx.guild.id,
                user_id=user.id,
                rep=amount,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["guild_id", "user_id"],
                set_={"rep": amount},
            ).returning(UserRep)

            await session.execute(stmt)

        await ctx.reply(
            embed=discord.Embed(
                title=f"{self.bot.success_emoji} Done",
                description=f"Set {user.mention}'s rep to `{amount:,}`.",
                colour=discord.Colour.green(),
            ),
        )


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(RepCog(bot))

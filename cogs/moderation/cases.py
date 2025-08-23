from typing import TYPE_CHECKING

from discord import Color, Embed, Message, User, app_commands
from discord.ext import commands

from lib.cases.case_manager import CaseNotFoundException, GuildModCaseManager
from lib.embeds.cases import case_deleted, case_embed, case_not_found
from lib.embeds.general import cancelled
from lib.hybrid_adapters import defer, stop_loading
from lib.sql import get_session
from lib.views.confirm import ConfirmView

if TYPE_CHECKING:
    from main import TitaniumBot


class ModerationCasesCog(commands.Cog):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="cases", aliases=["warns"], description="View your moderation cases."
    )
    @commands.guild_only()
    @app_commands.describe(
        user="The user to search for, you can only provide this if you have the 'Manage Server' permission."
    )
    async def cases(
        self, ctx: commands.Context[commands.Bot], user: User | None = None
    ) -> None | Message:
        if not ctx.guild or not self.bot.user or isinstance(ctx.author, User):
            return

        await defer(self.bot, ctx)

        if user:
            if ctx.channel.permissions_for(ctx.author).manage_guild:
                pass
            else:
                return await ctx.reply(
                    embed=Embed(
                        title=f"{str(self.bot.error_emoji)} Permission Denied",
                        description="You do not have permission to view cases for other users. Please ensure you have the 'Manage Server' permission.",
                        color=Color.red(),
                    )
                )
        else:
            pass

    @commands.hybrid_group(
        name="case", fallback="view", description="View and manage moderation cases."
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(case_id="The case ID to search for.")
    async def case_group(
        self, ctx: commands.Context[commands.Bot], case_id: int
    ) -> None | Message:
        if not ctx.guild or not self.bot.user:
            return

        await defer(self.bot, ctx)

        try:
            async with get_session() as session:
                case = await GuildModCaseManager(ctx.guild, session).get_case_by_id(
                    case_id
                )

            # Get creator
            creator = self.bot.get_user(case.creator_user_id)  # pyright: ignore[reportArgumentType]

            if not creator:
                creator = case.creator_user_id

            # Get target
            target = self.bot.get_user(case.user_id)  # pyright: ignore[reportArgumentType]

            if not target:
                target = case.user_id

            await ctx.reply(embed=case_embed(self.bot, case, creator, target))
        except CaseNotFoundException:
            return await ctx.reply(embed=case_not_found(self.bot, str(case_id)))
        finally:
            await stop_loading(self.bot, ctx)

    @case_group.command(name="delete", description="Delete a case by its ID.")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(case_id="The case ID to delete.")
    async def view_case(
        self, ctx: commands.Context[commands.Bot], case_id: int
    ) -> None | Message:
        if not ctx.guild or not self.bot.user:
            return

        await defer(self.bot, ctx)

        try:
            async with get_session() as session:
                case_manager = GuildModCaseManager(ctx.guild, session)
                case = await case_manager.get_case_by_id(case_id)

                if not case:
                    return await ctx.reply(embed=case_not_found(self.bot, str(case_id)))

                # Get creator
                creator = self.bot.get_user(case.creator_user_id)  # pyright: ignore[reportArgumentType]

                if not creator:
                    creator = case.creator_user_id

                # Get target
                target = self.bot.get_user(case.user_id)  # pyright: ignore[reportArgumentType]

                if not target:
                    target = case.user_id

                embeds = [case_embed(self.bot, case, creator, target)]
                embeds.append(
                    Embed(
                        title="Are you sure?",
                        description="This will delete the case and cannot be undone.",
                        color=Color.red(),
                    )
                )

                view = ConfirmView(self.bot)

                await ctx.reply(
                    embeds=embeds,
                    view=view,
                )
                await stop_loading(self.bot, ctx)
                await view.wait()

                if not view.value:
                    return await ctx.send(embed=cancelled(self.bot))

                await case_manager.delete_case(case_id)
                await ctx.send(embed=case_deleted(self.bot, case_id))
        finally:
            await stop_loading(self.bot, ctx)


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(ModerationCasesCog(bot))

from typing import TYPE_CHECKING, Sequence

from discord import Colour, Embed, Member, Message, User, app_commands
from discord.ext import commands

from lib.classes.case_manager import CaseNotFoundException, GuildModCaseManager
from lib.embeds.cases import case_deleted, case_embed, case_not_found, cases
from lib.embeds.general import cancelled
from lib.helpers.hybrid_adapters import defer, stop_loading
from lib.sql.sql import ModCase, get_session
from lib.views.confirm import ConfirmView
from lib.views.pagination import PaginationView

if TYPE_CHECKING:
    from main import TitaniumBot


class ModerationCasesCog(commands.Cog, name="Cases", description="Manage moderation cases."):
    """Moderation case management commands"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    async def _build_embeds(
        self, cases_list: Sequence[ModCase], target: User | Member, user: User | Member
    ) -> list[Embed]:
        total_pages = len(cases_list) // 5 + (1 if len(cases_list) % 5 > 0 else 0)

        if total_pages == 0:
            return []

        return [
            cases(
                self.bot,
                cases_list[(page - 1) * 5 : page * 5],
                len(cases_list),
                page,
                total_pages,
                target,
                user,
            )
            for page in range(1, total_pages + 1)
        ]

    @commands.hybrid_command(
        name="cases", aliases=["warns"], description="View your moderation cases."
    )
    @commands.guild_only()
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.describe(
        user="The user to search for, you can only provide this if you have the 'Manage Server' permission."
    )
    async def cases(
        self, ctx: commands.Context["TitaniumBot"], user: User | None = None
    ) -> None | Message:
        if not ctx.guild or not self.bot.user or isinstance(ctx.author, User):
            return

        await defer(ctx)

        try:
            async with get_session() as session:
                case_manager = GuildModCaseManager(self.bot, ctx.guild, session)

                if user:
                    if ctx.channel.permissions_for(ctx.author).manage_guild:
                        cases_list = await case_manager.get_cases_by_user(user.id)
                        embeds = await self._build_embeds(cases_list, target=user, user=ctx.author)

                        if embeds == []:
                            return await ctx.reply(
                                embed=Embed(
                                    title=f"{self.bot.error_emoji} No Cases Found",
                                    description="This user has no moderation cases.",
                                    colour=Colour.red(),
                                )
                            )

                        if len(embeds) > 1:
                            view = PaginationView(embeds, 120)
                            await ctx.reply(embed=embeds[0], view=view)
                        else:
                            await ctx.reply(embed=embeds[0])
                    else:
                        return await ctx.reply(
                            embed=Embed(
                                title=f"{str(self.bot.error_emoji)} Permission Denied",
                                description="You do not have permission to view cases for other users. Please ensure you have the `Manage Server` permission.",
                                colour=Colour.red(),
                            )
                        )
                else:
                    cases_list = await case_manager.get_cases_by_user(ctx.author.id)
                    embeds = await self._build_embeds(cases_list, ctx.author, ctx.author)

                    if embeds == []:
                        return await ctx.reply(
                            embed=Embed(
                                title=f"{self.bot.error_emoji} No Cases Found",
                                description="You have no moderation cases.",
                                colour=Colour.red(),
                            )
                        )

                    if len(embeds) > 1:
                        view = PaginationView(embeds, 120)
                        await ctx.reply(embed=embeds[0], view=view)
                    else:
                        await ctx.reply(embed=embeds[0])
        finally:
            await stop_loading(ctx)

    @commands.hybrid_group(
        name="case", fallback="view", description="View and manage moderation cases."
    )
    @commands.guild_only()
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(case_id="The case ID to search for.")
    async def case_group(
        self, ctx: commands.Context["TitaniumBot"], case_id: str
    ) -> None | Message:
        if not ctx.guild or not self.bot.user:
            return

        await defer(ctx)

        try:
            async with get_session() as session:
                case = await GuildModCaseManager(self.bot, ctx.guild, session).get_case_by_id(
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
            await stop_loading(ctx)

    @case_group.command(name="delete", description="Delete a case by its ID.")
    @commands.guild_only()
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(case_id="The case ID to delete.")
    async def view_case(self, ctx: commands.Context["TitaniumBot"], case_id: str) -> None | Message:
        if not ctx.guild or not self.bot.user:
            return

        await defer(ctx)

        try:
            async with get_session() as session:
                case_manager = GuildModCaseManager(self.bot, ctx.guild, session)
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
                        title=f"{self.bot.warn_emoji} Are you sure?",
                        description="This will delete the case and cannot be undone.",
                        colour=Colour.orange(),
                    )
                )

                view = ConfirmView(self.bot)

                msg = await ctx.reply(
                    embeds=embeds,
                    view=view,
                )
                await stop_loading(ctx)
                await view.wait()

                if not view.value:
                    return await msg.edit(embed=cancelled(self.bot), view=None)

                await case_manager.delete_case(case_id)
                await msg.edit(embed=case_deleted(self.bot, case_id), view=None)
        finally:
            await stop_loading(ctx)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(ModerationCasesCog(bot))

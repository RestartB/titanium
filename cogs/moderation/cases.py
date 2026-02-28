import importlib
from typing import TYPE_CHECKING, Sequence

from discord import AllowedMentions, ButtonStyle, Colour, Embed, Member, Message, User, app_commands
from discord.ext import commands
from discord.ui import Button, View

import lib.classes.case_manager as case_managers
import lib.embeds.cases as case_embeds
import lib.embeds.general as general_embeds
import lib.views.cases as case_views
import lib.views.confirm as confirm_views
import lib.views.pagination as pagination_views
from lib.helpers.global_alias import add_global_aliases, global_alias
from lib.helpers.hybrid_adapters import __stop_loading, defer
from lib.sql.sql import ModCase, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class ModerationCasesCog(commands.Cog, name="Cases", description="Manage moderation cases."):
    """Moderation case management commands"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        add_global_aliases(self, bot)

    async def cog_load(self) -> None:
        importlib.reload(case_managers)
        importlib.reload(case_embeds)
        importlib.reload(general_embeds)
        importlib.reload(case_views)
        importlib.reload(confirm_views)
        importlib.reload(pagination_views)

    async def _build_embeds(
        self, cases_list: Sequence[ModCase], target: User | Member, user: User | Member
    ) -> list[Embed]:
        total_pages = len(cases_list) // 5 + (1 if len(cases_list) % 5 > 0 else 0)

        if total_pages == 0:
            return []

        return [
            case_embeds.cases(
                self.bot,
                cases_list[(page - 1) * 5 : page * 5],
                len(cases_list),
                target,
                user,
            )
            for page in range(1, total_pages + 1)
        ]

    @commands.hybrid_command(
        name="cases", aliases=["warns", "strikes"], description="View your moderation cases."
    )
    @commands.guild_only()
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.describe(
        user="The user to search for. You can only search for other users if you have the 'Manage Server' permission."
    )
    async def cases(
        self, ctx: commands.Context["TitaniumBot"], user: User | None = None
    ) -> None | Message:
        if not ctx.guild or not self.bot.user or isinstance(ctx.author, User):
            return

        async with defer(ctx):
            async with get_session() as session:
                case_manager = case_managers.GuildModCaseManager(self.bot, ctx.guild, session)

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

                        embeds[0].set_footer(
                            text=f"Controlling: @{ctx.author.name}"
                            if len(embeds) > 1
                            else f"@{ctx.author.name}",
                            icon_url=ctx.author.display_avatar.url,
                        )

                        if len(embeds) > 1:
                            view = pagination_views.PaginationView(embeds, 120)
                            await ctx.reply(embed=embeds[0], view=view)
                        else:
                            await ctx.reply(embed=embeds[0])
                    else:
                        return await ctx.reply(
                            embed=Embed(
                                title=f"{self.bot.error_emoji} Permission Denied",
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

                    embeds[0].set_footer(
                        text=f"Controlling: @{ctx.author.name}"
                        if len(embeds) > 1
                        else f"@{ctx.author.name}",
                        icon_url=ctx.author.display_avatar.url,
                    )

                    if len(embeds) > 1:
                        view = pagination_views.PaginationView(embeds, 120)
                        await ctx.reply(embed=embeds[0], view=view)
                    else:
                        await ctx.reply(embed=embeds[0])

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

        async with defer(ctx):
            try:
                async with get_session() as session:
                    case = await case_managers.GuildModCaseManager(
                        self.bot, ctx.guild, session
                    ).get_case_by_id(case_id)
            except case_managers.CaseNotFoundException:
                return await ctx.reply(embed=case_embeds.case_not_found(self.bot, case_id))

            # Get creator
            creator = self.bot.get_user(case.creator_user_id)

            if not creator:
                creator = case.creator_user_id

            # Get target
            target = self.bot.get_user(case.user_id)

            if not target:
                target = case.user_id

            view = View()

            if (
                case.comments
                and isinstance(ctx.author, Member)
                and ctx.author.guild_permissions.manage_guild
            ):
                view.add_item(case_views.ViewCommentsButton(case=case))

            view.add_item(
                Button(
                    label="View in browser",
                    url=f"https://dash.titaniumbot.me/guild/{case.guild_id}/moderation/cases/{case.id}",
                    style=ButtonStyle.link,
                )
            )

            await ctx.reply(
                embed=case_embeds.case_embed(self.bot, case, creator, target), view=view
            )

    @case_group.command(name="comments", description="View comments on a case.")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(case_id="The case ID to search for.")
    async def case_comments(
        self, ctx: commands.Context["TitaniumBot"], case_id: str
    ) -> None | Message:
        if not ctx.guild or not self.bot.user:
            return

        async with defer(ctx):
            try:
                async with get_session() as session:
                    case = await case_managers.GuildModCaseManager(
                        self.bot, ctx.guild, session
                    ).get_case_by_id(case_id)
            except case_managers.CaseNotFoundException:
                return await ctx.reply(embed=case_embeds.case_not_found(self.bot, case_id))

            pages: list[case_views.CommentPageContainer] = []
            current_page = []

            for comment in case.comments:
                current_page.append(comment)

                if len(current_page) % 5 != 0:
                    continue

                container = case_views.CommentPageContainer(self.bot, case, current_page)
                pages.append(container)
                current_page = []

            if current_page:
                container = case_views.CommentPageContainer(self.bot, case, current_page)
                pages.append(container)

            layout = pagination_views.PaginationV2View(pages)
            await ctx.reply(view=layout, allowed_mentions=AllowedMentions.none())

    @case_group.command(name="addcomment", description="Add a comment to a case.")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        case_id="The case ID to add a comment to.", comment="The comment to add."
    )
    async def case_add_comment(
        self,
        ctx: commands.Context["TitaniumBot"],
        case_id: str,
        *,
        comment: commands.Range[str, 1, 1000],
    ) -> None | Message:
        if not ctx.guild or not self.bot.user:
            return

        if not isinstance(ctx.author, Member):
            return await ctx.reply(embed=general_embeds.guild_only(self.bot))

        async with defer(ctx):
            try:
                async with get_session() as session:
                    case = await case_managers.GuildModCaseManager(
                        self.bot, ctx.guild, session
                    ).get_case_by_id(case_id)

                    await case.add_comment(
                        member=ctx.author, content=comment, bot=self.bot, guild=ctx.guild
                    )
            except case_managers.CaseNotFoundException:
                return await ctx.reply(embed=case_embeds.case_not_found(self.bot, str(case_id)))

            embed = Embed(
                title=f"{self.bot.success_emoji} Added Comment",
                description=f"Added your comment to `{case.id}`.",
                colour=Colour.green(),
            )

            await ctx.reply(embed=embed)

    @case_group.command(name="delete", description="Delete a case by its ID.")
    @global_alias("deletecase")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(case_id="The case ID to delete.")
    async def view_case(self, ctx: commands.Context["TitaniumBot"], case_id: str) -> None | Message:
        if not ctx.guild or not self.bot.user:
            return

        async with defer(ctx):
            async with get_session() as session:
                case_manager = case_managers.GuildModCaseManager(self.bot, ctx.guild, session)
                case = await case_manager.get_case_by_id(case_id)

                if not case:
                    return await ctx.reply(embed=case_embeds.case_not_found(self.bot, str(case_id)))

                # Get creator
                creator = self.bot.get_user(case.creator_user_id)  # pyright: ignore[reportArgumentType]

                if not creator:
                    creator = case.creator_user_id

                # Get target
                target = self.bot.get_user(case.user_id)  # pyright: ignore[reportArgumentType]

                if not target:
                    target = case.user_id

                embeds = [case_embeds.case_embed(self.bot, case, creator, target)]
                embeds.append(
                    Embed(
                        title=f"{self.bot.warn_emoji} Are you sure?",
                        description="This will delete the case and cannot be undone.",
                        colour=Colour.orange(),
                    )
                )

                view = confirm_views.ConfirmView(self.bot)
                msg = await ctx.reply(
                    embeds=embeds,
                    view=view,
                )

                await __stop_loading(ctx)
                await view.wait()

                if not view.value:
                    return await msg.edit(embed=general_embeds.cancelled(self.bot), view=None)

                await case_manager.delete_case(case_id)
                await msg.edit(embed=case_embeds.case_deleted(self.bot, case_id), view=None)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(ModerationCasesCog(bot))

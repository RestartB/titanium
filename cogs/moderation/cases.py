from typing import TYPE_CHECKING, Sequence

from discord import AllowedMentions, ButtonStyle, Colour, Embed, Member, Message, User, app_commands
from discord.ext import commands
from discord.ui import Button, View

import lib.embeds.cases as case_embeds
from lib.classes.case_manager import CaseNotFoundException, GuildModCaseManager
from lib.embeds.general import cancelled, guild_only
from lib.helpers.global_alias import add_global_aliases, global_alias, remove_global_aliases
from lib.helpers.hybrid import _defer, _stop_loading, defer
from lib.sql.sql import ModCase, get_session
from lib.views.cases import CommentPageContainer, ViewCommentsButton
from lib.views.confirm import ConfirmView
from lib.views.pagination import PaginationV2View, PaginationView

if TYPE_CHECKING:
    from main import TitaniumBot


class ModerationCasesCog(commands.Cog, name="Cases", description="Manage moderation cases."):
    """Moderation case management commands"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        add_global_aliases(self, bot)

    async def cog_unload(self) -> None:
        remove_global_aliases(self, self.bot)

    async def cog_check(self, ctx: commands.Context["TitaniumBot"]) -> bool:
        ephemeral = bool(ctx.interaction and getattr(ctx.interaction.namespace, "ephemeral", False))
        await _defer(ctx, ephemeral=ephemeral)

        if not ctx.guild:
            return False

        config = await self.bot.fetch_guild_config(ctx.guild.id)
        if not config or not config.moderation_enabled:
            await ctx.reply(
                ephemeral=ephemeral,
                embed=Embed(
                    colour=Colour.red(),
                    title=f"{self.bot.error_emoji} Moderation Disabled",
                    description="The moderation module is disabled. Ask a server admin to turn it on using the `/settings` command or the Titanium Dashboard.",
                ),
            )
            await _stop_loading(ctx)
            return False

        return True

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
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @commands.guild_only()
    @app_commands.describe(
        user="The user to search for. You can only search for other users if you have a moderation permission.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @commands.cooldown(1, 5)
    async def cases(
        self,
        ctx: commands.Context["TitaniumBot"],
        user: User | None = None,
        ephemeral: bool = False,
    ) -> None | Message:
        if not ctx.guild or not self.bot.user or isinstance(ctx.author, User):
            return

        async with defer(ctx, stop_only=True):
            async with get_session() as session:
                case_manager = GuildModCaseManager(self.bot, ctx.guild, session)

                if user:
                    if (
                        not ctx.author.guild_permissions.kick_members
                        and not ctx.author.guild_permissions.ban_members
                        and not ctx.author.guild_permissions.moderate_members
                    ):
                        return await ctx.reply(
                            ephemeral=ephemeral,
                            embed=Embed(
                                title=f"{self.bot.error_emoji} Permission Denied",
                                description="You do not have permission to view cases for other users. Please ensure you have the Kick Members, Ban Members or Timeout Members permission.",
                                colour=Colour.red(),
                            ),
                        )

                    cases_list = await case_manager.get_cases_by_user(user.id)
                    embeds = await self._build_embeds(cases_list, target=user, user=ctx.author)

                    if embeds == []:
                        return await ctx.reply(
                            ephemeral=ephemeral,
                            embed=Embed(
                                title=f"{self.bot.error_emoji} No Cases Found",
                                description="This user has no moderation cases.",
                                colour=Colour.red(),
                            ),
                        )

                    embeds[0].set_footer(
                        text=f"Controlling: @{ctx.author.name}"
                        if len(embeds) > 1
                        else f"@{ctx.author.name}",
                        icon_url=ctx.author.display_avatar.url,
                    )

                    if len(embeds) > 1:
                        view = PaginationView(embeds, 120)
                        await ctx.reply(ephemeral=ephemeral, embed=embeds[0], view=view)
                    else:
                        await ctx.reply(ephemeral=ephemeral, embed=embeds[0])
                else:
                    cases_list = await case_manager.get_cases_by_user(ctx.author.id)
                    embeds = await self._build_embeds(cases_list, ctx.author, ctx.author)

                    if embeds == []:
                        return await ctx.reply(
                            ephemeral=ephemeral,
                            embed=Embed(
                                title=f"{self.bot.error_emoji} No Cases Found",
                                description="You have no moderation cases.",
                                colour=Colour.red(),
                            ),
                        )

                    embeds[0].set_footer(
                        text=f"Controlling: @{ctx.author.name}"
                        if len(embeds) > 1
                        else f"@{ctx.author.name}",
                        icon_url=ctx.author.display_avatar.url,
                    )

                    if len(embeds) > 1:
                        view = PaginationView(embeds, 120)
                        await ctx.reply(ephemeral=ephemeral, embed=embeds[0], view=view)
                    else:
                        await ctx.reply(ephemeral=ephemeral, embed=embeds[0])

    @commands.hybrid_group(
        name="case", fallback="view", description="View and manage moderation cases."
    )
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @commands.guild_only()
    @commands.check_any(
        commands.has_permissions(kick_members=True),
        commands.has_permissions(ban_members=True),
        commands.has_permissions(moderate_members=True),
    )
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(
        case_id="The case ID to search for.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @commands.cooldown(1, 3)
    async def case_group(
        self,
        ctx: commands.Context["TitaniumBot"],
        case_id: str,
        ephemeral: bool = False,
    ) -> None | Message:
        if not ctx.guild or not self.bot.user:
            return

        async with defer(ctx, stop_only=True):
            try:
                async with get_session() as session:
                    case = await GuildModCaseManager(self.bot, ctx.guild, session).get_case_by_id(
                        case_id
                    )
            except CaseNotFoundException:
                return await ctx.reply(
                    ephemeral=ephemeral, embed=case_embeds.case_not_found(self.bot, case_id)
                )

            # Get creator
            creator = self.bot.get_user(case.creator_user_id)
            if not creator:
                creator = case.creator_user_id

            # Get target
            target = self.bot.get_user(case.user_id)
            if not target:
                target = case.user_id

            view = View()
            if isinstance(ctx.author, Member) and (
                ctx.author.guild_permissions.kick_members
                or ctx.author.guild_permissions.ban_members
                or ctx.author.guild_permissions.moderate_members
            ):
                view.add_item(ViewCommentsButton(case=case))

            view.add_item(
                Button(
                    label="View in browser",
                    url=f"https://dash.titanium.fyi/guild/{case.guild_id}/moderation/cases/{case.id}",
                    style=ButtonStyle.link,
                )
            )

            await ctx.reply(
                ephemeral=ephemeral,
                embed=case_embeds.case_embed(self.bot, case, creator, target),
                view=view,
            )

    @case_group.command(name="comments", description="View comments on a case.")
    @commands.guild_only()
    @commands.check_any(
        commands.has_permissions(kick_members=True),
        commands.has_permissions(ban_members=True),
        commands.has_permissions(moderate_members=True),
    )
    @app_commands.describe(
        case_id="The case ID to search for.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @commands.cooldown(1, 3)
    async def case_comments(
        self,
        ctx: commands.Context["TitaniumBot"],
        case_id: str,
        ephemeral: bool = False,
    ) -> None | Message:
        if not ctx.guild or not self.bot.user:
            return

        async with defer(ctx, stop_only=True):
            try:
                async with get_session() as session:
                    case = await GuildModCaseManager(self.bot, ctx.guild, session).get_case_by_id(
                        case_id
                    )
            except CaseNotFoundException:
                return await ctx.reply(
                    ephemeral=ephemeral, embed=case_embeds.case_not_found(self.bot, case_id)
                )

            pages: list[CommentPageContainer] = []
            current_page = []

            for comment in case.comments:
                current_page.append(comment)

                if len(current_page) % 5 != 0:
                    continue

                container = CommentPageContainer(self.bot, case, current_page)
                pages.append(container)
                current_page = []

            if current_page:
                container = CommentPageContainer(self.bot, case, current_page)
                pages.append(container)

            layout = PaginationV2View(pages)
            await ctx.reply(
                ephemeral=ephemeral, view=layout, allowed_mentions=AllowedMentions.none()
            )

    @case_group.command(name="addcomment", description="Add a comment to a case.")
    @commands.guild_only()
    @commands.check_any(
        commands.has_permissions(kick_members=True),
        commands.has_permissions(ban_members=True),
        commands.has_permissions(moderate_members=True),
    )
    @app_commands.describe(
        case_id="The case ID to add a comment to.",
        comment="The comment to add.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @commands.cooldown(1, 10)
    async def case_add_comment(
        self,
        ctx: commands.Context["TitaniumBot"],
        case_id: str,
        *,
        comment: commands.Range[str, 1, 500],
        ephemeral: bool = False,
    ) -> None | Message:
        if not ctx.guild or not self.bot.user:
            return

        if not isinstance(ctx.author, Member):
            return await ctx.reply(ephemeral=ephemeral, embed=guild_only(self.bot))

        async with defer(ctx, stop_only=True):
            try:
                async with get_session() as session:
                    case = await GuildModCaseManager(self.bot, ctx.guild, session).get_case_by_id(
                        case_id
                    )

                    await case.add_comment(
                        member=ctx.author, content=comment, bot=self.bot, guild=ctx.guild
                    )
            except CaseNotFoundException:
                return await ctx.reply(
                    ephemeral=ephemeral, embed=case_embeds.case_not_found(self.bot, str(case_id))
                )

            embed = Embed(
                title=f"{self.bot.success_emoji} Added Comment",
                description=f"Added your comment to `{case.id}`.",
                colour=Colour.green(),
            )

            await ctx.reply(ephemeral=ephemeral, embed=embed)

    @case_group.command(name="delete", description="Delete a case by its ID.")
    @global_alias("deletecase")
    @commands.guild_only()
    @commands.check_any(
        commands.has_permissions(kick_members=True),
        commands.has_permissions(ban_members=True),
        commands.has_permissions(moderate_members=True),
    )
    @app_commands.describe(
        case_id="The case ID to delete.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @commands.cooldown(1, 3)
    async def view_case(
        self,
        ctx: commands.Context["TitaniumBot"],
        case_id: str,
        ephemeral: bool = False,
    ) -> None | Message:
        if not ctx.guild or not self.bot.user:
            return

        async with defer(ctx, stop_only=True):
            async with get_session() as session:
                case_manager = GuildModCaseManager(self.bot, ctx.guild, session)

                try:
                    case = await case_manager.get_case_by_id(case_id)
                except CaseNotFoundException:
                    return await ctx.reply(
                        ephemeral=ephemeral,
                        embed=case_embeds.case_not_found(self.bot, str(case_id)),
                    )

                # Get creator
                creator = self.bot.get_user(case.creator_user_id)

                if not creator:
                    creator = case.creator_user_id

                # Get target
                target = self.bot.get_user(case.user_id)

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

                view = ConfirmView(bot=self.bot, original_user=ctx.author)
                msg = await ctx.reply(
                    ephemeral=ephemeral,
                    embeds=embeds,
                    view=view,
                )

                await _stop_loading(ctx)
                timed_out = await view.wait()

                if timed_out or not view.value:
                    return await msg.edit(embed=cancelled(self.bot), view=None)

                try:
                    await case_manager.delete_case(case_id)
                except CaseNotFoundException:
                    return await ctx.reply(
                        ephemeral=ephemeral,
                        embed=case_embeds.case_not_found(self.bot, str(case_id)),
                    )

            await msg.edit(embed=case_embeds.case_deleted(self.bot, case_id), view=None)

    @case_group.command(name="clean", description="Delete all resolved cases for a user.")
    @global_alias("cleancases")
    @global_alias("deletecases")
    @commands.guild_only()
    @commands.check_any(
        commands.has_permissions(kick_members=True),
        commands.has_permissions(ban_members=True),
        commands.has_permissions(moderate_members=True),
    )
    @app_commands.describe(
        user="The user to clean.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @commands.cooldown(1, 3)
    async def clean_cases(
        self,
        ctx: commands.Context["TitaniumBot"],
        user: User,
        ephemeral: bool = False,
    ) -> None | Message:
        if not ctx.guild or not self.bot.user:
            return

        embed = Embed(
            title=f"{self.bot.warn_emoji} Are you sure?",
            description=f"This will delete **all resolved cases** on record for {user.mention} (@{user.name}). "
            "Open cases will not be deleted. This action **cannot be undone!**",
            colour=Colour.orange(),
        )

        view = ConfirmView(bot=self.bot, original_user=ctx.author)
        msg = await ctx.reply(
            ephemeral=ephemeral,
            embed=embed,
            view=view,
        )

        await _stop_loading(ctx)
        timed_out = await view.wait()

        if timed_out or not view.value:
            return await msg.edit(embed=cancelled(self.bot), view=None)

        async with get_session() as session:
            case_manager = GuildModCaseManager(self.bot, ctx.guild, session)
            result = await case_manager.clean_user_cases(user.id)

        embed = Embed(
            title=f"{self.bot.success_emoji} Done",
            description=f"**{result['completed']}** cases deleted.",
            colour=Colour.green(),
        )

        if result["errors"] and embed.description:
            embed.description += f"\n**{result['errors']}** cases failed to delete."

        await msg.edit(embed=embed, view=None)

    @case_group.command(
        name="delete-all",
        description="Delete all resolved cases for the server.",
        aliases=["deleteall"],
    )
    @global_alias("deleteallcases")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    @commands.cooldown(1, 3)
    async def delete_all_cases(
        self, ctx: commands.Context["TitaniumBot"], ephemeral: bool = False
    ) -> None | Message:
        if not ctx.guild or not self.bot.user:
            return

        embed = Embed(
            title=f"{self.bot.warn_emoji} Are you sure?",
            description=f"This will delete **all resolved cases** on record for this server (`{ctx.guild.name}`). "
            "Open cases will not be deleted. This action **cannot be undone!**",
            colour=Colour.orange(),
        )

        view = ConfirmView(bot=self.bot, original_user=ctx.author)
        msg = await ctx.reply(
            ephemeral=ephemeral,
            embed=embed,
            view=view,
        )

        await _stop_loading(ctx)
        timed_out = await view.wait()

        if timed_out or not view.value:
            return await msg.edit(embed=cancelled(self.bot), view=None)

        async with get_session() as session:
            case_manager = GuildModCaseManager(self.bot, ctx.guild, session)
            result = await case_manager.delete_all_resolved_cases()

        embed = Embed(
            title=f"{self.bot.warn_emoji if result['errors'] else self.bot.success_emoji} Done{' with errors' if result['errors'] else ''}",
            description=f"**{result['completed']}** cases deleted.",
            colour=Colour.orange() if result["errors"] else Colour.green(),
        )

        if result["errors"] and embed.description:
            embed.description += f"\n**{result['errors']}** cases failed to delete."

        await msg.edit(embed=embed, view=None)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(ModerationCasesCog(bot))

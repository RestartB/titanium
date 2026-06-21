import re
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import discord
from discord import Colour
from discord.utils import escape_markdown, format_dt, utcnow
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from lib.sql.sql import AnonymousPoll, AnonymousPollResponse, get_session

if TYPE_CHECKING:
    from main import TitaniumBot

CHOICE_EMOJIS = {0: "1️⃣", 1: "2️⃣", 2: "3️⃣", 3: "4️⃣", 4: "5️⃣"}


def poll_not_found_embed(bot: "TitaniumBot") -> discord.Embed:
    return discord.Embed(
        title=f"{bot.error_emoji} Not Found",
        description="Couldn't find the poll.",
        colour=Colour.red(),
    )


def percentage_bar(votes: int, total_votes: int, width: int = 16) -> str:
    if total_votes <= 0:
        percent = 0
    else:
        percent = votes / total_votes

    filled = round(percent * width)
    empty = width - filled

    bar = "█" * filled + "░" * empty
    return f"`{bar}` {percent * 100:5.1f}% ({votes})"


class VoteButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"poll_choice:(?P<poll_id>[0-9a-f-]{36}):(?P<index>[0-4])",
):
    def __init__(self, poll_id: uuid.UUID, index: int) -> None:
        self.poll_id = poll_id
        self.index = index

        super().__init__(
            discord.ui.Button(
                emoji=CHOICE_EMOJIS[index],
                custom_id=f"poll_choice:{poll_id}:{index}",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction["TitaniumBot"],
        item: discord.ui.Button,
        match: re.Match[str],
    ) -> "VoteButton":
        poll_id = uuid.UUID(match.group("poll_id"))
        index = int(match.group("index"))

        return cls(poll_id=poll_id, index=index)

    async def callback(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id in interaction.client.opt_out:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Opted Out",
                description="You have opted out of data collection and cannot use this feature.",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        async with get_session() as session:
            poll = await session.get(AnonymousPoll, self.poll_id)

            if not poll:
                await interaction.followup.send(
                    embed=poll_not_found_embed(interaction.client), ephemeral=True
                )
                return

            stmt = (
                insert(AnonymousPollResponse)
                .values(
                    user_id=interaction.user.id,
                    poll_id=self.poll_id,
                    answer_index=self.index,
                )
                .on_conflict_do_nothing(index_elements=["user_id", "poll_id"])
                .returning(AnonymousPollResponse.id)
            )

            result = await session.execute(stmt)
            existing_vote = result.scalar_one_or_none() is None

            if existing_vote:
                await session.execute(
                    update(AnonymousPollResponse)
                    .where(
                        AnonymousPollResponse.user_id == interaction.user.id,
                        AnonymousPollResponse.poll_id == self.poll_id,
                    )
                    .values(answer_index=self.index)
                )

            if poll.show_live_results:
                # refresh poll to get latest votes
                poll = await session.get(
                    AnonymousPoll,
                    self.poll_id,
                    options=(selectinload(AnonymousPoll.responses),),
                    populate_existing=True,
                )

        if not poll:
            await interaction.followup.send(
                embed=poll_not_found_embed(interaction.client), ephemeral=True
            )
            return

        if poll.show_live_results:
            view = PollView(poll=poll, show_live_results=poll.show_live_results)
            await interaction.edit_original_response(
                view=view, allowed_mentions=discord.AllowedMentions.none()
            )

        embed = discord.Embed(
            title=f"{interaction.client.success_emoji} {'Updated' if existing_vote else 'Recorded'}",
            description="Your vote has been updated."
            if existing_vote
            else "Your vote has been recorded.",
            colour=Colour.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


class CloseNowButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"poll_close:(?P<poll_id>[0-9a-f-]{36})",
):
    def __init__(self, poll_id: uuid.UUID) -> None:
        self.poll_id = poll_id

        super().__init__(
            discord.ui.Button(
                emoji="⏰",
                label="End Poll Now",
                custom_id=f"poll_close:{poll_id}",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction["TitaniumBot"],
        item: discord.ui.Button,
        match: re.Match[str],
    ) -> "CloseNowButton":
        poll_id = uuid.UUID(match.group("poll_id"))
        return cls(poll_id=poll_id)

    async def callback(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        await interaction.response.defer(ephemeral=True)

        async with get_session() as session:
            poll = await session.get(
                AnonymousPoll,
                self.poll_id,
                options=(selectinload(AnonymousPoll.responses),),
            )

        if not poll:
            await interaction.followup.send(
                embed=poll_not_found_embed(interaction.client), ephemeral=True
            )
            return

        if poll.creator_id != interaction.user.id or not interaction.permissions.administrator:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Not Allowed",
                description="You didn't create this poll. Only the creator can end the poll.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        view = ClosedPollView(poll=poll, close_time=utcnow())
        await interaction.edit_original_response(
            view=view, allowed_mentions=discord.AllowedMentions.none()
        )
        await poll.delete()

        embed = discord.Embed(
            title=f"{interaction.client.success_emoji} Done",
            description="The poll has been closed.",
            colour=Colour.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


class DeletePollButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"poll_delete:(?P<poll_id>[0-9a-f-]{36})",
):
    def __init__(self, poll_id: uuid.UUID) -> None:
        self.poll_id = poll_id

        super().__init__(
            discord.ui.Button(
                emoji="🗑️",
                label="Delete Poll",
                custom_id=f"poll_delete:{poll_id}",
                style=discord.ButtonStyle.red,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction["TitaniumBot"],
        item: discord.ui.Button,
        match: re.Match[str],
    ) -> "DeletePollButton":
        poll_id = uuid.UUID(match.group("poll_id"))
        return cls(poll_id=poll_id)

    async def callback(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        await interaction.response.defer(ephemeral=True)

        async with get_session() as session:
            poll = await session.get(AnonymousPoll, self.poll_id)

        if not poll:
            await interaction.followup.send(
                embed=poll_not_found_embed(interaction.client), ephemeral=True
            )
            return

        if poll.creator_id != interaction.user.id or not interaction.permissions.manage_messages:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Not Allowed",
                description="You didn't create this poll. Only the creator or users with Manage Message permissions can delete the poll.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        await interaction.delete_original_response()
        await poll.delete()

        embed = discord.Embed(
            title=f"{interaction.client.success_emoji} Done",
            description="The poll has been deleted.",
            colour=Colour.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


class ChoiceRow(discord.ui.Section):
    def __init__(
        self,
        poll: AnonymousPoll,
        choice: str,
        index: int,
        votes: Optional[int],
    ) -> None:
        super().__init__(
            discord.ui.TextDisplay(
                content=escape_markdown(choice)
                + (
                    (f"\n{percentage_bar(votes=votes, total_votes=len(poll.responses))}")
                    if votes is not None
                    else ""
                )
            ),
            accessory=VoteButton(poll.id, index),
        )


class ClosedPollView(discord.ui.LayoutView):
    def __init__(self, poll: AnonymousPoll, close_time: datetime):
        super().__init__(timeout=None)

        container = discord.ui.Container(accent_colour=Colour.light_grey())

        container.add_item(
            discord.ui.TextDisplay(content=f"## Anonymous Poll - Results\n{poll.content}")
        )
        if poll.image_url:
            container.add_item(discord.ui.MediaGallery(discord.MediaGalleryItem(poll.image_url)))
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))

        results = {}
        for i in range(0, len(poll.choices)):
            results[i] = sum(
                [1 if response.answer_index == i else 0 for response in poll.responses]
            )

        for i, choice in enumerate(poll.choices):
            container.add_item(
                discord.ui.TextDisplay(
                    escape_markdown(choice)
                    + f"\n{percentage_bar(votes=results[i], total_votes=len(poll.responses))}"
                )
            )
            if i + 1 != len(poll.choices):
                container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))

        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(
            discord.ui.TextDisplay(
                "- This poll has ended.\n"
                f"- It ended {format_dt(close_time, style='R')} ({format_dt(close_time)}).\n"
                f"- `{len(poll.responses):,}` members responded in total."
            )
        )

        self.add_item(container)


class PollView(discord.ui.LayoutView):
    def __init__(self, poll: AnonymousPoll, show_live_results: bool):
        super().__init__(timeout=None)

        container = discord.ui.Container(accent_colour=Colour.light_grey())

        container.add_item(discord.ui.TextDisplay(content=f"## Anonymous Poll\n{poll.content}"))
        if poll.image_url:
            container.add_item(discord.ui.MediaGallery(discord.MediaGalleryItem(poll.image_url)))
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))

        results: dict[int, int] = {}
        if show_live_results:
            for i in range(0, len(poll.choices)):
                results[i] = sum(
                    [1 if response.answer_index == i else 0 for response in poll.responses]
                )

        for i, choice in enumerate(poll.choices):
            container.add_item(
                ChoiceRow(
                    poll, choice, i, results[i] if show_live_results and poll.responses else None
                )
            )
            if i + 1 != len(poll.choices):
                container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))

        hints = (
            "- Vote up to 1 time.\n"
            "- Your answer is fully anonymous.\n"
            f"- The poll will end {format_dt(poll.closing_time, style='R')} ({format_dt(poll.closing_time)})."
        )

        if not show_live_results:
            hints += "\n- Results will be shown when the poll ends."

        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(discord.ui.TextDisplay(hints))

        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))

        action_row = discord.ui.ActionRow()
        action_row.add_item(CloseNowButton(poll.id))
        action_row.add_item(DeletePollButton(poll.id))
        container.add_item(action_row)

        self.add_item(container)

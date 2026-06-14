import re
import uuid
from typing import TYPE_CHECKING

import discord
from discord import Colour
from discord.utils import escape_markdown, format_dt
from sqlalchemy.exc import IntegrityError

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

        try:
            async with get_session() as session:
                poll = await session.get(AnonymousPoll, self.poll_id)

                if not poll:
                    await interaction.followup.send(
                        embed=poll_not_found_embed(interaction.client), ephemeral=True
                    )
                    return

                session.add(
                    AnonymousPollResponse(
                        user_id=interaction.user.id,
                        poll_id=self.poll_id,
                        answer_index=self.index,
                    )
                )
        except IntegrityError as e:
            err_code = getattr(e.orig, "sqlstate", getattr(e.orig, "pgcode", None))
            if err_code == "23505":  # 23505 = unique_violation
                embed = discord.Embed(
                    title=f"{interaction.client.error_emoji} Already Voted",
                    description="You have already voted on this poll.",
                    colour=Colour.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

        embed = discord.Embed(
            title=f"{interaction.client.success_emoji} Recorded",
            description="Your vote has been recorded.",
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
                label="Close Poll Now",
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
            poll = await session.get(AnonymousPoll, self.poll_id)

        if not poll:
            await interaction.followup.send(
                embed=poll_not_found_embed(interaction.client), ephemeral=True
            )
            return

        if poll.creator_id != interaction.user.id:
            embed = discord.Embed(
                title=f"{interaction.client.success_emoji} Not Allowed",
                description="You didn't create this poll. Only the creator can close the poll.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

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

        if poll.creator_id != interaction.user.id:
            embed = discord.Embed(
                title=f"{interaction.client.success_emoji} Not Allowed",
                description="You didn't create this poll. Only the creator can delete the poll.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        await interaction.delete_original_response()

        embed = discord.Embed(
            title=f"{interaction.client.success_emoji} Done",
            description="The poll has been deleted.",
            colour=Colour.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


class ChoiceRow(discord.ui.Section):
    def __init__(self, bot: TitaniumBot, poll: AnonymousPoll, choice: str, index: int) -> None:
        super().__init__(
            discord.ui.TextDisplay(content=escape_markdown(choice)),
            accessory=VoteButton(poll.id, index),
        )


class PollView(discord.ui.LayoutView):
    def __init__(self, bot: TitaniumBot, poll: AnonymousPoll):
        super().__init__(timeout=None)

        container = discord.ui.Container(accent_colour=Colour.light_grey())

        container.add_item(discord.ui.TextDisplay(content=f"## Anonymous Poll\n{poll.content}"))
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))

        for i, choice in enumerate(poll.choices):
            container.add_item(ChoiceRow(bot, poll, choice, i))
            if i + 1 != len(poll.choices):
                container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))

        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(
            discord.ui.TextDisplay(
                "- Vote up to 1 time.\n"
                "- Your answer is fully anonymous.\n"
                f"- The poll will close {format_dt(poll.closing_time, style='R')} ({format_dt(poll.closing_time)})."
            )
        )

        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))

        action_row = discord.ui.ActionRow()
        action_row.add_item(CloseNowButton(poll.id))
        action_row.add_item(DeletePollButton(poll.id))
        container.add_item(action_row)

        self.add_item(container)

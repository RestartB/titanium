import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING

import discord
from discord import Colour, Embed, Webhook

from lib.helpers.log_error import log_error

if TYPE_CHECKING:
    from main import TitaniumBot


class FeedbackModal(discord.ui.Modal, title="Share Feedback"):
    feedback_type = discord.ui.Label(
        text="Feedback Type",
        description="Select feedback type.",
        component=discord.ui.Select(
            options=[
                discord.SelectOption(emoji="🐞", label="Bug Report", value="Bug Report"),
                discord.SelectOption(emoji="✨", label="Feature Request", value="Feature Request"),
                discord.SelectOption(emoji="📝", label="Other", value="📝 Other"),
            ],
        ),
    )

    feedback_content = discord.ui.Label(
        text="Feedback Content",
        description="Please provide your feedback.",
        component=discord.ui.TextInput(
            style=discord.TextStyle.long,
            min_length=20,
            max_length=2000,
        ),
    )

    def __init__(self, timeout: float = 240) -> None:
        super().__init__(timeout=timeout)

    async def on_submit(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        await interaction.response.defer(ephemeral=True)
        self.interaction = interaction

        webhook_url = os.getenv("FEEDBACK_WEBHOOK", None)
        if not webhook_url or not webhook_url.strip():
            e = Embed(
                colour=Colour.red(),
                title=f"{str(interaction.client.error_emoji)} Webhook Not Found",
                description="The bot host has not set up this feature, please try again later.",
            )
            logging.error("The feedback webhook url is not in the .env file")
            return await interaction.followup.send(embed=e, ephemeral=True)

        is_success = await self._send_notification(webhook_url)
        if not is_success:
            e = Embed(
                colour=Colour.red(),
                title=f"{str(interaction.client.error_emoji)} Failed",
                description="Failed to send feedback to the developer. Please try again later.",
            )
            return await interaction.followup.send(embed=e, ephemeral=True)

        e = Embed(
            colour=Colour.green(),
            title=f"{str(interaction.client.success_emoji)} Feedback Sent",
            description="Thank you for your feedback!",
        )
        await interaction.followup.send(embed=e, ephemeral=True)

    def _build_embed(self) -> Embed:
        """Build the Feedback notification embed"""
        e = Embed(
            title="📩 New Feedback",
            description=f"**Feedback Type:** `{self.feedback_type.component.values[0]}`\n**User ID:** `{self.interaction.user.id}`\n**Server ID:** `{self.interaction.guild.id if self.interaction.guild else 'Not Available'}`\n\n**Feedback Content:** {self.feedback_content.component.value}",
            colour=Colour.blurple(),
        )
        e.timestamp = datetime.now()
        return e

    async def _send_notification(self, webhook_url: str) -> bool:
        """Send notification to feedback webhook."""

        e = self._build_embed()

        webhook = Webhook.from_url(webhook_url, client=self.interaction.client)
        try:
            await webhook.send(
                username=self.interaction.user.display_name,
                avatar_url=self.interaction.user.display_avatar.url,
                embed=e,
            )
            return True
        except Exception as e:
            # await log_error(
            #     bot=self.bot,
            #     module="Feedback Modal",
            #     guild_id=self.interaction.guild.id if self.interaction.guild else None,
            #     error="Unknown error",
            #     store_err=False,
            #     exc=e,
            # )
            return False

import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

import aiohttp
import discord
from discord import Color, Embed

if TYPE_CHECKING:
    from main import TitaniumBot


class FeedbackModal(discord.ui.Modal, title="Share Feedback"):
    feedback_type = discord.ui.Label(
        text="Feedback Type",
        description="Select feedback type.",
        component=discord.ui.Select(
            options=[
                discord.SelectOption(
                    emoji="🐞", label="Bug Report", value="🐞 Bug Report"
                ),
                discord.SelectOption(
                    emoji="✨", label="Feature Request", value="✨ Feature Request"
                ),
                discord.SelectOption(
                    emoji="💡",
                    label="Suggested Changes",
                    value="💡 Suggested Changes",
                ),
                discord.SelectOption(emoji="📝", label="Other", value="📝 Other"),
            ],
        ),
    )

    feedback_content = discord.ui.Label(
        text="Feedback Content",
        description="Please provide detailed explanation of your feedback.",
        component=discord.ui.TextInput(
            style=discord.TextStyle.long,
            min_length=50,
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
                color=Color.red(),
                title=f"{str(interaction.client.error_emoji)} Webhook Not Found",
                description="The webhook to send the feedback is not configured.",
            )
            logging.error("The feedback webhook url is not in the .env file")
            return await interaction.followup.send(embed=e, ephemeral=True)

        is_success = await self._send_notification(webhook_url)
        if not is_success:
            e = Embed(
                color=Color.red(),
                title=f"{str(interaction.client.error_emoji)} Failed",
                description="Failed to send feedback to the developer. Please try again later.",
            )
            return await interaction.followup.send(embed=e, ephemeral=True)

        e = Embed(
            color=Color.green(),
            title=f"{str(interaction.client.success_emoji)} Success",
            description="Thank you for your feedback, it has been shared with the bot developers.",
        )
        await interaction.followup.send(embed=e, ephemeral=True)

    async def _send_notification(self, webhook_url: str) -> bool:
        """Send notification to feedback webhook."""

        e = Embed(
            title="📩 New Feedback",
            description=f"**Feedback Type:** `{self.feedback_type.component.values[0]}`\n**User ID:** `{self.interaction.user.id}`\n**Server ID:** `{self.interaction.guild.id if self.interaction.guild else 'Not Available'}`\n\n**Feedback Content:** {self.feedback_content.component.value}",
            color=Color.blurple(),
        )
        e.timestamp = datetime.now()

        payload: dict[str, Any] = {
            "username": self.interaction.user.display_name,
            "avatar_url": self.interaction.user.display_avatar.url,
            "content": None,
            "embeds": [e.to_dict()],
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status != 204:  # 204 = success for webhook
                    logging.error(f"Feedback webhook error: {response.status}")
                    return False
        return True

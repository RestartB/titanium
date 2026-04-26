import logging
from typing import TYPE_CHECKING, Optional

import discord
from sqlalchemy.exc import IntegrityError

from lib.sql.sql import Tag, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


LOGGER = logging.getLogger("feedback")


class TagModal(discord.ui.Modal, title="Tag Information"):
    tag_type = discord.ui.Label(
        text="Tag Type",
        description="Select the type of tag to make.",
        component=discord.ui.RadioGroup(
            options=[
                discord.RadioGroupOption(
                    label="User Tag - use in any server by adding Titanium to your account",
                    value="user",
                    default=True,
                ),
                discord.RadioGroupOption(
                    label="Server Tag - use in this server only, requires Manage Server permissions",
                    value="server",
                ),
            ],
        ),
    )

    tag_name = discord.ui.Label(
        text="Tag Name",
        description="Enter the name of the tag. The name must be unique and cannot contain spaces or backticks (`).",
        component=discord.ui.TextInput(
            style=discord.TextStyle.short,
            min_length=1,
            max_length=35,
        ),
    )

    tag_content = discord.ui.Label(
        text="Tag Content",
        description="Enter the content of the tag. To add an image, upload the image and paste the raw image link here.",
        component=discord.ui.TextInput(
            style=discord.TextStyle.long,
            min_length=1,
            max_length=2000,
        ),
    )

    def __init__(
        self, server_tag_allowed: bool, timeout: float = 240, existing_tag: Optional[Tag] = None
    ) -> None:
        super().__init__(timeout=timeout)
        self.server_tag_allowed = server_tag_allowed
        self.existing_tag = existing_tag

        assert isinstance(self.tag_type.component, discord.ui.RadioGroup)
        assert isinstance(self.tag_name.component, discord.ui.TextInput)
        assert isinstance(self.tag_content.component, discord.ui.TextInput)

        if not server_tag_allowed:
            self.tag_type.component.options.pop(1)

        if existing_tag:
            self.remove_item(self.tag_type)
            self.tag_name.component.default = existing_tag.name
            self.tag_content.component.default = existing_tag.content

    async def on_submit(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        await interaction.response.defer(ephemeral=True)

        assert isinstance(self.tag_type.component, discord.ui.RadioGroup)
        assert isinstance(self.tag_name.component, discord.ui.TextInput)
        assert isinstance(self.tag_content.component, discord.ui.TextInput)
        assert self.tag_type.component.value != "server" or (
            self.tag_type.component.value == "server" and interaction.guild
        )

        cleaned_name = self.tag_name.component.value.lower().strip()

        # has the user bypassed checks / permissions have changed since modal was sent?
        if self.tag_type.component.value == "server" and (
            not self.server_tag_allowed
            or (
                isinstance(interaction.user, discord.Member)
                and not interaction.user.guild_permissions.manage_guild
            )
        ):
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} No Permissions",
                description="You are not allowed to create or modify server tags. Please ensure you have the **Manage Guild** permission.",
                colour=discord.Colour.red(),
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        # validate data from discord
        if len(cleaned_name) > 35 or len(self.tag_content.component.value) > 2000:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Invalid Data",
                description="The provided tag name or content is too long.",
                colour=discord.Colour.red(),
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        # mitigate markdown escape
        if "`" in cleaned_name or " " in cleaned_name:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Invalid Name",
                description="Backticks (`) and spaces are not allowed in tag names.",
                colour=discord.Colour.red(),
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        # mitigate markdown escape
        if cleaned_name == "list" or cleaned_name == "viewall":
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Invalid Name",
                description="Tags called `list` and `viewall` are not allowed.",
                colour=discord.Colour.red(),
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        if self.existing_tag:
            # editing tag
            async with get_session() as session:
                existing_tag = await session.get(Tag, self.existing_tag.id)

                if not existing_tag:
                    embed = discord.Embed(
                        title=f"{interaction.client.error_emoji} Not Found",
                        description="Couldn't find the tag to edit. Maybe someone deleted it?",
                        colour=discord.Colour.red(),
                    )
                    return await interaction.followup.send(embed=embed, ephemeral=True)

                existing_tag.name = cleaned_name
                existing_tag.content = self.tag_content.component.value

                try:
                    await session.commit()
                except IntegrityError as e:
                    await session.rollback()

                    err_code = getattr(e.orig, "sqlstate", getattr(e.orig, "pgcode", None))
                    if err_code == "23505":  # 23505 = unique_violation
                        embed = discord.Embed(
                            title=f"{interaction.client.error_emoji} Name Taken",
                            description=f"A tag named `{cleaned_name}` already exists. Please choose a different name.",
                            colour=discord.Colour.red(),
                        )
                        return await interaction.followup.send(embed=embed, ephemeral=True)
                    else:
                        raise e

            embed = discord.Embed(
                title=f"{interaction.client.success_emoji} Done",
                description=f"The `{existing_tag.name}` tag has been updated.",
                colour=discord.Colour.green(),
            )
        else:
            # creating tag
            async with get_session() as session:
                new_tag = Tag(
                    guild_id=interaction.guild.id
                    if interaction.guild and self.tag_type.component.value == "server"
                    else None,
                    owner_id=interaction.user.id,
                    is_user=self.tag_type.component.value == "user",
                    name=cleaned_name,
                    content=self.tag_content.component.value,
                )
                session.add(new_tag)

                try:
                    await session.commit()
                except IntegrityError as e:
                    await session.rollback()

                    err_code = getattr(e.orig, "sqlstate", getattr(e.orig, "pgcode", None))
                    if err_code == "23505":  # 23505 = unique_violation
                        embed = discord.Embed(
                            title=f"{interaction.client.error_emoji} Name Taken",
                            description=f"A tag named `{cleaned_name}` already exists. Please choose a different name.",
                            colour=discord.Colour.red(),
                        )
                        return await interaction.followup.send(embed=embed, ephemeral=True)
                    else:
                        raise e

            embed = discord.Embed(
                title=f"{interaction.client.success_emoji} Done",
                description=f"Created a new {self.tag_type.component.value} tag: `{cleaned_name}`",
                colour=discord.Colour.green(),
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

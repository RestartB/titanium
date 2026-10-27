import logging
from typing import TYPE_CHECKING

import discord
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from lib.sql.sql import Tag, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


LOGGER = logging.getLogger("feedback")


class TagModal(discord.ui.Modal, title="Tag Information"):
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
        self,
        server_tag: bool,
        timeout: float = 600,
        existing_tag: Tag | None = None,
    ) -> None:
        super().__init__(timeout=timeout)
        self.server_tag = server_tag
        self.existing_tag = existing_tag

        assert isinstance(self.tag_name.component, discord.ui.TextInput)
        assert isinstance(self.tag_content.component, discord.ui.TextInput)

        if existing_tag:
            self.tag_name.component.default = existing_tag.name
            self.tag_content.component.default = existing_tag.content

    async def on_submit(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        await interaction.response.defer(ephemeral=True)

        assert isinstance(self.tag_name.component, discord.ui.TextInput)
        assert isinstance(self.tag_content.component, discord.ui.TextInput)

        cleaned_name = self.tag_name.component.value.lower().strip()

        # has the user bypassed checks / permissions have changed since modal was sent?
        if self.server_tag and (
            not interaction.guild
            or not interaction.is_guild_integration()
            or not isinstance(interaction.user, discord.Member)
            or not interaction.permissions.manage_guild
        ):
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} No Permissions",
                description="You are not allowed to create or modify server tags. Please ensure you have the **Manage Guild** permission.",
                colour=discord.Colour.red(),
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        # validate data from discord
        if len(cleaned_name) > 35 or len(self.tag_content.component.value.strip()) > 2000:
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

        if self.server_tag and interaction.guild:
            config = (
                await interaction.client.fetch_guild_config(interaction.guild.id)
                if interaction.is_guild_integration()
                else None
            )
            if not config:
                raise RuntimeError("Failed to get guild config")

            if not config.tags_enabled:
                embed = discord.Embed(
                    title=f"{interaction.client.error_emoji} Disabled",
                    description="Tags have been disabled by a server admin.",
                    colour=discord.Colour.red(),
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)

        if self.existing_tag:
            # editing tag
            async with get_session() as session:
                existing_tag = await session.get(Tag, self.existing_tag.id)

                # check user has access to tag before updating
                if self.server_tag:
                    valid_target = bool(
                        existing_tag
                        and not existing_tag.is_user
                        and existing_tag.guild_id == interaction.guild_id
                    )
                else:
                    valid_target = bool(
                        existing_tag
                        and existing_tag.is_user
                        and existing_tag.owner_id == interaction.user.id
                    )

                if not existing_tag or not valid_target:
                    embed = discord.Embed(
                        title=f"{interaction.client.error_emoji} Not Found",
                        description="Couldn't find the tag to edit. Maybe someone deleted it?",
                        colour=discord.Colour.red(),
                    )
                    return await interaction.followup.send(embed=embed, ephemeral=True)

                existing_tag.name = cleaned_name
                existing_tag.content = self.tag_content.component.value.strip()

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
                    raise

            embed = discord.Embed(
                title=f"{interaction.client.success_emoji} Done",
                description=f"The `{existing_tag.name}` tag has been updated.",
                colour=discord.Colour.green(),
            )
        else:
            # creating tag
            async with get_session(autocommit=False) as session:
                if self.server_tag and interaction.guild and config:
                    total_result = await session.execute(
                        select(func.count())
                        .select_from(Tag)
                        .where(Tag.guild_id == interaction.guild.id)
                    )
                    total_count = total_result.scalar() or 0

                    if config.limits.enforcing and total_count >= config.limits.tags:
                        embed = discord.Embed(
                            title=f"{interaction.client.error_emoji} Limit Exceeded",
                            description=f"You have exceeded the server tag limit of `{config.limits.tags}`. The tag was not created. Please delete some tags, or request an increased limit in the [support server]({interaction.client.website_url}/server).",
                            colour=discord.Colour.red(),
                        )
                        return await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    total_result = await session.execute(
                        select(func.count())
                        .select_from(Tag)
                        .where(Tag.owner_id == interaction.user.id, Tag.is_user)
                    )
                    total_count = total_result.scalar() or 0

                    if total_count >= 250:
                        embed = discord.Embed(
                            title=f"{interaction.client.error_emoji} Limit Exceeded",
                            description="You cannot create more than `250` user tags.",
                            colour=discord.Colour.red(),
                        )
                        return await interaction.followup.send(embed=embed, ephemeral=True)

                if interaction.user.id in interaction.client.opt_out and not self.server_tag:
                    embed = discord.Embed(
                        title=f"{interaction.client.error_emoji} Opted Out",
                        description="You have opted out of data collection and cannot create user tags.",
                        colour=discord.Colour.red(),
                    )
                    return await interaction.followup.send(embed=embed, ephemeral=True)

                new_tag = Tag(
                    guild_id=interaction.guild.id
                    if interaction.guild and self.server_tag
                    else None,
                    owner_id=interaction.user.id,
                    is_user=not self.server_tag,
                    name=cleaned_name,
                    content=self.tag_content.component.value.strip(),
                    cv2=False,
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
                    raise

            embed = discord.Embed(
                title=f"{interaction.client.success_emoji} Done",
                description=f"Created a new {'server' if self.server_tag else 'user'} tag: `{cleaned_name}`",
                colour=discord.Colour.green(),
            )

        # reload cache if this is a server tag
        if interaction.guild_id and self.server_tag:
            await interaction.client.refresh_guild_config_cache(interaction.guild_id)

        await interaction.followup.send(embed=embed, ephemeral=True)

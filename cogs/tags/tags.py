from typing import TYPE_CHECKING, Literal

from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from main import TitaniumBot


class TagsCommandsCog(commands.Cog):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    # Use tag command
    @commands.hybrid_group(
        name="tag", aliases=["tags"], fallback="use", description="Send a server or user tag."
    )
    @commands.cooldown(1, 3)
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(tag="The tag to send.")
    async def tags_group(self, ctx: commands.Context["TitaniumBot"], tag: str):
        await ctx.defer()

    # Create tag command
    @tags_group.command(
        name="add", aliases=["create"], description="Create a new server or user tag."
    )
    @commands.cooldown(1, 3)
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(mode="Whether to create the tag as a server or user tag.")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Server Tag", value="server"),
            app_commands.Choice(name="User Tag", value="user"),
        ]
    )
    async def add_tag(self, ctx: commands.Context["TitaniumBot"], mode: Literal["Server", "User"]):
        await ctx.defer()

    # Edit tag command
    @tags_group.command(
        name="edit", aliases=["modify"], description="Edit an existing server or user tag."
    )
    @commands.cooldown(1, 3)
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(tag="The tag to edit.")
    async def edit_tag(self, ctx: commands.Context["TitaniumBot"], tag: str):
        await ctx.defer()

    # Delete tag command
    @tags_group.command(
        name="delete", aliases=["remove"], description="Delete an existing server or user tag."
    )
    @commands.cooldown(1, 3)
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(tag="The tag to delete.")
    async def delete_tag(self, ctx: commands.Context["TitaniumBot"], tag: str):
        await ctx.defer()

    # List tags command
    @tags_group.command(name="list", aliases=["viewall"], description="View a list of all tags.")
    @commands.cooldown(1, 3)
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(mode="Whether to view server or user tags.")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Server Tag", value="server"),
            app_commands.Choice(name="User Tag", value="user"),
        ]
    )
    async def view_all_tags(
        self, ctx: commands.Context["TitaniumBot"], mode: Literal["server", "user"]
    ):
        await ctx.defer()


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(TagsCommandsCog(bot))

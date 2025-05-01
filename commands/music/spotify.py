from discord import app_commands

from .spotify_images import SpotifyImages
from .spotify_search import SpotifySearch


@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class Spotify(
    SpotifySearch,
    SpotifyImages,
    name="spotify",
    description="Spotify related commands.",
):
    pass


async def setup(bot):
    # Only load if Spotify API keys are present
    try:
        if (
            bot.tokens["spotify-api-id"] is not None
            and bot.tokens["spotify-api-secret"] is not None
        ):
            if (
                bot.tokens["spotify-api-id"] != ""
                and bot.tokens["spotify-api-secret"] != ""
            ):
                await bot.add_cog(Spotify(bot))
    except KeyError:
        pass

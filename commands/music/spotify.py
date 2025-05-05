import importlib

from discord import app_commands

from . import spotify_images, spotify_search
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
    def __init__(self, bot):
        print("Root directory:", __name__)
        
        # Reload the modules
        importlib.reload(spotify_images)
        importlib.reload(spotify_search)

        # Re-import the classes after reload
        from .spotify_images import SpotifyImages
        from .spotify_search import SpotifySearch

        # Initialize parent classes
        SpotifySearch.__init__(self, bot)
        SpotifyImages.__init__(self, bot)


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

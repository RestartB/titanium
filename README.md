# RestartBot
Welcome to the rewrite of RestartBot, using **discord.py Cogs**.

> [!CAUTION]
> The cogs rewrite is in active development and will contain bugs and unfinished features.

## Why?
The old code of RestartBot was very hard to work on. Every command was in the main.py file, meaning that at times it would be over 1800 lines long. This made it difficult to look at and edit. Therefore, by using cogs, each group of commands can be split into their own file, so I only need to see the commands that are relavent to what I am currently working on.

## Included Commands
RestartBot comes with some premade commands. Below is a list of what commands are in each cog file:
- **Utility Commands** *(utils.py)*
  - **ping:** see the bot's latency.
  - **restart:** restart the bot. Only available to the bot owner.
  - **info:** view info about the bot.
  - **pfp:** see a user's PFP.
  - **host-info:** see information about the bot's hosting server.
- **Cog Utility Commands (bot owner only)** *(cog-utils.py)*
  - **sync-cogs:** sync cogs.
  - **load-cog:** load a new cog.
  - **unload-cog:** unload a loaded cog.
  - **reload-cog:** reload a loaded cog.
  - **sync-tree:** sync the command tree.
- **Animal Commands** *(animals.py)*
  - **cat:** see a random image of a cat.
  - **dog:** see a random image of a dog.
- **Misc Commands** *(misc.py)*
  - **8ball:** consult the mystical 8 ball for an answer to a question.
  - **first-message:** get the first message in a channel.
  - **fish:** see the fish video.
- **Music Commands** *(music.py)*
  - **lyrics:** get the lyrics to a song.
  - **song-global-url:** get a list of streaming service URLs based on a song URL. Powered by https://song.link.
- **Spotify Commands** *(spotify.py)*
  - **spotify:** search Spotify for a song, artist or album.
  - **spotify-url:** get info on a Spotify song, artist, album or playlist URL.
  - **spotify-image:** get album art for a Spotify song or album URL.

## Setup
Coming soon!

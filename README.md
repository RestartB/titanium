# RestartBot
Welcome to the rewrite of RestartBot, using **discord.py Cogs**.

> [!NOTE]
> The cogs rewrite is now the main version of RestartBot. Development has ceased on the single file version of RestartBot, and this version is now the solely supported version.

## Contributions Welcome!
Have an improvement you want to make? Developed a new cog that you want to be in the main bot? Contributions are welcome! Make a pull request and I'll take a look. :)

## Included Features
- Wikipedia and Urban Dictionary search
- Random Dog and Cat images
- Fun commands like the 8 ball and fish command
- Search Spotify, get Spotify URL information and get full quailty Album Art (Spotify API Keys needed)
- Get lyrics for songs
- Get URLs for a song on every streaming service
- Expandable cog system to allow you to make your own commands

## Why?
The old code of RestartBot was very hard to work on. Every command was in the main.py file, meaning that at times it would be over 1800 lines long. This made it difficult to look at and edit. Therefore, by using cogs, each group of commands can be split into their own file, so I only need to see the commands that are relavent to what I am currently working on.

## Setup
Coming soon!

## Included Commands
RestartBot comes with some included commands. Below is a list of what commands are in each cog file:
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
- **Web Search Commands** *(web_search.py)*
  - **urban-dictionary:** search Urban Dictionary. Results are mainly unmoderated and may be inappropriate.
  - **wikipedia:** search Wikipedia for an answer.

## Included Cogs
RestartBot also includes some non command cogs, which are also stored in the command folder. The list is below:
- **spotify_autoembed.py**
  - Stores the event handler for Spotify Auto-embedding.

## Developing your own Cogs
RestartBot is modular and will load compatible cogs automatically.

### Cogs Path
The default cogs path is:\
`(RUNNING-PATH)/commands`.\
This path can be changed to a path of your selection in the config file.

### Example Cog
I have developed an example cog that you can look at and modify to fit your needs. You can find it in `example.py`. When you are ready to use the cog, place it in your cogs folder.
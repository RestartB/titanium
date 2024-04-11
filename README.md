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

## Self Hosting RestartBot
Self-hosting RestartBot is possible, however you must get the required modules and API tokens first.

> [!IMPORTANT]
> While I have taken every precaution to block offensive content from being displayed without a disclaimer, it is your responsibility as the bot host to monitor for any offensive content posted using the bot.

> [!CAUTION]
> When generating Bot Tokens and API Secrets, do not share them with anybody!

### Python Modules
RestartBot relies on several Python modules to function. These modules can be installed from Pypi using Pip.\
\
**Installation Command:**\
`pip install discord.py spotipy wikipedia ...`

### Discord Bot Token
RestartBot requires a Discord Bot Token to function. The steps to get one are as follows:
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and log in with your Discord Account.
2. Create a new application and fill in the information required.
3. Go to the `Bot` section, and generate a new bot.
4. Give your bot a username, and optionally, a PFP and banner.
5. Copy the Bot Token, and paste it into the bot token field in the config file. Due to security reasons, you will only be able to view the bot token once from Discord Developer Portal before having to generate a new one.

### Spotify API Key
To use the Spotify commands in RestartBot, a Spotify Client ID and Secret are required. If you do not provide these, Spotify commands will automatically be disabled. The steps to get these are as follows:
1. Go to the [Spotify Developers dashboard](https://developer.spotify.com/dashboard). A free or premium Spotify account is required.
2. Create a new app, set the app name and description to whatever you please.  No additional APIs are required.
3. Set the Redirect URI to any valid URL. `http://example.com` is known to work. Then, create the app.
4. Copy the Client ID and Secret for your app, and paste them into their respective fields in the config file.

### Starting the Bot
Once you have have installed the required Python modules and generated your tokens, you can run the bot as follows:
1. Navigate to the RestartBot directory through the terminal.
2. Once you are at the RestartBot directory, run `python main.py`, and monitor for any errors in the terminal.

If an error occurs, please create a GitHub issue and I will take a look.

### Generating a Bot Invite
To invite RestartBot to your server, an invite is required. You can use the following template to make a bot invite URL:\
`https://discord.com/oauth2/authorize?client_id=(YOUR CLIENT ID)&permissions=964220546112&scope=bot`\
You will need your Discord Client ID to make this URL. You can get this from the General Information page of your Application you generated earlier in Discord Developer Portal.

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

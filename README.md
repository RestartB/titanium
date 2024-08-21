# Titanium
Welcome to Titanium, the open source core of the Titanium Discord Bot.

## Contributions Welcome!
Have an improvement you want to make? Developed a new cog that you want to be in the main bot? Contributions are welcome! Make a pull request and I'll take a look. :)

### Licence
This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License in the [licence file](/LICENSE) for more details.

## Included Features
- Wikipedia and Urban Dictionary search
- Random Dog and Cat images
- Fun commands like the 8 ball and fish command
- Search Spotify and get full quailty Album Art (Spotify API Keys needed)
- Get lyrics for songs
- Get URLs for a song link from any popular streaming service
- Expandable cog system to allow you to make your own commands

## Self Hosting TitaniumCore
Self-hosting TitaniumCore is possible, however you must get the required modules and API tokens first.

> [!IMPORTANT]
> While I have taken every precaution to block offensive content from being displayed without a disclaimer, it is your responsibility as the bot host to monitor for any offensive content posted using the bot.

> [!CAUTION]
> When generating Bot Tokens and API Secrets, do not share them with anybody!

### Python Modules
TitaniumCore relies on several Python modules to function. These modules can be installed from Pypi using Pip or your preferred package manager.\
\
**Installation Command:**\
`pip install discord.py spotipy wikipedia colorthief py-cpuinfo psutil`

### Discord Bot Token
TitaniumCore requires a Discord Bot Token to function. The steps to get one are as follows:
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and log in with your Discord Account.
2. Create a new application and fill in the information required.
3. Go to the `Bot` section, and generate a new bot.
4. Give your bot a username, and optionally, a PFP and banner.
5. Copy the Bot Token, and paste it into the bot token field in the config file. Due to security reasons, you will only be able to view the bot token once from Discord Developer Portal before having to generate a new one.

### Spotify API Key
To use the Spotify commands in TitaniumCore, a Spotify Client ID and Secret are required. If you do not provide these, Spotify commands will automatically be disabled. The steps to get these are as follows:
1. Go to the [Spotify Developers dashboard](https://developer.spotify.com/dashboard). A free or premium Spotify account is required.
2. Create a new app, set the app name and description to whatever you please.  No additional APIs are required.
3. Set the Redirect URI to any valid URL. `http://example.com` is known to work. Then, create the app.
4. Copy the Client ID and Secret for your app, and paste them into their respective fields in the config file.

### Starting the Bot
Once you have have installed the required Python modules and generated your tokens, you can run the bot as follows:
1. Navigate to the TitaniumCore directory through the terminal.
2. Once you are at the TitaniumCore directory, run `python main.py`, and monitor for any errors in the terminal.

If an error occurs, please create a GitHub issue and I will take a look.

### Generating a Bot Invite
To invite your instance of TitaniumCore to your server, an invite is required. You can use the following template to make a bot invite URL:\
`https://discord.com/oauth2/authorize?client_id=(YOUR CLIENT ID)&permissions=964220546112&scope=bot`\
You will need your Discord Client ID to make this URL. You can get this from the General Information page of your Application you generated earlier in Discord Developer Portal.

## Included Commands
TitaniumCore comes with some included commands. Below is a list of what commands are in each cog file:
- **Animal Commands** *(animals.py)*
  - **animals cat:** see a random image of a cat.
  - **animals dog:** see a random image of a dog.
  - **animals sand-cat:** get a random sand cat - requires /content/sand-cat to be present and have images inside
- **Bot Utility Commands** *(bot_utils.py)*
  - **bot ping:** see the bot's latency.
  - **bot info:** view info about the bot.
  - **bot host-info:** see information about the bot's hosting server.
  - **bot send-message:** send a message through the bot (bot owner only).
- **Cog Utility Commands (bot owner only)** *(cog_utils.py)*
  - **cogs load:** load a new cog.
  - **cogs unload:** unload a loaded cog.
  - **cogs reload:** reload a loaded cog.
  - **cogs sync:** sync the command tree.
- **Leaderboard Commands** *(leaderboard.py)*
  - **leaderboard:** see the server leaderboard.
  - **lb-control enable:** enable the server leaderboard.
  - **lb-control enable:** disable the server leaderboard.
  - **lb-control reset:** reset the server leaderboard.
  - **lb-control reset-user:** reset a user on the leaderboard.
- **Misc Commands** *(misc.py)*
  - **fun 8ball:** consult the mystical 8 ball for an answer to a question.
  - **fun random-num:** get a random number.
  - **fun dice:** roll a dice.
- **Music Commands** *(music.py)*
  - **lyrics:** get the lyrics to a song.
- **Bot Utility Commands** *(server_utils.py)*
  - **server icon:** get the current server's icon.
  - **server info:** get info about the current server.
- **Song URL Command** *(song-url.py)*
  - **song-url:** get info about a music streaming service URL. Powered by https://song.link.
- **Spotify Commands** *(spotify.py)*
  - **spotify search:** search Spotify for a song, artist or album.
  - **spotify image:** get album art for a Spotify song, album or playlist URL.
- **Web Search Commands** *(web_search.py)*
  - **urban-dictionary:** search Urban Dictionary. Results are mainly unmoderated and may be inappropriate.
  - **wikipedia:** search Wikipedia for an answer.

## Included Cogs
TitaniumCore also includes some non command cogs, which are also stored in the command folder. The list is below:
- **spotify_autoembed.py**
  - Stores the event handler for Spotify Auto-embedding.

## Developing your own Cogs
TitaniumCore is modular and will load compatible cogs automatically.

### Cogs Path
The default cogs path is:\
`(RUNNING-PATH)/commands`.\
This path can be changed to a path of your selection in the config file.

### Example Cog
I have developed an example cog that you can look at and modify to fit your needs. You can find it in `example.py`. When you are ready to use the cog, place it in your cogs folder (`/commands` by default).

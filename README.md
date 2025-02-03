# Titanium
Welcome to Titanium, the multipurpose, open source Discord bot.

[Add Titanium Now!](https://titaniumbot.me/invite) ([Privacy Policy](/Privacy.md))

## Contributions Welcome!
Have an improvement you want to make? Developed a new cog that you want to be in the main bot? Contributions are welcome! Make a pull request and I'll take a look. :3

### Licence
This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License in the [licence file](/LICENSE) for more details.

## Included Features
- Wikipedia and Urban Dictionary search
- Random Dog and Cat images
- Fun commands like the 8-ball and fish command
- Search Spotify and get full quailty Album Art (Spotify API Keys needed)
- Get lyrics for songs
- Convert any streaming service URL to Spotify and get info
- Fireboard system
- Message leaderboard
- Expandable cog system to allow you to make your own commands

## Credit
- me: bot code
- [deeppyer](https://github.com/Ovyerus/deeppyer): deepfry image code [(licenced under MIT)](https://github.com/Ovyerus/deeppyer/blob/master/LICENSE)

## Quick Start
You can quickly start using Titanium with the following link to add the main Titanium instance:\
[Add Titanium](https://titaniumbot.me/invite) ([Privacy Policy](/Privacy.md))

If you would like to self-host your own instance of Titanium instead, please read the section below.

## Self Hosting Titanium
Self-hosting Titanium is possible, however you must get the required modules and API tokens first.

> [!IMPORTANT]
> While I have taken every precaution to block offensive content from being displayed without a disclaimer, it is your responsibility as the bot host to monitor for any offensive content being posted using the bot.

> [!CAUTION]
> When generating Bot Tokens and API Secrets, do not share them with anybody!

### Discord Bot Token
Titanium requires a Discord Bot Token to function. The steps to get one are as follows:
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and log in with your Discord Account.
2. Create a new application and fill in the information required.
3. Go to the `Bot` section, and generate a new bot.
4. Give your bot a username, and optionally, a PFP and banner.
5. Copy the Bot Token, and paste it into the bot token field in the config file. Due to security reasons, you will only be able to view the bot token once from Discord Developer Portal before having to generate a new one.

### Spotify API Key
To use the Spotify commands in Titanium, a Spotify Client ID and Secret are required. If you do not provide these, Spotify commands will automatically be disabled. The steps to get these are as follows:
1. Go to the [Spotify Developers dashboard](https://developer.spotify.com/dashboard). A free or premium Spotify account is required.
2. Create a new app, set the app name and description to whatever you please.  No additional APIs are required.
3. Set the Redirect URI to any valid URL. `http://example.com` is known to work. Then, create the app.
4. Copy the Client ID and Secret for your app, and paste them into their respective fields in the config file.

### Python Modules
Titanium relies on several Python packages. A `pyproject.toml` file has been provided; it contains the list of required dependencies and target Python version that can be used with many package managers. I have also provided `uv.lock` and `.python-version` files for the **uv** package manager, see the instructions below to use it:\
\
**Installation**
1. [Install UV.](https://docs.astral.sh/uv/getting-started/installation/) This is the tool I use to manage dependencies for the project.
2. Open a terminal inside Titanium's root directory.
3. Run `uv run main.py` to install all required packages and start the bot.

If an error occurs, please create a GitHub issue and I will take a look.

### Generating a Bot Invite
To invite your instance of Titanium to your server, an invite is required. You can use the following template to make a bot invite URL:\
`https://discord.com/oauth2/authorize?client_id=(YOUR CLIENT ID)&permissions=1689814080810048`\
You will need your Discord Client ID to make this URL. You can get this from the General Information page of your Application you generated earlier in Discord Developer Portal.

## Included Commands
Titanium comes with some included commands. Below is a list of what commands are in each cog file:

> [!NOTE]
> This list was last updated 21/08/2024 and is now considered outdated. Please check the command list by looking in the files themselves, or from the command list within Discord.

- **Admin Commands** *(admin_utils.py)*
  - **admin load:** load a cog.
  - **admin unload:** unload a cog.
  - **admin reload:** reload a cog.
  - **admin sync:** sync the command tree.
  - **admin clear-console:** clear the console.
  - **admin send-message:** send a message as the bot.
  - **admin server-list:** see a list of all the servers the bot is in.
- **Animal Commands** *(animals.py)*
  - **animals cat:** see a random image of a cat.
  - **animals dog:** see a random image of a dog.
  - **animals sand-cat:** get a random sand cat.
- **Bot Utility Commands** *(bot_utils.py)*
  - **bot ping:** see the bot's latency.
  - **bot info:** view info about the bot.
  - **bot host-info:** see information about the bot's hosting server.
- **Leaderboard Commands** *(leaderboard.py)*
  - **leaderboard view:** see the server leaderboard.
  - **leaderboard privacy:** see the server leaderboard.
  - **lb-control enable:** enable the server leaderboard.
  - **lb-control disable:** disable the server leaderboard.
  - **lb-control reset:** reset the server leaderboard.
  - **lb-control reset-user:** reset a user on the server leaderboard.
- **Misc Commands** *(misc.py)*
  - **fun 8ball:** consult the mystical 8-ball for an answer to a question.
  - **fun random-num:** get a random number.
  - **fun dice:** roll a dice.
  - **fun github-roast:** get a GitHub profile roast from https://github-roast.pages.dev/.
  - **first-message:** get the first message in a channel.
  - **pfp:** get the PFP of a user.
- **Music Commands** *(music.py)*
  - **lyrics:** get the lyrics to a song.
- **Review Commands** *(reviews.py)*
  - **reviews:** see a user's ReviewDB reviews.
- **Bot Utility Commands** *(server_utils.py)*
  - **server icon:** get the current server's icon.
  - **server info:** get info about the current server.
  - **server boosts:** get info about the current server.
- **Song URL Command** *(song-url.py)*
  - **song-url:** get info about a music streaming service URL. Powered by https://song.link.
- **Spotify Commands** *(spotify.py)*
  - **spotify search:** search Spotify for a song, artist or album.
  - **spotify image:** get album art for a Spotify song, album or playlist URL.
- **Web Search Commands** *(web_search.py)*
  - **urban-dictionary:** search Urban Dictionary. Results are mainly unmoderated and may be inappropriate.
  - **wikipedia:** search Wikipedia for an answer.

## Included Cogs
Titanium also includes some non-command cogs, which are also stored in the command folder. The list is below:
- **status_update.py**
  - Stores the autoupdater for the bot's activity status.
- **welcome.py**
  - Stores the automatic welcome message for when the bot joins a server.

## Intents
Titanium uses several privileged intents. If your bot instance is verified (required for 100+ servers), you **MUST** get approval from Discord before you can use them.

- Presence Intent - needed for the now playing command.
- Server Members Intent - needed for server member counts in the server info command.
- Message Content Intent - Required for getting message content for the starboard, and for processing the leaderboard.

## Developing your own Cogs
Titanium is modular and will load compatible cogs automatically.

### Cogs Path
The default cogs path is:\
`(RUNNING-PATH)/commands`.\
This path can be changed to a path of your selection in the config file.

### Example Cog
I have developed an example cog that you can look at and modify to fit your needs. You can find it in `example.py`. When you are ready to use the cog, place it in your cogs folder (`/commands` by default).

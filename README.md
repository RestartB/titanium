# Titanium
Welcome to Titanium's main code repo! Titanium is your multipurpose, open source Discord bot.

[Add Titanium Now!](https://titaniumbot.me/invite) (you will agree to the [Privacy Policy](/Privacy.md) and [Terms of Use policy](/Terms.md))

## Contributions Welcome!
Have an improvement you want to make? Developed a new cog that you want to be in the main bot? Contributions are welcome! Make a pull request and I'll take a look. When contributing, please ensure that you use Ruff to check and format your code. This ensures that all of Titanium's code stays a consistent style. To do this with the uv package manager, run `uvx ruff format` and `uvx ruff check --fix`.

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
[Add Titanium](https://titaniumbot.me/invite) (you will agree to the [Privacy Policy](/Privacy.md) and [Terms of Use policy](/Terms.md))

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
`https://discord.com/oauth2/authorize?client_id=(YOUR CLIENT ID)`\
After you have done this, you will need to go to the [Discord Developer Portal](https://discord.dev/) and complete the following steps:
1. Select your bot from the list of apps.
2. Go to the Installation tab.
3. Tick `Guild Install` and `User Install`.
4. Select `Discord Provided Link` for the install link.
5. In Default Install Settings, select the following options:\
**User Install**\
*Scopes*\
applications.commands
\
\
**Guild Install**\
*Scopes*\
`applications.commands, bot`
\
\
*Permissions*\
`Add Reactions, Attach Files, Embed Links, Manage Messages, Manage Webhooks, Read Message History, Send Messages, Send Messages in Threads, Use Embedded Activities, Use External Emojis, Use External Stickers, Use Slash Commands, View Audit Log, View Channels`
7. Remember to save your changes when you're done!

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

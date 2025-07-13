# Self-hosting Titanium

This guide will walk you though how to self host your own instance of Titanium. If you find any issues when selfhosting, such as hardcodes values or an inaccuracy in the guide, please create a GitHub issue or send a message in the [Discord server.](https://titaniumbot.me/server)

> [!IMPORTANT]
> While I have taken every precaution to block offensive content from being displayed without a disclaimer, it is your responsibility as the bot host to monitor for any offensive content being posted using the bot.

> [!CAUTION]
> When generating Bot Tokens and API Secrets, do not share them with anybody!

## Setting up `uv`

`uv` is the package manager that I use for Titanium, that I officially support. If you haven't already installed it, go to the [uv website](https://docs.astral.sh/uv/#installation) for instructions. Once you've installed it, you can install required packages by running `uv sync` from Titanium's root folder.

> [!IMPORTANT]
> Once you have installed dependencies with uv, please ensure that ImageMagick is installed on your system.

## Copy config file

I have provided an example config file for you to use. To start using it, simply copy `example-config.cfg` and call it `config.cfg`. Then, walk through the rest of this guide to fill it in.

## Getting Spotify API Keys

Titanium has several features that rely on the Spotify API. If you don't follow this step, any commands that use the Spotify API will be disabled. To get an API key, follow these instructions:

1. Go to the [Spotify Developers dashboard](https://developer.spotify.com/dashboard). A free or premium Spotify account is required.
2. Create a new app, set the app name and description to whatever you please.  No additional APIs are required.
3. Set the Redirect URI to any valid URL. `http://example.com` is known to work. Then, create the app.
4. Copy the Client ID and Secret for your app, and paste them into their respective fields in the config file.

## Setting up Playwright

Titanium uses Playwright to render quotes using HTML. Playwright uses a headless browser to render the HTML and take a screenshot. To set it up, follow these steps:

1. Run `uv run playwright install-deps` to install dependencies.
2. Run `uv run playwright install chromium` to install the Chromium browser.
3. To verify the install was successful, run `uv run playwright codegen https://google.com`. A Chromium window and a Playwright window should open. If this happens, the install was sucessful.

> [!IMPORTANT]
> Playwright only officially supports Windows, macOS and Ubuntu. While I have gotten it to work on Fedora before, this is not supported by the Playwright team.

## Getting Discord Token

Titanium requires a Discord Bot Token to function. Here's how to get one:

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and log in with your Discord Account.
2. Create a new application and fill in the information required.
3. Go to the `Bot` section, and generate a new bot.
4. Give your bot a username, and optionally, a PFP and banner.
5. Copy the Bot Token, and paste it into the `discord-bot-token` field in the config file. Due to security reasons, you will only be able to view the bot token once from Discord Developer Portal before having to generate a new one.

## Bot Emojis

Titanium uses custom loading and explicit emojis. To upload your own, follow these steps:

1. Go to your bot in the [Discord Developer Portal](https://discord.com/developers/applications).
2. Go to the emoji tab and upload your emojis.
3. Copy the markdown for each one, and put it into the `loading-emoji` or `explicit-emoji` fields of the config file.

## (optional) Analytics Webhooks

Titanium supports outputting basic analytics to a Discord webhook. Below is an explaination of each webhook type from the config file:

- `analytics-webhook` - triggers when someone runs a Titanium command or context menu item.
- `raw-analytics-webhook` - triggers when an interaction gets triggered, this could be a slash command, context menu item, button press, loading results from autocomplete, etc. This can cause a lot of spam.
- `error-webhook` - triggers when an error is detected. Generates a unique error ID, sends command, arguments, location, user, and a full stacktrace for debugging.

If any one is left blank in the config file, it will be disabled.

## (optional) Uptime Kuma

Titanium has a basic automated system that lets you set up a push server wiht Uptime Kuma, for uptime tracking. To configure this:

1. In Uptime Kuma, create a new `Push` monitor.
2. Copy the URL provided and paste it into the `uptime-kuma-push` field in the config file.
3. Remove any arguments like `?status=up&msg=OK` from the URL, as Titanium handles this for you.
4. Change the `Heartbeat Interval` in Uptime Kuma to 30 seconds.

## (optional) Internal API Server

Titanium also includes an internal API server, for getting information about the bot from Discord. This is mainly intended to be used by the website. Please keep in mind that this API has no authentication so should be kept private. If you wish to customise it, you can do so with the following properties in the config file:

- `api-host` -  host address for the internal API server. Use 127.0.0.1 for localhost only or 0.0.0.0 for all interfaces. Defaults to `127.0.0.1`.
- `api-port` - port number for the internal API server. Defaults to `5000`.

## Other Config Values

Below is an explaination of other config file values:

- `owner-ids` - ***DEPRECATED*** - provide user IDs that are allowed to use management commands. Now automatically managed by Titanium and uses bot owner / team members.
- `control-guild` - ID of the guild that will include Titanium's management commands.
- `support-server` - ***CURRENTLY UNUSED*** - invite for a support server.
- `sync-on-start` - whether to sync commands on start. Recommended for the first time you start the bot, not for future starts as you may get rate limited by Discord.

## Running the Bot

Now you have filled out the config file and completed other setup steps, you can start the bot! To start Titanium, run the following command from Titanium's root directory:
`uv run main.py`

If the bot has started sucessfully, you should see the following line of text in the terminal:
`root: [INIT] Bot is ready and connected as (your bot name here).`

If you do not see this, please ask for help in the Discord server, or create an issue.

## Generating a Bot Invite

To invite your instance of Titanium to your server or add it to your account, an invite is required. You can use the following template to make a bot invite URL:\
`https://discord.com/oauth2/authorize?client_id=(YOUR CLIENT ID)`\
To make this link work, you will need to go to the [Discord Developer Portal](https://discord.dev/) and complete the following steps:

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
`Add Reactions, Attach Files, Embed Links, Manage Channels, Manage Messages, Manage Webhooks, Read Message History, Send Messages, Send Messages in Threads, Use Embedded Activities, Use External Emojis, Use External Stickers, Use Slash Commands, View Audit Log, View Channels`
6. Remember to save your changes when you're done!

> [!NOTE]
> It is recommended to add your instance to the control server you defined in the config file, so you can use the admin control commands.

## Adding your own cogs

Now Titanium is running, you can start to add your own cogs! Take a look at `example.py` in the root of the repository for an example, then add the cog to the `commands` folder to use it. You can also create the `commands-private` folder and put your cogs in there, if you don't want them to be tracked by Git. Once you have put the cog into your folder of choice, run the `/admin load` command to load the cog, and `/admin sync` to sync the command tree if the cog contains slash commands or context menu items. While developing, you can also run `/admin reload` to reload the cog and `/admin unload` to unload the cog.

# RestartBot
Welcome to the rewrite of RestartBot, using **discord.py Cogs**.

> [!CAUTION]
> The cogs rewrite is in active development and will contain bugs and unfinished features.

## Why?
The old code of RestartBot was very hard to work on. Every command was in the main.py file, meaning that at times it would be over 1800 lines long. This made it difficult to look at and edit. Therefore, by using cogs, each group of commands can be split into their own file, so I only need to see the commands that are relavent to what I am currently working on.

## Included Commands
RestartBot comes with some premade commands. Below is a list of what is in each cog file:\
- **utils.py**
  - **ping:** see the bot's latency.
  - **restart:** restart the bot. Only available to the bot owner.
  - **info:** view info about the bot.
  - **pfp:** see a user's PFP.
  - **host-info:** see information about the bot's hosting server.
- **cog-utils.py**
  - **sync-cogs:** sync cogs.
  - **load-cog:** load a new cog.
  - **unload-cog:** unload a loaded cog.
  - **sync-tree:** sync the command tree.
- **animals.py**
  - **cat:** see a random image of a cat.
  - **dog:** see a random image of a dog.

## Setup
Coming soon!

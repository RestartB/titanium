# Titanium v2

Welcome to Titanium's main code repo! Titanium is your multipurpose, open source Discord bot.

[Add Titanium Now!](https://titanium.fyi/invite) (you will agree to the [Privacy Policy](https://titanium.fyi/privacy/bot) and [Terms of Use policy](https://titanium.fyi/terms))

Titanium v2 includes many features designed to improve your Discord experience, such as:

- complete rewrite of Titanium v1 to include better code and SQLAlchemy ORM
- full user app support with info commands, Spotify commands, image commands and more
- prefix and slash commmand support
- fully custom [web dashboard](https://github.com/RestartB/titanium-dashboard) written in SvelteKit
- advanced moderation and automod features
- bouncer to monitor users as they join and update their profiles
- logging to keep a log of events that happen in your server
- fireboard and leaderboard to increase server engagement
- server counters for live updating stats in the channel list
- confessions to allow users to write anonymous messages, with logging for moderators
- tags to allow you to send quick responses to messages
- and more!

> [!IMPORTANT]
> Due to developer workload, I am only accepting PRs for minor features or bug fixes at this time. Please create an issue or discussion first before creating a PR, to allow me to review your request.

> [!CAUTION]
> You will need to run a PostgreSQL server to run the bot. Additionally, Titanium v2 is only tested to run on macOS and Linux. Windows support is untested, and may have unexpected issues.

## Licence

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License in the [licence file](/LICENSE) for more details.

## API

> [!CAUTION]
> NEVER publicly expose the internal API. The internal API provides full access to Titanium's data and features, and should only be used for internal communications!

Titanium exposes an internal API, allowing remote control of the bot and access to data / information. This API is designed to be internal only, to communicate with tools such as the Titanium Dashboard. To change the API's settings, change the `BOT_API_` environment variables listed in the `.env.example` file. Also ensure that you set a token via the `BOT_API_TOKEN` environment variable, that blocks access to user/server information and settings API endpoints unless the correct token is provided. If no token is provided, the bot will warn you on startup, but will allow all requests through without authentication.

### Prometheus

Titanium also exposes various Prometheus metrics via the `/metrics` endpoint. These include server and user install counts, command execution totals, error totals, and websocket / API latency. By connecting Prometheus to this endpoint, you can link to tools like Grafana and create custom dashboards, alerting, etc.

## Dashboard

It is recommended to run the [Titanium Dashboard](https://github.com/RestartB/titanium-dashboard) alongside the Titanium bot. This allows you to manage Titanium's settings from a web browser. This is required to manage some features of Titanium, such as the automod and bouncer system.

## Self hosting guide

### Database Setup

1. Create a PostgreSQL 18 database - this can be done with Docker or similar tools
2. Note down the username and password, add these to the .env file along with the host, port and database name
3. Download and install the [Atlas CLI](https://atlasgo.io/getting-started#installation) (you may also need to install Docker)
4. When you run the bot, the bot will automatically create required tables in the database and complete any needed migrations

#### Modifying tables

When developing, you may modify, add or remove tables. To migrate the database to the new schema, follow these steps:

1. If you're adding or removing a table, make sure to also add / remove it from the `lib/sql/atlas.py` file.
2. Run `atlas migrate diff --env sqlalchemy` - this will create a migration file in the `/migrations` folder
3. Review the created migration file to ensure that it looks accurate

> [!IMPORTANT]
> If you have manually modified a migration file, you will need to run `atlas migrate hash`, otherwise the migration process will fail.

#### Migrating database

Once you have generated your migration file, or if you have pulled in new migration files from an update, you should now migrate the database. Run the `t!admin migrate-db` command, restart the bot, or use the `--migrate` argument on `main.py`. The database must be running to complete the migration.

### Download Fonts

Titanium requires some fonts to be downloaded to use features such as the image caption feature. To use these features, please download:

- Figtree Font (figtree.ttf)
- Impact Font (impact.ttf)
- Futura Condensed Font (futura.otf)

Once required fonts have been downloaded, place them into the `lib/fonts` folder.

### Running the bot

1. Ensure that you have filled out the .env file with any required information
2. Install the [`uv` package manager](https://docs.astral.sh/uv/getting-started/installation/) - other package managers may work, but I develop with uv in mind
3. Ensure that the database is running, as per the instructions above
4. Run `uv run main.py` - a Python venv will be created and any required packages will be installed
5. Watch the terminal output for any errors that may appear

## Migrating v1 data

If you are moving from Titanium v1 to v2, you should migrate user data so users do not lose their preferences and data. Titanium v2 comes with an official migration script that will move Titanium v1 data to appropriate places in Titanium v2.

### Supported data

Currently, the migration script can migrate fireboard, leaderboard, server counter settings / data, and server / user tags.

### Migrating data

1. Make sure to cleanly stop Titanium v1 so all pending database writes can be completed.
2. Copy the applicable databases from the `content/sql` folder in Titanium v1 to the `v1_to_v2/dbs` folder in Titanium v2.
3. Run Titanium v2 with the `--v1tov2` argument from the root folder (folder that contains `main.py`), eg. `uv run main.py --v1tov2`.
4. Follow the steps in the terminal to complete the migration. Once done, the bot will exit.

If you have more data to migrate, simply place the new databases into the folder and start the migration script again. Data already migrated will not be overwritten.

# Titanium v2

Welcome to the Titanium v2 branch! This branch is used for Titanium v2 development, and will eventually become the main Titanium branch.

> [!CAUTION]
> Titanium v2 currently in active development. Many features are constantly changing, haven't been tested yet, and may be removed at any time. It is certain that there will be unfixed bugs. It is not recommended at this time to use Titanium v2 in production. I will not provide any support for discovered bugs at this time, and the terms of service / privacy policies for Titanium v1 do not apply to Titanium v2.

> [!IMPORTANT]
> This project is in highly active development. Therefore, I am not accepting PRs or code edits for this repo at this time. Once the initial version has been released, I will be happy to accept new PRs again.

> [!IMPORTANT]
> You will need to run a PostgreSQL server to run the bot.

<!-- > [!IMPORTANT]
> When developing, you should ensure that you're using ruff to format and lint your code, and Pyright basic type checking to ensure that code remains high quality and type safe. -->

## Database Setup

### Initial Setups

1. Create a PostgreSQL 18 database - this can be done with Docker or similar tools
2. Note down the username and password, add these to the .env file along with the host, port and database name
3. Download and install the [Atlas CLI](https://atlasgo.io/getting-started#installation) (you may also need to install Docker)
4. When you run the bot, the bot will automatically create required tables in the database and complete any needed migrations

### Modifying tables

When developing, you may modify, add or remove tables. To migrate the database to the new schema, follow these steps:

1. If you're adding or removing a table, make sure to also add / remove it from the `lib/sql/atlas.py` file.
2. Run `atlas migrate diff --env sqlalchemy` - this will create a migration file in the `/migrations` folder
3. Review the created migration file to ensure that it looks good
4. Run the `t!admin migrate-db` command, restart the bot, or use the `--migrate` argument on `main.py` to migrate the database

> [!IMPORTANT]
> If you have manually modified a migration file, you will need to run `atlas migrate hash`, otherwise the migration will fail.

## Running the bot

1. Ensure that you have filled out the .env file with any required information
2. Install the [`uv` package manager](https://docs.astral.sh/uv/getting-started/installation/) - other package managers may work, but I develop with uv in mind
3. Ensure that the database is running, as per the instructions above
4. Run `uv run main.py` - a Python venv will be created and any required packages will be installed
5. Watch the terminal output for any errors that may appear

## Migrating v1 data

If you are moving from Titanium v1 to v2, you should migrate user data so users do not lose their preferences and data.

### Supported data

Currently, the migration script can migrate fireboard, leaderboard and server counter settings / data. Tag support will be implemented when tags are added to the bot.

### Migrating data

1. Make sure to cleanly stop Titanium v1 so all pending database writes can be completed.
2. Copy the applicable databases from the `content/sql` folder in Titanium v1 to the `v1_to_v2/dbs` folder in Titanium v2.
3. Run Titanium v2 with the `--v1tov2` argument from the root folder (folder that contains `main.py`), eg. `uv run main.py --v1tov2`.
4. Allow for the migration to complete. Once done, the bot will exit.

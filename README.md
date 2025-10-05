# Titanium v2

Welcome to the Titanium v2 branch! This branch is used for Titanium v2 development, and will eventually become the main Titanium branch.

> [!CAUTION]
> Titanium v2 currently in active development. Many features are constantly changing, haven't been tested yet, and may be removed at any time. It is certain that there will be unfixed bugs. It is not recommended at this time to use Titanium v2 in production.

> [!IMPORTANT]
> You will need to run a PostgreSQL server to run the bot.

> [!IMPORTANT]
> When developing, you should ensure that you're using ruff to format and lint your code, and Pyright basic type checking to ensure that code remains high quality and type safe.

## Database Setup

### Initial Setups

1. Create a PostgreSQL 18 database - this can be done with Docker or similar tools
2. Note down the username and password, add these to the .env file along with the host, port and database name
3. Download and install the [Atlas CLI](https://atlasgo.io/getting-started#installation) (you may also need to install Docker)
4. When you run the bot, the bot will automatically create required tables in the database and complete any needed migrations

### Modifying tables

When developing, you may modify, add or remove tables. To migrate the database to the new schema, follow these steps:

1. Run `atlas migrate diff --env sqlalchemy` - this will create a migration file in the `/migrations` folder
2. Review the created migration file to ensure that it looks ok
3. Run the `t!admin migrate-db` command or restart the bot to migrate the database

## Running the bot

1. Ensure that you have filled out the .env file with any required information
2. Install the [`uv` package manager](https://docs.astral.sh/uv/getting-started/installation/) - other package managers may work, but I develop with uv in mind
3. Ensure that the database is running, as per the instructions above
4. Run `uv run main.py` - a Python venv will be created and any required packages will be installed
5. Watch the terminal output for any errors that may appear

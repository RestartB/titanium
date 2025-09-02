import logging
from typing import TYPE_CHECKING

import aiohttp
from discord.ext import commands, tasks

if TYPE_CHECKING:
    from main import TitaniumBot


class BadLinkFetcherCog(commands.Cog):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot

        # Start tasks
        self.malicious_update.start()
        self.phishing_update.start()

    def cog_unload(self) -> None:
        # Stop tasks on unload
        self.malicious_update.cancel()
        self.phishing_update.cancel()

    # Malicious update task
    @tasks.loop(hours=6)
    async def malicious_update(self) -> None:
        async with aiohttp.ClientSession() as session:
            logging.info("Fetching malicious links...")

            async with session.get(
                "https://urlhaus.abuse.ch/downloads/text/"
            ) as response:
                if response.status == 200:
                    data = (await response.text()).splitlines()

                    self.bot.phishing_links = [
                        line for line in data if not line.startswith("#")
                    ]

                    logging.info(
                        f"Updated malicious links • {len(self.bot.malicious_links)} links fetched."
                    )
                else:
                    logging.error("Failed to fetch malicious links:", response.status)

    # Phishing update task
    @tasks.loop(hours=6)
    async def phishing_update(self) -> None:
        async with aiohttp.ClientSession() as session:
            logging.info("Fetching phishing links...")

            async with session.get(
                "https://phish.co.za/latest/phishing-domains-ACTIVE.txt"
            ) as response:
                if response.status == 200:
                    self.bot.phishing_links = (await response.text()).splitlines()

                    logging.info(
                        f"Updated phishing links • {len(self.bot.phishing_links)} links fetched."
                    )
                else:
                    logging.error("Failed to fetch phishing links:", response.status)


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(BadLinkFetcherCog(bot))

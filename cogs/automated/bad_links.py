import logging
from typing import TYPE_CHECKING

import aiohttp
from discord.ext import commands, tasks

if TYPE_CHECKING:
    from main import TitaniumBot


class BadLinkFetcherCog(commands.Cog):
    """Automatic tasks to fetch and update bad / phishing links"""

    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot
        self.logger: logging.Logger = logging.getLogger("links")

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
            self.logger.info("Fetching malicious links...")

            async with session.get(
                "https://raw.githubusercontent.com/romainmarcoux/malicious-domains/main/full-domains-aa.txt"
            ) as response:
                if response.status == 200:
                    data = (await response.text()).splitlines()

                    new_malicious_links = [
                        line for line in data if not line.startswith("#")
                    ]
                else:
                    self.logger.error(
                        "Failed to fetch malicious links:", response.status
                    )
                    return

            async with session.get(
                "https://raw.githubusercontent.com/romainmarcoux/malicious-domains/main/full-domains-ab.txt"
            ) as response:
                if response.status == 200:
                    data = (await response.text()).splitlines()

                    new_malicious_links += [
                        line for line in data if not line.startswith("#")
                    ]

                else:
                    self.logger.error(
                        "Failed to fetch malicious links:", response.status
                    )
                    return

            self.bot.malicious_links = new_malicious_links

            self.logger.info(
                f"Updated malicious links • {len(new_malicious_links)} links fetched."
            )

    # Phishing update task
    @tasks.loop(hours=6)
    async def phishing_update(self) -> None:
        async with aiohttp.ClientSession() as session:
            self.logger.info("Fetching phishing links...")

            async with session.get(
                "https://phish.co.za/latest/phishing-domains-ACTIVE.txt"
            ) as response:
                if response.status == 200:
                    new_phishing_links = (await response.text()).splitlines()

                    self.bot.phishing_links = new_phishing_links

                    self.logger.info(
                        f"Updated phishing links • {len(new_phishing_links)} links fetched."
                    )
                else:
                    self.logger.error(
                        "Failed to fetch phishing links:", response.status
                    )
                    return


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(BadLinkFetcherCog(bot))

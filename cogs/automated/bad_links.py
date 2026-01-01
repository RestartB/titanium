import json
import logging
import os
from typing import TYPE_CHECKING

import aiohttp
from discord.ext import commands, tasks

if TYPE_CHECKING:
    from main import TitaniumBot


class BadLinkFetcherCog(commands.Cog):
    """Automatic tasks to fetch and update bad links"""

    REQUEST_HEADERS = {
        "User-Agent": os.getenv("REQUEST_USER_AGENT", ""),
    }

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.logger: logging.Logger = logging.getLogger("links")

        # Start tasks
        self.malicious_update.start()
        self.phishing_update.start()
        self.nsfw_update.start()

        print(self.REQUEST_HEADERS)

    def cog_unload(self) -> None:
        # Stop tasks on unload
        self.malicious_update.cancel()
        self.phishing_update.cancel()
        self.nsfw_update.cancel()

    def _generate_list(self, data: str, host_file: bool = False) -> list[str]:
        lines = data.splitlines()
        result = []

        for line in lines:
            if line.startswith("#") or not line.strip():
                continue

            if host_file:
                parts = line.split()
                if len(parts) >= 2:
                    domain = parts[1]
                    result.append(domain)
            else:
                result.append(line.strip())

        return result

    # Malicious update task
    @tasks.loop(hours=6)
    async def malicious_update(self) -> None:
        async with aiohttp.ClientSession() as session:
            self.logger.info("Fetching malicious links...")

            async with session.get(
                "https://raw.githubusercontent.com/romainmarcoux/malicious-domains/main/full-domains-aa.txt",
                headers=self.REQUEST_HEADERS,
            ) as response:
                if response.status == 200:
                    new_malicious_links = self._generate_list(await response.text())
                else:
                    self.logger.error("Failed to fetch malicious links:", response.status)
                    return

            async with session.get(
                "https://raw.githubusercontent.com/romainmarcoux/malicious-domains/main/full-domains-ab.txt",
                headers=self.REQUEST_HEADERS,
            ) as response:
                if response.status == 200:
                    new_malicious_links += self._generate_list(await response.text())
                else:
                    self.logger.error("Failed to fetch malicious links:", response.status)
                    return

            # legit links that are marked as malicious
            whitelisted_links = {
                "https://kkinstagram.com",
                "kkinstagram.com",
            }
            new_malicious_links = [
                link for link in new_malicious_links if link not in whitelisted_links
            ]

            self.bot.malicious_links = new_malicious_links
            self.logger.info(f"Updated malicious links • {len(new_malicious_links)} links fetched.")

    # Phishing update task
    @tasks.loop(hours=6)
    async def phishing_update(self) -> None:
        async with aiohttp.ClientSession() as session:
            self.logger.info("Fetching phishing links...")

            async with session.get(
                "https://raw.githubusercontent.com/Phishing-Database/Phishing.Database/refs/heads/master/phishing-domains-ACTIVE.txt",
                headers=self.REQUEST_HEADERS,
            ) as response:
                if response.status == 200:
                    new_phishing_links = self._generate_list(await response.text())
                else:
                    self.logger.error("Failed to fetch phishing links:", response.status)
                    return

            # legit links that are marked as phishing
            whitelisted_links = {
                "kkinstagram.com",
            }
            new_phishing_links = [
                link for link in new_phishing_links if link not in whitelisted_links
            ]

            self.bot.phishing_links = new_phishing_links
            self.logger.info(f"Updated phishing links • {len(new_phishing_links)} links fetched.")

    # NSFW update task
    @tasks.loop(hours=6)
    async def nsfw_update(self) -> None:
        async with aiohttp.ClientSession() as session:
            self.logger.info("Fetching NSFW links...")

            # Get meta
            async with session.get(
                "https://raw.githubusercontent.com/Bon-Appetit/porn-domains/refs/heads/main/meta.json",
                headers=self.REQUEST_HEADERS,
            ) as response:
                if response.status == 200:
                    meta = json.loads(await response.text())
                    nsfw_name = meta.get("blocklist").get("name")

                    if not nsfw_name:
                        self.logger.error("NSFW list name not found in meta.")
                        return
                else:
                    self.logger.error("Failed to fetch NSFW meta:", response.status)
                    return

            nsfw_url = f"https://raw.githubusercontent.com/Bon-Appetit/porn-domains/refs/heads/main/{nsfw_name}"
            self.logger.info(f"Obtained NSFW list URL ({nsfw_url}), fetching links...")

            async with session.get(nsfw_url, headers=self.REQUEST_HEADERS) as response:
                if response.status == 200:
                    new_nsfw_links = (await response.text()).splitlines()
                else:
                    self.logger.error("Failed to fetch NSFW links:", response.status)
                    return

            self.bot.nsfw_links = new_nsfw_links
            self.logger.info(f"Updated NSFW links • {len(new_nsfw_links)} links fetched.")


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(BadLinkFetcherCog(bot))

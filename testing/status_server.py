from discord.ext import commands
from aiohttp import web
import asyncio

class status_server(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    async def webserver(self):
        async def root(request):
            return web.Response(json={"latency-ms": round(self.bot.latency*1000, 2)})

        app = web.Application()
        runner = web.AppRunner(app)
        
        app.router.add_get('/', root)

        await runner.setup()
        
        self.site = web.TCPSite(runner, 6969)
        
        await self.bot.wait_until_ready()
        await self.site.start()

    def __unload(self):
        asyncio.ensure_future(self.site.stop())

async def setup(bot):
    await bot.add_cog(status_server(bot))

    await bot.loop.create_task(status_server.webserver())
    
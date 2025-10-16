import logging
from discord.ext import commands, tasks
from ._nodeManager import NodeManager
from .commands._musicGeneral import MusicGeneral
from .commands._musicQueueSystem import MusicQueueSystem

logging.basicConfig(level=logging.INFO)

# This is just a wrapper cog to initialize the NodeManager and load the Music commands.
class _Music(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.nodeInitialize.start()

    def cog_unload(self):
        self.nodeInitialize.cancel()



    # Initialize the NodeManager when the cog is loaded, only once.
    # self.bot.loop.create_task is not recommended as it can lead to unawaited coroutine errors when the bot is shutting down.
    @tasks.loop(count=1)
    async def nodeInitialize(self):
        self.node_manager = NodeManager(self.bot)
        await self.node_manager.start_nodes()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(_Music(bot))
    await bot.add_cog(MusicGeneral(bot))
    await bot.add_cog(MusicQueueSystem(bot))
    
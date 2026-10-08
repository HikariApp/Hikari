from discord.ext import commands, tasks
from hikari_bot.bot.extensions.musicplayer._nodemanager import NodeManager
from hikari_bot.bot.extensions.musicplayer.commands._music_general import MusicGeneral
from hikari_bot.bot.extensions.musicplayer.commands._music_queuesystem import MusicQueueSystem

# This is just a wrapper cog to initialize the NodeManager and load the Music commands.
class _Music(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.node_initialize.start()

    def cog_unload(self):
        self.node_initialize.cancel()



    # Initialize the NodeManager when the cog is loaded, only once.
    # self.bot.loop.create_task is not recommended as it can lead to unawaited coroutine errors when the bot is shutting down.
    @tasks.loop(count=1)
    async def node_initialize(self):
        self.node_manager = NodeManager(self.bot)
        await self.node_manager.start_nodes()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(_Music(bot))
    await bot.add_cog(MusicGeneral(bot))
    await bot.add_cog(MusicQueueSystem(bot))

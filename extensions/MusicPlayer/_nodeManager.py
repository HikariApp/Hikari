import logging
import pomice
from discord.ext import commands

logger = logging.getLogger("music_v2")

class NodeManager:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pomice = pomice.NodePool()

    async def start_nodes(self) -> None:
        """Initialize and start the Lavalink nodes."""
        try:
            await self.pomice.create_node(
                bot=self.bot,
                host="lavalink.lolicon.wtf",
                port=443,
                secure=True,
                password="youshallnotpass",
                identifier="MAIN",
            )
            logger.info("Pomice node created successfully.")
        except Exception as exc:
            logger.exception("Failed to create pomice node: %s", exc)

    async def get_node_pool(self):
        """Get the node pool instance."""
        return self.pomice

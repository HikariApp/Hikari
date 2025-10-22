import logging
import os
from pomice import NodePool
from discord.ext import commands

logger = logging.getLogger("music_v2")

class NodeManager:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.nodePool = NodePool()
        self.logger = self.bot.get_logger()

    async def start_nodes(self) -> None:
        """Initialize and start the Lavalink nodes."""
        try:
            await self.nodePool.create_node(
                bot=self.bot,
                host=os.getenv("LAVALINK_HOST"),
                port=int(os.getenv("LAVALINK_PORT")),
                secure=os.getenv("LAVALINK_IS_SECURE").lower() == "true",
                password=os.getenv("LAVALINK_PASSWORD"),
                identifier="MAIN",
            )
            self.logger.info("Pomice node created successfully.")
        except Exception as exc:
            self.logger.exception("Failed to create pomice node: %s", exc)

    async def get_node_pool(self):
        """Get the node pool instance."""
        return self.nodePool

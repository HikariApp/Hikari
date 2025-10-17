import logging
import os
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
                host=os.getenv("LAVALINK_HOST"),
                port=os.getenv("LAVALINK_PORT"),
                secure=os.getenv("LAVALINK_IS_SECURE").lower() == "true",
                password=os.getenv("LAVALINK_PASSWORD"),
                identifier="MAIN",
            )
            logger.info("Pomice node created successfully.")
        except Exception as exc:
            logger.exception("Failed to create pomice node: %s", exc)

    async def get_node_pool(self):
        """Get the node pool instance."""
        return self.pomice

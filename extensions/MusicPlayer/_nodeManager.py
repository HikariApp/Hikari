import os
from lava_lyra import NodePool
from discord.ext.commands import Bot


class NodeManager:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.nodePool = NodePool()
        self.logger = self.bot.getLogger()


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
            self.logger.info(f"LavaLyra (Pomice) node has been established to a Lavalink server at {self.nodePool.nodes if self.nodePool.nodes else '<unknown host>'}.")

        except Exception as exc:
            self.logger.exception("Failed to create lava_lyra node: %s", exc)


    async def get_node_pool(self):
        """Get the node pool instance."""
        return self.nodePool



"""
The MIT License (MIT)

Copyright (c) 2025 Hikari

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

# SPDX-License-Identifier: MIT

import os
from lava_lyra import NodePool
from discord.ext.commands import Bot

ENV_TRUTHY_VALUES = {"1", "true", "yes"}

def customBoolCheck(str: str) -> bool:
    """Check if the string is a truthy value."""
    return str.strip().lower() in ENV_TRUTHY_VALUES

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
                secure=customBoolCheck(os.getenv("LAVALINK_IS_SECURE")),
                password=os.getenv("LAVALINK_PASSWORD"),
                identifier="MAIN",
            )
            self.logger.info(f"LavaLyra (Pomice) node has been established to a Lavalink server at {self.nodePool.nodes if self.nodePool.nodes else '<unknown host>'}.")

        except Exception as exc:
            self.logger.exception("Failed to create lava_lyra node: %s", exc)


    async def get_node_pool(self):
        """Get the node pool instance."""
        return self.nodePool


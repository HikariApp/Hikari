from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import discord
from discord import Thread
from discord.ext.commands import Bot

from hikari_bot.bot.extensions.chatbot._claudeservice import DEFAULT_TIER, TIER_PRIORITY


class ChatBotRepository:
    """MongoDB storage for ChatBot conversations and access tiers.

    Each conversation is one document in `chatbot.conversations`, keyed by its Discord thread ID.
    `messages` holds the Claude message history and is only ever appended to, which keeps the
    prompt cache warm and the thinking blocks valid.
    """

    def __init__(self, db_cluster):
        database = db_cluster["chatbot"]
        self.conversations = database["conversations"]
        self.user_access = database["user_access"]
        self.server_access = database["server_access"]


    async def get_access_level(self, bot: Bot, user: discord.abc.User, guild_id: Optional[int]) -> str:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Return the highest access tier of a user and their server. Defaults to `'trial'`.
        The bot owner (and team members) always get `'premium'`.
        """

        if await bot.is_owner(user):
            return "premium"

        levels = [DEFAULT_TIER]

        user_entry = await self.user_access.find_one({"_id": user.id})
        if user_entry:
            levels.append(user_entry.get("access_level", DEFAULT_TIER))

        if guild_id:
            server_entry = await self.server_access.find_one({"_id": guild_id})
            if server_entry:
                levels.append(server_entry.get("access_level", DEFAULT_TIER))

        # Unknown levels rank as trial, and max() keeps the first of equal ranks, so this is always a known tier.
        return max(levels, key=lambda level: TIER_PRIORITY.get(str(level).lower(), 0)).lower()


    async def get_conversation(self, thread_id: int) -> Optional[Dict[str, Any]]:
        return await self.conversations.find_one({"_id": thread_id})


    async def create_conversation(self, thread: Thread, owner_id: int, access_level: str, messages: List[Dict[str, Any]], file_ids: List[str]) -> None:
        await self.conversations.insert_one({
            "_id": thread.id,
            "guild_id": thread.guild.id,
            "parent_channel_id": thread.parent_id,
            "owner_id": owner_id,
            "access_level": access_level,
            "messages": messages,
            "file_ids": file_ids,
            "created_at": datetime.now(timezone.utc),
        })


    async def append_turn(self, thread_id: int, messages: List[Dict[str, Any]], file_ids: List[str]) -> None:
        await self.conversations.update_one(
            {"_id": thread_id},
            {
                "$push": {"messages": {"$each": messages}, "file_ids": {"$each": file_ids}},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )


    async def delete_conversations(self, query: Dict[str, Any]) -> tuple[int, List[str]]:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Delete the conversations matching `query`.

        Returns
        -------
        tuple[int, list[str]]:
            The number of conversations deleted, and the Claude file IDs they referenced.
        """

        file_ids = []
        async for entry in self.conversations.find(query, {"file_ids": 1}):
            file_ids.extend(entry.get("file_ids", []))

        result = await self.conversations.delete_many(query)
        return result.deleted_count, file_ids

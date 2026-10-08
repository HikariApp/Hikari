import asyncio
from collections import defaultdict
from typing import Any, Dict, List, Optional

import anthropic
import discord
from discord import Embed, Interaction, Thread, app_commands
from discord.app_commands import BotMissingPermissions, MissingPermissions
from discord.ext.commands import Bot, Cog

from hikari_bot.bot.extensions.chatbot._chatbotrepository import ChatBotRepository
from hikari_bot.bot.extensions.chatbot._chatbotui import (
    CUT_OFF_NOTE,
    REPLY_MENTIONS,
    ChatBotModal,
    api_error_embed,
    error_embed,
    split_message,
)
from hikari_bot.bot.extensions.chatbot._claudeservice import (
    DEFAULT_TIER,
    ChatBotError,
    ClaudeService,
    build_user_message,
    system_prompt,
)
from hikari_bot.helpers.errorhandling import NotBotOwnerError


THREAD_NAME_PREFIX = "Chat with "


class ChatBot(Cog):
    """ChatBot Discord bot integration, powered by Claude"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.repository = ChatBotRepository(self.bot.get_mongo_cluster_db())
        self.claude = ClaudeService()
        self._locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


    async def cog_unload(self) -> None:
        await self.claude.close()


    def system_prompt(self) -> str:
        return system_prompt(self.bot.user.name if self.bot.user else "AI Assistant")


    async def start_conversation(self, interaction: Interaction, text: str, attachment: Optional[discord.Attachment]) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Answer the first message of a conversation, then open a thread on the reply for the rest of it.
        """

        file_ids: List[str] = []
        saved = False

        try:
            access_level = await self.repository.get_access_level(self.bot, interaction.user, interaction.guild_id)
            blocks, file_ids, skipped = await self.claude.upload_attachments([attachment] if attachment else [])
            user_message = build_user_message(interaction.user, text, blocks, skipped)

            reply, assistant_message, cut_off = await self.claude.reply(self.system_prompt(), access_level, [user_message])

            chunks = split_message(reply)
            if cut_off:
                chunks.append(CUT_OFF_NOTE)

            first = await interaction.followup.send(chunks[0], allowed_mentions=REPLY_MENTIONS, wait=True)
            message = await interaction.channel.fetch_message(first.id)
            thread = await message.create_thread(
                name=f"{THREAD_NAME_PREFIX}{interaction.user.display_name}"[:100],
                auto_archive_duration=1440,  # Archive after 24 hours of inactivity
            )

            await self.repository.create_conversation(thread, interaction.user.id, access_level, [user_message, assistant_message], file_ids)
            saved = True

            for chunk in chunks[1:]:
                await thread.send(chunk, allowed_mentions=REPLY_MENTIONS)

        except ChatBotError as e:
            await interaction.followup.send(embed=error_embed(str(e)))

        except anthropic.APIError as e:
            await interaction.followup.send(embed=api_error_embed(e))

        except discord.Forbidden:
            await interaction.followup.send(embed=error_embed("I couldn't **create the thread** for our conversation. Please **double-check** my **permissions** and **role position**."))

        finally:
            if not saved and file_ids:
                await self.claude.delete_files(file_ids)


    async def continue_conversation(self, message: discord.Message, entry: Dict[str, Any]) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Answer a message sent in a ChatBot thread.

        A turn is only stored once Claude has answered it, so failed or refused messages don't
        become part of the history.
        """

        file_ids: List[str] = []
        saved = False

        try:
            blocks, file_ids, skipped = await self.claude.upload_attachments(message.attachments)
            user_message = build_user_message(message.author, message.content, blocks, skipped)

            reply, assistant_message, cut_off = await self.claude.reply(
                self.system_prompt(),
                entry.get("access_level", DEFAULT_TIER),
                [*entry["messages"], user_message],
            )

            await self.repository.append_turn(message.channel.id, [user_message, assistant_message], file_ids)
            saved = True

            chunks = split_message(reply)
            if cut_off:
                chunks.append(CUT_OFF_NOTE)

            # Reply to the user's message with the first chunk, then send the rest normally
            await message.reply(chunks[0], allowed_mentions=REPLY_MENTIONS)
            for chunk in chunks[1:]:
                await message.channel.send(chunk, allowed_mentions=REPLY_MENTIONS)

        except ChatBotError as e:
            await message.reply(embed=error_embed(str(e)), allowed_mentions=REPLY_MENTIONS)

        except anthropic.APIError as e:
            await message.reply(embed=api_error_embed(e), allowed_mentions=REPLY_MENTIONS)

        finally:
            if not saved and file_ids:
                await self.claude.delete_files(file_ids)


    # Command to initiate ChatBot interaction
    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=True)
    @app_commands.checks.has_permissions(create_public_threads=True)
    @app_commands.checks.bot_has_permissions(create_public_threads=True, send_messages_in_threads=True)
    async def chatbot(self, interaction: discord.Interaction, attachment: Optional[discord.Attachment] = None):
        """
        Chat with our ChatBot in a dedicated thread.

        Parameters
        ----------
        attachment: Optional[discord.Attachment]
            An image, PDF or text file to send along with your message.
        """

        if isinstance(interaction.channel, discord.Thread):
            return await interaction.response.send_message(embed=error_embed(f"I don't have the ablilty to start a new conversation in an **existing thread** :thinking: ... Perhaps try to use it in a **text channel** instead. {interaction.user.mention} :pleading_face: ?"))

        async def on_content(modal_interaction: Interaction, text: str) -> None:
            await self.start_conversation(modal_interaction, text, attachment)

        await interaction.response.send_modal(ChatBotModal(on_content))


    @chatbot.error
    async def chatbot_error(self, interaction: Interaction, error):
        if isinstance(error, MissingPermissions):
            await interaction.response.send_message(embed=error_embed(f"This command **requires** `create_public_threads` permission, and you probably **don't have** it, {interaction.user.mention}."))

        elif isinstance(error, BotMissingPermissions):
            await interaction.response.send_message(embed=error_embed("I couldn't **create** a public thread for our conversation. Please **double-check** my **permissions** and **role position**."))

        else:
            raise error


    # Listen for messages in ChatBot threads
    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.type not in (discord.MessageType.default, discord.MessageType.reply):
            return

        # Only threads the bot started can be ChatBot threads
        if not isinstance(message.channel, Thread) or message.channel.owner_id != self.bot.user.id:
            return

        # One reply at a time per thread, so every turn sees the one before it
        async with self._locks[message.channel.id]:
            entry = await self.repository.get_conversation(message.channel.id)
            if not entry:
                return  # Not a ChatBot thread we're tracking

            # Show "{bot_name} is typing..." while Claude answers
            async with message.channel.typing():
                await self.continue_conversation(message, entry)


    # Command to reset ChatBot history
    @app_commands.command(name="resetchatbot", description="Clear chat history in ChatBot")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=True)
    @app_commands.checks.has_permissions(manage_threads=True, manage_guild=True)
    @app_commands.describe(type="Reset options")
    @app_commands.choices(type=[
        app_commands.Choice(name="Reset for current channel", value="channel"),
        app_commands.Choice(name="Reset for current thread", value="thread"),
        app_commands.Choice(name="Reset for current server", value="server"),
        app_commands.Choice(name="Reset for all channel(s) and server(s)", value="all")
    ])
    async def resetchatbot(self, interaction: Interaction, type: app_commands.Choice[str]) -> None:
        """
        Clear chat history in ChatBot

        Parameters
        ----------
        type: app_commands.Choice[str]
            The reset options choice.
        """

        if type.value == "all" and not await self.bot.is_owner(interaction.user):
            return await interaction.response.send_message(NotBotOwnerError(), ephemeral=True)

        channel = interaction.channel
        is_thread = isinstance(channel, Thread)

        if type.value == "channel":
            # In a thread, "current channel" means the channel the thread belongs to
            channel_id = channel.parent_id if is_thread else channel.id
            query, scope = {"parent_channel_id": channel_id}, f"<#{channel_id}>"

        elif type.value == "thread":
            if not is_thread:
                return await interaction.response.send_message(embed=error_embed(f"<#{channel.id}> is **not a thread**."), ephemeral=True)
            query, scope = {"_id": channel.id}, f"{channel.mention} in **current thread**"

        elif type.value == "server":
            query, scope = {"guild_id": interaction.guild_id}, "**this server**"

        else:
            query, scope = {}, "**all server(s), channel(s) and thread(s)**"

        await interaction.response.defer(ephemeral=True)

        deleted, file_ids = await self.repository.delete_conversations(query)
        if not deleted:
            return await interaction.followup.send(embed=error_embed(f"No **chat history** found on {scope}."), ephemeral=True)

        await self.claude.delete_files(file_ids)

        reset_embed = Embed(title="", color=interaction.user.color)
        reset_embed.add_field(name="", value=f"**Chat history** reset for {scope}.", inline=False)
        await interaction.followup.send(embed=reset_embed, ephemeral=True)


    @resetchatbot.error
    async def resetchatbot_error(self, interaction: Interaction, error):
        if isinstance(error, MissingPermissions):
            await interaction.response.send_message(embed=error_embed(f"This command **requires** `manage_threads` and `manage_guild` permission, and you probably **don't have** it, {interaction.user.mention}."))

        else:
            raise error


async def setup(bot: Bot):
    await bot.add_cog(ChatBot(bot))

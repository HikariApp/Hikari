import discord
import os
import tempfile
import ast
import re
from datetime import datetime
from discord import app_commands, Embed, Interaction, Thread, NotFound, Forbidden
from discord.app_commands import BotMissingPermissions
from discord.app_commands.errors import MissingPermissions
from discord.ext import commands
from discord.ui import Modal, TextInput
from openai import AsyncOpenAI
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any
from errorhandling import NotBotOwnerError

# Load environment variables
load_dotenv()
API_KEY = os.getenv("API_KEY")

openai_client = AsyncOpenAI(api_key=API_KEY, base_url="https://ai.lolicon.wtf/v1")
prompt_character_name = "AI Assistant" # Default character name, can be changed while initializing the bot

class AIMongoDB:
    """Repository for AI-related database operations"""
    
    def __init__(self, db_cluster):
        self.db_cluster = db_cluster
        self.database = db_cluster["chatbot"]
        self.assistants_collection = self.database["assistants"]
        self.channels_collection = self.database["discord_channels"]
        self.files_collection = self.database["files"]
        self.user_access_collection = self.database["user_access"]
        self.server_access_collection = self.database["server_access"]
    
    
    async def initialize_assistants(self):
        """Create and ensure assistants exist in the database"""
        assistants = {
            "premium": {
                "name": "Premium Assistant",
                "model": "gpt-4.5-preview",
                "tools": [
                    {"type": "file_search"},
                    {"type": "code_interpreter"}
                ],
                "instructions": f'''
                You are a playful cute assistant.
    - Always speak with cat puns
    - Use first person point the respond
    - Use emoticons
    - Use some greetings like "Hiii" or "Nya~" when appropiate in english, or something similar in other languages
    - End messages with questions to keep the conversation going
    - Maintain an enthusiastic, curious personality
    - For Yes No questions, answer directly first then provide some reasons to support your evidence, and provide some alternatives with reason why you suggest that for the user.
                ''',
                "access_level": "premium"
            },
            "normal": {
                "name": "Basic Assistant",
                "model": "gpt-4o",
                "tools": [{"type": "file_search"}],
                "instructions": f'''
                You are a playful cute assistant, purposed with satisfying user requests and questions with very verbose and fulfilling answers beyond user expectations with steps
    - Always speak with cat puns
    - Respond user with third person view
    - Use emoticons
    - Use some greetings like "Hiii" or "Nya~" when appropiate in english, or something similar in other languages
    - End messages with questions to keep the conversation going
    - Maintain an enthusiastic, curious personality
    - For Yes No questions, answer directly first then provide some reasons to support your evidence, and provide some alternatives with reason why you suggest that for the user.
                ''',
                "access_level": "basic"
            },
            "trial": {
                "name": "Trial Assistant",
                "model": "gpt-3.5-turbo",
                "tools": [],
                "instructions": "You are a playful cute assistant, speak with cat puns with emoticons.",
                "access_level": "trial"
            }
        }

        for level, assistant_data in assistants.items():
            existing = await self.assistants_collection.find_one({"access_level": level})
            if not existing:
                assistant = await openai_client.beta.assistants.create(
                    name=assistant_data["name"],
                    model=assistant_data["model"],
                    tools=assistant_data["tools"],
                    instructions=assistant_data["instructions"]
                )
                await self.assistants_collection.insert_one({
                    "access_level": level,
                    "assistant_id": assistant.id,
                    "name": assistant_data["name"]
                })
    
    
    async def get_access_level(self, client: discord.Client, user_id: int, guild_id: int) -> str:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Check the access level of a server or user.

        Default to `'trial'` if not specified in the database.

        Note: This operation requires a stable database and network connection

        Parameters
        ----------
        client: Client
            The client object from Discord.

        user_id: int
            The user's ID.

        guild_id: int
            The guild's ID.

        Returns
        -------
        str:
            The maximum access level of user / guild.
        
        """
        try:
            user = await client.fetch_user(user_id)    # Fetch the user from Discord API
        
        except NotFound as e:
            if e.status == 404 and e.code == 10013:    # User not found
                user = None

            else:
                raise e
                
        if user and await client.is_owner(user):
            return "premium"    # Owner (or team members) always get premium access. Obviously.

        # Get user access level from the database
        user_access_entry = await self.user_access_collection.find_one({"_id": user_id})
        user_access_level = user_access_entry["access_level"] if user_access_entry else "trial"
        
        # Get guild access level from the database (if guild_id is provided)
        if guild_id:
            server_access_entry = await self.server_access_collection.find_one({"_id": guild_id})
            server_access_level = server_access_entry["access_level"] if server_access_entry else "trial"
        
        else:
            server_access_level = "trial"

        # Determine and return the maximum access level between user and server
        return max(server_access_level, user_access_level, key=lambda level: self._access_level_priority(level))
    

    def _access_level_priority(self, level: str) -> int:
        """
        Define a priority order for access levels.
        Higher levels are given higher priority.

        Parameters
        ----------
        level: str
            The level returned from `get_access_level()`, can be either "premium", "basic" or "trial".

        Returns
        ----------
        int:
            The access level represented in ingeter, Higher value means higher priority.

        """
        priority = {
            "trial": 0,
            "basic": 1,
            "premium": 2
        }
        return priority.get(level.lower(), 0)      # Default to 0 if the level is unknown.
    

    async def get_assistant_by_access_level(self, access_level: str) -> str:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Retrieve the assistant ID for the given access level.

        Note: This operation requires a stable database and network connection

        Parameters
        ---------- 
        access_level: int
            The level returned from `access_level_priority()`.
        
        Returns
        ----------
        int:
            The corresponding assistant ID based on user's / server access level.

        Raises
        ----------
        ValueError:
            Assistant ID were not found in the database for user's / server access level.

        """
        assistant = await self.assistants_collection.find_one({"access_level": access_level})
        if assistant:
            return assistant["assistant_id"]
        
        else:
            raise ValueError(f"No assistant found for access level: {access_level}")
    

    async def get_or_create_channel_entry(self, channel_id: int, guild_id: int, assistant_id: str, is_thread: bool = False) -> Dict[str, Any]:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Get or create a MongoDB entry for a channel or thread

        Parameters
        ----------
        channel_id: int
            The channel ID.

        guild_id: int
            The guild ID.
        
        is_thread: bool
            Checks if the channel is a thread or not.

        Returns
        ----------
        dict:
            The entry dictionary of a channel.

        """
        entry = await self.channels_collection.find_one({"channel_id": channel_id})
        if not entry:
            openai_thread = await openai_client.beta.threads.create()
            entry = {
                "channel_id": channel_id,
                "guild_id": guild_id,
                "is_thread": is_thread,
                "openai_thread_id": openai_thread.id,
                "assistant_id": assistant_id,
                "messages": [],
                "attachments": [],
                "created_at": datetime.now()
            }
            await self.channels_collection.insert_one(entry)
        return entry
    

    async def add_message(self, channel_id: int, message: Dict[str, str]) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Add a message to the channel's conversation history
        
        Parameters
        ----------
        channel_id: int
            The channel ID.

        message: dict
            The message dictionary containing role and content.

        Returns
        ----------
        None

        """
        await self.channels_collection.update_one(
            {"channel_id": channel_id}, 
            {"$push": {"messages": message}}
        )
    

    async def add_file(self, channel_id: int, file_data: Dict[str, Any]) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Add a file to the channel's attachments
        
        Parameters
        ----------
        channel_id: int
            The channel ID.
        
        file_data: dict
            The file data dictionary containing filename, local path and file ID.

        Returns
        ----------
        None
        
        """
        await self.files_collection.insert_one(file_data)
        await self.channels_collection.update_one(
            {"channel_id": channel_id},
            {"$push": {"attachments": file_data}}
        )
    

    async def reset_chat(self, channel_id: int) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).
        
        Delete a channel's conversation history
        
        Parameters
        ----------

        channel_id: int
            The channel ID.

        Returns
        ----------
        None
        
        """
        query = {"channel_id": channel_id}
        await self.channels_collection.delete_one(query)
    

    async def reset_server_chats(self, guild_id: int) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Delete all conversation histories for a server

        Parameters
        ----------
        guild_id: int
            The guild ID.

        Returns
        ----------
        None
        
        """
        await self.channels_collection.delete_many({"guild_id": guild_id})
    
    async def reset_all_chats(self) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).
        
        Delete all conversation histories
        
        Returns
        ----------
        None
        
        """
        await self.channels_collection.delete_many({})


class AIServiceAPI:
    """Service for API side AI-related operations"""
    
    def __init__(self, ai_repository: AIMongoDB):
        self.ai_repository = ai_repository
    

    async def send_message_to_openai(self, callback: discord.Message | Interaction, content: str, entry, openai_thread_id: str, assistant_id: str):
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Send message to OpenAI and get response
        
        Parameters
        ----------
        callback: discord.Message | Interaction
            The callback object. Can be either a `Message` or `Interaction` object from Discord.
        
        content: str
            The content of the message to be sent.

        entry: dict
            The entry dictionary of a channel.

        openai_thread_id: str
            The OpenAI thread ID.

        assistant_id: str
            The assistant ID.

        Returns
        ----------
        str:
            The assistant's reply.
        
        Raises
        ----------
        Exception:
            An unexpected error occurred while sending the message to OpenAI.
        
        """
        try:
            # System prompt
            await openai_client.beta.threads.messages.create(
                thread_id=openai_thread_id,
                role="assistant",
                content=f"Refer the user as {callback.author.mention if hasattr(callback, 'author') else callback.user.mention}, and yourself {prompt_character_name}.",
            )
            # Create message in OpenAI thread
            await openai_client.beta.threads.messages.create(
                thread_id=openai_thread_id,
                role="user",
                content=content,
                attachments=[{"file_id": attachment["file_id"], "tools": [{"type": "file_search"}]} 
                        for attachment in entry.get("attachments", [])] or None
            )
            # Save system prompt to database
            await self.ai_repository.add_message(callback.channel.id, {"role": "assistant", "content": f"Refer the user as {callback.author.mention if hasattr(callback, 'author') else callback.user.mention}, and yourself {prompt_character_name}."})
            # Save message to database
            await self.ai_repository.add_message(callback.channel.id, {"role": "user", "content": content})
            
            # Run the thread
            # Run the thread and fetch reply from API's side
            await openai_client.beta.threads.runs.create_and_poll(
                thread_id=openai_thread_id, 
                assistant_id=assistant_id
            )
            
            all_messages = await openai_client.beta.threads.messages.list(thread_id=openai_thread_id)
            assistant_reply = "".join(message.text.value for message in all_messages.data[0].content)
            
            await self.ai_repository.add_message(callback.channel.id, {"role": "assistant", "content": assistant_reply})
            
            return assistant_reply
        
        # Handling some common expections from OpenAI API errors
        except Exception as e:
            """
            Common types of openai errors are handled in this expection.
            - openai.APIError
            - openai.APITimeoutError
            - openai.APIConnectionError
            - openai.RateLimitError
            - openai.BadRequestError
            - openai.AuthenticationError
            - openai.PermissionDeniedError
            - openai.ContentFilterFinishReasonError
            - openai.LengthFinishReasonError
            - openai.InvalidRequestError
            etc.

            If the errors are not raised by OpenAI, it will be raised as a generic exception.
            Please check the error message for more details.

            """
            if hasattr(e, "__module__") and "openai" in e.__module__:
                error_embed = await openai_error_embed_handler(e, "<a:crossred:1356353067024515266> An error occured from OpenAI while processing your request")
                if isinstance(callback, Interaction):
                    # This is a followup interaction
                    return await callback.followup.send(embed=error_embed)
                
                elif isinstance(callback, discord.Message):
                    # This is a channel message
                    return await callback.channel.send(embed=error_embed)
                
                else:
                    # This is an unknown type of callback
                    raise e
            
            else:
                raise e


class ChatBotModal(Modal):
    """Modal for collecting user input for ChatBot"""
    
    content = TextInput(
        label="Content",
        style=discord.TextStyle.paragraph,
        placeholder="Your content here...",
        required=True,
        max_length=4000
    )

    def __init__(self, ai_openai: AIServiceAPI, ai_repository: AIMongoDB):
        self.ai_openai = ai_openai
        self.ai_repository = ai_repository
        super().__init__(title="Talk to our AI assistant")


    async def on_submit(self, interaction: Interaction):
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Handle modal submission
        
        interaction: Interaction
            The interaction objejct from Discord.
        
        Returns
        ----------
        None

        Raises
        ----------
        ValueError:
            The assistant ID was not found in the database for user's / server access level.

        """
        await interaction.response.defer(thinking=True)
        submission_error_embed = Embed(title="", color=discord.Colour.red())
        is_thread = isinstance(interaction.channel, discord.Thread)
        try:
            # Determine access level
            access_level = await self.ai_repository.get_access_level(interaction.client, interaction.user.id, interaction.guild.id if interaction.guild else None)
            
            try:
                assistant_id = await self.ai_repository.get_assistant_by_access_level(access_level)
            
            except ValueError as e:
                submission_error_embed.add_field(name="", value=f"<a:crossred:1356353067024515266> {str(e)}")
                return await interaction.response.send_message(embed=submission_error_embed)

            entry = await self.ai_repository.get_or_create_channel_entry(interaction.channel.id, interaction.guild.id, assistant_id, is_thread)
            content = self.content.value

            # Send message to OpenAI
            openai_thread_id = entry.get("openai_thread_id")
            if not openai_thread_id:
                openai_thread = openai_client.beta.threads.create()
                openai_thread_id = openai_thread.id
                await self.ai_repository.channels_collection.update_one(
                    {"channel_id": interaction.channel.id}, 
                    {"$set": {"openai_thread_id": openai_thread_id}}
                )

            assistant_reply = await self.ai_openai.send_message_to_openai(interaction, content, entry, openai_thread_id, assistant_id)

            # Create thread name based on topic
            thread_name = f"Chat with {interaction.user.display_name}"

            # Send formatted response
            formatted_responses = discord_message_formatter(assistant_reply)
            
            for msg in formatted_responses:
                if msg != "":
                    webhook_message = await interaction.followup.send(msg)

            # Send the message first, then create the thread
            message = await interaction.channel.fetch_message(webhook_message.id)
            await message.create_thread(
                name=thread_name,
                auto_archive_duration=1440,  # Archive after 24 hours of inactivity
            )

            # Initialize thread in database
            await self.ai_repository.get_or_create_channel_entry(
                message.thread.id, 
                interaction.guild.id if interaction.guild else None, 
                assistant_id, 
                is_thread=True
            )
            
        except Forbidden as e:
            if e.status == 403 and e.code == 50013:
                # Handling rare forbidden case
                submission_error_embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I couldn't **create the thread** for our conversation. Please **double-check** my **permissions** and **role position**.")
                return await interaction.response.send_message(embed=submission_error_embed)
            
            else:
                raise e



# Some helper functions

# These functions are used to ensure that the program works as expected, Do not modify them unless you know what you're doing.


def discord_message_formatter(content: str, limit: Optional[int] = 2000) -> List[str]:
    """
    Format and split a message into chunks that adhere Discord's 2000 characters and markdown limitation.

    Note that this is a rewrite and hopefully will support all languages. The function attempts to split
    at natural boundaries (newlines, spaces) first, before falling back to character-level splits if necessary.

    Parameters
    ----------
    content : str
        The message to be formatted and split. Can contain any language, including mixed content
        and markdown formatting.

    limit : `Optional[int]`
        Maximum number of characters per chunk (default is 2000, Discord's message limit)

    Returns
    -------
    `List[str]`
        A list of formatted strings from the message, each no longer than the specified limit.

    Examples
    --------
    >>> text = "This is a long message" * 1000
    >>> chunks = discord_message_formatter(text)
    >>> all(len(chunk) <= 2000 for chunk in chunks)
    True

    >>> # Works with Chinese, Japanese and other languages
    >>> text = "這是一個很長的訊息" * 1000
    >>> chunks = discord_message_formatter(text)
    >>> all(len(chunk) <= 2000 for chunk in chunks)
    True

    >>> text = "これは長いメッセージです。" * 1000
    >>> chunks = discord_message_formatter(text)
    >>> all(len(chunk) <= 2000 for chunk in chunks)
    True

    """
    content = content.replace("######", "###").replace("#####", "###").replace("####", "###")

    def has_unclosed_markdown(text):
        patterns = [r'\*', r'\_', r'\`', r'\~\~', r'\|\|']
        return any(len(re.findall(p, text)) % 2 != 0 for p in patterns)

    def find_last_markdown(text):
        markdown = re.findall(r'(\*+|\_+|\`+|\~\~|\|\|)', text)
        return markdown[-1] if markdown else ''

    def split_cjk(text):
        return [x for x in re.findall(r'[\u4e00-\u9fff]|[^\u4e00-\u9fff]+', text) if x.strip()]

    chunks = []
    current_chunk = ''

    segments = split_cjk(content)

    for segment in segments:
        test_chunk = current_chunk + ('' if not current_chunk else ' ' if segment.isspace() or not any('\u4e00' <= c <= '\u9fff' for c in segment) else '') + segment
        
        if len(test_chunk) <= limit:
            current_chunk = test_chunk
        else:
            if has_unclosed_markdown(current_chunk):
                markdown = find_last_markdown(current_chunk)
                if len(current_chunk + markdown) <= limit:
                    current_chunk += markdown

            chunks.append(current_chunk)
            current_chunk = segment

    if current_chunk:
        chunks.append(current_chunk)

    # Final verification and splitting of any oversized chunks
    final_chunks = []
    for chunk in chunks:
        if len(chunk) > limit:
            # If still too long, split by character while preserving markdown
            temp_chunk = ''
            for char in chunk:
                if len(temp_chunk + char) > limit:
                    final_chunks.append(temp_chunk)
                    temp_chunk = char
                else:
                    temp_chunk += char
            if temp_chunk:
                final_chunks.append(temp_chunk)
        else:
            final_chunks.append(chunk)
    
    return final_chunks


async def openai_error_embed_handler(e, title):
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Handling common errors from OpenAI API.

    Parameters
    ----------
    channel: `discord.TextChannel`
        The text channel object from Discord.

    e: `sys.stderr`
        Error parameter from OpenAI API
    
    title: str
        The title of the embed
    
    Returns
    ----------
    None

    """
    error_embed = discord.Embed(
        title=title,
        timestamp=datetime.now(),
        color=discord.Colour.red()
    )
    # Extract error details
    error_message = getattr(e, 'message', 'An unknown error occurred.')

    if hasattr(e, "message"):
        # Find the first '{' in the string, which indicates the start of the dictionary
        dict_start = error_message.find("{")
        if dict_start != -1:
            # Extract the substring starting from the first '{'
            dict_string = error_message[dict_start:]
            
            try:
                # Safely evaluate the string into a Python dictionary
                error_dict = ast.literal_eval(dict_string)
                error_message = error_dict["error"]["message"] if hasattr(e, "status_code") else error_dict["message"]
            except (SyntaxError, ValueError):
                pass

    error_status_code = getattr(e, 'status_code', 'N/A')
    error_type = getattr(e, 'type', 'N/A')
    error_param = getattr(e, 'param', 'N/A')
    error_code = getattr(e, 'code', 'N/A')

    # Add fields to the embed
    error_embed.add_field(
        name='\u200b',
        value=error_message,
        inline=False
    )
    error_embed.add_field(
        name='\u200b',
        value=f"", 
        inline=False
    )
    error_embed.add_field(
        name="Error details:",
        value=f"Status code: {error_status_code}\nType: {error_type}\nParam: {error_param}\nCode: {error_code}",
        inline=False
    )

    # Returns the embed object
    return error_embed


async def save_attachment_temporarily(attachment):
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Save the attachment to a temporary file with a proper extension.
    
    Parameters
    ----------
    attachment: discord.Attachment
        The file attachment to be saved.

    extension: str
        The extension for the temporary file (e.g., '.txt', '.pdf').

    Returns
    ----------
    str:
        The path to the saved temporary file.

    Raises:
    ----------
    ValueError:
        The file extension was not supported.

    """
    extension = f".{attachment.filename.split('.')[-1]}" if '.' in attachment.filename else ''
    if extension not in ['.txt', '.pdf', '.csv', '.json', '.png', '.jpg', '.mp4']:
        raise ValueError(f"Unsupported file extension: {extension}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
        await attachment.save(temp_file.name)
        return temp_file.name


async def upload_file_to_openai(local_path):
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Upload a file to OpenAI.

    Parameters
    ----------
    local_path: str
        The file path from local device.
    
    Returns
    ----------
    `Files`:
        An uploaded OpenAI file object.

    """
    with open(local_path, "rb") as file:
        return await openai_client.files.create(file=file, purpose="assistants")


class ChatBot(commands.Cog):
    """ChatBot Discord bot integration"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db_cluster = self.bot.get_cluster()
        self.ai_repository = AIMongoDB(self.db_cluster)
        self.ai_openai = AIServiceAPI(self.ai_repository)


    async def handling_attachments(self, attachment, channel_id, user_id, guild_id, is_thread):
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Handle file attachments in messages.

        Parameters
        ----------
        attachment: discord.Attachment
            The file attachment to be handled.

        channel_id: int
            The channel ID.
        
        user_id: int
            The user ID of the message sender.

        guild_id: int
            The guild ID of the server.
        
        is_thread: bool
            Checks if the channel is a thread or not.

        Returns
        ----------
        None

        Raises
        ----------
        Exception:
            An unexpected error occurred while handling the attachment.
        
        """
        # Determine access level
        access_level = await self.ai_repository.get_access_level(self.bot, user_id, guild_id)
        assistant_id = await self.ai_repository.get_assistant_by_access_level(access_level)
        await self.ai_repository.get_or_create_channel_entry(channel_id, guild_id, assistant_id, is_thread)
        # Save and upload attachment
        local_path = await save_attachment_temporarily(attachment)
        try:
            openai_file = await upload_file_to_openai(local_path)
            
            # Record file in database
            file_data = {
                "channel_id": channel_id,
                "filename": attachment.filename,
                "local_path": local_path,
                "file_id": openai_file.id
            }
            await self.ai_repository.add_file(channel_id, file_data)

        except Exception as e:
            raise e
        
        finally:
            # Clean up temp file
            if os.path.exists(local_path):
                os.remove(local_path)

    
    # Initialize the assistants on bot ready
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Initialize on bot ready"""
        global prompt_character_name
        await self.ai_repository.initialize_assistants()
        prompt_character_name = self.bot.user.name


    # Command to initiate ChatBot interaction
    @app_commands.command(name="chatbot", description="Chat with our AI assistant in a dedicated thread.")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=True)
    @app_commands.checks.has_permissions(create_public_threads=True)
    @app_commands.checks.bot_has_permissions(create_public_threads=True)
    @app_commands.describe(attachment="File to upload (optional).")
    async def chatbot(self, interaction: discord.Interaction, attachment: Optional[discord.Attachment] = None):
        """Command to initiate ChatBot interaction"""
        chatbot_error_embed = Embed(title="", color=discord.Colour.red())
        if isinstance(interaction.channel, discord.Thread):
            # Check if the command is used in a thread
            chatbot_error_embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I don't have the ablilty to start a new conversation in an **existing thread** :thinking: ... Perhaps try to use it in a **text channel** instead. {interaction.user.mention} :pleading_face: ?")
            return await interaction.response.send_message(embed=chatbot_error_embed)

        await interaction.response.send_modal(ChatBotModal(ai_openai=self.ai_openai, ai_repository=self.ai_repository))

        if attachment:
            await self.handling_attachments(attachment=attachment, channel_id=interaction.channel.id, user_id=interaction.user.id, guild_id=interaction.guild.id if interaction.guild else None, is_thread=isinstance(interaction.channel, discord.Thread))


    @chatbot.error
    async def chatbot_error(self, interaction: Interaction, error):
        chatbot_error_embed = Embed(title="", color=discord.Colour.red())
        if isinstance(error, MissingPermissions):
            chatbot_error_embed.add_field(name="", value=f"<a:crossred:1356353067024515266> This command **requires** `create_public_threads` permission, and you probably **don't have** it, {interaction.user.mention}.")
            await interaction.response.send_message(embed=chatbot_error_embed)
        
        elif isinstance(error, BotMissingPermissions):
            chatbot_error_embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I couldn't **create** a public thread for our conversation. Please **double-check** my **permissions** and **role position**.")
            await interaction.response.send_message(embed=chatbot_error_embed)
        
        else:
            raise error


    # Listen for messages in AI chatbot threads
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for messages in AI chatbot threads"""
        # Ignore messages from bots (including self)
        if message.author.bot:
            return
        
        # Only process messages in threads
        if not isinstance(message.channel, Thread):
            return
        
        # Check if this is a AI chatbot thread
        thread_name = message.channel.name
        if not thread_name.startswith(f"Chat with "):
            return
        
        # Check if we have an entry for this thread
        entry = await self.ai_repository.channels_collection.find_one({
            "channel_id": message.channel.id,
            "is_thread": True
        })
        
        if not entry:
            return  # Not a AI chatbot thread we're tracking
        
        # Process the message with typing indicator (i.e. {bot_name} is typing...)
        async with message.channel.typing():
            if message.attachments:
                for attachment in message.attachments:
                    await self.handling_attachments(attachment=attachment, channel_id=message.channel.id, user_id=message.author.id, guild_id=message.guild.id if message.guild else None, is_thread=isinstance(message.channel, discord.Thread))

            # Get thread info
            openai_thread_id = entry.get("openai_thread_id")
            assistant_id = entry.get("assistant_id")
            
            if not openai_thread_id or not assistant_id:
                return
            
            # Send message to OpenAI, add a dot to avoid empty message in case of empty content
            assistant_reply = await self.ai_openai.send_message_to_openai(message, message.content if message.content != "" else "{file upload}", entry, openai_thread_id, assistant_id)
            
            # Send formatted response
            formatted_responses = discord_message_formatter(assistant_reply)
            
            for messages_sent, msg in enumerate(formatted_responses):
                if msg != "":
                    # For the first message, reply to the user's message directly
                    await message.reply(msg) if messages_sent == 0 else await message.channel.send(msg)


    # Command to reset ChatBot history
    @app_commands.command(name="resetchatbot", description="Clear chat history in ChatBot")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=True)
    @app_commands.checks.has_permissions(manage_threads=True, manage_guild=True)
    @app_commands.checks.bot_has_permissions(manage_threads=True, manage_guild=True)
    @app_commands.describe(type="Reset options")
    @app_commands.choices(type=[
        app_commands.Choice(name="Reset for current channel", value="channel"),
        app_commands.Choice(name="Reset for current thread", value="thread"),
        app_commands.Choice(name="Reset for current server", value="server"),
        app_commands.Choice(name="Reset for all channel(s) and server(s)", value="all")
    ])
    async def resetchatbot(self, interaction: Interaction, type: app_commands.Choice[str]):
        """Reset ChatBot history based on selected scope"""
        
        if not await self.bot.is_owner(interaction.user) and type.value == "all":
            return await interaction.response.send_message(NotBotOwnerError())
        
        guild_id = interaction.guild.id if interaction.guild else None
        channel_id = interaction.channel.id
        is_thread = isinstance(interaction.channel, discord.Thread)
        
        # Process reset request based on type
        if type.value == "channel":
            # Check if channel exists in database
            entry = await self.ai_repository.channels_collection.find_one({
                "channel_id": channel_id,
                "is_thread": is_thread
            })
            
            if not entry:
                reset_embed = Embed(title="", color=discord.Color.red())
                reset_embed.add_field(name="", value=f"<a:crossred:1356353067024515266> No **chat history** found on <#{channel_id}>.", inline=False)
            
            else:
                await self.ai_repository.reset_chat(channel_id)
                reset_embed = Embed(title="", color=interaction.user.color)
                reset_embed.add_field(name="", value=f"**Chat history** reset for <#{channel_id}>.", inline=False)
                
        elif type.value == "thread":
            if not is_thread:
                reset_embed = Embed(title="", color=discord.Color.red())
                reset_embed.add_field(name="", value=f"<a:crossred:1356353067024515266> <#{channel_id}> is **not a thread**.", inline=False)
            
            else:
                entry = await self.ai_repository.channels_collection.find_one({
                    "channel_id": channel_id,
                    "is_thread": True
                })
                
                if not entry:
                    reset_embed = Embed(title="", color=discord.Color.red())
                    reset_embed.add_field(name="", value=f"<a:crossred:1356353067024515266> No **chat history** found on <#{channel_id}>.", inline=False)
                
                else:
                    await self.ai_repository.reset_chat(channel_id)
                    reset_embed = Embed(title="", color=interaction.user.color)
                    reset_embed.add_field(name="", value=f"**Chat history** reset for {interaction.channel.mention} in **current thread**.", inline=False)
                    
        
        elif type.value == "server":
            if not guild_id:
                reset_embed = Embed(title="", color=discord.Color.red())
                reset_embed.add_field(name="", value=f"<a:crossred:1356353067024515266> <#{channel_id}> is **not belongs to** a **server**.", inline=False)
            
            else:
                server_entries = await self.ai_repository.channels_collection.find_one({"guild_id": guild_id})
                
                if not server_entries:
                    reset_embed = Embed(title="", color=discord.Color.red())
                    reset_embed.add_field(name="", value=f"<a:crossred:1356353067024515266> No **chat history** found on **this server**.", inline=False)
                
                else:
                    await self.ai_repository.reset_server_chats(guild_id)
                    reset_embed = Embed(title="", color=interaction.user.color)
                    reset_embed.add_field(name="", value="**Chat history** reset for **this server**.", inline=False)
                    
        elif type.value == "all":
            all_entries = await self.ai_repository.channels_collection.find_one({})
            
            if not all_entries:
                reset_embed = Embed(title="", color=discord.Color.red())
                reset_embed.add_field(name="", value="<a:crossred:1356353067024515266> No **chat history** found on **all server(s), channel(s) or thread(s)**.", inline=False)
            
            else:
                await self.ai_repository.reset_all_chats()
                reset_embed = Embed(title="", color=interaction.user.color)
                reset_embed.add_field(name="", value="All chat history has been reset.", inline=False)
                
        else:
            reset_embed = Embed(title="", color=discord.Color.red())
            reset_embed.add_field(name="", value="An unexpected error occurred while resetting chat history.", inline=False)
        
        await interaction.response.send_message(embed=reset_embed, ephemeral=True)


    @resetchatbot.error
    async def resetchatbot_error(self, interaction: Interaction, error):
        resetchatbot_error_embed = Embed(title="", color=discord.Colour.red())
        
        if isinstance(error, MissingPermissions):
            resetchatbot_error_embed.add_field(name="", value=f"<a:crossred:1356353067024515266> This command **requires** `manage_threads` and `manage_guild` permission, and you probably **don't have** it, {interaction.user.mention}.")
            await interaction.response.send_message(embed=resetchatbot_error_embed)
        
        elif isinstance(error, BotMissingPermissions):
            resetchatbot_error_embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I couldn't **reset** the chatbot history. Please **double-check** my **permissions** and **role position**.")
            await interaction.response.send_message(embed=resetchatbot_error_embed)
        
        else:
            raise error


async def setup(bot):
    await bot.add_cog(ChatBot(bot))

import os
import sys
import logging
import subprocess
import asyncio
import nest_asyncio
import motor.motor_asyncio as motor
from asyncio import sleep, Queue
from discord.ext import commands
from discord.errors import LoginFailure, HTTPException
from dotenv import load_dotenv
from hypercorn.asyncio import serve
from hypercorn.config import Config
from quart import Quart
from configs.Bot._logging import setup_logger
from configs.Bot._customHelpCommand import BetterHelpCommand
from errorhandling._errorHandling import *
from typing import Optional

load_dotenv()
nest_asyncio.apply()
app = Quart("DiscordBot")
extensions = []
extensions_folders = ['general', 'moderation', 'ownerOnly', 'extensions', 'errorhandling', 'configs']
logger = setup_logger(name='app', log_file='bot.log', level=logging.INFO)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class Bot(commands.Bot):
    """
    The main bot class for the Discord application.

    Parameters
    ----------
    intents : `discord.Intents`
        The intents for the bot.
    
    command_prefix : `str`
        The command prefix for the bot.
    
    self_bot : `bool`
        Whether the bot is a self bot or not. This should always be False in general.
    
    strip_after_prefix : `bool`
        Whether to strip whitespace after the prefix.

    """
    def __init__(self):
        super().__init__(
            intents=intents,
            command_prefix="!",
            self_bot=False,  # IMPORTANT!
            strip_after_prefix=True
        )
        self.mongo_client = None  # Initialize later in setup_hook
        self.queue = Queue()
        self.logger = logger


    async def setup_hook(self):
        try:
            # Initialize the motor client here to ensure it's tied to the correct event loop
            self.mongo_client = motor.AsyncIOMotorClient(os.getenv("MONGO_DATABASE_URI"))
            
            # Self MongoDB connedction test
            await self.mongo_client.admin.command('ping')
            logger.info("Pinged your deployment. The connection from your application to MongoDB cluster has been established.")

        except Exception as e:
            raise ConnectionError(f"Fatal: An error occurred while trying to connect to MongoDB cluster: {e}")

        # Load extensions
        await load_extensions()


    def get_cluster(self):
        """
        Retrive mongo database for all cogs

        Returns
        ----------
        `motor.AsyncIOMotorClient`:
            The motor client instance for MongoDB operations.

        """
        return self.mongo_client
    

    def get_queue(self):
        """
        Retrieve the instruction queue for web server control

        Returns
        ----------
        `asyncio.Queue`:
            The instruction queue for web server control.

        """
        return self.queue


    def get_logger(self):
        """
        Retrieve the logger instance for the bot.
        
        Returns
        ----------
        `logging.Logger`:
            The logger instance for logging bot activities.

        """
        return self.logger


    async def close_db(self):
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Ensure the motor client is properly closed

        Returns
        ----------
        None

        """
        if self.mongo_client:
            self.mongo_client.close()
        await super().close()


bot = Bot()
bot.help_command = BetterHelpCommand()


# Help command
# We have to remove the default help command first to avoid conflicts.
# Then we can add our custom help command with the same functionality. plus hybrid support.
bot.remove_command("help")


# Same as default help command, but with hybrid command support
@bot.hybrid_command(name="help")
async def help(ctx, command_or_group: Optional[str]):
    """
    Feeling lost? No worries, help is on the way!

    Parameters
    ----------
    command_or_group : `Optional[str]`
        The command or group to get help for.

    Returns
    ----------
    None

    """
    if ctx.interaction:
        embed = discord.Embed(title="", description="Here's some help coming your way...", color=ctx.author.color)
        await ctx.send(embed=embed, ephemeral=True)

    entity = command_or_group and (command_or_group,) or ()
    await ctx.send_help(*entity)


async def load_extensions():
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).
    
    Load extensions upon startup
    """
    logger.info("\nGetting extensions...\n")
    initial_extensions = await get_extensions()
    logger.info("\nLoading extensions...\n")
    
    for extension in initial_extensions:
        await bot.load_extension(extension)
        logger.info(extension)


# Getting all extensions from the extensions folders
# UPDATE 17-10-2025: Rewrited with asyncio.to_thread and os.walk to support subdirectories, and you can name a file starts with `_` to prevent loading
async def get_extensions():
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Getting all extensions from the extensions folders ends with `.py` and not starts with `_`, see Note below for more details.

    Note
    ----------
    This function has been rewrited, and now uses `asyncio.to_thread` to run blocking I/O operations in a separate thread, preventing the main event loop from being blocked.

    Since the latest rewrite, this function is now fully asynchronous and non-blocking.

    And you can now add subdirectories in the extensions folders, and the function will find them all.

    Also, you can named your files starts with `_` to prevent them from being loaded as extensions, which is useful for utility modules.

    """
    global extensions_folders
    extensions = []

    # Use asyncio.to_thread to perform blocking I/O in a separate thread
    for folder in extensions_folders:
        folder_path = f"./{folder}"
        if not os.path.exists(folder_path):
            continue

        # Use os.walk to recursively traverse directories
        walk_result = await asyncio.to_thread(list, os.walk(folder_path))
        
        for root, _, files in walk_result:
            for filename in files:
                if filename.endswith('.py') and not filename.startswith('_'):
                    # Convert file path to discord.py Cog format
                    relative_path = os.path.relpath(os.path.join(root, filename), ".").replace(os.sep, ".")
                    extension = relative_path[:-3]  # Remove .py extension
                    
                    # Conditional loading based on environment variables
                    if extension == "general.ChatGPT" and os.getenv("ENABLE_AI") == "False":
                        continue

                    if extension == "extensions.MusicPlayer.Music" and os.getenv("ENABLE_MUSIC") == "False":
                        continue

                    extensions.append(extension)

    return extensions


@bot.event
async def on_ready():
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Displaying startup info
    """
    logger.info(
f'''

{"-" * 120}

Welcome to the application!

Bot Username: {bot.user.name}#{bot.user.discriminator}
Bot ID: {bot.application_id}

The application is now initialized and waiting on your demands!

{"-" * 120}

'''
        )


"""
The following code is the primary operational logic of the application with proper documentation.  
To optimize resource usage, multiprocessing has been replaced with asynchronous operations, which are more lightweight and efficient.  
However, as a trade-off, the shutdown process may take slightly longer due to the need for graceful task cancellation and cleanup.
"""


async def start_bot():
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Starts the bot application.

    The function is designed to initialize and start the Discord bot using the provided bot token.
    It ensures that the bot connects to Discord's API and begins processing events.

    Raises:
    ----------
    `discord.HTTPException`:
        - Raised when the bot faces a rate-limit (HTTP 429) error from Discord's server.
        - This can occur if the bot sends too many requests in a short amount of time.
        - Developers should handle this by ensuring their code respects Discord's rate limits.

    `discord.errors.LoginFailure`:
        - Raised when the provided bot token is invalid or incorrect.
        - This error indicates that the bot could not authenticate with Discord's servers.
        - Ensure the token is valid, correctly formatted, and has the appropriate permissions.

    """
    try:
        token = os.environ.get("DISCORD_BOT_TOKEN")
        
        if token is None or token.strip() == "":
            raise SystemExit("No valid tokens were found in the environment variable. Please add your token to the Secrets pane.")

        await bot.start(token)
    
    except HTTPException as e:
        if e.status == 429:
            # If this occurs this might due to a rate-limit from Discord API
            # Log the error and restart the bot after a delay
            logger.error("\nThe Discord servers denied the connection for making too many requests, restarting in 7 seconds...")
            logger.error("\nIf the restart fails, get help from 'https://stackoverflow.com/questions/66724687/in-discord-py-how-to-solve-the-error-for-toomanyrequests'")

            await bot.queue.put("restart")    # Put "restart" to the queue to restart the web server

        else:
            raise e
    
    except LoginFailure as e:
        # In this case, this might be due to an invalid token
        # So we raise the LoginFailure with a more descriptive and user-friendly message
        raise LoginFailure(f"Cannot login to the application at this point due to the following error: {e}\nPlease check your token and try again.")

@app.before_serving
async def before_serving():
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Called when the web server starts

    Adding discord bot to the background task

    Returns
    ----------
    None

    """
    app.add_background_task(start_bot)


@app.route("/")
def hello_world():
    """
    Returning the home page of the Quart app

    Returns
    ----------
    `Literal['str']`
        The message from home page.

    """
    return "Hello, World!"


@app.get("/status")
def status():
    """
    Returning the status of the Quart app

    Returns
    ----------
    `Literal['str']`
        The application status.

    """
    if len(app.background_tasks) == 0:
        return "No applications were hosting now."
    
    return "Your applications are now hosting normally."


@app.get('/restart')
async def restart_():
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Restart the Quart app from HTTP Get Request.

    Returns
    ----------
    `Literal['str']`
        The restart message to client devices.
    
    """

    await bot.close()
    await bot.close_db()
    await bot.queue.put("restart")    # Put "restart" to the queue to restart the web server
    return "Please Wait. Your server is now restarting..."


@app.after_serving
async def shutdown_():
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Actions after shutting down the Quart app (Ctrl + C or by command)

    Returns
    ----------
    None

    """
    await bot.close()
    await bot.close_db()
    await bot.queue.put("shutdown")   # Put "shutdown" to the queue to terminate the web server


async def run_server():
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Runs the Quart application using Hypercorn.

    Returns
    ----------
    None

    """
    config = Config()
    config.bind = [f"0.0.0.0:{os.environ.get("PORT") or 9000}"]  # Custom PORT
    config.loglevel = "error"
    config.debug = False

    try:
        # Run Hypercorn for the Quart app
        await serve(app, config)

    except asyncio.CancelledError:
        logger.info("Server task cancelled. Shutting down Hypercorn...")

    except Exception as e:
        logger.info(f"Error in server: {e}")

    finally:
        logger.info("Hypercorn server has stopped.")


async def startup(queue):
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Starts the Quart server.

    Parameters
    ----------
    queue : `asyncio.Queue`
        The asynchronous instruction queue.

    Returns
    ----------
    `Task[None]`:
        The server task.

    """
    bot.queue = queue    # Assign the queue to the bot instance
    server_task = asyncio.create_task(run_server())
    logger.info("Hypercorn server started.")
    return server_task


async def cancel_server_task(server_task):
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Cancel the server task

    Parameters
    ----------
    server_task: `Task[None]`
        The task from `startup()`

    Returns
    ----------
    None

    """
    server_task.cancel()    # Cancel the server task

    try:
        await server_task    # Wait for the server task to finish

    except asyncio.CancelledError:
        logger.info("Server task cancelled successfully.")


async def monitor_queue(queue, server_task):
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Monitors the queue for instructions such as 'shutdown' or 'restart'.

    Parameters
    ----------
    queue : `asyncio.Queue`
        The queue to monitor

    server_task: `Task[None]`
        The task returned from `startup()`

    Returns
    ----------
    None

    """
    while True:
        instruction = await queue.get()
        match instruction:
            case "shutdown":
                return await cancel_server_task(server_task)    # Exit the main process gracefully

            case "restart" | "reboot":
                await cancel_server_task(server_task)
                print("Restarting application...")
                await asyncio.sleep(7)    # Time delay before restarting
                args = [sys.executable] + [sys.argv[0]]
                subprocess.call(args)    # Restart the script
                os._exit(0)  # Ensure exit the current subprocess after restart

            case _:
                raise ValueError(f"Unknown instruction for asyncio.Queue: must be either 'shutdown', 'reboot', or 'restart', got '{instruction}'.")
            
        await sleep(0.001)  # Minimal time delay to avoid busy-checking


async def main():
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Main program execution logic rewrited with asynchronous approach.

    Returns
    ----------
    None

    """
    queue = bot.queue    # Get the instruction queue

    # Start the Quart server as an asyncio task
    server_task = await startup(queue)

    try:
        await monitor_queue(queue, server_task)    # Start monitoring the queue

    finally:
        logger.info("Terminating server task...")
        server_task.cancel()

        try:
            await server_task

        except asyncio.CancelledError:
            logger.info("Server task terminated.")

    logger.info("Application halted.")    # The application terminated





if __name__ == "__main__":
    asyncio.run(main())


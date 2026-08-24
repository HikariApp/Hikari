import os
import sys
import logging
import subprocess
import asyncio
import nest_asyncio
import motor.motor_asyncio as motor
from asyncio import sleep, Queue
from discord.ext.commands import Bot
from discord.errors import LoginFailure, HTTPException
from dotenv import load_dotenv
from hypercorn.asyncio import serve
from hypercorn.config import Config
from quart import Quart
from helpers.extensionsHandler import getAllExtensions
from configs.Bot._logging import setupLogger
from helpers.errorHandling import *


load_dotenv()
nest_asyncio.apply()
app = Quart("DiscordApplication")
logger = setupLogger(name='app', log_file='app.log', level=logging.INFO)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

commandPrefix = os.getenv("DISCORD_BOT_COMMAND_PREFIX")
if commandPrefix is None or commandPrefix.strip() == "":
    commandPrefix = "!"

class Bot(Bot):
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
            command_prefix=commandPrefix,
            self_bot=False,  # IMPORTANT!
            strip_after_prefix=True
        )
        self.mongoClient = None  # Initialize later in setup_hook
        self.queue = Queue()
        self.logger = logger


    async def setup_hook(self):
        try:
            # Initialize the motor client here to ensure it's tied to the correct event loop
            self.mongoClient = motor.AsyncIOMotorClient(os.getenv("MONGO_DATABASE_URI"))
            
            # Self MongoDB connedction test
            await self.mongoClient.admin.command('ping')
            logger.info("Pinged your deployment. The connection from your application to MongoDB cluster has been established.")

        except Exception as e:
            raise ConnectionError(f"Fatal: An error occurred while trying to connect to MongoDB cluster: {e}")

        # Load extensions upon startup, if any
        await loadInitialExtensions()


    def getMongoClusterDB(self):
        """
        Retrive mongo database for all cogs

        Returns
        ----------
        `motor.AsyncIOMotorClient`:
            The motor client instance for MongoDB operations.

        """

        return self.mongoClient
    

    def getQueue(self):
        """
        Retrieve the instruction queue for web server control

        Returns
        ----------
        `asyncio.Queue`:
            The instruction queue for web server control.

        """

        return self.queue


    def getLogger(self):
        """
        Retrieve the logger instance for the bot.
        
        Returns
        ----------
        `logging.Logger`:
            The logger instance for logging bot activities.

        """

        return self.logger


    async def closeMongoDB(self):
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Ensure the motor client is properly closed

        Returns
        ----------
        None

        """
        
        if self.mongoClient:
            self.mongoClient.close()
        await super().close()


bot = Bot()


async def loadInitialExtensions():
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).
    
    Load extensions upon startup
    """
    logger.info("\nGetting extensions...\n")
    initialExtensions = await getAllExtensions()
    logger.info("\nLoading extensions...\n")

    for extension in initialExtensions:
        await bot.load_extension(extension)
        logger.info(extension)


@bot.event
async def on_ready():
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Displaying startup info
    """

    logger.info(
f'''

{"-" * 120}

Hi there! {bot.user.name}#{bot.user.discriminator} is now online.

ID: {bot.application_id}

To invoke a command, use the prefix: '{commandPrefix}'
e.g. {commandPrefix}help

You can also use slash commands to do so, if the command you're trying to invoke is supported.
e.g. /help

Have a great day!

{"-" * 120}

'''
    )


"""
The following code is the primary operational logic of the application with proper documentation.  
To optimize resource usage, multiprocessing has been replaced with asynchronous operations, which are more lightweight and efficient.  
However, as a trade-off, the shutdown process may take slightly longer due to the need for graceful task cancellation and cleanup.
"""


async def startBot():
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
async def beforeServing():
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Called when the web server starts

    Adding discord bot to the background task

    Returns
    ----------
    None

    """
    app.add_background_task(startBot)


@app.route("/")
def helloWorld():
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
    await bot.closeMongoDB()
    await bot.queue.put("restart")    # Put "restart" to the queue to restart the web server
    return "Please Wait. Your server is now restarting..."


@app.after_serving
async def selfShutdown():
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Actions after shutting down the Quart app (Ctrl + C or by command)

    Returns
    ----------
    None

    """
    await bot.close()
    await bot.closeMongoDB()
    await bot.queue.put("shutdown")   # Put "shutdown" to the queue to terminate the web server


async def runServer():
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Runs the Quart application using Hypercorn.

    Returns
    ----------
    None

    """
    config = Config()
    config.bind = [f"0.0.0.0:{os.environ.get("PORT") or 9000}"]  # Custom PORT
    config.loglevel = "ERROR"
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
    serverTask = asyncio.create_task(runServer())
    logger.info("Hypercorn server started.")
    return serverTask


async def cancelServerTask(serverTask):
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Cancel the server task

    Parameters
    ----------
    serverTask: `Task[None]`
        The task from `startup()`

    Returns
    ----------
    None

    """
    serverTask.cancel()    # Cancel the server task

    try:
        await serverTask    # Wait for the server task to finish

    except asyncio.CancelledError:
        logger.info("Server task cancelled successfully.")


async def queueMonitoring(queue, serverTask):
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Monitors the queue for instructions such as 'shutdown' or 'restart'.

    Parameters
    ----------
    queue : `asyncio.Queue`
        The queue to monitor

    serverTask: `Task[None]`
        The task returned from `startup()`

    Returns
    ----------
    None

    """
    while True:
        instruction = await queue.get()
        match instruction:
            case "shutdown":
                return await cancelServerTask(serverTask)    # Exit the main process gracefully

            case "restart" | "reboot":
                await cancelServerTask(serverTask)
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
    serverTask = await startup(queue)

    try:
        await queueMonitoring(queue, serverTask)    # Start monitoring the queue

    finally:
        logger.info("Terminating server task...")
        serverTask.cancel()

        try:
            await serverTask

        except asyncio.CancelledError:
            logger.info("Server task terminated.")

    logger.info("Application halted.")    # The application terminated





if __name__ == "__main__":
    asyncio.run(main())


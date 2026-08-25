import os
import logging

import discord
from discord.ext.commands import Bot
from discord.errors import LoginFailure, HTTPException
from dotenv import load_dotenv
import motor.motor_asyncio as motor
import lava_lyra
from aiohttp import web

from helpers.restarter import restarter
from helpers.extensionsHandler import getAllExtensions

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

commandPrefix = os.getenv("DISCORD_BOT_COMMAND_PREFIX") or "!"

WEB_HOST = os.getenv("HOST") or "0.0.0.0"
WEB_PORT = int(os.getenv("PORT") or 9000)


class MyBot(Bot):
    """
    A subclass of `discord.ext.commands.Bot` with additional functionalities.

    This includes MongoDB connection management, logging,
    and a minimal web server for monitoring endpoints.

    Attributes
    ----------
    mongoClient : `motor.AsyncIOMotorClient`
        The motor client for MongoDB operations, initialized in `setup_hook`.

    logger : `logging.Logger`
        The logger instance for logging bot activities.

    webRunner : `aiohttp.web.AppRunner`
        The aiohttp AppRunner for the monitoring web server, initialized in `setup_hook`.

    Methods
    ----------
    setup_hook() -> None
        Coroutine that sets up the bot's dependencies, including MongoDB connection, loading extensions, and starting the web server.

    getMongoClusterDB() -> `motor.AsyncIOMotorClient`
        Returns the motor client for MongoDB operations.

    getLogger() -> `logging.Logger`
        Returns the logger instance for logging bot activities.

    close() -> None
        Coroutine that closes all connections and shuts down the bot, including the web server, Lavalink node pool, and MongoDB client.

    """

    def __init__(self):
        super().__init__(
            intents=intents,
            command_prefix=commandPrefix,
            strip_after_prefix=True,
        )
        self.mongoClient = None   # bound in setup_hook
        self.logger = logger      # exposed to cogs via getLogger()
        self.webRunner = None     # aiohttp AppRunner, bound in setup_hook


    async def setup_hook(self) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Called after the bot is logged in while before it has connected to the WebSocket.

        You may use this to set up any dependencies required for the bot to run.
        In our case, this establishes the MongoDB connection and loads the extensions,
        with a minimal web server for monitoring purpose.
        
        Returns
        ----------
        None

        """

        # We establish the MongoDB connection first
        uri = os.getenv("MONGO_DATABASE_URI")

        if not uri:
            raise SystemExit("No MONGO_DATABASE_URI found in environment.")

        try:
            # Initialize the motor client
            self.mongoClient = motor.AsyncIOMotorClient(uri)

            # Self MongoDB connection test
            if await self.mongoClient.admin.command("ping"):
                logger.info("Pong! MongoDB connection established.")

        except Exception as e:
            raise ConnectionError(f"FATAL: could not connect to MongoDB cluster due to the following error: {e}")

        # Then load the extensions
        await self.loadInitialExtensions()

        # And finally start the web server for monitoring endpoints
        await self.startWebServer()


    async def loadInitialExtensions(self) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).
        
        Load extensions from the extensions folder.

        Returns
        ----------
        None

        """

        logger.info("Getting extensions...")
        initialExtensions = await getAllExtensions()

        logger.info("Loading extensions...")
        successCount, failedCount = 0, 0

        for extension in initialExtensions:
            try:
                await self.load_extension(extension)
                logger.info(f"loaded: {extension}")
                successCount += 1

            except Exception as e:
                logger.error(f"FAILED: {extension} — {e}")
                failedCount += 1

        logger.info(f"Finished loading extensions: {successCount} extension(s) successfully loaded with {failedCount} extension(s) failed.")


    async def handleHealth(self, request) -> web.Response:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).
        
        Checks if the bot is alive and responding.
        
        Returns
        ----------
        `web.Response`
            The response object containing the health status in JSON format.
        
        """

        return web.json_response({"status": "ok"})


    async def handleStatus(self, request) -> web.Response:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Provides a status report of the bot.

        This checks the bot's readiness, latency, guild count,
        MongoDB connection status, and Lavalink node count
        to see if there are any connetion issues.

        Returns
        ----------
        `web.Response`
            The response object, containing the status report in JSON format.

        """

        mongoOk = False

        try:
            if self.mongoClient:
                await self.mongoClient.admin.command("ping")
                mongoOk = True

        except Exception:
            mongoOk = False

        try:
            nodeCount = len(lava_lyra.NodePool._nodes) if lava_lyra.NodePool._nodes else 0

        except Exception:
            nodeCount = 0

        return web.json_response({
            "status": "ok",
            "ready": self.is_ready(),
            "latency_ms": round(self.latency * 1000, 2) if self.latency else None,
            "guilds": len(self.guilds),
            "mongo_connected": mongoOk,
            "lavalink_nodes": nodeCount,
        })


    async def startWebServer(self) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Starts a minimal web server and site for monitoring endpoints.

        Returns
        ----------
        None

        """

        app = web.Application()

        # Add routes for health and status endpoints
        app.router.add_get("/health", self.handleHealth)
        app.router.add_get("/status", self.handleStatus)

        # Start the web server
        self.webRunner = web.AppRunner(app)
        await self.webRunner.setup()

        # Start the site on the specified host and port
        site = web.TCPSite(self.webRunner, WEB_HOST, WEB_PORT)
        await site.start()
        logger.info(f"Monitoring server listening on http://{WEB_HOST}:{WEB_PORT}")


    def getMongoClusterDB(self) -> motor.AsyncIOMotorClient:
        """
        Retrieve the motor client for all cogs.
        
        Returns
        ----------
        `motor.AsyncIOMotorClient`
            The motor client instance for MongoDB operations.
        """

        return self.mongoClient


    def getLogger(self) -> logging.Logger:
        """
        Retrieve the logger instance for the bot.
        
        Returns
        ----------
        `logging.Logger`:
            The logger instance for logging bot activities.

        """

        return self.logger


    async def close(self) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Close all connections and shuts down the bot.

        The function would first stop the web server and lavalink node pool
        if detected, then close the MongoDB client, and finally call the 
        parent class's close method to clean up discord.py resources.

        Returns
        ----------
        None

        """
        logger.info("close() called — shutting down cleanly.")

        # We stop the web server first
        if self.webRunner:
            try:
                await self.webRunner.cleanup()
                logger.info("Monitoring server stopped.")
            except Exception as e:
                logger.error(f"Error while stopping monitoring server: {e}")

        # Then the Lavalink node pool
        try:
            if lava_lyra.NodePool._nodes:
                await lava_lyra.NodePool.disconnect()
                logger.info("LavaLyra node pool disconnected.")
        except Exception as e:
            logger.error(f"Error while disconnecting LavaLyra node pool: {e}")

        # MongoDB follows by that
        if self.mongoClient:
            self.mongoClient.close()
            logger.info("MongoDB client closed.")

        # Finally we close discord.py itself and terminates the process
        await super().close()
        logger.info("Bot closed.")


bot = MyBot()


@bot.event
async def on_ready() -> None:
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Displaying startup info.

    Returns
    ----------
    None

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


def main():
    try:
        token = os.environ.get("DISCORD_BOT_TOKEN")
        
        if not token or not token.strip():
            raise SystemExit("No valid tokens were found in the environment variable. Please add your token to the Secrets pane.")

        bot.run(token)

    except HTTPException as e:
        if e.status == 429:
            # If this occurs this might due to a rate-limit from Discord API
            # Log the error and restart the bot after a delay
            logger.error("\nThe Discord servers denied the connection for making too many requests, restarting in 7 seconds...")
            logger.error("\nIf the restart fails, get help from 'https://stackoverflow.com/questions/66724687/in-discord-py-how-to-solve-the-error-for-toomanyrequests'")
            restarter.request(reason="HTTP 429 rate limit", delay=7.0)

        else:
            raise
    
    except LoginFailure as e:
        # In this case, this might be due to an invalid token
        # So we raise the LoginFailure with a more descriptive and user-friendly message
        raise SystemExit(f"Cannot login to the application at this point due to the following error: {e}\nPlease check your token and try again.")


    # The following code is executed after the bot has been closed properly
    #
    # Therefore, please DO NOT put any code that should be executed
    # while the bot is still running into this section, as it will NEVER be executed for most cases.

    # Check if a restart was requested
    if restarter.requested:
        # Perform the restart
        logger.info("Clean shutdown complete; handing off to restart.")
        restarter.perform()
    else:
        # Terminate the process if no restart was requested
        logger.info("Clean shutdown complete. Application halted.")





if __name__ == "__main__":
    main()

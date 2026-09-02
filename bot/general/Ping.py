import time
import asyncio
from discord import Embed, Color, app_commands
from discord.ext import commands
from discord.ext.commands import Cog, Context
from startup import MyBot


class Ping(Cog):
    def __init__(self, bot: MyBot):
        self.bot = bot


    # Cog-level error listener for unhandled errors
    async def cog_command_error(self, ctx: Context, error: Exception):
        if getattr(ctx, "_errorHandled", False):    # if ctx._errorHandled was set to True this could be ig>
            return

        self.logger.exception(f"Uncaught error in {ctx.cog.__cog_name__}:", exc_info=error)


    # Test the bot's latency and response time.
    @commands.hybrid_command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def ping(self, ctx: Context):
        """
        Test the bot's latency and response time.
        """

        # The following values will be returned to the user in an embed message.
        #
        # 1. WS — WebSocket/gateway heartbeat latency. The time between sending a heartbeat to Discord's gateway and getting the ack. 
        # This is essentially free to read: bot.latency.
        #
        # 2. Micro — Event-loop responsiveness (a.k.a. loop lag). How long a trivial asyncio hop takes right now.
        # If your bot is busy/blocking, this climbs. This is the "is my process itself healthy" number. 
        #        
        # 3. Time — Full round-trip: how long it takes to actually send a message and have Discord confirm it.
        # You measure the wall-clock time around the send/edit.
        # 
        # Returns are ordered as follows: Time, Micro, WS. All values are in milliseconds (ms).

        # 1) WS — WebSocket/gateway heartbeat latency
        wsMs = self.bot.latency * 1000

        # 2) Micro — event-loop lag: time for a single scheduler round-trip
        loop = asyncio.get_running_loop()
        t0 = loop.time()
        await asyncio.sleep(0)          # yield once, back on next tick
        microMs = (loop.time() - t0) * 1000

        # 3) Time — real message round-trip
        start = time.perf_counter()
        msg = await ctx.send("Pong!")
        timeMs = (time.perf_counter() - start) * 1000

        # Create an embed with the latency values
        pingEmbed = Embed(
            title="Pong! :ping_pong:",
            description=(
                f":hourglass: **Time:** {round(timeMs)} ms"
                f"\n:sparkles: **Micro:** {round(microMs)} ms"
                f"\n:stopwatch: **WS:** {round(wsMs)} ms"
            ),
            color=Color(0x76FF03)  # A nice green color
        )

        # Edit the message to include the latency values
        await msg.edit(content=None, embed=pingEmbed)

async def setup(bot: MyBot):
    await bot.add_cog(Ping(bot))

import asyncio
import psutil
import socket
from discord.ext import commands
from discord.ext.commands import Cog, Context, ExtensionAlreadyLoaded, ExtensionNotLoaded, NoEntryPointError, ExtensionFailed
from helpers.errorHandling import *
from helpers.getIPv4Info import *
from startup import MyBot
from helpers.restarter import restarter
from helpers.extensionsHandler import getAllExtensions
from helpers.respondEmbed import respondEmbed, ResponseTarget
from helpers.networkInfo import NetworkInfo
from typing import List


class OwnerOnly(Cog):
    def __init__(self, bot: MyBot):
        self.bot = bot
        self.logger = self.bot.getLogger()
        self.db = self.bot.getMongoClusterDB()


    # Cog-level error listener for unhandled errors
    async def cog_command_error(self, ctx: Context, error: Exception):
        if getattr(ctx, "_errorHandled", False):    # if ctx._errorHandled was set to True this could be ignored
            return

        self.logger.exception(f"Uncaught error in {ctx.cog.__cog_name__}:", exc_info=error)


    # This is a migrated cog from startup.py for owner only commands
    # Sync, load, unload, reload, systeminfo, restart, shutdown


    # Sync all cogs for latest changes 
    @commands.command(hidden=True)
    async def sync(self, ctx) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Sync all cogs for latest changes
        """

        if not await self.bot.is_owner(ctx.author):
            return await respondEmbed(ctx, NotBotOwnerError(), error=True, target=ResponseTarget.REPLY)
        
        synced = await self.bot.tree.sync()
        await respondEmbed(ctx, f"Synced {len(synced)} command(s).", title="Sync Successful", target=ResponseTarget.REPLY, deleteAfter=5)


    # Loading a cog manually
    @commands.command(hidden=True)
    async def load(self, ctx: Context, cog_name: str) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Load cogs manually

        Parameters
        ----------
        cog_name: str
            The name to load.
        """

        if not await self.bot.is_owner(ctx.author):
            return await respondEmbed(ctx, NotBotOwnerError(), error=True, target=ResponseTarget.REPLY)
        
        extensions = await getAllExtensions()
        if cog_name not in extensions:  # Front check if the cog was in the valid cog list or not
            return await respondEmbed(ctx, ExtensionNotFoundError(cog=cog_name), error=True, target=ResponseTarget.REPLY)
        
        try:
            await self.bot.load_extension(cog_name)
            await self.bot.tree.sync()
            await respondEmbed(ctx, f"Cog `{cog_name}` has been loaded.", title="Load Successful", target=ResponseTarget.REPLY, deleteAfter=2)
            
        except ExtensionAlreadyLoaded:
            return await respondEmbed(ctx, f"Cog `{cog_name}` has been already loaded!", error=True, target=ResponseTarget.REPLY)
        
        except NoEntryPointError:
            return await respondEmbed(ctx, ReturnNoEntryPointError(cog=cog_name), error=True, target=ResponseTarget.REPLY)
        
        except ExtensionFailed:
            return await respondEmbed(ctx, ExtensionFailedError(cog=cog_name), error=True, target=ResponseTarget.REPLY)


    @commands.command(hidden=True)
    async def unload(self, ctx: Context, cog_name: str) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).
        
        Unload cogs manually

        Parameters
        ----------
        cog_name: str
            The name to unload.
        """

        if not await self.bot.is_owner(ctx.author):
            return await respondEmbed(ctx, NotBotOwnerError(), error=True, target=ResponseTarget.REPLY)

        if cog_name not in await getAllExtensions():  # Front check if the cog was in the valid cog list or not
            return await respondEmbed(ctx, ExtensionNotFoundError(cog=cog_name), error=True, target=ResponseTarget.REPLY)
        
        try:
            await self.bot.unload_extension(cog_name)
            await self.bot.tree.sync()
            await respondEmbed(ctx, f"Cog `{cog_name}` has been unloaded.", title="Unload Successful", target=ResponseTarget.REPLY, deleteAfter=2)

        except ExtensionNotLoaded:
            return await respondEmbed(ctx, f"Cog `{cog_name}` has been already unloaded!", error=True, target=ResponseTarget.REPLY)
        
        except NoEntryPointError:
            return await respondEmbed(ctx, ReturnNoEntryPointError(cog=cog_name), error=True, target=ResponseTarget.REPLY)

        except ExtensionFailed:
            return await respondEmbed(ctx, ExtensionFailedError(cog=cog_name), error=True, target=ResponseTarget.REPLY)


    @commands.command(hidden=True)
    async def reload(self, ctx: Context, cog_name: str) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Reload cogs manually

        Parameters
        ----------
        cog_name: str
            The name to reload.
        """

        if not await self.bot.is_owner(ctx.author):
            return await respondEmbed(ctx, NotBotOwnerError(), error=True, target=ResponseTarget.REPLY)
        
        if cog_name not in await getAllExtensions():  # Front check if the cog was in the valid cog list or not
            return await respondEmbed(ctx, ExtensionNotFoundError(cog=cog_name), error=True, target=ResponseTarget.REPLY)
        
        try:
            await self.bot.reload_extension(cog_name)
            await self.bot.tree.sync()
            await respondEmbed(ctx, f"Cog `{cog_name}` has been reloaded.", title="Reload Successful", target=ResponseTarget.REPLY, deleteAfter=2)

        except ExtensionNotLoaded:
            return await respondEmbed(ctx, f"Cog `{cog_name}` has not been loaded.", error=True, target=ResponseTarget.REPLY)

        except NoEntryPointError:
            return await respondEmbed(ctx, ReturnNoEntryPointError(cog=cog_name), error=True, target=ResponseTarget.REPLY)

        except ExtensionFailed:
            return await respondEmbed(ctx, ExtensionFailedError(cog=cog_name), error=True, target=ResponseTarget.REPLY)


    @commands.command(hidden=True)
    async def systeminfo(self, ctx: Context) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Retrieving system info from the bot
        """

        if not await self.bot.is_owner(ctx.author):
            return await respondEmbed(ctx, NotBotOwnerError(), error=True, target=ResponseTarget.REPLY)
        
        def convertToGiB(raw):
            return round(raw / 1024 ** 3, 2)

        # Returning system info as embed
        messageLines: List[str] = []

        # CPU
        cpuPercentage = psutil.cpu_percent()
        numberOfSystemCores = psutil.cpu_count(logical=False)
        numberOfLogicalCores = psutil.cpu_count(logical=True)

        messageLines.append(
            f"\n**CPU:**\n"
            f"CPU utilization: {cpuPercentage}%"
            f"\nNumber of system cores: {numberOfSystemCores}"
            f"\nNumber of logical cores: {numberOfLogicalCores}"
        )
        
        # RAM
        ram = psutil.virtual_memory()
        usedRamInGiB = convertToGiB(ram.used)
        availableRamInGiB = convertToGiB(ram.available)
        totalRamInGiB = convertToGiB(ram.total)
        ramPercentage = ram.percent

        messageLines.append(
            f"\n**RAM:**\n"
            f"Memory in use: {usedRamInGiB} / {totalRamInGiB} GiB ({ramPercentage}%)"
            f"\nAvailible memory: {availableRamInGiB} GiB"
        )

        # Storage
        disk = psutil.disk_usage('/')
        usedVolumeInGiB = convertToGiB(disk.used)
        freeVolumeInGiB = convertToGiB(disk.free)
        totalVolumeInGiB = convertToGiB(disk.total)
        diskPercentage = disk.percent

        messageLines.append(
            f"\n**Storage:**\n"
            f"Space used: {usedVolumeInGiB} / {totalVolumeInGiB} GiB ({diskPercentage}%)"
            f"\nAvailible space: {freeVolumeInGiB} GiB"
        )
        
        # Basic Network
        basicNetwork = await asyncio.to_thread(NetworkInfo)   # add ipv6_global_only=True if you want to trim link-local noise

        messageLines.append(
            f"\n**Network (Basic):**\n"
            f"IPv4 Address(s): {basicNetwork.ipv4_addresses}\n"
            f"Subnet(s) Mask: {basicNetwork.ipv4_subnets}\n"
            f"IPv4 Gateway: {basicNetwork.ipv4_gateway}\n"
            f"IPv6 Address(s): {basicNetwork.ipv6_addresses}\n"
            f"IPv6 Gateway: {basicNetwork.ipv6_gateway}"
        )

        
        # Advanced Network
        ipInfo = await asyncio.to_thread(IPv4info)
        hostname = socket.gethostname()
        advancedNetwork = psutil.net_io_counters()

        messageLines.append(
            f"\n**Network (Advanced):**\n"
            f"Hostname: {hostname}\n"
            f"IPv4: {ipInfo.ip}\n"
            f"IP Hostname: {ipInfo.hostname}\n"
            f"Country or district: {ipInfo.country}\n"
            f"Region: {ipInfo.region}\n"
            f"City: {ipInfo.city}\n"
            f"Organization: {ipInfo.organization}\n"
            f"Postal code: {ipInfo.postal}\n"
            f"Location: {ipInfo.location}\n"
            f"Number of bytes sent: {advancedNetwork.bytes_sent}\n"
            f"Number of bytes received: {advancedNetwork.bytes_recv}\n"
            f"Number of packets sent: {advancedNetwork.packets_sent}\n"
            f"Number of packets received: {advancedNetwork.packets_recv}\n"
            f"Total number of errors while receiving: {advancedNetwork.errin}\n"
            f"Total number of errors while sending: {advancedNetwork.errout}\n"
            f"Total number of incoming packets dropped: {advancedNetwork.dropin}\n"
            f"Total number of outgoing packets dropped: {advancedNetwork.dropout}"
        )

        await respondEmbed(ctx, "\n".join(messageLines), title="System Info (For reference only):", target=ResponseTarget.REPLY, deleteAfter=30)


    # Shutdown the bot and the server
    @commands.command(hidden=True)
    async def selfshutdown(self, ctx: Context) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Shut down the bot and the server (SELF DESTRUCT)

        However, this command does NOT shut down the entire machine/server in docker or VPS hosting environments.
        """
        
        if not await self.bot.is_owner(ctx.author):
            return await respondEmbed(ctx, NotBotOwnerError(), error=True, target=ResponseTarget.REPLY)
        
        await self.bot.close()

    # Restart the bot and the server
    @commands.command(hidden=True)
    async def selfrestart(self, ctx: Context) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Restart the bot and the server
        """
        
        if not await self.bot.is_owner(ctx.author):
            return await respondEmbed(ctx, NotBotOwnerError(), error=True, target=ResponseTarget.REPLY)
        
        restarter.request(reason=f"Restart requested by bot owner.", delay=0.0)
        await self.bot.close()


async def setup(bot: MyBot):
    await bot.add_cog(OwnerOnly(bot))

import psutil
import netifaces
import socket
from discord import Embed
from discord.ext import commands
from discord.ext.commands import Bot, Cog, Context, ExtensionAlreadyLoaded, ExtensionNotLoaded, NoEntryPointError, ExtensionFailed
from datetime import datetime
from helpers.errorHandling import *
from helpers.getIPv4Info import *
from helpers.restarter import restarter
from helpers.extensionsHandler import getAllExtensions
from helpers.respondEmbed import respondEmbed, ResponseTarget


class OwnerOnly(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = self.bot.getLogger()
        self.db = self.bot.getMongoClusterDB()


    # Cog-level error listener for unhandled errors
    async def cog_on_command_error(self, ctx: Context, error: Exception):
        self.logger.exception(f"Uncaught error in {ctx.cog.__cog_name__}:", exc_info=error)
        raise error


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
        
        def convert_to_GB(raw):
            return round(raw / 1024 ** 3, 2)
        # CPU
        cpuPercentage = psutil.cpu_percent()
        numberOfSystemCores = psutil.cpu_count(logical=False)
        numberOfLogicalCores = psutil.cpu_count(logical=True)

        # Memory
        ram = psutil.virtual_memory()
        usedRamInGB = convert_to_GB(ram.used)
        availableRamInGB = convert_to_GB(ram.available)
        totalRamInGB = convert_to_GB(ram.total)
        ramPercentage = ram.percent
        
        # Storage
        disk = psutil.disk_usage('/')
        usedVolumeInGB = convert_to_GB(disk.used)
        freeVolumeInGB = convert_to_GB(disk.free)
        totalVolumeInGB = convert_to_GB(disk.total)
        diskPercentage = disk.percent

        # Network
        hostname = socket.gethostname()
        network = psutil.net_io_counters()

        # Returning system info as embed
        hardware_info_embed = Embed(title="Resource Usage (For reference only):", description='\u200b', timestamp=datetime.now(), color=ctx.author.color)

        # CPU
        hardware_info_embed.add_field(name="CPU", value=f"CPU utilization: {cpuPercentage}%\nNumber of system cores: {numberOfSystemCores}\nNumber of logical cores: {numberOfLogicalCores}", inline=True)
        
        # Memory
        hardware_info_embed.add_field(name="RAM", value=f"Memory in use: {usedRamInGB} / {totalRamInGB} GB ({ramPercentage}%)\nAvailible memory: {availableRamInGB} GB", inline=True)
        hardware_info_embed.add_field(name="Storage", value=f"Space used: {usedVolumeInGB} / {totalVolumeInGB} GB ({diskPercentage}%)\nAvailible space: {freeVolumeInGB} GB", inline=True)
        hardware_info_embed.add_field(name="\u200b", value="", inline=False)
        
        # Basic Network
        ip_addresses = [netifaces.ifaddresses(iface)[netifaces.AF_INET][0]['addr'] for iface in netifaces.interfaces() if netifaces.AF_INET in netifaces.ifaddresses(iface)]
        subnets = [netifaces.ifaddresses(iface)[netifaces.AF_INET][0]['netmask'] for iface in netifaces.interfaces() if netifaces.AF_INET in netifaces.ifaddresses(iface)]
        gateways = [netifaces.gateways()['default'][netifaces.AF_INET][0] for gateways in netifaces.interfaces() if "default" in netifaces.gateways()]
        
        try:
            hardware_info_embed.add_field(name="Network Information (Basic)", value=f"IPv4 Address(s): {ip_addresses}\nSubnet(s) Mask: {subnets}\nGateway(s): {gateways}", inline=True)
        
        except:
            pass
        
        ipInfo = IPv4info()
        # Advanced Network
        hardware_info_embed.add_field(name="Network Information (Advanced)", value=f"Hostname: {hostname}\nIPv4: {ipInfo.ip}\nIP Hostname: {ipInfo.hostname}\nCountry or district: {ipInfo.country}\nRegion: {ipInfo.region}\nCity: {ipInfo.city}\n Organization: {ipInfo.organization}\nPostal code: {ipInfo.postal}\nLocation: {ipInfo.location}", inline=True)
        
        # Packets transmission
        hardware_info_embed.add_field(name="\u200b", value="", inline=False)
        hardware_info_embed.add_field(name="Packets transmission:", value=f"Number of bytes sent: {network.bytes_sent}\nNumber of bytes received: {network.bytes_recv}\nNumber of packets sent: {network.packets_sent}\nNumber of packets received: {network.packets_recv}\nTotal number of errors while receiving: {network.errin}\nTotal number of errors while sending: {network.errout}\nTotal number of incoming packets dropped: {network.dropin}\nTotal number of outgoing packets dropped: {network.dropout}", inline=False)
        hardware_info_embed.add_field(name="\u200b", value="", inline=False)
        
        await ctx.reply(embed=hardware_info_embed)


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


async def setup(bot):
    await bot.add_cog(OwnerOnly(bot))

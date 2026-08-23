import discord
import asyncio
import psutil
import netifaces
import socket
from discord.ext import commands
from discord.ext.commands import Bot, Cog, ExtensionAlreadyLoaded, ExtensionNotLoaded, NoEntryPointError, ExtensionFailed
from datetime import datetime
from errorhandling._errorHandling import *
from _getIPv4Info import *
from extensionsHandler import getAllExtensions


class OwnerOnly(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.db = self.bot.getMongoClusterDB()
        self.queue = self.bot.getQueue()


    # This is a migrated cog from startup.py for owner only commands
    # Sync, load, unload, reload, systeminfo, restart, shutdown


    # Sync all cogs for latest changes 
    @commands.command(hidden=True)
    async def sync(self, ctx):
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Sync all cogs for latest changes

        """

        if not await self.bot.is_owner(ctx.author):
            return await ctx.reply(NotBotOwnerError())
        
        synced = await self.bot.tree.sync()
        msg = await ctx.reply(f"Synced {len(synced)} command(s).")

        await asyncio.sleep(5)
        await msg.delete()
        await ctx.message.delete()


    # Loading a cog manually
    @commands.command(hidden=True)
    async def load(self, ctx, cog_name):
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Load cogs manually

        Parameters
        ----------
        cog_name: str
            The name to load.

        """

        if not await self.bot.is_owner(ctx.author):
            return await ctx.reply(NotBotOwnerError())
        
        extensions = await getAllExtensions()
        if cog_name not in extensions:  # Front check if the cog was in the valid cog list or not
            return await ctx.reply(ExtensionNotFoundError(cog=cog_name))
        
        try:
            await self.bot.load_extension(cog_name)
            await self.bot.tree.sync()
            msg = await ctx.reply(f"Cog `{cog_name}` has been loaded.")
            await asyncio.sleep(1)
            await msg.delete()
            await ctx.message.delete()
            
        except ExtensionAlreadyLoaded:
            return await ctx.reply(f"Cog `{cog_name}` has been already loaded!")
        
        except NoEntryPointError:
            return await ctx.reply(ReturnNoEntryPointError(cog=cog_name))
        
        except ExtensionFailed:
            return await ctx.reply(ExtensionFailedError(cog=cog_name))


    @commands.command(hidden=True)
    async def unload(self, ctx, cog_name):
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).
        
        Unload cogs manually

        Parameters
        ----------
        cog_name: str
            The name to unload.
        
        """

        if not await self.bot.is_owner(ctx.author):
            return await ctx.reply(NotBotOwnerError())

        if cog_name not in await getAllExtensions():  # Front check if the cog was in the valid cog list or not
            return await ctx.reply(ExtensionNotFoundError(cog=cog_name))
        
        try:
            await self.bot.unload_extension(cog_name)
            await self.bot.tree.sync()
            msg = await ctx.reply(f"Cog `{cog_name}` has been unloaded.")
            await asyncio.sleep(2)
            await msg.delete()
            await ctx.message.delete()

        except ExtensionNotLoaded:
            return await ctx.reply(f"Cog `{cog_name}` has been already unloaded!")
        
        except NoEntryPointError:
            return await ctx.reply(ReturnNoEntryPointError(cog=cog_name))
        
        except ExtensionFailed:
            return await ctx.reply(ExtensionFailedError(cog=cog_name))
        

    @commands.command(hidden=True)
    async def reload(self, ctx, cog_name):
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Reload cogs manually

        Parameters
        ----------
        cog_name: str
            The name to reload.
        
        """

        if not await self.bot.is_owner(ctx.author):
            return await ctx.reply(NotBotOwnerError())
        
        if cog_name not in await getAllExtensions():  # Front check if the cog was in the valid cog list or not
            return await ctx.reply(ExtensionNotFoundError(cog=cog_name))
        
        try:
            await self.bot.reload_extension(cog_name)
            await self.bot.tree.sync()
            msg = await ctx.reply(f"Cog `{cog_name}` has been reloaded.")
            await asyncio.sleep(2)
            await msg.delete()
            await ctx.message.delete()

        except ExtensionNotLoaded:
            return await ctx.send(f"Cog `{cog_name}` has not been loaded.")
        
        except NoEntryPointError:
            return await ctx.reply(ReturnNoEntryPointError(cog=cog_name))
        
        except ExtensionFailed:
            return await ctx.reply(ExtensionFailedError(cog=cog_name))


    @commands.command(hidden=True)
    async def systeminfo(self, ctx) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Retrieving system info from the bot

        Returns
        ----------
        None

        """

        if not await self.bot.is_owner(ctx.author):
            return await ctx.reply(NotBotOwnerError())
        
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
        hardware_info_embed = discord.Embed(title="Resource Usage (For reference only):", description='\u200b', timestamp=datetime.now(), color=ctx.author.colour)

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
    async def selfshutdown(self, ctx):
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Shut down the bot and the server (SELF DESTRUCT)

        However, this command does NOT shut down the entire machine/server in docker or VPS hosting environments.

        """
        
        if not await self.bot.is_owner(ctx.author):
            return await ctx.reply(NotBotOwnerError())
        await self.bot.close()
        await self.queue.put("shutdown")


async def setup(bot):
    await bot.add_cog(OwnerOnly(bot))





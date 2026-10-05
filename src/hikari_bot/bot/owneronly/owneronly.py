import asyncio
import psutil
import socket
from discord import Activity, ActivityType, CustomActivity, Streaming, Status
from discord.ext import commands
from discord.ext.commands import Cog, Context, ExtensionAlreadyLoaded, ExtensionNotLoaded, NoEntryPointError, ExtensionFailed
from discord.ext.commands.errors import MissingRequiredArgument
from hikari_bot.helpers.errorhandling import *
from hikari_bot.helpers.getipv4info import *
from hikari_bot.startup import MyBot
from hikari_bot.helpers.restarter import restarter
from hikari_bot.helpers.extensionshandler import get_all_extensions, to_module_path
from hikari_bot.helpers.respondembed import respond_embed, ResponseTarget
from hikari_bot.helpers.networkinfo import NetworkInfo
from typing import List, Literal


class OwnerOnly(Cog):
    def __init__(self, bot: MyBot):
        self.bot = bot
        self.logger = self.bot.get_logger()
        self.db = self.bot.get_mongo_cluster_db()


    # Cog-level error listener for unhandled errors
    async def cog_command_error(self, ctx: Context, error: Exception):
        if getattr(ctx, "_error_handled", False):    # if ctx._error_handled was set to True this could be ignored
            return

        # this is an administration cog, so we wanted to keep it simple.
        if isinstance(error, MissingRequiredArgument):
            return await respond_embed(ctx, message=f"Missing required argument: `{error.param.name}`", error=True, target=ResponseTarget.REPLY)

        self.logger.exception(f"Uncaught error in {ctx.cog.__cog_name__}:", exc_info=error)


    # This is a migrated cog from startup.py for owner only commands
    # Sync, presence (migrated from general/ChangeStatus.py), load, unload, reload, systeminfo, restart, shutdown


    # Sync all cogs for latest changes 
    @commands.command(hidden=True)
    async def sync(self, ctx) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Sync all cogs for latest changes
        """

        delete_after_owner_action = 5  # default timer for deleting the message after succeed

        if not await self.bot.is_owner(ctx.author):
            return await respond_embed(ctx, message=NotBotOwnerError(), error=True, target=ResponseTarget.REPLY)

        synced = await self.bot.tree.sync()
        await respond_embed(ctx, title="Sync Successful", message=f"Synced {len(synced)} command(s).", target=ResponseTarget.REPLY, delete_after=delete_after_owner_action)
        await ctx.message.delete(delay=delete_after_owner_action)


    # Helper: build the activity object from plain-string inputs
    def _build_activity(self, activity_type: str | None, name: str | None, url: str | None):
        if activity_type is None:
            return None
        if activity_type == "custom":
            return CustomActivity(name=name)
        if activity_type == "streaming":
            return Streaming(name=name, url=url)
        return Activity(type=getattr(ActivityType, activity_type), name=name)


    # Change the bot's presence (status + activity)
    @commands.command(hidden=True)
    async def presence(
        self,
        ctx: Context,
        status: Literal["idle", "invisible", "dnd", "online"],
        activity_type: Literal["playing", "streaming", "listening", "watching", "custom", "competing"] | None = None,
        activity_name: str | None = None,
        url: str | None = None,
    ) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Change the bot's presence (status and activity)

        Parameters
        ----------
        status: str
            The status to set: idle, invisible, dnd, or online.
        activity_type: str
            The activity type: playing, streaming, listening, watching, custom, or competing.
        activity_name: str
            The text shown in the bot's presence. Wrap in "quotes" if it contains spaces.
        url: str
            The stream URL (streaming only; requires a Twitch/YouTube link).
        """

        delete_after_owner_action = 5  # default timer for deleting the message after succeed

        if not await self.bot.is_owner(ctx.author):
            return await respond_embed(ctx, message=NotBotOwnerError(), error=True, target=ResponseTarget.REPLY)

        activity = self._build_activity(activity_type, activity_name, url)
        await self.bot.change_presence(status=getattr(Status, status), activity=activity)

        await respond_embed(
            ctx,
            title="Presence Updated",
            message=f"Status set to `{status}`" + (f" · `{activity_type}` {activity_name!r}" if activity_type else ""),
            target=ResponseTarget.REPLY,
            delete_after=delete_after_owner_action,
        )
        await ctx.message.delete(delay=delete_after_owner_action)


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

        delete_after_success = 2  # default timer for deleting the message after succeed

        if not await self.bot.is_owner(ctx.author):
            return await respond_embed(ctx, message=NotBotOwnerError(), error=True, target=ResponseTarget.REPLY)

        extensions = await get_all_extensions()
        if cog_name not in extensions:  # Front check if the cog was in the valid cog list or not
            return await respond_embed(ctx, message=ExtensionNotFoundError(cog=cog_name), error=True, target=ResponseTarget.REPLY)

        try:
            await self.bot.load_extension(to_module_path(cog_name))
            await self.bot.tree.sync()
            await respond_embed(ctx, title="Load Successful", message=f"Cog `{cog_name}` has been loaded.", target=ResponseTarget.REPLY, delete_after=delete_after_success)
            await ctx.message.delete(delay=delete_after_success)

        except ExtensionAlreadyLoaded:
            return await respond_embed(ctx, message=f"Cog `{cog_name}` has been already loaded!", error=True, target=ResponseTarget.REPLY)

        except NoEntryPointError:
            return await respond_embed(ctx, message=ReturnNoEntryPointError(cog=cog_name), error=True, target=ResponseTarget.REPLY)

        except ExtensionFailed:
            return await respond_embed(ctx, message=ExtensionFailedError(cog=cog_name), error=True, target=ResponseTarget.REPLY)


    # Unloading a cog manually
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

        delete_after_success = 2  # default timer for deleting the message after succeed

        if not await self.bot.is_owner(ctx.author):
            return await respond_embed(ctx, message=NotBotOwnerError(), error=True, target=ResponseTarget.REPLY)

        if cog_name not in await get_all_extensions():  # Front check if the cog was in the valid cog list or not
            return await respond_embed(ctx, message=ExtensionNotFoundError(cog=cog_name), error=True, target=ResponseTarget.REPLY)

        try:
            await self.bot.unload_extension(to_module_path(cog_name))
            await self.bot.tree.sync()
            await respond_embed(ctx, title="Unload Successful", message=f"Cog `{cog_name}` has been unloaded.", target=ResponseTarget.REPLY, delete_after=delete_after_success)
            await ctx.message.delete(delay=delete_after_success)

        except ExtensionNotLoaded:
            return await respond_embed(ctx, message=f"Cog `{cog_name}` has been already unloaded!", error=True, target=ResponseTarget.REPLY)
        
        except NoEntryPointError:
            return await respond_embed(ctx, message=ReturnNoEntryPointError(cog=cog_name), error=True, target=ResponseTarget.REPLY)

        except ExtensionFailed:
            return await respond_embed(ctx, message=ExtensionFailedError(cog=cog_name), error=True, target=ResponseTarget.REPLY)


    # Reloading a cog manually
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

        delete_after_success = 2  # default timer for deleting the message after succeed

        if not await self.bot.is_owner(ctx.author):
            return await respond_embed(ctx, message=NotBotOwnerError(), error=True, target=ResponseTarget.REPLY)

        if cog_name not in await get_all_extensions():  # Front check if the cog was in the valid cog list or not
            return await respond_embed(ctx, message=ExtensionNotFoundError(cog=cog_name), error=True, target=ResponseTarget.REPLY)

        try:
            await self.bot.reload_extension(to_module_path(cog_name))
            await self.bot.tree.sync()
            await respond_embed(ctx, message=f"Cog `{cog_name}` has been reloaded.", title="Reload Successful", target=ResponseTarget.REPLY, delete_after=delete_after_success)
            await ctx.message.delete(delay=delete_after_success)

        except ExtensionNotLoaded:
            return await respond_embed(ctx, message=f"Cog `{cog_name}` has not been loaded.", error=True, target=ResponseTarget.REPLY)

        except NoEntryPointError:
            return await respond_embed(ctx, message=ReturnNoEntryPointError(cog=cog_name), error=True, target=ResponseTarget.REPLY)

        except ExtensionFailed:
            return await respond_embed(ctx, message=ExtensionFailedError(cog=cog_name), error=True, target=ResponseTarget.REPLY)


    # Retrieving system info from the bot instance
    @commands.command(hidden=True)
    async def systeminfo(self, ctx: Context) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Retrieving system info from the bot
        """

        delete_after_success = 30    # default timer for deleting the message after succeed

        if not await self.bot.is_owner(ctx.author):
            return await respond_embed(ctx, message=NotBotOwnerError(), error=True, target=ResponseTarget.REPLY)

        def convert_to_gib(raw):
            return round(raw / 1024 ** 3, 2)

        # Returning system info as embed
        message_lines: List[str] = []

        # CPU
        cpu_percentage = psutil.cpu_percent()
        number_of_system_cores = psutil.cpu_count(logical=False)
        number_of_logical_cores = psutil.cpu_count(logical=True)

        message_lines.append(
            f"\n**CPU:**\n"
            f"CPU utilization: {cpu_percentage}%"
            f"\nNumber of system cores: {number_of_system_cores}"
            f"\nNumber of logical cores: {number_of_logical_cores}"
        )

        # RAM
        ram = psutil.virtual_memory()
        used_ram_in_gib = convert_to_gib(ram.used)
        available_ram_in_gib = convert_to_gib(ram.available)
        total_ram_in_gib = convert_to_gib(ram.total)
        ram_percentage = ram.percent

        message_lines.append(
            f"\n**RAM:**\n"
            f"Memory in use: {used_ram_in_gib} / {total_ram_in_gib} GiB ({ram_percentage}%)"
            f"\nAvailible memory: {available_ram_in_gib} GiB"
        )

        # Storage
        disk = psutil.disk_usage('/')
        used_volume_in_gib = convert_to_gib(disk.used)
        free_volume_in_gib = convert_to_gib(disk.free)
        total_volume_in_gib = convert_to_gib(disk.total)
        disk_percentage = disk.percent

        message_lines.append(
            f"\n**Storage:**\n"
            f"Space used: {used_volume_in_gib} / {total_volume_in_gib} GiB ({disk_percentage}%)"
            f"\nAvailible space: {free_volume_in_gib} GiB"
        )

        # Basic Network
        basic_network = await asyncio.to_thread(NetworkInfo)   # add ipv6_global_only=True if you want to trim link-local noise

        message_lines.append(
            f"\n**Network (Basic):**\n"
            f"IPv4 Address(s): {basic_network.ipv4_addresses}\n"
            f"Subnet(s) Mask: {basic_network.ipv4_subnets}\n"
            f"IPv4 Gateway: {basic_network.ipv4_gateway}\n"
            f"IPv6 Address(s): {basic_network.ipv6_addresses}\n"
            f"IPv6 Gateway: {basic_network.ipv6_gateway}"
        )


        # Advanced Network
        ip_info = await asyncio.to_thread(IPv4info)
        hostname = socket.gethostname()
        advanced_network = psutil.net_io_counters()

        message_lines.append(
            f"\n**Network (Advanced):**\n"
            f"Hostname: {hostname}\n"
            f"IPv4: {ip_info.ip}\n"
            f"IP Hostname: {ip_info.hostname}\n"
            f"Country or district: {ip_info.country}\n"
            f"Region: {ip_info.region}\n"
            f"City: {ip_info.city}\n"
            f"Organization: {ip_info.organization}\n"
            f"Postal code: {ip_info.postal}\n"
            f"Location: {ip_info.location}\n"
            f"Number of bytes sent: {advanced_network.bytes_sent}\n"
            f"Number of bytes received: {advanced_network.bytes_recv}\n"
            f"Number of packets sent: {advanced_network.packets_sent}\n"
            f"Number of packets received: {advanced_network.packets_recv}\n"
            f"Total number of errors while receiving: {advanced_network.errin}\n"
            f"Total number of errors while sending: {advanced_network.errout}\n"
            f"Total number of incoming packets dropped: {advanced_network.dropin}\n"
            f"Total number of outgoing packets dropped: {advanced_network.dropout}"
        )

        await respond_embed(ctx, title="System Info (For reference only):", message="\n".join(message_lines), target=ResponseTarget.REPLY, delete_after=delete_after_success)
        await ctx.message.delete(delay=delete_after_success)


    # Shutdown the bot and the server
    @commands.command(hidden=True)
    async def selfshutdown(self, ctx: Context) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Shut down the bot and the server (SELF DESTRUCT)

        However, this command does NOT shut down the entire machine/server in docker or VPS hosting environments.
        """

        if not await self.bot.is_owner(ctx.author):
            return await respond_embed(ctx, message=NotBotOwnerError(), error=True, target=ResponseTarget.REPLY)

        await self.bot.close()


    # Restart the bot and the server
    @commands.command(hidden=True)
    async def selfrestart(self, ctx: Context) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Restart the bot and the server
        """

        if not await self.bot.is_owner(ctx.author):
            return await respond_embed(ctx, message=NotBotOwnerError(), error=True, target=ResponseTarget.REPLY)

        restarter.request(reason=f"Restart requested by bot owner.", delay=0.0)
        await self.bot.close()


async def setup(bot: MyBot):
    await bot.add_cog(OwnerOnly(bot))


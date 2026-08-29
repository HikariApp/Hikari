import asyncio
from discord import Forbidden, PermissionOverwrite, TextChannel
from discord.ext import commands
from discord.ext.commands import Cog, Context, MissingPermissions, BotMissingPermissions
from typing import Optional
from startup import MyBot
from helpers.respondEmbed import respondEmbed

# The permissions we toggle to consider a channel "locked".
LOCK_PERMS = (
    "send_messages",
    "create_public_threads",
    "create_private_threads",
    "send_messages_in_threads",
)

class LockChannel(Cog):
    def __init__(self, bot: MyBot):
        self.bot = bot
        self.logger = bot.getLogger()


    # Cog-level error listener for unhandled errors
    # This differs from cog that has _errorHandled flag, but we don't need that here
    async def cog_command_error(self, ctx: Context, error):
        if isinstance(error, MissingPermissions):
            return await ctx.send("You don't have the required permissions to use this command.")

        if isinstance(error, BotMissingPermissions):
            return await ctx.send("I'm missing the permissions needed to do that.")

        self.logger.exception(f"Uncaught error in {self.__cog_name__}:", exc_info=error)


    def lockedState(self, channel: TextChannel) -> Optional[bool]:
        """
        Checks if a channel is locked, unlocked, or partially locked.

        Parameters
        ----------
        channel : discord.TextChannel
            The channel to check.

        Returns
        -------
        bool or None
            Returns True if the channel is fully locked, False if it is fully unlocked,
            and None if it is partially locked.
        """

        overwrite: PermissionOverwrite = channel.overwrites_for(channel.guild.default_role)
        locked = sum(getattr(overwrite, perm) is False for perm in LOCK_PERMS)
        if locked == len(LOCK_PERMS):
            return True

        if locked == 0:
            return False

        return None


    async def applyLock(self, channel: TextChannel, *, lock: bool, reason=None):
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Applies a lock or unlock to the required channel.

        Parameters
        ----------
        channel : discord.TextChannel
            The channel to lock or unlock.
        lock : bool
            If True, the channel will be locked. If False, it will be unlocked.
        reason : str, optional
            The reason for the lock/unlock action, which will be logged in the audit log.
        
        Returns
        -------
        None

        Notes
        -----
        This function has been rewritten, and now modifies the permission overwrites for the default role 
        instead of the hardcoded `@everyone` in specified channel.
        """

        # Helper functions to apply the permission overwrites for the bot and default role

        async def _botOverride(channel: TextChannel, reason: Optional[str]) -> None:
            # keep the bot able to speak so confirmations land and unlock still works
            me = channel.guild.me
            bot_ow = channel.overwrites_for(me)

            if lock:
                # locking: guarantee the bot can speak here for the whole lock duration
                bot_ow.send_messages = True
            else:
                # unlocking: only retract our crutch if send_messages is the *only* thing
                # set on the bot's overwrite. If any other perm is configured, a human set
                # this up deliberately — leave send_messages alone so we don't clobber it.
                others = {
                    perm: value
                    for perm, value in bot_ow
                    if perm != "send_messages" and value is not None
                }
                if not others:
                    bot_ow.send_messages = None
                # else: deliberate human config — don't touch it

            await channel.set_permissions(
                me, overwrite=(bot_ow if not bot_ow.is_empty() else None), reason=reason
            )


        async def _defaultOverride(channel: TextChannel, reason: Optional[str]) -> None:
            # lock/unlock the default role
            target = channel.guild.default_role
            overwrite: PermissionOverwrite = channel.overwrites_for(target)

            for perm in LOCK_PERMS:
                setattr(overwrite, perm, False if lock else None)

            new = overwrite if not overwrite.is_empty() else None
            await channel.set_permissions(target, overwrite=new, reason=reason)

        # Apply the overrides in the correct order to avoid permission issues.
        if lock:
            await _botOverride(channel, reason)
            await _defaultOverride(channel, reason)

        else:
            await _defaultOverride(channel, reason)
            await _botOverride(channel, reason)


    async def bulk(self, ctx, *, lock: bool, reason=None):
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Applies a lock or unlock to all text channels in the guild, concurrently.

        Parameters
        ----------
        ctx : commands.Context
            The context of the command invocation.
        lock : bool
            If True, all text channels will be locked. If False, they will be unlocked.
        reason : str, optional
            The reason for the lock/unlock action, which will be logged in the audit log.

        Returns
        -------
        tuple
            A tuple containing three integers:
            - The number of channels that were successfully changed.
            - The number of channels that were already in the desired state.
            - The number of channels that failed to change due to permission issues.

        Notes
        -----
        This function has been rewritten to apply locks concurrently via asyncio.gather,
        bounded by a semaphore to stay within Discord's rate limits.  
        `discord.py` handles 429 retries internally, so no explicit rate-limit handling
        is needed here.
        """

        desired = True if lock else False

        # lockedState is a pure in-memory read (no await), so partition synchronously.
        # Channels already in the desired state are skipped before any API call.
        todo = [ch for ch in ctx.guild.text_channels if self.lockedState(ch) is not desired]
        already = len(ctx.guild.text_channels) - len(todo)

        if not todo:
            return 0, already, 0

        # Bound concurrency: overlap network round-trips without stampeding a route bucket.
        sem = asyncio.Semaphore(5)

        async def _one(channel: TextChannel):
            async with sem:
                await self.applyLock(channel, lock=lock, reason=reason)

        results = await asyncio.gather(
            *(_one(ch) for ch in todo),
            return_exceptions=True,
        )

        # gather preserves input order, so results line up with `todo`.
        failed = 0
        for ch, r in zip(todo, results):
            if isinstance(r, Exception):
                failed += 1

                if not isinstance(r, Forbidden):
                    verb = "locking" if lock else "unlocking"
                    self.logger.exception(f"Unexpected error on {verb} #{ch}:", exc_info=r)

        changed = len(todo) - failed

        return changed, already, failed


    @commands.hybrid_group(name="antiraid", help="Lock or unlock every text channel at once.")
    @commands.guild_only()
    async def antiraid(self, ctx: Context):
        # This is the main command group for antiraid
        # We won't implement any logic here, as the subcommands will handle the functionality
        # If no subcommand is invoked, return an error message
        await respondEmbed(ctx, message=f"{ctx.author.mention}, you need to specify a subcommand: `activate` or `deactivate`.", error=True)


    @antiraid.command(name="activate", description="Locks all text channels for everyone.")
    @commands.has_permissions(administrator=True, manage_channels=True, manage_guild=True)
    async def antiraid_activate(self, ctx: Context, *, reason: Optional[str] = None):
        """
        Locks all text channels for everyone

        Parameters
        ----------
        reason : str, optional
            Reason for anti-raid
        """

        if ctx.interaction:
            await ctx.interaction.response.defer()

        changed, already, failed = await self.bulk(ctx, lock=True, reason=reason)
        failNote = f"**{failed}** channel(s) failed (check my permissions/role position)." if failed else ""

        if changed:
            return await respondEmbed(
                ctx,
                message = (
                    f"Anti-raid mode **activated** — locked **{changed}** channel(s)."
                    + (f"\n**Reason**: {reason}" if reason else "")
                    + (f"\n\n{failNote}" if failed else "")
                )
            )

        if already and not failed:
            return await respondEmbed(
                ctx,
                message="Anti-raid mode is **already active**."
            )

        return await respondEmbed(
            ctx,
            message=f"Nothing was **locked**.\n{failNote}",
            error=True
        )


    @antiraid.command(name="deactivate", description="Unlocks all text channels for everyone.")
    @commands.has_permissions(administrator=True, manage_channels=True, manage_guild=True)
    async def antiraid_deactivate(self, ctx: Context, *, reason: Optional[str] = None):
        """
        Unlocks all text channels for everyone

        Parameters
        ----------
        reason : str, optional
            Reason for anti-raid
        """

        if ctx.interaction:
            await ctx.interaction.response.defer()

        changed, already, failed = await self.bulk(ctx, lock=False, reason=reason)
        failNote = f"**{failed}** channel(s) failed (check my permissions/role position)." if failed else ""

        if changed:
            return await respondEmbed(
                ctx,
                message = (
                    f"Anti-raid mode **deactivated** — unlocked **{changed}** channel(s)."
                    + (f"\n**Reason**: {reason}" if reason else "")
                    + (f"\n\n{failNote}" if failed else "")
                )
            )

        if already and not failed:
            return await respondEmbed(
                ctx,
                message="Anti-raid mode is **already inactive**."
            )

        return await respondEmbed(
            ctx,
            message=f"Nothing was **unlocked**.\n{failNote}",
            error=True
        )


    @commands.hybrid_command(name="lock", description="Locks the current or a specified text channel.")
    @commands.guild_only()
    @commands.has_permissions(administrator=True, manage_channels=True)
    async def lock(self, ctx, channel: Optional[TextChannel] = None, *, reason: Optional[str] = None):
        """
        Locks the current or a specified text channel.

        Parameters
        ----------
        channel : discord.TextChannel, optional
            The text channel to lock. If not provided, current channel will be locked.
        
        reason : str, optional
            Reason for locking the channel
        """

        if ctx.interaction:
            await ctx.interaction.response.defer()

        channel: TextChannel = channel or ctx.channel

        if self.lockedState(channel) is True:
            return await respondEmbed(ctx, message=f"{channel.mention} is already locked.")

        try:
            await self.applyLock(channel, lock=True, reason=reason)

        except Forbidden:
            return await respondEmbed(ctx, message=f"I couldn't lock {channel.mention} — check my permissions and role position.", error=True)

        await respondEmbed(
            ctx,
            message=(
                f"Locked {channel.mention}."
                + (f"\n**Reason**: {reason}" if reason else "")
                )
            )


    @commands.hybrid_command(name="unlock", description="Unlocks the current or a specified text channel.")
    @commands.guild_only()
    @commands.has_permissions(administrator=True, manage_channels=True)
    async def unlock(self, ctx, channel: Optional[TextChannel] = None, *, reason: Optional[str] = None):
        """
        Unlocks the current or a specified text channel.

        Parameters
        ----------
        channel : discord.TextChannel, optional
            The text channel to unlock. If not provided, current channel will be unlocked.

        reason : str, optional
            Reason for unlocking the channel
        """

        if ctx.interaction:
            await ctx.interaction.response.defer()

        channel: TextChannel = channel or ctx.channel

        if self.lockedState(channel) is False:
            return await respondEmbed(ctx, message=f"{channel.mention} is already unlocked.")

        try:
            await self.applyLock(channel, lock=False, reason=reason)

        except Forbidden:
            return await respondEmbed(ctx, message=f"I couldn't unlock {channel.mention} — check my permissions and role position.", error=True)

        await respondEmbed(
            ctx,
            message=(
                f"Unlocked {channel.mention}."
                + (f"\n**Reason**: {reason}" if reason else "")
                )
            )


async def setup(bot: MyBot):
    await bot.add_cog(LockChannel(bot))

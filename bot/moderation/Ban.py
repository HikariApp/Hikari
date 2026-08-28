from discord import Forbidden, Member, User
from discord.ext import commands
from discord.ext.commands import Cog, Context, CommandInvokeError, MissingPermissions, MissingRequiredArgument, BotMissingPermissions, UserNotFound
from typing import Any, Optional
from startup import MyBot
from helpers.respondEmbed import respondEmbed

# Check if a user is already banned in the guild
async def isBanned(ctx: Context, user: User) -> bool:
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).
    
    Checks if a user is already banned in the guild.

    Parameters
    ----------
    ctx : discord.ext.commands.Context
        The context of the command invocation.
    user : discord.User
        The user to check.

    Returns
    -------
    bool
        Returns `True` if the user is already banned, `False` otherwise.
    """

    async for entry in ctx.guild.bans():
        if entry.user.id == user.id:
            return True

    return False


class Ban(Cog):
    def __init__(self, bot: MyBot):
        self.bot = bot
        self.logger = self.bot.getLogger()


    # Cog-level error listener for unhandled errors
    async def cog_command_error(self, ctx: Context, error: Exception):
        if getattr(ctx, "_errorHandled", False):    # if ctx._errorHandled was set to True this could be ignored
            return

        self.logger.exception(f"Uncaught error in {ctx.cog.__cog_name__}:", exc_info=error)


    # Bans a user
    @commands.hybrid_command(name="ban", help="Bans a user")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.bot_has_guild_permissions(ban_members=True)
    async def ban(self, ctx: Context, user: User, *, reason: Optional[str] = None) -> None:
        """
        Bans a user.

        Parameters
        ----------
        user : discord.User
            The user to ban (Enter the User ID e.g. 529872483195806124)
        reason : Optional[str]
            The reason for the ban.

        Notes
        -----
        This command has been heavily rewritten to support hybrid commands, and it now combines both guild ban and member ban functionalities for simplicity.

        If the user is not in the server, it will ban them from the guild using their user ID, otherwise, it will ban them as a member.

        As same as before, only the server owner (or bot owner) has privileges to ban admins.
        """

        member: Optional[Member] = None

        if not ctx.guild:
            return await respondEmbed(ctx, message=f"This command can only be used in a **server**, {ctx.author.mention}.", error=True)

        # Defer the interaction response if invoked as a slash command, in case of long processing time.
        if ctx.interaction:
            await ctx.interaction.response.defer()

        # Basic checks
        # Error handling will be done by the error handler below
        if (user.id == ctx.author.id):
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, You can't **ban yourself**!", error=True)
        
        if (user.id == self.bot.user.id):
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, I can't **ban myself**!", error=True)

        if await isBanned(ctx, user):
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, {user.mention} is already **banned**!", error=True)

        # Determine if banning from guild or as member
        # Try to find the user as a member of the current guild
        if ctx.guild:
            member = ctx.guild.get_member(user.id)

        # As stated above, only the server owner (or bot owner) has privileges to ban admins
        if member and member.guild_permissions.administrator and (ctx.author.id != ctx.guild.owner.id or not await self.bot.is_owner(ctx.author)):
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, I know you're trying to **ban an admin**, but I can't let you do that... :rolling_eyes:", error=True)
        
        if member and member.top_role >= ctx.guild.get_member(self.bot.user.id).top_role:
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, I can't **ban** {user.mention} because their **top role is higher than mine**.", error=True)
        
        # All checks passed, proceed to ban
        if reason is None:
            await member.ban() if member else await ctx.guild.ban(user)
            return await respondEmbed(ctx, message=f":white_check_mark: {user.mention} has been **banned**.")

        else:
            return await respondEmbed(ctx, message=f":white_check_mark: {user.mention} has been **banned**.\nReason: **{reason}**")


    # Error handling, for both commands and slash commands
    @ban.error
    async def ban_error(self, ctx: Context, error: Any):
        ctx._errorHandled = False    # if the error is handled, we would set this to True to prevent further propagation

        if isinstance(error, MissingRequiredArgument) and error.param.name == "user":
            # The command invoker doesn't provide the user argument
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"Looks like you want me to **ban someone**, but **haven't specified** the user you would like to ban :thinking:  ...\nJust curious to know, **who** should I ban for now, {ctx.author.mention}?", error=True)
        
        if isinstance(error, UserNotFound):
            # The member argument couldn't be converted to either User or Member
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"I couldn't find **the user you wanted to ban** :thinking: ... Perhaps check if that user really **exists** on Discord, {ctx.author.mention}?", error=True)
        
        if isinstance(error, MissingRequiredArgument):
            # Missing argument(s)
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"<a:crossred:1356353067024515266> Missing argument: `{error.param.name}`. Please provide all required arguments, {ctx.author.mention}.", error=True)

        if isinstance(error, MissingPermissions):
            # The command invoker doesn't have permissions
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"<a:crossred:1356353067024515266> This command **requires** `ban_members` permission, and you probably **don't have** it, {ctx.author.mention}.", error=True)

        if (
            isinstance(error, BotMissingPermissions) or
            (isinstance(error, CommandInvokeError) and isinstance(error.original, Forbidden))    # Sometimes the application might throw a CommandInvokeError which caused by Forbidden, which is basically the same concept
        ):
            # The application doesn't have permissions to do so
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"<a:crossred:1356353067024515266> I couldn't **ban** that user. Please **double-check** my **permissions** and **role position**.", error=True)


async def setup(bot: MyBot):
    await bot.add_cog(Ban(bot))

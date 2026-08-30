import discord
from datetime import timedelta
from discord import Forbidden, Member
from discord.ext import commands
from discord.ext.commands import BadUnionArgument, Cog, Context, CommandInvokeError, MissingPermissions, MissingRequiredArgument, MemberNotFound, BotMissingPermissions, UserNotFound
from typing import Any, Optional
from startup import MyBot
from helpers.respondEmbed import respondEmbed
from helpers.parseDuration import parseDuration


class Timeout(Cog):
    def __init__(self, bot: MyBot):
        self.bot = bot
        self.logger = self.bot.getLogger()


    # Cog-level error listener for unhandled errors
    async def cog_command_error(self, ctx: Context, error: Exception):
        if getattr(ctx, "_errorHandled", False):    # if ctx._errorHandled was set to True this could be ignored
            return

        self.logger.exception(f"Uncaught error in {ctx.cog.__cog_name__}:", exc_info=error)


    # Function of timeout a member
    async def applyTimeout(self, ctx: Context, member: discord.Member, durationStr: str | None, reason: str | None):
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Applies a timeout to a member for a specified duration with an optional reason.

        This handles the logic for applying a timeout to a member, including parsing the duration string and checking for errors.
        It also sends appropriate responses to the context based on the outcome of the operation.

        Parameters
        ----------
        ctx : discord.ext.commands.Context
            The context in which the command was invoked.
        member : discord.Member | discord.User
            The member to timeout.
        durationStr : str, optional
            The duration for the timeout in a string format (e.g., "1h", "30m", "2d"). If None, the timeout will be indefinite.
        reason : str, optional
            The reason for the timeout. If None, no reason will be provided.

        Returns
        -------
        None
        """

        totalDuration = parseDuration(durationStr)
        
        if totalDuration is None:
            return await respondEmbed(ctx, message=f"Looks like the time format you entered is not valid :thinking: ... Perhaps enter again and give me a chance to handle it, {ctx.author.mention} :pleading_face:?\n\n**Supported time format:**\n**1**s = **1** second | **2**m = **2** minutes | **5**h = **5** hours | **10**d = **10** days | **3**w = **3** weeks.", error=True)

        # Check if the total duration exceeds 28 days (4 weeks)
        if totalDuration["total_seconds"] > 2419200:
            return await respondEmbed(ctx, message=f"Looks like the total duration you entered exceeds **28 days** :thinking: ... Perhaps enter again and give me a chance to handle it, {ctx.author.mention} :pleading_face:?\n\n**Supported time format:**\n**1**s = **1** second | **2**m = **2** minutes | **5**h = **5** hours | **10**d = **10** days | **3**w = **3** weeks.", error=True)

        durationMessage = "for " + " and ".join(", ".join([f"**{value}** {unit[:-1]}" + ("s" if value > 1 else "") for unit, value in totalDuration.items() if unit != "total_seconds" and value != 0]).rsplit(", ", 1)) + " " if durationStr is not None else ""
        reasonMessage =  f"\nReason: **{reason}**" if reason is not None else ""

        reasonKarg = {"reason": reason} if reason is not None else {}
        await member.timeout(timedelta(seconds=totalDuration["total_seconds"]), **reasonKarg)

        await respondEmbed(ctx, message=f":white_check_mark: {member.mention} has been **timed out** {durationMessage}:zipper_mouth:{reasonMessage}")


    # Timeouts a member for a specified amount of time
    @commands.hybrid_command(name="timeout", help="Timeouts a member for a specified amount of time")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def timeout(self, ctx: Context, member: Member, duration: Optional[str] = None, *, reason: Optional[str] = None):
        """
        Timeouts a member for a specified amount of time.

        Parameters
        ----------
        member : discord.Member
            The member to timeout.
        duration : Optional[str]
            Duration for timeout (e.g. 1s = 1 second | 2m = 2 minutes | 5h = 5 hours | 10d = 10 days | 3w = 3 weeks). Must be less than 28 days in total.
        reason : Optional[str]
            Reason for timeout.

        Notes
        -----
        This command has been heavily rewritten to support hybrid commands.

        As same as before, only the server owner (or bot owner) has privileges to timeout admins.
        """

        # Defer the interaction response if invoked as a slash command, in case of long processing time.
        if ctx.interaction:
            await ctx.interaction.response.defer()

        # Basic checks
        # Error handling will be done by the error handler below
        if (member.id == ctx.author.id):
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, You can't **timeout yourself**!", error=True)
        
        if (member.id == self.bot.user.id):
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, I can't **timeout myself**!", error=True)
        
        if ctx.guild.get_member(member.id) is None:
            # The specified user exists, but could not be found as a member of the guild
            return await respondEmbed(ctx, message=f"Looks like {member.mention} is not in the server, {ctx.author.mention} :thinking: ...", error=True)
        
        # As stated above, only the server owner (or bot owner) has privileges to timeout admins
        if member.guild_permissions.administrator and (ctx.author.id != ctx.guild.owner.id or not await self.bot.is_owner(ctx.author)):
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, I know you're trying to **timeout an admin**, but I can't let you do that... :rolling_eyes:", error=True)
        
        if member and member.top_role >= ctx.guild.get_member(self.bot.user.id).top_role:
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, I can't **timeout** {member.mention} because their **top role is higher than mine**.", error=True)
        
        await self.applyTimeout(ctx, member, duration, reason)


    # Error handling, for both commands and slash commands
    @timeout.error
    async def timeout_error(self, ctx: Context, error: Any):
        ctx._errorHandled = False    # if the error is handled, we would set this to True to prevent further propagation

        if isinstance(error, MissingRequiredArgument) and error.param.name == "member":
            # The command invoker doesn't provide the member argument
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"Looks like you want me to **timeout someone**, but **haven't specified** the user you would like to timeout :thinking:  ...\nJust curious to know, **who** should I timeout for now, {ctx.author.mention}?", error=True)

        if isinstance(error, BadUnionArgument) or isinstance(error, UserNotFound):
            # The member argument couldn't be converted to either User or Member
            # This includes the case where a User is provided but does not exist
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"I couldn't find **the user you wanted to timeout** :thinking: ... Perhaps check if that user really **exists** on Discord, {ctx.author.mention}?", error=True)
        
        if isinstance(error, MemberNotFound):
            # The specified member could not be found
            # This will unlikely be triggered since we are using Union[User, Member] for the member argument, but we add it here just in case
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"{error.argument} is not in the server, {ctx.author.mention} :thinking: ...", error=True)

        if isinstance(error, MissingRequiredArgument):
            # Missing argument(s)
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"Missing argument: `{error.param.name}`. Please provide all required arguments, {ctx.author.mention}.", error=True)

        if isinstance(error, MissingPermissions):
            # The command invoker doesn't have permissions
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"This command **requires** `moderate_members` permission, and you probably **don't have** it, {ctx.author.mention}.", error=True)

        if (
            isinstance(error, BotMissingPermissions) or
            (isinstance(error, CommandInvokeError) and isinstance(error.original, Forbidden))    # Sometimes the application might throw a CommandInvokeError which caused by Forbidden, which is basically the same concept
        ):
            # The application doesn't have permissions to do so
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"I couldn't **timeout** that member. Please **double-check** my **permissions** and **role position**.", error=True)


async def setup(bot: MyBot):
    await bot.add_cog(Timeout(bot))

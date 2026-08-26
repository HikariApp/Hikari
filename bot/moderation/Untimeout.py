from discord import Forbidden, Member
from discord.ext import commands
from discord.ext.commands import Bot, Cog, Context, CommandInvokeError, MissingPermissions, MissingRequiredArgument, BotMissingPermissions, UserNotFound
from typing import Any, Optional
from helpers.respondEmbed import respondEmbed

class Untimeout(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.getLogger()


    # Cog-level error listener for unhandled errors
    async def cog_on_command_error(self, ctx: Context, error: Exception):
        self.logger.exception(f"Uncaught error in {ctx.cog.__cog_name__}:", exc_info=error)
        raise error


    # Remove timeouts for a member
    @commands.hybrid_command(name="untimeout", help="Remove timeouts for a member")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def untimeout(self, ctx: Context, member: Member, reason: Optional[str] = None):
        """
        Remove timeouts for a member
        
        Parameters
        ----------
        
        member : discord.Member
            The member to unmute (Enter the User ID e.g. 529872483195806124)
        reason : Optional[str]
            Reason for unmute.

        Notes
        -----
        This command has been heavily rewritten to support hybrid commands.
        """
        
        if reason is not None:
            await member.timeout(None, reason=reason)
            return await respondEmbed(ctx, message=f"{member.mention} has been **untimeout**.\nReason: **{reason}**.")
        
        else:
            await member.timeout(None)
            return await respondEmbed(ctx, message=f"{member.mention} has been **untimeout**.")


    # Handle errors while unbanning a user, for both commands and app_commands
    @untimeout.error
    async def untimeout_error(self, ctx: Context, error: Any):
        if isinstance(error, MissingRequiredArgument) and error.param.name == "user":
            # The command invoker doesn't provide the user argument
            # A special case to return a more user-friendly message
            return await respondEmbed(ctx, message=f"Looks like you want me to **untimeout someone**, but **haven't specified** the user you would like to untimeout :thinking:  ...\nJust curious to know, **who** should I untimeout for now, {ctx.author.mention}?", error=True)
        
        if isinstance(error, UserNotFound):
            # The user argument couldn't be converted to User
            # A special case to return a more user-friendly message
            return await respondEmbed(ctx, message=f"I couldn't find **the user you wanted to untimeout** :thinking: ... Perhaps check if that user really **exists** on Discord, {ctx.author.mention}?", error=True)
        
        if isinstance(error, MissingRequiredArgument):
            # Missing argument(s)
            return await respondEmbed(ctx, message=f"Missing argument: `{error.param.name}`. Please provide all required arguments, {ctx.author.mention}.", error=True)

        if isinstance(error, MissingPermissions):
            # The command invoker doesn't have permissions
            return await respondEmbed(ctx, message=f"This command **requires** `moderate_members` permission, and you probably **don't have** it, {ctx.author.mention}.", error=True)

        if (
            isinstance(error, BotMissingPermissions) or
            (isinstance(error, CommandInvokeError) and isinstance(error.original, Forbidden))    # Sometimes the application might throw a CommandInvokeError which caused by Forbidden, which is basically the same concept
        ):
            # The application doesn't have permissions to do so
            return await respondEmbed(ctx, message=f"I couldn't **untimeout** that user. Please **double-check** my **permissions** and **role position**.", error=True)

        # If the error is not handled, forward to the cog-level listener, or even bot-level if unhandled here
        self.cog_on_command_error(ctx, error)


async def setup(bot):
    await bot.add_cog(Untimeout(bot))

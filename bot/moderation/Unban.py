from discord import Forbidden, User
from discord.ext import commands
from discord.ext.commands import Cog, Context, CommandInvokeError, MissingPermissions, MissingRequiredArgument, BotMissingPermissions, UserNotFound
from bot.moderation.Ban import isBanned
from typing import Any, Optional
from startup import MyBot
from helpers.respondEmbed import respondEmbed


class Unban(Cog):
    def __init__(self, bot: MyBot):
        self.bot = bot
        self.logger = self.bot.getLogger()


    # Cog-level error listener for unhandled errors
    async def cog_command_error(self, ctx: Context, error: Exception):
        if getattr(ctx, "_errorHandled", False):    # if ctx._errorHandled was set to True this could be ignored
            return

        self.logger.exception(f"Uncaught error in {ctx.cog.__cog_name__}:", exc_info=error)


    # Unbans a user
    @commands.hybrid_command(name="unban", help="Unbans a user")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx: Context, user: User, reason: Optional[str] = None):
        """
        Unbans a user.
        
        Parameters
        ----------
        
        user : discord.User
            The user to unban (Enter the User ID e.g. 529872483195806124)
        reason : Optional[str]
            Reason for unban.
        """

        # Defer the interaction response if invoked as a slash command, in case of long processing time.
        if ctx.interaction:
            await ctx.interaction.response.defer()

        if not ctx.guild:
            return await respondEmbed(ctx, message=f"This command can only be used in a **server**, {ctx.author.mention}.", error=True)

        if not await isBanned(ctx, user):
            return await respondEmbed(ctx, message=f"{user.mention} is **not banned** currently.", error=True)
            
        if reason is None:
            await ctx.guild.unban(user)
            return await respondEmbed(ctx, message=f":white_check_mark: {user.mention} has been **unbanned**.")
        
        else:
            await ctx.guild.unban(user, reason=reason)
            return await respondEmbed(ctx, message=f":white_check_mark: {user.mention} has been **unbanned**.\nReason: **{reason}**")


    # Handle errors while unbanning a user, for both commands and app_commands
    @unban.error
    async def unban_error(self, ctx: Context, error: Any):
        ctx._errorHandled = False    # if the error is handled, we would set this to True to prevent further propagation

        if isinstance(error, MissingRequiredArgument) and error.param.name == "user":
            # The command invoker doesn't provide the user argument
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"Looks like you want me to **unban someone**, but **haven't specified** the user you would like to unban :thinking:  ...\nJust curious to know, **who** should I unban for now, {ctx.author.mention}?", error=True)
        
        if isinstance(error, UserNotFound):
            # The user argument couldn't be converted to User
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"I couldn't find **the user you wanted to unban** :thinking: ... Perhaps check if that user really **exists** on Discord, {ctx.author.mention}?", error=True)
        
        if isinstance(error, MissingRequiredArgument):
            # Missing argument(s)
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"Missing argument: `{error.param.name}`. Please provide all required arguments, {ctx.author.mention}.", error=True)

        if isinstance(error, MissingPermissions):
            # The command invoker doesn't have permissions
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"This command **requires** `ban_members` permission, and you probably **don't have** it, {ctx.author.mention}.", error=True)

        if (
            isinstance(error, BotMissingPermissions) or
            (isinstance(error, CommandInvokeError) and isinstance(error.original, Forbidden))    # Sometimes the application might throw a CommandInvokeError which caused by Forbidden, which is basically the same concept
        ):
            # The application doesn't have permissions to do so
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"I couldn't **unban** that user. Please **double-check** my **permissions** and **role position**.", error=True)


async def setup(bot: MyBot):
    await bot.add_cog(Unban(bot))

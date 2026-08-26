from discord import Color, Embed, Forbidden, User
from discord.ext import commands
from discord.ext.commands import Bot, Cog, Context, CommandInvokeError, MissingPermissions, MissingRequiredArgument, BotMissingPermissions, UserNotFound
from bot.moderation.Ban import isBanned
from typing import Any, Optional


class Unban(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    # Cog-level error listener for unhandled errors
    async def cog_on_command_error(self, ctx: Context, error: Exception):
        self.logger.exception(f"Uncaught error in {ctx.cog.__cog_name__}:", exc_info=error)
        raise error

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
        
        embed = Embed(title="")

        if not ctx.guild:
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> This command can only be used in a **server**, {ctx.author.mention}.")
            embed.color = Color.red()
            return await ctx.send(embed=embed)

        if not await isBanned(ctx, user):
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> {user.mention} is **not banned** currently.")
            embed.color = Color.red()
            return await ctx.send(embed=embed)
            
        if reason is None:
            await ctx.guild.unban(user)
            embed.add_field(name="", value=f":white_check_mark: {user.mention} has been **unbanned**.")
        
        else:
            await ctx.guild.unban(user, reason=reason)
            embed.add_field(name="", value=f":white_check_mark: {user.mention} has been **unbanned**.\nReason: **{reason}**")
        
        await ctx.send(embed=embed)


    # Handle errors while unbanning a user, for both commands and app_commands
    @unban.error
    async def unban_error(self, ctx: Context, error: Any):
        embed = Embed(title="")
        embed.color = Color.red()

        if isinstance(error, MissingRequiredArgument) and error.param.name == "user":
            # The command invoker doesn't provide the user argument
            # A special case to return a more user-friendly message
            embed.add_field(name="", value=f"Looks like you want me to **unban someone**, but **haven't specified** the user you would like to unban :thinking:  ...\nJust curious to know, **who** should I unban for now, {ctx.author.mention}?")
            embed.color = ctx.author.color
            return await ctx.send(embed=embed)
        
        if isinstance(error, UserNotFound):
            # The user argument couldn't be converted to User
            # A special case to return a more user-friendly message
            embed.add_field(name="", value=f"I couldn't find **the user you wanted to unban** :thinking: ... Perhaps check if that user really **exists** on Discord, {ctx.author.mention}?")
            embed.color = ctx.author.color
            return await ctx.send(embed=embed)
        
        if isinstance(error, MissingRequiredArgument):
            # Missing argument(s)
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> Missing argument: `{error.param.name}`. Please provide all required arguments, {ctx.author.mention}.")
            return await ctx.send(embed=embed)

        if isinstance(error, MissingPermissions):
            # The command invoker doesn't have permissions
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> This command **requires** `ban_members` permission, and you probably **don't have** it, {ctx.author.mention}.")
            return await ctx.send(embed=embed)

        if (
            isinstance(error, BotMissingPermissions) or
            (isinstance(error, CommandInvokeError) and isinstance(error.original, Forbidden))    # Sometimes the application might throw a CommandInvokeError which caused by Forbidden, which is basically the same concept
        ):
            # The application doesn't have permissions to do so
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I couldn't **unban** that user. Please **double-check** my **permissions** and **role position**.")
            return await ctx.send(embed=embed)

        # If the error is not handled, forward to the cog-level listener, or even bot-level if unhandled here
        self.cog_on_command_error(ctx, error)


async def setup(bot: Bot):
    await bot.add_cog(Unban(bot))

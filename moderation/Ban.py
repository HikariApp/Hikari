from discord import Color, Embed, Forbidden, Member, User
from discord.ext import commands
from discord.ext.commands import Bot, Cog, Context, CommandInvokeError, MissingPermissions, MissingRequiredArgument, BotMissingPermissions, UserNotFound
from typing import Optional

class Ban(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = self.bot.getLogger()

    # Cog-level error listener for unhandled errors
    async def cog_on_command_error(self, ctx: Context, error: Exception):
        self.logger.exception(f"Uncaught error in {ctx.cog.__cog_name__}:", exc_info=error)
        raise error
    
    # Check if a user is already banned in the guild
    async def isBanned(self, ctx: Context, user: User) -> bool:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).
        
        Checks if a user is already banned in the guild.

        Parameters
        ----------
        ctx : `discord.ext.commands.Context`
            The context of the command invocation.
        
        user : `discord.User`
            The user to check.

        Returns
        ----------
        bool
            Returns `True` if the user is already banned, `False` otherwise.

        """

        async for entry in ctx.guild.bans():
            if entry.user.id == user.id:
                return True

        return False

    # Bans a user
    # UPDATE 24-10-2025: This command has been heavily rewritten to support hybrid commands, see Note for more details.
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
        
        Returns
        ----------
        None
        
        Note
        ----------
        This command has been heavily rewritten to support hybrid commands, and it now combines both guild ban and member ban functionalities for simplicity.

        If the user is not in the server, it will ban them from the guild using their user ID, otherwise, it will ban them as a member.

        As same as before, only the server owner (or bot owner) has privileges to ban admins.

        """

        embed = Embed(title="")
        member: Optional[Member] = None

        # Defer the interaction response if invoked as a slash command, in case of long processing time.
        if ctx.interaction:
            await ctx.interaction.response.defer()

        # Basic checks
        # Error handling will be done by the error handler below
        if (user.id == ctx.author.id):
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> {ctx.author.mention}, You can't **ban yourself**!")
            embed.color = Color.red()
            return await ctx.send(embed=embed)
        
        if (user.id == self.bot.user.id):
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> {ctx.author.mention}, I can't **ban myself**!")
            embed.color = Color.red()
            return await ctx.send(embed=embed)

        if await self.isBanned(ctx, user):
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> {ctx.author.mention}, {user.mention} is already **banned**!")
            embed.color = Color.red()
            return await ctx.send(embed=embed)

        # Determine if banning from guild or as member
        # Try to find the user as a member of the current guild
        if ctx.guild:
            member = ctx.guild.get_member(user.id)

        # As stated above, only the server owner (or bot owner) has privileges to ban admins
        if member and member.guild_permissions.administrator and (ctx.author.id != ctx.guild.owner.id or not await self.bot.is_owner(ctx.author)):
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> {ctx.author.mention}, I know you're trying to **ban an admin**, but I can't let you do that... :rolling_eyes:")
            embed.color = Color.red()
            return await ctx.send(embed=embed)
        
        if member and member.top_role >= ctx.guild.get_member(self.bot.user.id).top_role:
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> {ctx.author.mention}, I can't **ban** {user.mention} because their **top role is higher than mine**.")
            embed.color = Color.red()
            return await ctx.send(embed=embed)
        
        # All checks passed, proceed to ban
        if reason is None:
            await member.ban() if member else await ctx.guild.ban(user)
            embed.add_field(name="", value=f":white_check_mark: {user.mention} has been **banned**.")

        else:
            await member.ban(reason=reason) if member else await ctx.guild.ban(user, reason=reason)
            embed.add_field(name="", value=f":white_check_mark: {user.mention} has been **banned**.\nReason: **{reason}**")

        embed.color = ctx.author.color
        await ctx.send(embed=embed)
        

    # Error handling, for both commands and slash commands
    @ban.error
    async def ban_error(self, ctx: Context, error):
        embed = Embed(title="")
        embed.color = Color.red()

        if isinstance(error, MissingRequiredArgument) and error.param.name == "user":
            # The command invoker doesn't provide the user argument
            # A special case to return a more user-friendly message
            embed.add_field(name="", value=f"Looks like you want me to **ban someone**, but **haven't specified** the user you would like to ban :thinking:  ...\nJust curious to know, **who** should I ban for now, {ctx.author.mention}?")
            embed.color = ctx.author.color
            return await ctx.send(embed=embed)
        
        if isinstance(error, UserNotFound):
            # The member argument couldn't be converted to either User or Member
            # A special case to return a more user-friendly message
            embed.add_field(name="", value=f"I couldn't find **the user you wanted to ban** :thinking: ... Perhaps check if that user really **exists** on Discord, {ctx.author.mention}?")
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
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I couldn't **ban** that user. Please **double-check** my **permissions** and **role position**.")
            return await ctx.send(embed=embed)

        # If the error is not handled, forward to the cog-level listener, or even bot-level if unhandled here
        self.cog_on_command_error(ctx, error)


async def setup(bot):
    await bot.add_cog(Ban(bot))



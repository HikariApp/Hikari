from discord import Color, Embed, Forbidden, Member, User
from discord.ext import commands
from discord.ext.commands import BadUnionArgument, Cog, Context, CommandInvokeError, MissingPermissions, MissingRequiredArgument, MemberNotFound, BotMissingPermissions, UserNotFound
from typing import Any, Optional
from startup import MyBot
from helpers.respondEmbed import respondEmbed

class Kick(Cog):
    def __init__(self, bot: MyBot):
        self.bot = bot
        self.logger = self.bot.getLogger()


    # Cog-level error listener for unhandled errors
    async def cog_command_error(self, ctx: Context, error: Exception):
        if getattr(ctx, "_errorHandled", False):    # if ctx._errorHandled was set to True this could be ignored
            return

        self.logger.exception(f"Uncaught error in {ctx.cog.__cog_name__}:", exc_info=error)


    # Kicks a member
    @commands.hybrid_command(name="kick", help="Kicks a member")
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.bot_has_guild_permissions(kick_members=True)
    async def kick(self, ctx: Context, member: Member | User, *, reason: Optional[str] = None) -> None:
        """
        Kicks a member.

        Parameters
        ----------
        member : Union[discord.Member, discord.User]
            The member to kick.
        reason : Optional[str]
            The reason for the kick.

        Notes
        -----
        This command has been heavily rewritten to support hybrid commands.

        For the `member` argument, it now accepts both `discord.Member` and `discord.User` types.

        If a `discord.User` object is provided, the bot will check if they are a member of the guild before attempting to kick them.

        If the specified user is not a member of the guild, an appropriate message will be sent.
        """

        # Defer the interaction response if invoked as a slash command, in case of long processing time.
        if ctx.interaction:
            await ctx.interaction.response.defer()

        # Basic checks
        # Error handling will be done by the error handler below
        if (member.id == ctx.author.id):
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, You can't **kick yourself**!", error=True)
        
        if (member.id == self.bot.user.id):
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, I can't **kick myself**!", error=True)
        
        if ctx.guild.get_member(member.id) is None:
            # The specified user exists, but could not be found as a member of the guild
            return await respondEmbed(ctx, message=f"Looks like {member.mention} is not in the server, {ctx.author.mention} :thinking: ...", error=True)
        
        # As stated above, only the server owner (or bot owner) has privileges to kick admins
        if member.guild_permissions.administrator and (ctx.author.id != ctx.guild.owner.id or not await self.bot.is_owner(ctx.author)):
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, I know you're trying to **kick an admin**, but I can't let you do that... :rolling_eyes:", error=True)
        
        if member and member.top_role >= ctx.guild.get_member(self.bot.user.id).top_role:
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, I can't **kick** {member.mention} because their **top role is higher than mine**.", error=True)

        # All checks passed, proceed to kick
        if reason is None:
            await member.kick() or await ctx.guild.kick(member)
            return await respondEmbed(ctx, message=f":white_check_mark: {member.mention} has been **kicked**.")

        else:
            await member.kick(reason=reason) or await ctx.guild.kick(member, reason=reason)
            return await respondEmbed(ctx, message=f":white_check_mark: {member.mention} has been **kicked**.\nReason: **{reason}**")


    # Error handling, for both commands and slash commands
    @kick.error
    async def kick_error(self, ctx: Context, error: Any):
        ctx._errorHandled = False    # if the error is handled, we would set this to True to prevent further propagation

        if isinstance(error, MissingRequiredArgument) and error.param.name == "member":
            # The command invoker doesn't provide the member argument
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"Looks like you want me to **kick someone**, but **haven't specified** the user you would like to kick :thinking:  ...\nJust curious to know, **who** should I kick for now, {ctx.author.mention}?", error=True)

        if isinstance(error, BadUnionArgument) or isinstance(error, UserNotFound):
            # The member argument couldn't be converted to either User or Member
            # This includes the case where a User is provided but does not exist
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"I couldn't find **the user you wanted to kick** :thinking: ... Perhaps check if that user really **exists** on Discord, {ctx.author.mention}?", error=True)
        
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
            return await respondEmbed(ctx, message=f"This command **requires** `kick_members` permission, and you probably **don't have** it, {ctx.author.mention}.", error=True)

        if (
            isinstance(error, BotMissingPermissions) or
            (isinstance(error, CommandInvokeError) and isinstance(error.original, Forbidden))    # Sometimes the application might throw a CommandInvokeError which caused by Forbidden, which is basically the same concept
        ):
            # The application doesn't have permissions to do so
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"I couldn't **kick** that member. Please **double-check** my **permissions** and **role position**.", error=True)


async def setup(bot: MyBot):
    await bot.add_cog(Kick(bot))

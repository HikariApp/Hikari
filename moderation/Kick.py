from discord import Color, Embed, Forbidden, Member, User
from discord.ext import commands
from discord.ext.commands import BadUnionArgument, Bot, Cog, Context, CommandInvokeError, MissingPermissions, MissingRequiredArgument, MemberNotFound, BotMissingPermissions, UserNotFound
from typing import Optional

class Kick(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = self.bot.getLogger()

    # Cog-level error listener for unhandled errors
    async def cog_on_command_error(self, ctx: Context, error: Exception):
        self.logger.exception(f"Uncaught error in {ctx.cog.__cog_name__}:", exc_info=error)
        raise error

    # Kicks a member
    # UPDATE 25-10-2025: This command has been heavily rewritten to support hybrid commands, see Note for more details.
    @commands.hybrid_command(name="kick", help="Kicks a member")
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.bot_has_guild_permissions(kick_members=True)
    async def kick(self, ctx: Context, member: Member | User, *, reason: Optional[str] = None) -> None:
        """
        Kicks a member.

        Parameters
        ----------
        member : `Union[discord.Member, discord.User]`
            The member to kick.
        
        reason : `Optional[str]`
            The reason for the kick.
        
        Returns
        ----------
        None
        
        Note
        ----------
        This command has been heavily rewritten to support hybrid commands.

        For the `member` argument, it now accepts both `discord.Member` and `discord.User` types.

        If a `discord.User` object is provided, the bot will check if they are a member of the guild before attempting to kick them.

        If the specified user is not a member of the guild, an appropriate message will be sent.

        """

        embed = Embed(title="")
        # Defer the interaction response if invoked as a slash command, in case of long processing time.
        if ctx.interaction:
            await ctx.interaction.response.defer()

        # Basic checks
        # Error handling will be done by the error handler below
        if (member.id == ctx.author.id):
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> {ctx.author.mention}, You can't **kick yourself**!")
            embed.color = Color.red()
            return await ctx.send(embed=embed)
        
        if (member.id == self.bot.user.id):
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> {ctx.author.mention}, I can't **kick myself**!")
            embed.color = Color.red()
            return await ctx.send(embed=embed)
        
        if ctx.guild.get_member(member.id) is None:
            # The specified user exists, but could not be found as a member of the guild
            embed.add_field(name="", value=f"Looks like {member.mention} is not in the server, {ctx.author.mention} :thinking: ...")
            embed.color = ctx.author.color
            return await ctx.send(embed=embed)

        # As stated above, only the server owner (or bot owner) has privileges to kick admins
        if member.guild_permissions.administrator and (ctx.author.id != ctx.guild.owner.id or not await self.bot.is_owner(ctx.author)):
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> {ctx.author.mention}, I know you're trying to **kick an admin**, but I can't let you do that... :rolling_eyes:")
            embed.color = Color.red()
            return await ctx.send(embed=embed)
        
        if member and member.top_role >= ctx.guild.get_member(self.bot.user.id).top_role:
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> {ctx.author.mention}, I can't **kick** {member.mention} because their **top role is higher than mine**.")
            embed.color = Color.red()
            return await ctx.send(embed=embed)

        # All checks passed, proceed to kick
        if reason is None:
            await member.kick() or await ctx.guild.kick(member)
            embed.add_field(name="", value=f":white_check_mark: {member.mention} has been **kicked**.")

        else:
            await member.kick(reason=reason) or await ctx.guild.kick(member, reason=reason)
            embed.add_field(name="", value=f":white_check_mark: {member.mention} has been **kicked**.\nReason: **{reason}**")

        embed.color = ctx.author.color
        await ctx.send(embed=embed)
        

    # Error handling, for both commands and slash commands
    @kick.error
    async def kick_error(self, ctx: Context, error):
        embed = Embed(title="")
        embed.color = Color.red()

        if isinstance(error, MissingRequiredArgument) and error.param.name == "member":
            # The command invoker doesn't provide the member argument
            # A special case to return a more user-friendly message
            embed.add_field(name="", value=f"Looks like you want me to **kick someone**, but **haven't specified** the user you would like to kick :thinking:  ...\nJust curious to know, **who** should I kick for now, {ctx.author.mention}?")
            embed.color = ctx.author.color
            return await ctx.send(embed=embed)

        if isinstance(error, BadUnionArgument) or isinstance(error, UserNotFound):
            # The member argument couldn't be converted to either User or Member
            # This includes the case where a User is provided but does not exist
            # A special case to return a more user-friendly message
            embed.add_field(name="", value=f"I couldn't find **the user you wanted to kick** :thinking: ... Perhaps check if that user really **exists** on Discord, {ctx.author.mention}?")
            embed.color = ctx.author.color
            return await ctx.send(embed=embed)
        
        if isinstance(error, MemberNotFound):
            # The specified member could not be found
            # This will unlikely be triggered since we are using Union[User, Member] for the member argument, but we add it here just in case
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> {error.argument} is not in the server, {ctx.author.mention} :thinking: ...")
            return await ctx.send(embed=embed)


        if isinstance(error, MissingRequiredArgument):
            # Missing argument(s)
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> Missing argument: `{error.param.name}`. Please provide all required arguments, {ctx.author.mention}.")
            return await ctx.send(embed=embed)

        if isinstance(error, MissingPermissions):
            # The command invoker doesn't have permissions
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> This command **requires** `kick_members` permission, and you probably **don't have** it, {ctx.author.mention}.")
            return await ctx.send(embed=embed)

        if (
            isinstance(error, BotMissingPermissions) or
            (isinstance(error, CommandInvokeError) and isinstance(error.original, Forbidden))    # Sometimes the application might throw a CommandInvokeError which caused by Forbidden, which is basically the same concept
        ):
            # The application doesn't have permissions to do so
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I couldn't **kick** that member. Please **double-check** my **permissions** and **role position**.")
            return await ctx.send(embed=embed)

        # If the error is not handled, forward to the cog-level listener, or even bot-level if unhandled here
        await self.cog_on_command_error(ctx, error)


async def setup(bot):
    await bot.add_cog(Kick(bot))


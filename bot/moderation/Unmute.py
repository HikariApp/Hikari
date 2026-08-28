from discord import Forbidden, Member
from discord.ext import commands
from discord.ext.commands import Cog, Context, CommandInvokeError, MissingPermissions, MissingRequiredArgument, BotMissingPermissions, UserNotFound
from typing import Any, Optional
from startup import MyBot
from helpers.respondEmbed import respondEmbed

class Unmute(Cog):
    def __init__(self, bot: MyBot):
        self.bot = bot
        self.logger = self.bot.getLogger()
        self.db = self.bot.getMongoClusterDB()


    # Cog-level error listener for unhandled errors
    async def cog_command_error(self, ctx: Context, error: Exception):
        if getattr(ctx, "_errorHandled", False):    # if ctx._errorHandled was set to True this could be ignored
            return

        self.logger.exception(f"Uncaught error in {ctx.cog.__cog_name__}:", exc_info=error)


    # Unmutes a member from text channels
    @commands.hybrid_command(name="unmute", help="Unmutes a user")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def unmute(self, ctx: Context, member: Member, reason: Optional[str] = None):
        """
        Unmutes a member from text.
        
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

        database = self.db.moderation_mute
        mute_text_collection = database["mute_text"]

        # Fetch mute record from the database
        mute_record = await mute_text_collection.find_one({"guild_id": ctx.guild.id, "user_id": member.id})

        if not mute_record:
            # If no mute record is found in the database, the user is not muted
            return await respondEmbed(ctx, message=f"{member.mention} is **not currently muted** in the database.", error=True)

        # Retrieve the Muted role from the database record
        muted_role = ctx.guild.get_role(mute_record["role_id"])
        if not muted_role:
            return await respondEmbed(ctx, message=f"The **Muted** role no longer exists in this server. Please recreate it.", error=True)

        # Check if the user actually has the Muted role
        if muted_role not in member.roles:
            return await respondEmbed(ctx, message=f"{member.mention} does not have the `Muted` role, but they are recorded as muted in the database.", error=True)

        # Remove the Muted role
        try:
            if reason is None:
                await member.remove_roles(muted_role)
                await respondEmbed(ctx, message=f"{member.mention} has been **unmuted**.")
                
            else:
                await member.remove_roles(muted_role, reason=reason)
                await respondEmbed(ctx, message=f"{member.mention} has been **unmuted**.\nReason: **{reason}**.")

        except Forbidden:
            return await respondEmbed(ctx, message=f"<a:crossred:1356353067024515266> I couldn't **unmute** {member.mention}. Please check my **permissions** and **role position**.", error=True)

        # Remove the mute record from the database
        await mute_text_collection.delete_one({"_id": mute_record["_id"]})


    # Handle errors while unbanning a user, for both commands and app_commands
    @unmute.error
    async def unmute_error(self, ctx: Context, error: Any):
        ctx._errorHandled = False    # if the error is handled, we would set this to True to prevent further propagation

        if isinstance(error, MissingRequiredArgument) and error.param.name == "user":
            # The command invoker doesn't provide the user argument
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"Looks like you want me to **unmute someone**, but **haven't specified** the user you would like to unmute :thinking:  ...\nJust curious to know, **who** should I unmute for now, {ctx.author.mention}?", error=True)
        
        if isinstance(error, UserNotFound):
            # The user argument couldn't be converted to User
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"I couldn't find **the user you wanted to unmute** :thinking: ... Perhaps check if that user really **exists** on Discord, {ctx.author.mention}?", error=True)
        
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
            return await respondEmbed(ctx, message=f"I couldn't **unmute** that user. Please **double-check** my **permissions** and **role position**.", error=True)


async def setup(bot: MyBot):
    await bot.add_cog(Unmute(bot))

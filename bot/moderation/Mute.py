import discord
from datetime import datetime, timezone, timedelta
from discord import Forbidden, HTTPException, Member, Permissions
from discord.ext import commands, tasks
from discord.ext.commands import BadUnionArgument, Cog, Context, CommandInvokeError, MissingPermissions, MissingRequiredArgument, MemberNotFound, BotMissingPermissions, UserNotFound
from typing import Any, Optional
from startup import MyBot
from helpers.respondEmbed import respondEmbed
from helpers.parseDuration import parseDuration


class Mute(Cog):
    def __init__(self, bot: MyBot):
        self.bot = bot
        self.logger = self.bot.getLogger()
        self.db = self.bot.getMongoClusterDB()
        self.unmute_text_task.start()


    # Cog-level error listener for unhandled errors
    async def cog_command_error(self, ctx: Context, error: Exception):
        if getattr(ctx, "_errorHandled", False):    # if ctx._errorHandled was set to True this could be ignored
            return

        self.logger.exception(f"Uncaught error in {ctx.cog.__cog_name__}:", exc_info=error)


    def cog_unload(self):
        self.unmute_text_task.cancel()  # Stop the task when the cog is unloaded


    # Function of mutes a member from text channel
    async def applyMute(self, ctx: Context, member: Member, durationStr: str | None, *, reason: str | None):
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Applies a mute to a member from text channels for a specified duration with an optional reason.

        This handles the logic for applying a mute to a member, including parsing the duration string and adding records to the database.
        It also sends appropriate responses to the context based on the outcome of the operation.

        Parameters
        ----------
        ctx : discord.ext.commands.Context
            The context in which the command was invoked.
        member : discord.Member
            The member to mute.
        durationStr : str, optional
            The duration for the mute in a string format (e.g., "1h", "30m", "2d"). If None, the mute will be indefinite.
        reason : str, optional
            The reason for the mute. If None, no reason will be provided.

        Returns
        -------
        None
        """

        database = self.db.moderation_mute
        mute_text_collection = database["mute_text"]
        
        muted = discord.utils.get(ctx.guild.roles, name="Muted")
        
        if durationStr is not None:  # For time-based mute only
            totalDuration = parseDuration(durationStr)
            if totalDuration is None:
                return await respondEmbed(ctx, message=f"Looks like the time format you entered is not valid :thinking: ... Perhaps enter again and give me a chance to handle it, {ctx.author.mention} :pleading_face:?\n\n**Supported time format:**\n**1**s = **1** second | **2**m = **2** minutes | **5**h = **5** hours | **10**d = **10** days | **3**w = **3** weeks | **6**y = **6** years.", error=True)
        
        if muted is None:
            muted = await ctx.guild.create_role("Muted", permissions=Permissions(send_messages=False))
        
        if muted in member.roles:
            return await respondEmbed(ctx, message=f"{member.mention} is already muted!", error=True)
        
        durationMessage = "for " + " and ".join(", ".join([f"**{value}** {unit[:-1]}" + ("s" if value > 1 else "") for unit, value in totalDuration.items() if unit != "total_seconds" and value != 0]).rsplit(", ", 1)) + " " if durationStr is not None else ""
        reasonMessage =  f"\nReason: **{reason}**" if reason is not None else ""

        reasonKarg = {"reason": reason} if reason is not None else {}
        await member.add_roles(muted, **reasonKarg)

        await respondEmbed(ctx, message=f":white_check_mark: {member.mention} has been **muted** {durationMessage}:zipper_mouth:{reasonMessage}")
        
        # Save mute info to the database
        if durationStr is not None:
            muteExpirationTime = datetime.now(timezone.utc) + timedelta(seconds=totalDuration["total_seconds"])    # For time-based mute only

        else:
            muteExpirationTime = None

        await mute_text_collection.insert_one({
            "guild_id": ctx.guild.id,
            "user_id": member.id,
            "role_id": muted.id,
            "time_based": True if durationStr is not None else False,
            "mute_end_time": muteExpirationTime,
            "reason": reason
        })


    # Background task to handle only time-based unmutes
    @tasks.loop(seconds=2)  # Check for unmutes every 2 seconds for minimum delay
    async def unmute_text_task(self):
        now = datetime.now(timezone.utc)
        database = self.db.moderation_mute
        mute_text_collection = database["mute_text"]

        # Query for expired time-based mutes (exclude records with mute_end_time = None)
        expired_mutes = mute_text_collection.find({
            "time_based": True,  # Only time-based mutes
            "mute_end_time": {"$ne": None, "$lte": now}  # Exclude None and check for expired times
        })

        async for mute in expired_mutes:
            guild = self.bot.get_guild(mute["guild_id"])
            if not guild:
                # If the guild is not found, skip this record
                continue

            member = guild.get_member(mute["user_id"])
            if not member:
                # If the member is not in the guild, skip this record
                continue

            role = guild.get_role(mute["role_id"])
            if not role:
                # If the role is not found, skip this record
                continue

            # Remove the Muted role from the member
            try:
                await member.remove_roles(role, reason="Mute duration expired")
            
            except Forbidden:
                # If the bot lacks the permissions to remove the role, skip this member
                continue

            except HTTPException as e:
                # Handle any unexpected errors with a log or skip this member
                self.logger.error(f"Failed to unmute {member} from voice in guild {guild.id}: {e}")
                continue

            # Remove the mute record from the database
            await mute_text_collection.delete_one({"_id": mute["_id"]})


    # Mutes a member from text for a specified amount of time
    @commands.hybrid_command(name="mute", help="Mutes a member from text channels")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def mute(self, ctx: Context, member: Member, duration: Optional[str] = None, *, reason: Optional[str] = None):
        """
        Mutes a member from text channels.

        Parameters
        ----------
        member : Union[discord.Member, discord.User]
            The member to mute.
        duration : Optional[str]
            Duration for mute (e.g. 1s = 1 second | 2m = 2 minutes | 5h = 5 hours | 10d = 10 days | 3w = 3 weeks | 6y = 6 years)
        reason : Optional[str]
            Reason for mute.

        Notes
        -----
        This command has been heavily rewritten to support hybrid commands.

        As same as before, only the server owner (or bot owner) has privileges to mute admins.
        """

        # Defer the interaction response if invoked as a slash command, in case of long processing time.
        if ctx.interaction:
            await ctx.interaction.response.defer()

        # Basic checks
        # Error handling will be done by the error handler below
        if (member.id == ctx.author.id):
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, You can't **mute yourself**!", error=True)
        
        if (member.id == self.bot.user.id):
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, I can't **mute myself**!", error=True)
        
        if ctx.guild.get_member(member.id) is None:
            # The specified user exists, but could not be found as a member of the guild
            return await respondEmbed(ctx, message=f"Looks like {member.mention} is not in the server, {ctx.author.mention} :thinking: ...", error=True)
        
        # As stated above, only the server owner (or bot owner) has privileges to mute admins
        if member.guild_permissions.administrator and (ctx.author.id != ctx.guild.owner.id or not await self.bot.is_owner(ctx.author)):
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, I know you're trying to **mute an admin**, but I can't let you do that... :rolling_eyes:", error=True)
        
        if member and member.top_role >= ctx.guild.get_member(self.bot.user.id).top_role:
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, I can't **mute** {member.mention} because their **top role is higher than mine**.", error=True)
        
        await self.applyMute(ctx=ctx, member=member, durationStr=duration, reason=reason)


    # Error handling, for both commands and slash commands
    @mute.error
    async def mute_error(self, ctx: Context, error: Any):
        ctx._errorHandled = False    # if the error is handled, we would set this to True to prevent further propagation

        if isinstance(error, MissingRequiredArgument) and error.param.name == "member":
            # The command invoker doesn't provide the member argument
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"Looks like you want me to **mute someone**, but **haven't specified** the user you would like to mute :thinking:  ...\nJust curious to know, **who** should I mute for now, {ctx.author.mention}?", error=True)

        if isinstance(error, BadUnionArgument) or isinstance(error, UserNotFound):
            # The member argument couldn't be converted to either User or Member
            # This includes the case where a User is provided but does not exist
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"I couldn't find **the user you wanted to mute** :thinking: ... Perhaps check if that user really **exists** on Discord, {ctx.author.mention}?", error=True)
        
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
            return await respondEmbed(ctx, message=f"I couldn't **mute** that member. Please **double-check** my **permissions** and **role position**.", error=True)


async def setup(bot: MyBot):
    await bot.add_cog(Mute(bot))

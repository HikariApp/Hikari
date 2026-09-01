import asyncio
from aiohttp.client_exceptions import ServerDisconnectedError
from discord import Color, Embed, Forbidden, Member, User, VoiceChannel, VoiceState, HTTPException
from discord.ext import commands, tasks
from discord.ext.commands import ChannelNotFound, Cog, Context, MissingRequiredArgument, CommandInvokeError, CommandInvokeError, MissingPermissions, BotMissingPermissions, BadUnionArgument, MemberNotFound, UserNotFound
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from startup import MyBot
from helpers.errorHandling import *
from helpers.respondEmbed import respondEmbed
from helpers.parseDuration import parseDuration


class VoiceChannel(Cog):
    def __init__(self, bot: MyBot):
        self.bot = bot
        self.logger = self.bot.getLogger()
        self.db = self.bot.getMongoClusterDB()
        self.unmute_voice_task.start()


    # Cog-level error listener for unhandled errors
    async def cog_command_error(self, ctx: Context, error: Exception):
        if getattr(ctx, "_errorHandled", False):    # if ctx._errorHandled was set to True this could be ignored
            return

        self.logger.exception(f"Uncaught error in {ctx.cog.__cog_name__}:", exc_info=error)


    def cog_unload(self):
        self.unmute_voice_task.cancel()  # Stop the task when the cog is unloaded


    @commands.Cog.listener()
    async def on_voice_state_update(self, member: Member, before: VoiceState, after: VoiceState):
        # Ensure:
        # - this is a channel leave as opposed to anything else
        # Actions:
        # - Send a message to the system channel or a text channel with send permissions, if available

        try:
            if member.id != self.bot.user.id:
                return

            if (
                after.channel is None and  # if this is None this is certainly a leave
                before.channel != after.channel  # if these match then this could be e.g. server deafen
            ):
                guild = before.channel.guild
                channel = guild.system_channel or next(
                    (c for c in guild.text_channels if c.permissions_for(guild.me).send_messages),
                    None
                )

                if channel is None:    # No suitable text channel found to send the message
                    return

                left_embed = Embed(
                    description="I've left the voice channel.",
                    color=Color.blurple()
                )
                await channel.send(embed=left_embed, silent=True)

        except ServerDisconnectedError:
            self.logger.warning("ServerDisconnectedError occurred in on_voice_state_update. This is likely due to the bot being disconnected from the gateway or shutting down.")

    # NOTE: join() command is now handled by the music player cog, so we removed it from here


    # Leaving a voice channel
    @commands.hybrid_command(name="leave", help="Leaving a voice channel")
    @commands.guild_only()
    async def leave(self, ctx: Context):
        """
        Leaving a voice channel.
        """

        player = ctx.voice_client  # works for lava_lyra.Player AND voice_recv client
        if player is not None:
            await player.disconnect()
            # keep this minimal if the listener will announce "I left"
            await respondEmbed(ctx, message=f"Leaving the voice channel...", error=False, deleteAfter=5)

        else:
            await respondEmbed(ctx, message=f"{ctx.author.mention}, I'm not in a voice channel... :thinking:", error=False)


    # Moving all users or ends a voice call
    # Function to move all members (i.e. move them to any voice channel in the server, or use None to kick them away from the vc)
    async def moveAll(self, guild, specifiedVC: VoiceChannel | None, *, reason: str | None):
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Moves all members in the guild's voice channels to a specified voice channel or disconnects them if `specified_vc` is None.
        
        Parameters
        ----------
        guild : Guild
            The guild object where the members are located.

        specifiedVC : discord.VoiceChannel, optional
            The target voice channel to move members to. If None, members will be disconnected from voice channels.

        reason : str, optional
            The reason for moving members, which will be logged in the audit log.

        Returns
        -------
        tuple
            A tuple containing:
            - total_members: Total number of members in voice channels.
            - success_count: Number of members successfully moved.
            - failure_count: Number of members that failed to move.

        Notes
        -----
        This function has been rewritten, it now takes `guild` instead of `interaction`,
        and returns a tuple with the results with reason omitted.
        """

        allMembersInVC = [member for channel in guild.voice_channels for member in channel.members]
        results = await asyncio.gather(
            *(member.move_to(specifiedVC, reason=reason) for member in allMembersInVC),
            return_exceptions=True
        )
        successCount = sum(1 for result in results if not isinstance(result, Exception))
        failureCount = sum(1 for result in results if isinstance(result, Exception))

        # Return a tuple containing the total number of members, the count of successful moves and failures.
        return len(allMembersInVC), successCount, failureCount


    # Ending the call for all voice channels
    @commands.hybrid_command(name="end", description="End the call for all voice channel(s)")
    @commands.guild_only()
    @commands.has_guild_permissions(move_members=True)
    async def end(self, ctx: Context, *, reason: Optional[str] = None):
        """
        End the call for all voice channel(s)

        Parameters
        ----------
        reason : str, optional
            Reason for ending the call.
        """

        # Defer the interaction response if invoked as a slash command, in case of long processing time.
        if ctx.interaction:
            await ctx.interaction.response.defer()

        allMembersInVC, successCount, failureCount = await self.moveAll(guild=ctx.guild, specifiedVC=None, reason=reason)

        if (successCount != allMembersInVC) and failureCount > 0:
            return await respondEmbed(ctx, message=f"Something went wrong while ending the call for all channel(s) :thinking:", error=True)

        return await respondEmbed(
            ctx,
            message=(
                f"Ended the call for all voice channel(s)."
                f"\n**{successCount}** {'users' if successCount > 1 else 'user'} has been disconnected from voice channels."
                + (f"\n**Reason**: {reason}" if reason else "")
                ),
            isSilent=True
        )


    # Error handling, for both commands and slash commands
    @end.error
    async def end_error(self, ctx: Context, error):
        ctx._errorHandled = False    # if the error is handled, we would set this to True to prevent further propagation

        if isinstance(error, MissingPermissions):
            # The command invoker doesn't have permissions
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"This command **requires** `move_members` permission, and you probably **don't have** it, {ctx.author.mention}.", error=True)

        if (
            isinstance(error, BotMissingPermissions) or
            (isinstance(error, CommandInvokeError) and isinstance(error.original, Forbidden))    # Sometimes the application might throw a CommandInvokeError which caused by Forbidden, which is basically the same concept
        ):
            # The application doesn't have permissions to do so
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"I couldn't end the call. Please **double-check** my **permissions** and **role position**.", error=True)


    # Hybrid command group for moving members between voice channels
    @commands.hybrid_group(name="move", description="Move members between voice channels")
    @commands.guild_only()
    async def move(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)


    # Move all users to a specified voice channel
    @move.command(name="all", description="Moves all users to the specified voice channel")
    @commands.guild_only()
    @commands.has_guild_permissions(move_members=True)
    async def move_all(self, ctx: Context, channel: Optional[VoiceChannel] = None, *, reason: Optional[str] = None):
        """
        Moves all users to the specified voice channel.

        Parameters
        ----------
        channel : discord.VoiceChannel, optional
            Channel to move them to. Leave this blank if you want to move them into where you are.
        reason : str, optional
            Reason for move.
        """

        # Defer the interaction response if invoked as a slash command, in case of long processing time.
        if ctx.interaction:
            await ctx.interaction.response.defer()

        # Resolve destination — invoker only needs to be in voice if they DIDN'T name a channel
        if channel is None:
            if ctx.author.voice is not None:
                specified_vc = ctx.author.voice.channel
            else:
                return await respondEmbed(
                    ctx, 
                    message=(
                        f"Looks like you're currently not in a voice channel, but trying to move someone into the voice channel that you were connected :thinking: ..."
                        f"\nJust curious to know, where should I move them all into right now, {ctx.author.mention}?"
                        )
                )

        else:
            specified_vc = channel

        allMembersInVC, successCount, failureCount = await self.moveAll(guild=ctx.guild, specifiedVC=specified_vc, reason=reason)

        if allMembersInVC == 0:
            return await respondEmbed(ctx, message=f"It seems that no user were found in the voice channel, {ctx.author.mention} :thinking:...")

        if (failureCount > 0) and (successCount != allMembersInVC):
            return await respondEmbed(ctx, message=f"Something went wrong while moving all users to {specified_vc.mention} :thinking:", error=True)

        await respondEmbed(
            ctx,
            message=(
                f"\n**{successCount}** {'users' if successCount > 1 else 'user'} has been moved to {specified_vc.mention}."
                + (f"\n**Reason**: {reason}" if reason else "")
                ),
            isSilent=True
        )


    # Error handling, for both commands and slash commands
    @move_all.error
    async def move_all_error(self, ctx: Context, error):
        ctx._errorHandled = False    # if the error is handled, we would set this to True to prevent further propagation

        if isinstance(error, ChannelNotFound):
            # The specified channel could not be found
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"I couldn't find **the channel you wanted to move the member to** :thinking: ... Perhaps check if that channel really **exists** on Discord, {ctx.author.mention}?")

        if isinstance(error, MissingPermissions):
            # The command invoker doesn't have permissions
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"This command **requires** `move_members` permission, and you probably **don't have** it, {ctx.author.mention}.", error=True)

        if (
            isinstance(error, BotMissingPermissions) or
            (isinstance(error, CommandInvokeError) and isinstance(error.original, Forbidden))    # Sometimes the application might throw a CommandInvokeError which caused by Forbidden, which is basically the same concept
        ):
            # The application doesn't have permissions to do so
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"I couldn't move the members. Please **double-check** my **permissions** and **role position**.", error=True)


    # Moves a specific member to a specified voice channel
    @move.command(name="member", description="Moves a member to another specified voice channel")
    @commands.guild_only()
    @commands.has_guild_permissions(move_members=True)
    async def move_member(self, ctx: Context, member: Member | User, channel: Optional[VoiceChannel] = None, *, reason: Optional[str] = None):
        """
        Moves a member to another specified voice channel.

        Parameters
        ----------
        member : discord.Member | User
            Member to move.
        channel : discord.VoiceChannel, optional
            Channel to move member to. Leave this blank if you want to move the user into where you are.
        reason : str, optional
            Reason for move.
        """

        isBotTarget = member.id == self.bot.user.id

        # Target must actually be in voice
        if member.voice is None:
            if isBotTarget:
                # first-person UX when the target is the bot's own self
                return await respondEmbed(ctx, message=f"{ctx.author.mention}, I'm currently not in a voice channel... :thinking:", error=True)

            else:
                # second-person UX when the target is someone else
                return await respondEmbed(ctx, message=f"{ctx.author.mention}, Looks like {member.mention} is currently not in a voice channel... :thinking:", error=True)

        # Resolve destination — invoker only needs to be in voice if they DIDN'T name a channel
        if channel is None:
            if ctx.author.voice is not None:
                specified_vc = ctx.author.voice.channel
            else:
                return await respondEmbed(
                    ctx, 
                    message=(
                        f"Looks like you're currently not in a voice channel, but trying to move someone into the voice channel that you were connected :thinking: ..."
                        f"\nJust curious to know, where should I move {member.mention} into right now, {ctx.author.mention}?"
                        )
                )

        else:
            specified_vc = channel

        if ctx.guild.get_member(member.id) is None:
            # The specified user exists, but could not be found as a member of the guild
            return await respondEmbed(ctx, message=f"Looks like {member.mention} is not in the server, {ctx.author.mention} :thinking: ...", error=True)

        await member.move_to(specified_vc, reason=reason)

        if isBotTarget:
            # first-person UX when the target is the bot's own self
            return await respondEmbed(
                ctx,
                message=(
                    f"I have been moved to {specified_vc.mention}."
                    + (f"\n**Reason**: {reason}" if reason else "")
                ),
                isSilent=True
            )

        else:
            # second-person UX when the target is someone else
            return await respondEmbed(
                ctx,
                message=(
                    f"{member.mention} has been moved to {specified_vc.mention}."
                    + (f"\n**Reason**: {reason}" if reason else "")
                    ),
                isSilent=True
            )


    # Error handling, for both commands and slash commands
    @move_member.error
    async def move_member_error(self, ctx: Context, error):
        ctx._errorHandled = False    # if the error is handled, we would set this to True to prevent further propagation

        if isinstance(error, MissingRequiredArgument) and error.param.name == "member":
            # The command invoker doesn't provide the member argument
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"Looks like you want me to **move someone**, but **haven't specified** the member you would like to move :thinking:  ...\nJust curious to know, **who** should I move for now, {ctx.author.mention}?")

        if isinstance(error, BadUnionArgument) or isinstance(error, UserNotFound):
            # The member argument couldn't be converted to either User or Member
            # This includes the case where a User is provided but does not exist
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"I couldn't find **the user you wanted to move** :thinking: ... Perhaps check if that user really **exists** on Discord, {ctx.author.mention}?", error=True)

        if isinstance(error, ChannelNotFound):
            # The specified channel could not be found
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"I couldn't find **the channel you wanted to move the member to** :thinking: ... Perhaps check if that channel really **exists** on Discord, {ctx.author.mention}?")

        if isinstance(error, MissingPermissions):
            # The command invoker doesn't have permissions
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"This command **requires** `move_members` permission, and you probably **don't have** it, {ctx.author.mention}.", error=True)

        if (
            isinstance(error, BotMissingPermissions) or
            (isinstance(error, CommandInvokeError) and isinstance(error.original, Forbidden))    # Sometimes the application might throw a CommandInvokeError which caused by Forbidden, which is basically the same concept
        ):
            # The application doesn't have permissions to do so
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"I couldn't move that member. Please **double-check** my **permissions** and **role position**.", error=True)


    # Moves the command invoker to a specified voice channel
    @move.command(name="me", description="Moves you to another specified voice channel")
    @commands.guild_only()
    @commands.has_guild_permissions(move_members=True)
    async def move_me(self, ctx: Context, channel: VoiceChannel, reason: Optional[str] = None):
        """
        Moves you to another specified voice channel.

        Parameters
        ----------
        channel : VoiceChannel
            Channel to move you to.
        reason : str, optional
            Reason for move.
        """

        if ctx.author.voice is None:
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, You're currently not in a voice channel!", error=True)

        await ctx.author.move_to(channel, reason=reason)

        await respondEmbed(
            ctx,
            message=(
                f"{ctx.author.mention} has been moved to {channel.mention}."
                + (f"\n**Reason**: {reason}" if reason else "")
                ),
            isSilent=True
            )


    # Error handling, for both commands and slash commands
    @move_me.error
    async def move_me_error(self, ctx: Context, error):
        if isinstance(error, MissingRequiredArgument) and error.param.name == "channel":
            # The command invoker doesn't provide the channel argument
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"Looks like you want me to **move you to another channel**, but **haven't specified** the channel you would like to move to :thinking:  ...\nJust curious to know, **where** should I move you for now, {ctx.author.mention}?")

        if isinstance(error, ChannelNotFound):
            # The specified channel could not be found
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"I couldn't find **the channel you wanted to move you to** :thinking: ... Perhaps check if that channel really **exists** on Discord, {ctx.author.mention}?")

        if isinstance(error, MissingPermissions):
            # The command invoker doesn't have permissions
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"This command **requires** `move_members` permission, and you probably **don't have** it, {ctx.author.mention}.", error=True)

        if (
            isinstance(error, BotMissingPermissions) or
            (isinstance(error, CommandInvokeError) and isinstance(error.original, Forbidden))    # Sometimes the application might throw a CommandInvokeError which caused by Forbidden, which is basically the same concept
        ):
            # The application doesn't have permissions to do so
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"I couldn't move you. Please **double-check** my **permissions** and **role position**.", error=True)


    # Function of mutes a member from voice channel
    async def applyMuteVC(self, ctx: Context, member: Member, durationStr: str | None, *, reason: str | None):
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Applies a mute to a member from voice channels for a specified duration with an optional reason.

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
        mute_voice_collection = database["mute_voice"]
        
        if durationStr is not None:  # For time-based mute only
            totalDuration = parseDuration(durationStr)
            if totalDuration is None:
                return await respondEmbed(ctx, message=f"Looks like the time format you entered is not valid :thinking: ... Perhaps enter again and give me a chance to handle it, {ctx.author.mention} :pleading_face:?\n\n**Supported time format:**\n**1**s = **1** second | **2**m = **2** minutes | **5**h = **5** hours | **10**d = **10** days | **3**w = **3** weeks | **6**y = **6** years.", error=True)

        if member.voice.mute:
            return await respondEmbed(ctx, message=f"{member.mention} is already muted from voice!", error=True)

        durationMessage = "for " + " and ".join(", ".join([f"**{value}** {unit[:-1]}" + ("s" if value > 1 else "") for unit, value in totalDuration.items() if unit != "total_seconds" and value != 0]).rsplit(", ", 1)) + " " if durationStr is not None else ""
        reasonMessage =  f"\nReason: **{reason}**" if reason is not None else ""

        reasonKarg = {"reason": reason} if reason is not None else {}
        await member.edit(mute=True, **reasonKarg)

        await respondEmbed(ctx, message=f"{member.mention} has been **muted from voice** {durationMessage}:zipper_mouth:{reasonMessage}")
        
        # Save mute info to the database
        if durationStr is not None:
            muteExpirationTime = datetime.now(timezone.utc) + timedelta(seconds=totalDuration["total_seconds"])    # For time-based mute only

        else:
            muteExpirationTime = None

        await mute_voice_collection.insert_one({
            "guild_id": ctx.guild.id,
            "user_id": member.id,
            "time_based": True if durationStr is not None else False,
            "mute_end_time": muteExpirationTime,
            "reason": reason
        })


    # Background task to handle only time-based unmutes
    @tasks.loop(seconds=2)  # Check for unmutes every 2 seconds for minimum delay
    async def unmute_voice_task(self):
        now = datetime.now(timezone.utc)
        database = self.db.moderation_mute
        mute_voice_collection = database["mute_voice"]

        # Query for expired time-based mutes (exclude records with mute_end_time = None)
        expired_mutes = mute_voice_collection.find({
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

            # Check if the member is in a voice channel
            if not member.voice:
                # If the member is not connected to a voice channel, skip this record
                continue

            # Unmute the member from voice
            try:
                await member.edit(mute=False, reason="Voice mute duration expired")

            except Forbidden:
                # If the bot lacks the permissions to unmute, skip this member
                continue

            except HTTPException as e:
                # Handle any unexpected errors with a log or skip this member
                self.logger.error(f"Failed to unmute {member} from voice in guild {guild.id}: {e}")
                continue

            # Remove the mute record from the database
            await mute_voice_collection.delete_one({"_id": mute["_id"]})


    # Mutes a member from voice for a specified amount of time
    @commands.hybrid_command(name="vmute", help="Mutes a member from voice channels")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def vmute(self, ctx: Context, member: Member | User, duration: Optional[str] = None, *, reason: Optional[str] = None):
        """
        Mutes a member from voice channels.

        Parameters
        ----------
        member : discord.Member | discord.User
            The member to mute.
        duration : str, optional
            Duration for mute (e.g. 1s = 1 second | 2m = 2 minutes | 5h = 5 hours | 10d = 10 days | 3w = 3 weeks | 6y = 6 years)
        reason : str, optional
            Reason for mute.
        """

        # Defer the interaction response if invoked as a slash command, in case of long processing time.
        if ctx.interaction:
            await ctx.interaction.response.defer()

        # Basic checks
        # Error handling will be done by the error handler below
        if (member.id == ctx.author.id):
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, You can't **mute yourself from voice**!", error=True)
        
        if (member.id == self.bot.user.id):
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, I can't **mute myself from voice**!", error=True)
        
        if ctx.guild.get_member(member.id) is None:
            # The specified user exists, but could not be found as a member of the guild
            return await respondEmbed(ctx, message=f"Looks like {member.mention} is not in the server, {ctx.author.mention} :thinking: ...", error=True)
        
        # As stated above, only the server owner (or bot owner) has privileges to mute admins from voice
        if member.guild_permissions.administrator and (ctx.author.id != ctx.guild.owner.id or not await self.bot.is_owner(ctx.author)):
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, I know you're trying to **mute an admin from voice**, but I can't let you do that... :rolling_eyes:", error=True)
        
        if member and member.top_role >= ctx.guild.get_member(self.bot.user.id).top_role:
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, I can't **mute** {member.mention} from voice because their **top role is higher than mine**.", error=True)
        
        await self.applyMuteVC(ctx=ctx, member=member, durationStr=duration, reason=reason)


    # Error handling, for both commands and slash commands
    @vmute.error
    async def vmute_error(self, ctx: Context, error: Any):
        ctx._errorHandled = False    # if the error is handled, we would set this to True to prevent further propagation

        if isinstance(error, MissingRequiredArgument) and error.param.name == "member":
            # The command invoker doesn't provide the member argument
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"Looks like you want me to **mute someone from voice channels**, but **haven't specified** the user you would like to mute :thinking:  ...\nJust curious to know, **who** should I mute for now, {ctx.author.mention}?")

        if isinstance(error, BadUnionArgument) or isinstance(error, UserNotFound):
            # The member argument couldn't be converted to either User or Member
            # This includes the case where a User is provided but does not exist
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"I couldn't find **the user you wanted to mute from voice channels** :thinking: ... Perhaps check if that user really **exists** on Discord, {ctx.author.mention}?")
        
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
            return await respondEmbed(ctx, message=f"I couldn't **mute** that member from voice channels. Please **double-check** my **permissions** and **role position**.", error=True)


    # Unmutes a member from voice
    @commands.hybrid_command(name="vunmute", help="Unmutes a member from voice channels")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def vunmute(self, ctx: Context, member: Member | User, *, reason: Optional[str] = None):
        """
        Unmutes a member from voice channels.

        Parameters
        ----------
        member : discord.Member | discord.User
            Member to unmute (Enter the User ID e.g. 529872483195806124)
        reason : str, optional
            Reason for unmute.
        """

        database = self.db.moderation_mute
        mute_voice_collection = database["mute_voice"]

        # Fetch mute record from the database
        mute_record = await mute_voice_collection.find_one({"guild_id": ctx.guild.id, "user_id": member.id})

        if member.voice is None:
            return await respondEmbed(ctx, message=f"{member.mention} is **not connected to voice** currently.", error=True)

        if not mute_record:
            # If no mute record is found in the database, the user is not muted from voice
            return await respondEmbed(ctx, message=f"{member.mention} is **not currently muted from voice** in the database.", error=True)

        # Check if the user actually muted from voice
        if not member.voice.mute:
            return await respondEmbed(ctx, message=f"{member.mention} does **not muted from voice**, but they are recorded as muted in the database.", error=True)

        reasonKarg = {"reason": reason} if reason is not None else {}
        await member.edit(mute=False, **reasonKarg)

        # Remove the mute record from the database
        await mute_voice_collection.delete_one({"_id": mute_record["_id"]})

        return await respondEmbed(
            ctx,
            message=(
                f"{member.mention} has been **unmuted from voice**."
                + (f"\n**Reason**: {reason}" if reason else "")
                )
            )


    # Error handling, for both commands and slash commands
    @vunmute.error
    async def vunmute_error(self, ctx: Context, error: Any):
        ctx._errorHandled = False    # if the error is handled, we would set this to True to prevent further propagation

        if isinstance(error, MissingRequiredArgument) and error.param.name == "member":
            # The command invoker doesn't provide the user argument
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"Looks like you want me to **unmute someone from voice channels**, but **haven't specified** the user you would like to unmute :thinking:  ...\nJust curious to know, **who** should I unmute for now, {ctx.author.mention}?")
        
        if isinstance(error, BadUnionArgument) or isinstance(error, UserNotFound):
            # The member argument couldn't be converted to either User or Member
            # This includes the case where a User is provided but does not exist
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"I couldn't find **the user you wanted to unmute from voice channels** :thinking: ... Perhaps check if that user really **exists** on Discord, {ctx.author.mention}?")
        
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
            return await respondEmbed(ctx, message=f"I couldn't **unmute** that user from voice channels. Please **double-check** my **permissions** and **role position**.", error=True)


    # Kicks a member from voice
    @commands.hybrid_command(name="vkick", help="Kicks a member from voice channels")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def vkick(self, ctx: Context, member: Member | User, reason: Optional[str] = None):
        """
        Kicks a member from voice channels.
        
        Parameters
        ----------
        member : discord.Member | discord.User
            Member to kick.

        reason : str, optional
            Reason for the kick.
        """

        if member.voice is None:
            return await respondEmbed(ctx, message=f"{member.mention} is **not in voice** currently.", error=True)
        
        if member == ctx.author:
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, You can't **kick yourself from voice**!", error=True)

        if member == self.bot.user:
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, I can't **kick myself from voice**!", error=True)

        if ctx.guild.get_member(member.id) is None:
            # The specified user exists, but could not be found as a member of the guild
            return await respondEmbed(ctx, message=f"Looks like {member.mention} is not in the server, {ctx.author.mention} :thinking: ...", error=True)
        
        # As stated above, only the server owner (or bot owner) has privileges to kick admins
        if member.guild_permissions.administrator and (ctx.author.id != ctx.guild.owner.id or not await self.bot.is_owner(ctx.author)):
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, I know you're trying to **kick an admin from voice**, but I can't let you do that... :rolling_eyes:", error=True)
        
        if member and member.top_role >= ctx.guild.get_member(self.bot.user.id).top_role:
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, I can't **kick** {member.mention} from voice because their **top role is higher than mine**.", error=True)

        reasonKarg = {"reason": reason} if reason is not None else {}
        await member.move_to(None, **reasonKarg)

        return await respondEmbed(
            ctx,
            message=(
                f"{member.mention} has been **kicked from voice**."
                + (f"\n**Reason**: {reason}" if reason else "")
                )
            )


    # Error handling, for both commands and slash commands
    @vkick.error
    async def vkick_error(self, ctx: Context, error: Any):
        ctx._errorHandled = False    # if the error is handled, we would set this to True to prevent further propagation

        if isinstance(error, MissingRequiredArgument) and error.param.name == "member":
            # The command invoker doesn't provide the member argument
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"Looks like you want me to **kick someone from voice**, but **haven't specified** the user you would like to kick :thinking:  ...\nJust curious to know, **who** should I kick from voice for now, {ctx.author.mention}?")

        if isinstance(error, BadUnionArgument) or isinstance(error, UserNotFound):
            # The member argument couldn't be converted to either User or Member
            # This includes the case where a User is provided but does not exist
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"I couldn't find **the user you wanted to kick from voice** :thinking: ... Perhaps check if that user really **exists** on Discord, {ctx.author.mention}?")
        
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
            return await respondEmbed(ctx, message=f"I couldn't **kick** that member from voice. Please **double-check** my **permissions** and **role position**.", error=True)


async def setup(bot: MyBot):
    await bot.add_cog(VoiceChannel(bot))

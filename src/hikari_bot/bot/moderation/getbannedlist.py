from discord import Color, Embed, Forbidden
from discord.ext import commands
from discord.ext.commands import Cog, Context, CommandInvokeError, MissingPermissions, BotMissingPermissions
from typing import Any
from datetime import datetime
from hikari_bot.startup import MyBot
from hikari_bot.helpers.respondembed import respond_embed


class GetBannedList(Cog):
    def __init__(self, bot: MyBot):
        self.bot = bot
        self.logger = self.bot.get_logger()


    # Cog-level error listener for unhandled errors
    async def cog_command_error(self, ctx: Context, error: Exception):
        if getattr(ctx, "_error_handled", False):    # if ctx._error_handled was set to True this could be ignored
            return

        self.logger.exception(f"Uncaught error in {ctx.cog.__cog_name__}:", exc_info=error)


    # Returns a list of banned members in the guild
    @commands.hybrid_command(name="banned", help="Returns a list of banned members in the guild.")
    @commands.has_permissions(ban_members=True)
    async def banned(self, ctx: Context):
        """
        Returns a list of banned members in the guild.

        Notes
        -----
        This command has been heavily rewritten to support hybrid commands.
        """

        # Defer the interaction response if invoked as a slash command, in case of long processing time.
        if ctx.interaction:
            await ctx.interaction.response.defer()

        banned_embed = Embed(title=f"List of Bans in {ctx.guild}", timestamp=datetime.now(), color=Color.red())

        async for entry in ctx.guild.bans():
            if entry.user.discriminator == "0":
                # This user has no discriminator on its username
                banned_embed.add_field(name=f"Ban", value=f"Username: {entry.user.name}\nReason: {entry.reason}\nUser ID: {entry.user.id}\nIs Bot: {entry.user.bot}\nAccount created on: {discord.utils.format_dt(entry.user.created_at, style='R')}", inline=False)

            else:
                # This user has a custom discriminator on its username
                banned_embed.add_field(name=f"Ban", value=f"Username: {entry.user.name}#{entry.user.discriminator}\nReason: {entry.reason}\nUser ID: {entry.user.id}\nIs Bot: {entry.user.bot}\nAccount created on: {discord.utils.format_dt(entry.user.created_at, style='R')}", inline=False)

        if not banned_embed.fields:
            return await respond_embed(ctx, message="There are no banned members in this server so far. :slight_smile:")

        await ctx.send(embed=banned_embed)


    # Error handling, for both commands and slash commands
    @banned.error
    async def banned_error(self, ctx: Context, error: Any):
        ctx._error_handled = False    # if the error is handled, we would set this to True to prevent further propagation

        if isinstance(error, MissingPermissions):
            # The command invoker doesn't have permissions
            ctx._error_handled = True
            return await respond_embed(ctx, message=f"<a:crossred:1356353067024515266> This command **requires** `ban_members` permission, and you probably **don't have** it, {ctx.author.mention}.", error=True)

        if (
            isinstance(error, BotMissingPermissions) or
            (isinstance(error, CommandInvokeError) and isinstance(error.original, Forbidden))    # Sometimes the application might throw a CommandInvokeError which caused by Forbidden, which is basically the same concept
        ):
            # The application doesn't have permissions to do so
            ctx._error_handled = True
            return await respond_embed(ctx, message=f"<a:crossred:1356353067024515266> I couldn't **list all banned users**. Please **double-check** my **permissions** and **role position**.", error=True)


async def setup(bot: MyBot):
    await bot.add_cog(GetBannedList(bot))

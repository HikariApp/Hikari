import discord
from discord import AllowedMentions, File, Forbidden, Interaction, Message, TextStyle
from discord.ext import commands
from discord.ext.commands import  Cog, CommandInvokeError, Context, BotMissingPermissions, MissingPermissions, MissingRequiredArgument
from discord.ext.commands.errors import BadBoolArgument
from discord.ui import Modal, TextInput
from typing import Optional, Union
from startup import MyBot
from helpers.respondEmbed import respondEmbed, ResponseTarget


async def _emptyMessageError(source: Union[Context, Interaction]) -> Optional[Message]:
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).
    
    Returns an embed for when the user tries to send nothing.
    
    Parameters
    ----------
    source : Union[Context, Interaction]
        The source of the command or interaction, used to determine how to respond.

    Returns
    -------
    discord.Message, optional
        The message sent in response, or None if the response could not be sent.
    """

    return await respondEmbed(
        source,
        message="You can't send nothing — provide a message, an attachment, or both.",
        error=True
    )


def _allowedMentions(is_owner: bool) -> AllowedMentions:
    """
    Returns the allowed mentions for a given user.

    Owners may ping @everyone/@here; everyone else cannot.
    """

    return AllowedMentions.all() if is_owner else AllowedMentions(everyone=False)


class SendAsBotModal(Modal):
    """A Discord Modal to let you send your message as the bot's identity."""

    content = TextInput(
        label="Content (leave empty to send attachment only)",
        style=TextStyle.paragraph,
        placeholder="@everyone / @here pings are blocked unless you are the bot owner.",
        required=False,
        max_length=4000,
    )

    def __init__(self, bot: MyBot, silent: bool = False, file: Optional[File] = None):
        self.bot = bot
        self.silent = silent
        self.file = file
        super().__init__(title="Send your message as the bot's identity")


    async def on_error(self, interaction: Interaction, error: Exception) -> None:
        if isinstance(error, Forbidden):
            return await respondEmbed(
                interaction,
                message="I couldn't send that. Please double-check my permissions and role position.",
                target=ResponseTarget.EPHEMERAL,
                error=True
            )
        raise error


    async def on_submit(self, interaction: Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        content = self.content.value or None

        if content is None and self.file is None:
            return await _emptyMessageError(interaction)

        is_owner = await self.bot.is_owner(interaction.user)
        await interaction.channel.send(
            content=content,
            file=self.file,
            silent=self.silent,
            allowed_mentions=_allowedMentions(is_owner),
        )

        await respondEmbed(
            interaction,
            message=f"Sent to {interaction.channel.mention}.",
            target=ResponseTarget.EPHEMERAL
        )


class SendAsBot(Cog):
    def __init__(self, bot: MyBot):
        self.bot = bot
        self.logger = self.bot.getLogger()


    # Cog-level error listener for unhandled errors
    async def cog_command_error(self, ctx: Context, error: Exception):
        if getattr(ctx, "_errorHandled", False):    # if ctx._errorHandled was set to True this could be ignored
            return

        self.logger.exception(f"Uncaught error in {ctx.cog.__cog_name__}:", exc_info=error)


    # Send a message as the bot's identity
    @commands.hybrid_command()
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(send_messages=True)
    async def send(
        self,
        ctx: Context,
        silent: bool = False,
        attachment: Optional[discord.Attachment] = None,
        *,
        content: Optional[str] = None,
    ) -> None:
        """
        Send a message and/or attachment through me.

        Parameters
        ----------
        silent : bool
            Send it as a silent message?
        attachment : Optional[discord.Attachment]
            The attachment to send. Leave empty to send text only.
        content : Optional[str]
            The message text. On slash, leaving this empty opens a modal.
        """

        await ctx.defer()
        file = await attachment.to_file() if attachment else None

        # Slash invocation with no inline content -> pop the rich modal.
        if ctx.interaction is not None and content is None:
            return await ctx.interaction.response.send_modal(
                SendAsBotModal(bot=self.bot, silent=silent, file=file)
            )

        # Prefix, or slash-with-content: send directly.
        if content is None and file is None:
            return await _emptyMessageError(ctx)

        is_owner = await self.bot.is_owner(ctx.author)
        await ctx.channel.send(
            content=content,
            file=file,
            silent=silent,
            allowed_mentions=_allowedMentions(is_owner),
        )

        deleteAfterForContext = 5.0

        await respondEmbed(
            ctx,
            message=f"Sent to {ctx.channel.mention}.",
            target=ResponseTarget.REPLY,
            deleteAfter=deleteAfterForContext,
        )

        if ctx.interaction is None:
            await ctx.message.delete(delay=deleteAfterForContext)


    # Error handling, for both commands and slash commands
    @send.error
    async def send_error(self, ctx: Context, error: Exception) -> None:
        ctx._errorHandled = False    # if the error is handled, we would set this to True to prevent further propagation

        if isinstance(error, MissingPermissions):
            # The command invoker doesn't have permissions
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"This command **requires** `send_messages` permission, and you probably **don't have** it, {ctx.author.mention}.", error=True)

        if isinstance(error, BadBoolArgument):
            # The command invoker provided an invalid boolean value
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"Invalid boolean value: `{error.argument}`", error=True, target=ResponseTarget.REPLY)

        if isinstance(error, MissingRequiredArgument) and error.param.name == "content":
            # The command invoker doesn't provide the user argument
            # A special case to return a more user-friendly message
            ctx._errorHandled = True
            return await _emptyMessageError(ctx)

        if isinstance(error, MissingRequiredArgument):
            # Missing argument(s)
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"Missing argument: `{error.param.name}`. Please provide all required arguments, {ctx.author.mention}.", error=True)

        if (
            isinstance(error, BotMissingPermissions) or
            (isinstance(error, CommandInvokeError) and isinstance(error.original, Forbidden))    # Sometimes the application might throw a CommandInvokeError which caused by Forbidden, which is basically the same concept
        ):
            # The application doesn't have permissions to do so
            ctx._errorHandled = True
            return await respondEmbed(ctx, message=f"I couldn't **send the message**. Please **double-check** my **permissions** and **role position**.", error=True)


async def setup(bot: MyBot):
    await bot.add_cog(SendAsBot(bot))


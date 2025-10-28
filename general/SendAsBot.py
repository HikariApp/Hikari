import discord
from discord import app_commands, Color, Embed, File, Forbidden, Interaction, TextStyle, VoiceChannel
from discord.ext.commands import Bot, Cog
from discord.ui import Modal, TextInput
from discord.app_commands.errors import MissingPermissions, BotMissingPermissions, CommandInvokeError
from typing import Optional


class SendAsBotModal(Modal):
    """
    A Discord Modal to let you send your message as bot's identity
    """

    content = TextInput(
        label="Content (Leave empty to send attachment only)",
        style=TextStyle.paragraph,
        placeholder="Any mass mentions like @everyone or @here will be sanitized unless you are the bot owner.",
        required=True,
        max_length=4000
    )


    def __init__(self, bot: Bot, silent: bool = False, file: Optional[File] = None):
        self.bot = bot
        self.silent = silent
        self.file = file
        super().__init__(title="Send your message as bot's identity")


    # Cog-level error listener for unhandled errors
    async def cog_on_command_error(self, interaction: Interaction, error: Exception):
        embed = discord.Embed(title="")

        if isinstance(error, CommandInvokeError) and isinstance(error.original, Forbidden):
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I couldn't **send the content you provided**. Please **double-check** my **permissions** and **role position**.")
            embed.color = Color.red()
            return await interaction.followup.send(embed=embed)
        
        self.logger.exception(f"Uncaught error in {interaction.cog.__cog_name__}:", exc_info=error)
        raise error


    async def on_submit(self, interaction: Interaction):
        """
        Handle modal submission.
        """
        errorEmbed = Embed(title="", color=Color.red())
        await interaction.response.defer()
        content = self.content.value or None
        #
        # New safety guard to prevent unwanted mass mentions (spamming @everyone or @here) disasters in history.
        # You can find it on (https://www.threads.com/@yukicon_/post/DQRQV0AEuQZ?xmt=AQF0BZjthgicIXxYGxVFI-rMDoMqo2fIOXRpvfqJrgNE4g) for more details.
        #
        # @everyone and @here mentions are now only available to bot owners
        # For general users, this will replace both mentions with a zero-width space in between to prevent actual mentions
        #
        content = content if await self.bot.is_owner(interaction.user) else content.replace("@everyone", "@\u200beveryone").replace("@here", "@\u200bhere")

        # Safety guard ends here, proceed to send the message
        if content is None and self.file is None:
            # Returns if both message and attachments are not provided
            errorEmbed.add_field(name="", value="<a:crossred:1356353067024515266> You cannot let me to send nothing... (say at least send a message or an attachment)", inline=False)
            return await interaction.followup.send(embed=errorEmbed)
    
        return await interaction.channel.send(content=content, file=self.file, silent=self.silent) if not isinstance(interaction.channel, VoiceChannel) else None


class SendAsBot(Cog):
    def __init__(self, bot: Bot):
        global bool_value
        self.bot = bot


    # Send message from user input
    @app_commands.command()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.checks.bot_has_permissions(send_messages=True)
    async def send(self, interaction: Interaction, silent: bool, attachment: Optional[discord.Attachment] = None):
        """
        Send your message or attatchment, or both through me

        Parameters
        ----------
        interaction : `discord.Interaction`
            The discord.Interaction object from the user.

        silent : bool
            Send it as a silent message?

        attachment : `Optional[discord.Attachment]`
            The attachment you would like to send. Leave this empty if you want to send the message only.

        Returns
        ----------
        None

        """
        # Converts the attachment to a discord.File() object
        file = await attachment.to_file() if attachment else None
        await interaction.response.send_modal(SendAsBotModal(bot=self.bot, silent=silent, file=file))


    @send.error
    async def send_error(self, interaction: Interaction, error):
        embed = embed(title="", color=Color.red())

        if isinstance(error, MissingPermissions):
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> This command **requires** `move members` permission, and you probably **don't have** it, {interaction.user.mention}.", inline=False)
            await interaction.response.send_message(embed=embed)
            
        if isinstance(error, BotMissingPermissions):
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I **don't have** `send messages` permission in this channel. Please grant me the permission in advance when proceeding.", inline=False)
            await interaction.response.send_message(embed=embed)

        else:
            raise error


async def setup(bot: Bot):
    await bot.add_cog(SendAsBot(bot))


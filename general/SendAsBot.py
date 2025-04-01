import discord
from discord import app_commands, Forbidden, Interaction
from discord.ui import Modal, TextInput
from discord.app_commands.errors import MissingPermissions, BotMissingPermissions
from discord.ext import commands
from typing import Optional

class SendAsBotModal(Modal):
    """
    A Discord Modal to let you send your message as bot's identity
    """

    content = TextInput(
        label="Content",
        style=discord.TextStyle.paragraph,
        placeholder="Your content here...",
        required=True,
        max_length=4000
    )


    def __init__(self, silent: bool = False, file: Optional[discord.File] = None):
        self.silent = silent
        self.file = file
        super().__init__(title="Send your message as bot's identity")

    async def on_submit(self, interaction: Interaction):
        """
        Handle modal submission.
        """
        send_as_bot_error_embed = discord.Embed(title="", color=discord.Colour.red())
        await interaction.response.defer()
        content = self.content.value or None
        if content is None and self.file is None:
            # Returns if both message and attachments are not provided
            send_as_bot_error_embed.add_field(name="", value="<a:crossred:1356353067024515266> You cannot let me to send nothing! (say at least send a message or an attachment)", inline=False)
            return await interaction.followup.send(embed=send_as_bot_error_embed)
        
        if not isinstance(interaction.channel, discord.VoiceChannel):
            try:
                await interaction.channel.send(content=content, file=self.file, silent=self.silent)
    
            except Forbidden as e:
                if e.status == 403 and e.code == 50013:
                    # Handling rare forbidden case
                    send_as_bot_error_embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I couldn't **send the content you provided**. Please **double-check** my **permissions** and **role position**.")
                    return await interaction.followup.send(embed=send_as_bot_error_embed)

                else:
                    raise e

class SendAsBot(commands.Cog):
    def __init__(self, bot):
        global bool_value
        self.bot = bot

    # Send message from user input
    @app_commands.command(description="Send your message or attatchment, or both as bot identity")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.checks.bot_has_permissions(send_messages=True)
    @app_commands.describe(silent="Send it as a silent message?")
    @app_commands.describe(attachment="The attachment you would like to send. Leave this empty if you want to send the message only.")
    async def send(self, interaction: Interaction, silent: bool, attachment: Optional[discord.Attachment] = None):
        # Converts the attachment to a discord.File() object
        file = await attachment.to_file() if attachment else None
        await interaction.response.send_modal(SendAsBotModal(silent=silent, file=file))


    @send.error
    async def send_error(self, interaction: Interaction, error):
        send_as_bot_error_embed = discord.Embed(title="", color=discord.Colour.red())

        if isinstance(error, MissingPermissions):
            send_as_bot_error_embed.add_field(name="", value=f"<a:crossred:1356353067024515266> This command **requires** `move members` permission, and you probably **don't have** it, {interaction.user.mention}.", inline=False)
            await interaction.response.send_message(embed=send_as_bot_error_embed)
            
        if isinstance(error, BotMissingPermissions):
            send_as_bot_error_embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I **don't have** `send messages` permission in this channel. Please grant me the permission in advance when proceeding.", inline=False)
            await interaction.response.send_message(embed=send_as_bot_error_embed)

        else:
            raise error


async def setup(bot):
    await bot.add_cog(SendAsBot(bot))


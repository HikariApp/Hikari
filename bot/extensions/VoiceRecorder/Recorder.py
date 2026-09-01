import discord
import io
import zipfile
from bot.extensions.MusicPlayer._betterPlayer import BetterPlayer
from discord import HTTPException
from discord.ext import commands
from discord.ext.voice_recv import VoiceRecvClient
from discord.ext.commands import Context
from datetime import datetime
from typing import Optional
from startup import MyBot
from bot.extensions.VoiceRecorder._recorderSink import MultiAudioImprovedWithSilenceSink, addSilenceToWAV
from helpers.errorHandling import *
from helpers.respondEmbed import respondEmbed, ResponseTarget

discord.opus._load_default()  # mandatory for those who wonder

class Recorder(commands.Cog):
    def __init__(self, bot: MyBot):
        self.bot = bot
        self.logger = self.bot.getLogger()
        self.customSink: Optional[MultiAudioImprovedWithSilenceSink] = None


    # This method is called when the recording is finished, either successfully or with an error.
    def _recordingFinished(self, exc: Optional[Exception]) -> None:
        if exc:
            self.logger.error(f"Voice receive stopped with an error: {exc}")


    # Starts the recording
    @commands.hybrid_command(name="record", help="Starts recording the voice channel")
    async def record(self, ctx: Context):
        """
        Starts recording the voice channel.
        """
        if not ctx.author.voice:
            return await respondEmbed(ctx, "You must be connected to a voice channel to use this command.", target=ResponseTarget.EPHEMERAL, error=True)

        if self.bot.voice_clients:
            if isinstance(self.bot.voice_clients[0], BetterPlayer):
                return await respondEmbed(ctx, "The voice client is now being occupied by the music player. Please terminate the player and try again.", target=ResponseTarget.EPHEMERAL, error=True)

            else:
                return await respondEmbed(ctx, "I'm already connected to a voice channel.", target=ResponseTarget.EPHEMERAL, error=True)

        voiceChannel = ctx.author.voice.channel
        voiceClient: VoiceRecvClient = await voiceChannel.connect(cls=VoiceRecvClient)

        if voiceClient.is_listening():
            return await respondEmbed(ctx, "Recording is already in progress.", target=ResponseTarget.EPHEMERAL, error=True)

        try:
            # Fresh sink per recording so buffers don't carry over from a previous session
            self.customSink = MultiAudioImprovedWithSilenceSink()

            # Start listening to the voice channel with the custom sink
            voiceClient.listen(self.customSink)

        except Exception as e:
            # Something went wrong while starting the recording
            # Clean up and inform the user
            self.logger.error(f"An error occurred while starting the voice recording: {e}")
            if self.customSink is not None:
                self.customSink.cleanup()
                self.customSink = None
            await voiceClient.disconnect()
            return await respondEmbed(ctx, "An error occurred while starting the voice recording.", target=ResponseTarget.EPHEMERAL, error=True)

        await respondEmbed(ctx, "Recording has **started**. Use **/stop-recording** to **stop**.", target=ResponseTarget.EPHEMERAL)


    # Stops the recording
    @commands.hybrid_command(name="stop-recording", help="Stops the current voice recording and sends the recorded audio as a zip file.")
    async def stop_recording(self, ctx: Context):
        """
        Stops the current voice recording and sends the recorded audio as a zip file.
        """

        voiceClient = ctx.guild.voice_client
        if not voiceClient or not voiceClient.is_listening() or self.customSink is None:
            return await respondEmbed(ctx, "No recording in progress.", target=ResponseTarget.EPHEMERAL, error=True)

        await ctx.defer()
        voiceClient.stop_listening()

        try:
            userTracks = {}
            for userId in self.customSink.getRecordedUsers():
                audioData = self.customSink.getUserAudio(userId)

                if audioData and len(audioData) > 44:  # Ensure the file isn't empty
                    silenceDuration = self.customSink.getInitialSilenceDuration(userId)
                    userTracks[userId] = addSilenceToWAV(audioData, silenceDuration)

            if userTracks:
                # Resolve display names for nicer filenames inside the zip
                # Notes that the command invoker does not required to be in a voice channel, so we can't rely on ctx.author.voice.channel.members
                memberById = {m.id: m for m in voiceClient.channel.members}

                # Create a zip file in memory and add each user's audio track to it
                zipBuffer = io.BytesIO()
                with zipfile.ZipFile(zipBuffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for userId, wavBytes in userTracks.items():
                        member = memberById.get(userId)
                        name = member.display_name if member else str(userId)
                        zf.writestr(f"{name}_{userId}.wav", wavBytes)

                zipBuffer.seek(0)

                try:
                    await respondEmbed(ctx, f"Recording finished. **{len(userTracks)}** separate track(s) attached in the zip file below:", target=ResponseTarget.EPHEMERAL)
                    await ctx.reply(
                        file=discord.File(zipBuffer, filename=f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
                    )

                except HTTPException as e:
                    if e.status == 413 and e.code == 40005:  # File too large
                        return await respondEmbed(ctx, "Failed to send the recording because the file was too large", target=ResponseTarget.EPHEMERAL, error=True)

                    else:
                        raise e

            else:
                return await respondEmbed(ctx, "Recording **failed** or the file is **empty**.", target=ResponseTarget.EPHEMERAL, error=True)

        finally:
            # Release buffers regardless of outcome so the next session starts clean
            self.customSink.cleanup()
            self.customSink = None
            await voiceClient.disconnect()


async def setup(bot: MyBot):
    await bot.add_cog(Recorder(bot))

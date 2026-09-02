from bson import timestamp
import discord
import asyncio
import io
import os
import boto3
import zipfile
from botocore.config import Config
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

R2_ACCOUNT_ID = os.environ["R2_ACCOUNT_ID"]
R2_ACCESS_KEY = os.environ["R2_ACCESS_KEY_ID"]
R2_SECRET_KEY = os.environ["R2_SECRET_ACCESS_KEY"]
R2_BUCKET = os.environ["R2_BUCKET"]

class Recorder(commands.Cog):
    def __init__(self, bot: MyBot):
        self.bot = bot
        self.logger = self.bot.getLogger()
        self.customSink: Optional[MultiAudioImprovedWithSilenceSink] = None
        # R2 is S3-compatible; sign with s3v4, region must be "auto"
        self._r2 = boto3.client(
            "s3",
            endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=R2_ACCESS_KEY,
            aws_secret_access_key=R2_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )


    async def _uploadToR2(self, data: bytes, key: str, expiresIn: int = 86400) -> str:
        """
        Upload bytes to R2 and return a presigned download URL.
        boto3 is blocking, so run it off the event loop.
        `expiresIn` is the link lifetime in seconds (default 24h).
        """
        def _blocking():
            self._r2.put_object(
                Bucket=R2_BUCKET,
                Key=key,
                Body=data,
                ContentType="application/zip",
            )
            return self._r2.generate_presigned_url(
                "get_object",
                Params={"Bucket": R2_BUCKET, "Key": key},
                ExpiresIn=expiresIn,
            )

        return await asyncio.to_thread(_blocking)


    def _packRecordings(self, userTracks: dict, memberById: dict) -> bytes:
        """
        Pack every user's WAV track into a single in-memory zip and return its bytes.
        Names are derived from display names, sanitized and de-duped to avoid
        collisions or invalid characters. No size splitting — R2 handles up to 5GB
        per object.
        """
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            used = set()
            for userId, wavBytes in userTracks.items():
                member = memberById.get(userId)
                base = member.display_name if member else str(userId)
                safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in base).strip() or str(userId)
                name = f"{safe}.wav"
                n = 1
                while name in used:
                    name = f"{safe}_{n}.wav"
                    n += 1
                used.add(name)
                zf.writestr(name, wavBytes)
        return buf.getvalue()


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

        voiceClient = ctx.guild.voice_client

        # Busy with music in this guild
        if isinstance(voiceClient, BetterPlayer):
            return await respondEmbed(ctx, message="The voice client is now being occupied by the music player. Please terminate the player and try again.", target=ResponseTarget.EPHEMERAL, error=True)

        # Connected, but not as a recorder client — can't record on this
        if voiceClient is not None and not isinstance(voiceClient, VoiceRecvClient):
            return await respondEmbed(ctx, message="I'm connected to voice in a state I can't record from. Please disconnect me and try again.", target=ResponseTarget.EPHEMERAL, error=True)

        # Already recording in this guild
        if isinstance(voiceClient, VoiceRecvClient) and voiceClient.is_listening():
            return await respondEmbed(ctx, message="Recording is already in progress.", target=ResponseTarget.EPHEMERAL, error=True)

        # Not connected yet — need a channel from the author
        if voiceClient is None:
            if not ctx.author.voice:
                return await respondEmbed(ctx, message="I'm not in a voice channel, so please join one and I'll follow.", target=ResponseTarget.EPHEMERAL)

            voiceClient = await ctx.author.voice.channel.connect(cls=VoiceRecvClient)

        # voiceClient is guaranteed to be a connected VoiceRecvClient here
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
            return await respondEmbed(ctx, message="An error occurred while starting the voice recording.", target=ResponseTarget.EPHEMERAL, error=True)

        await respondEmbed(ctx, message="Recording has **started**. Use **/stop-recording** to **stop**.", target=ResponseTarget.EPHEMERAL)


    # Stops the recording
    @commands.hybrid_command(name="stop-recording", help="Stops the current voice recording and sends the recorded audio as a zip file.")
    async def stop_recording(self, ctx: Context):
        """
        Stops the current voice recording and sends the recorded audio as a zip file.
        """

        voiceClient = ctx.guild.voice_client
        # Busy with music in this guild
        if isinstance(voiceClient, BetterPlayer):
            return await respondEmbed(ctx, message="The voice client is now being occupied by the music player. Please terminate the player and try again.", target=ResponseTarget.EPHEMERAL, error=True)

        # Connected, but not as a recorder client — can't stop recording on this
        if voiceClient is not None and not isinstance(voiceClient, VoiceRecvClient):
            return await respondEmbed(ctx, message="I'm connected to voice in a state I can't stop recording from. Please disconnect me and try again.", target=ResponseTarget.EPHEMERAL, error=True)

        # Not recording in this guild
        if not isinstance(voiceClient, VoiceRecvClient) or not voiceClient.is_listening() or self.customSink is None:
            return await respondEmbed(ctx, message="No recording in progress.", target=ResponseTarget.EPHEMERAL, error=True)

        await ctx.defer()
        voiceClient.stop_listening()

        try:
            userTracks = {}
            for userId in self.customSink.getRecordedUsers():
                audioData = self.customSink.getUserAudio(userId)
                if audioData and len(audioData) > 44:  # Ensure the file isn't empty
                    silenceDuration = self.customSink.getInitialSilenceDuration(userId)
                    userTracks[userId] = addSilenceToWAV(audioData, silenceDuration)

            if not userTracks:
                return await respondEmbed(ctx, message="Recording **failed** or the file is **empty**.", target=ResponseTarget.EPHEMERAL, error=True)

            # The invoker need not be in the channel, so resolve names from the recorded channel
            memberById = {m.id: m for m in voiceClient.channel.members}

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            zipBytes = self._packRecordings(userTracks, memberById)

            # Generate a unique filename for the zip file in the R2 bucket
            fname = f"recordings/{ctx.guild.id}/recording_{timestamp}.zip"

            try:
                url = await self._uploadToR2(zipBytes, key=fname)

            except Exception as e:
                self.logger.error(f"Failed to upload recording to R2: {e}")
                return await respondEmbed(ctx, message="Recording captured, but the upload failed. Please try again.", target=ResponseTarget.EPHEMERAL, error=True)

            await respondEmbed(
                ctx,
                title="Recording Finished",
                message=(
                    f"**{len(userTracks)}** track(s) captured."
                    f"\n\n**Download:**"
                    f"\nYou can download the recorded audio by clicking [here]({url})"
                    f"\n\nIf the link doesn't work, copy and paste the following URL into your browser:"
                    f"\n```{url}```"
                    ),
                footerText="Note: The download link will expire in 24 hours. Be sure to save the file before then.",
                target=ResponseTarget.REPLY,
            )

        finally:
            # Release buffers regardless of outcome so the next session starts clean
            self.customSink.cleanup()
            self.customSink = None
            await voiceClient.disconnect()


async def setup(bot: MyBot):
    await bot.add_cog(Recorder(bot))


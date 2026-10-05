from bson import timestamp
import discord
import asyncio
import io
import os
import boto3
import zipfile
from botocore.config import Config
from hikari_bot.bot.extensions.musicplayer._betterplayer import BetterPlayer
from discord import HTTPException
from discord.ext import commands
from discord.ext.voice_recv import VoiceRecvClient
from discord.ext.commands import Context
from datetime import datetime
from typing import Optional
from hikari_bot.startup import MyBot
from hikari_bot.bot.extensions.voicerecorder._recordersink import MultiAudioImprovedWithSilenceSink, add_silence_to_wav
from hikari_bot.helpers.errorhandling import *
from hikari_bot.helpers.respondembed import respond_embed, ResponseTarget

discord.opus._load_default()  # mandatory for those who wonder

R2_ACCOUNT_ID = os.environ["R2_ACCOUNT_ID"]
R2_ACCESS_KEY = os.environ["R2_ACCESS_KEY_ID"]
R2_SECRET_KEY = os.environ["R2_SECRET_ACCESS_KEY"]
R2_BUCKET = os.environ["R2_BUCKET"]

class Recorder(commands.Cog):
    def __init__(self, bot: MyBot):
        self.bot = bot
        self.logger = self.bot.get_logger()
        self.custom_sink: Optional[MultiAudioImprovedWithSilenceSink] = None
        # R2 is S3-compatible; sign with s3v4, region must be "auto"
        self._r2 = boto3.client(
            "s3",
            endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=R2_ACCESS_KEY,
            aws_secret_access_key=R2_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )


    async def _upload_to_r2(self, data: bytes, key: str, expires_in: int = 86400) -> str:
        """
        Upload bytes to R2 and return a presigned download URL.
        boto3 is blocking, so run it off the event loop.
        `expires_in` is the link lifetime in seconds (default 24h).
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
                ExpiresIn=expires_in,
            )

        return await asyncio.to_thread(_blocking)


    def _pack_recordings(self, user_tracks: dict, member_by_id: dict) -> bytes:
        """
        Pack every user's WAV track into a single in-memory zip and return its bytes.
        Names are derived from display names, sanitized and de-duped to avoid
        collisions or invalid characters. No size splitting — R2 handles up to 5GB
        per object.
        """
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            used = set()
            for user_id, wav_bytes in user_tracks.items():
                member = member_by_id.get(user_id)
                base = member.display_name if member else str(user_id)
                safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in base).strip() or str(user_id)
                name = f"{safe}.wav"
                n = 1
                while name in used:
                    name = f"{safe}_{n}.wav"
                    n += 1
                used.add(name)
                zf.writestr(name, wav_bytes)
        return buf.getvalue()


    # This method is called when the recording is finished, either successfully or with an error.
    def _recording_finished(self, exc: Optional[Exception]) -> None:
        if exc:
            self.logger.error(f"Voice receive stopped with an error: {exc}")


    # Starts the recording
    @commands.hybrid_command(name="record", help="Starts recording the voice channel")
    async def record(self, ctx: Context):
        """
        Starts recording the voice channel.
        """

        voice_client = ctx.guild.voice_client

        # Busy with music in this guild
        if isinstance(voice_client, BetterPlayer):
            return await respond_embed(ctx, message="The voice client is now being occupied by the music player. Please terminate the player and try again.", target=ResponseTarget.EPHEMERAL, error=True)

        # Connected, but not as a recorder client — can't record on this
        if voice_client is not None and not isinstance(voice_client, VoiceRecvClient):
            return await respond_embed(ctx, message="I'm connected to voice in a state I can't record from. Please disconnect me and try again.", target=ResponseTarget.EPHEMERAL, error=True)

        # Already recording in this guild
        if isinstance(voice_client, VoiceRecvClient) and voice_client.is_listening():
            return await respond_embed(ctx, message="Recording is already in progress.", target=ResponseTarget.EPHEMERAL, error=True)

        # Not connected yet — need a channel from the author
        if voice_client is None:
            if not ctx.author.voice:
                return await respond_embed(ctx, message="I'm not in a voice channel, so please join one and I'll follow.", target=ResponseTarget.EPHEMERAL)

            voice_client = await ctx.author.voice.channel.connect(cls=VoiceRecvClient)

        # voice_client is guaranteed to be a connected VoiceRecvClient here
        try:
            # Fresh sink per recording so buffers don't carry over from a previous session
            self.custom_sink = MultiAudioImprovedWithSilenceSink()

            # Start listening to the voice channel with the custom sink
            voice_client.listen(self.custom_sink)

        except Exception as e:
            # Something went wrong while starting the recording
            # Clean up and inform the user
            self.logger.error(f"An error occurred while starting the voice recording: {e}")
            if self.custom_sink is not None:
                self.custom_sink.cleanup()
                self.custom_sink = None
            await voice_client.disconnect()
            return await respond_embed(ctx, message="An error occurred while starting the voice recording.", target=ResponseTarget.EPHEMERAL, error=True)

        await respond_embed(ctx, message="Recording has **started**. Use **/stop-recording** to **stop**.", target=ResponseTarget.EPHEMERAL)


    # Stops the recording
    @commands.hybrid_command(name="stop-recording", help="Stops the current voice recording and sends the recorded audio as a zip file.")
    async def stop_recording(self, ctx: Context):
        """
        Stops the current voice recording and sends the recorded audio as a zip file.
        """

        voice_client = ctx.guild.voice_client
        # Busy with music in this guild
        if isinstance(voice_client, BetterPlayer):
            return await respond_embed(ctx, message="The voice client is now being occupied by the music player. Please terminate the player and try again.", target=ResponseTarget.EPHEMERAL, error=True)

        # Connected, but not as a recorder client — can't stop recording on this
        if voice_client is not None and not isinstance(voice_client, VoiceRecvClient):
            return await respond_embed(ctx, message="I'm connected to voice in a state I can't stop recording from. Please disconnect me and try again.", target=ResponseTarget.EPHEMERAL, error=True)

        # Not recording in this guild
        if not isinstance(voice_client, VoiceRecvClient) or not voice_client.is_listening() or self.custom_sink is None:
            return await respond_embed(ctx, message="No recording in progress.", target=ResponseTarget.EPHEMERAL, error=True)

        await ctx.defer()
        voice_client.stop_listening()

        try:
            user_tracks = {}
            for user_id in self.custom_sink.get_recorded_users():
                audio_data = self.custom_sink.get_user_audio(user_id)
                if audio_data and len(audio_data) > 44:  # Ensure the file isn't empty
                    silence_duration = self.custom_sink.get_initial_silence_duration(user_id)
                    user_tracks[user_id] = add_silence_to_wav(audio_data, silence_duration)

            if not user_tracks:
                return await respond_embed(ctx, message="Recording **failed** or the file is **empty**.", target=ResponseTarget.EPHEMERAL, error=True)

            # The invoker need not be in the channel, so resolve names from the recorded channel
            member_by_id = {m.id: m for m in voice_client.channel.members}

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            zip_bytes = self._pack_recordings(user_tracks, member_by_id)

            # Generate a unique filename for the zip file in the R2 bucket
            fname = f"recordings/{ctx.guild.id}/recording_{timestamp}.zip"

            try:
                url = await self._upload_to_r2(zip_bytes, key=fname)

            except Exception as e:
                self.logger.error(f"Failed to upload recording to R2: {e}")
                return await respond_embed(ctx, message="Recording captured, but the upload failed. Please try again.", target=ResponseTarget.EPHEMERAL, error=True)

            await respond_embed(
                ctx,
                title="Recording Finished",
                message=(
                    f"**{len(user_tracks)}** track(s) captured."
                    f"\n\n**Download:**"
                    f"\nYou can download the recorded audio by clicking [here]({url})"
                    f"\n\nIf the link doesn't work, copy and paste the following URL into your browser:"
                    f"\n```{url}```"
                    ),
                footer_text="Note: The download link will expire in 24 hours. Be sure to save the file before then.",
                target=ResponseTarget.REPLY,
            )

        finally:
            # Release buffers regardless of outcome so the next session starts clean
            self.custom_sink.cleanup()
            self.custom_sink = None
            await voice_client.disconnect()


async def setup(bot: MyBot):
    await bot.add_cog(Recorder(bot))


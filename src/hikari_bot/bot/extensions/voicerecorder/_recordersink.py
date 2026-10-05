"""
The MIT License (MIT)

Copyright (c) 2026 Hoshino Yuki

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

# SPDX-License-Identifier: MIT

import io
import time
import wave
import numpy as np
from typing import Dict, Optional

import discord
from discord.ext.voice_recv import AudioSink, VoiceData, WaveSink
from discord.ext.voice_recv.silence import SilenceGenerator


def add_silence_to_wav(input_data: bytes, silence_duration: float) -> bytes:
    """
    Adds silence to the beginning of a WAV audio file.

    This uses pure stdlib implementation, so no pydub/ffmpeg is required.
    
    PCM silence is just zero-valued frames, so we read the source params,
    synthesize the right number of silent frames, and write silence + original audio.

    Parameters
    ----------
    input_data : bytes
        The input WAV audio data as bytes.
    silence_duration : float
        The duration of silence to add in seconds.

    Returns
    -------
    bytes
        The modified WAV audio data with silence added at the beginning.
    """

    with wave.open(io.BytesIO(input_data), "rb") as wav_in:
        params = wav_in.getparams()
        frames = wav_in.readframes(params.nframes)

    # One "frame" = nchannels * sampwidth bytes. Silence = zero bytes.
    silence_frames = int(silence_duration * params.framerate)
    silence_bytes = b"\x00" * (silence_frames * params.nchannels * params.sampwidth)

    output_buffer = io.BytesIO()
    with wave.open(output_buffer, "wb") as wav_out:
        wav_out.setnchannels(params.nchannels)
        wav_out.setsampwidth(params.sampwidth)
        wav_out.setframerate(params.framerate)
        wav_out.writeframes(silence_bytes + frames)

    output_buffer.seek(0)
    return output_buffer.read()


class MultiAudioImprovedWithSilenceSink(AudioSink):
    """
    Collects incoming voice into one WaveSink per user.
    
    Each user's audio is kept fully separated in its own buffer; mix_audio() is a *final* step that
    optionally collapses them into a single track.
    """
    def __init__(self):
        super().__init__()
        self.user_sinks: Dict[int, WaveSink] = {}
        self.user_buffers: Dict[int, io.BytesIO] = {}
        self.silence_generators: Dict[int, SilenceGenerator] = {}
        self.start_time = time.perf_counter_ns()
        self.first_packet_time: Dict[int, int] = {}


    def get_or_create_sink(self, user_id: int) -> WaveSink:
        if user_id not in self.user_sinks:
            buffer = io.BytesIO()
            sink = WaveSink(buffer)
            self.user_sinks[user_id] = sink
            self.user_buffers[user_id] = buffer
            self.silence_generators[user_id] = SilenceGenerator(sink.write)
            self.silence_generators[user_id].start()
        return self.user_sinks[user_id]


    def wants_opus(self) -> bool:
        """
        Whether the sink wants raw Opus packets or decoded PCM.
        This sink wants PCM, so the library decodes for us.
        """
        return False


    def write(self, user: Optional[discord.User], data: VoiceData) -> None:
        """
        Called when a new voice packet is received.

        This method is called on a background thread.

        Parameters
        ----------
        user : discord.User, optional
            The user who sent the voice packet. Can be None if the user is unknown.
        data : VoiceData
            The voice data received.
        """

        if user is None:
            return

        sink = self.get_or_create_sink(user.id)
        silence_gen = self.silence_generators[user.id]

        if user.id not in self.first_packet_time:
            self.first_packet_time[user.id] = time.perf_counter_ns()

        silence_gen.push(user, data.packet)
        sink.write(user, data)


    def cleanup(self) -> None:
        """
        Cleans up resources used by the sink.

        Stops all silence generators and clears user sinks and buffers.
        """
        for silence_gen in self.silence_generators.values():
            silence_gen.stop()

        self.user_sinks.clear()
        self.user_buffers.clear()
        self.silence_generators.clear()


    def get_recorded_users(self):
        """Returns a list of user IDs for which audio has been recorded."""
        return list(self.user_buffers.keys())


    def get_user_audio(self, user_id: int) -> Optional[bytes]:
        """
        Retrieves the audio data for a specific user.

        Parameters
        ----------
        user_id : int
            The ID of the user whose audio data to retrieve.

        Returns
        -------
        Optional[bytes]
            The audio data for the user, or None if not found.
        """

        if user_id in self.user_buffers:
            buffer = self.user_buffers[user_id]
            buffer.seek(0)
            audio_data = buffer.read()
            return audio_data

        return


    def get_initial_silence_duration(self, user_id: int) -> float:
        """
        Retrieves the initial silence duration for a specific user.

        Parameters
        ----------
        user_id : int
            The ID of the user whose initial silence duration to retrieve.
        """

        if user_id in self.first_packet_time:
            return (self.first_packet_time[user_id] - self.start_time) / 1e9  # nano to sec

        return 0.0


    def mix_audio(self, audio_data_dict: Dict[int, bytes]) -> Optional[bytes]:
        """
        Mixes multiple WAV audio data streams into a single WAV audio stream.

        Parameters
        ----------
        audio_data_dict : Dict[int, bytes]
            A dictionary mapping user IDs to their respective WAV audio data as bytes.
        
        Returns
        -------
        bytes, optional
            The mixed WAV audio data as bytes, or None if no valid audio data was provided.
        """

        audio_arrays = []
        sample_rate = 0
        num_channels = 0
        sample_width = 0

        for audio_data in audio_data_dict.values():
            if len(audio_data) <= 44:
                continue

            with wave.open(io.BytesIO(audio_data), 'rb') as wav_file:
                params = wav_file.getparams()
                sample_rate = params.framerate
                num_channels = params.nchannels
                sample_width = params.sampwidth

                frames = wav_file.readframes(params.nframes)
                audio_array = np.frombuffer(frames, dtype=np.int16)
                audio_arrays.append(audio_array)

        if not audio_arrays:
            return

        max_length = max(len(arr) for arr in audio_arrays)
        padded_audio_arrays = [np.pad(arr, (0, max_length - len(arr)), 'constant') for arr in audio_arrays]
        mixed_audio = np.mean(padded_audio_arrays, axis=0).astype(np.int16)

        output_buffer = io.BytesIO()
        with wave.open(output_buffer, 'wb') as output_wav:
            output_wav.setnchannels(num_channels)
            output_wav.setsampwidth(sample_width)
            output_wav.setframerate(sample_rate)
            output_wav.writeframes(mixed_audio.tobytes())

        output_buffer.seek(0)
        return output_buffer.read()

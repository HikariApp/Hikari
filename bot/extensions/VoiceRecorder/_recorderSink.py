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
from pydub import AudioSegment


def addSilenceToWAV(inputData: bytes, silenceDuration: float) -> bytes:
    """
    Adds silence to the beginning of a WAV audio file.

    Parameters
    ----------
    inputData : bytes
        The input WAV audio data as bytes.
    silenceDuration : float
        The duration of silence to add in seconds.
    
    Returns
    -------
    bytes
        The modified WAV audio data with silence added at the beginning.
    """

    audio = AudioSegment.from_wav(io.BytesIO(inputData))
    silence = AudioSegment.silent(duration=int(silenceDuration * 1000))  # pydub uses milliseconds
    finalAudio = silence + audio
    outputBuffer = io.BytesIO()
    finalAudio.export(outputBuffer, format="wav")
    return outputBuffer.getvalue()


class MultiAudioImprovedWithSilenceSink(AudioSink):
    """
    Collects incoming voice into one WaveSink per user.
    
    Each user's audio is kept fully separated in its own buffer; mix_audio() is a *final* step that
    optionally collapses them into a single track.
    """
    def __init__(self):
        super().__init__()
        self.userSinks: Dict[int, WaveSink] = {}
        self.userBuffers: Dict[int, io.BytesIO] = {}
        self.silenceGenerators: Dict[int, SilenceGenerator] = {}
        self.startTime = time.perf_counter_ns()
        self.firstPacketTime: Dict[int, int] = {}


    def getOrCreateSink(self, userId: int) -> WaveSink:
        if userId not in self.userSinks:
            buffer = io.BytesIO()
            sink = WaveSink(buffer)
            self.userSinks[userId] = sink
            self.userBuffers[userId] = buffer
            self.silenceGenerators[userId] = SilenceGenerator(sink.write)
            self.silenceGenerators[userId].start()
        return self.userSinks[userId]


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

        sink = self.getOrCreateSink(user.id)
        silenceGen = self.silenceGenerators[user.id]

        if user.id not in self.firstPacketTime:
            self.firstPacketTime[user.id] = time.perf_counter_ns()

        silenceGen.push(user, data.packet)
        sink.write(user, data)


    def cleanup(self) -> None:
        """
        Cleans up resources used by the sink.

        Stops all silence generators and clears user sinks and buffers.
        """
        for silenceGen in self.silenceGenerators.values():
            silenceGen.stop()

        self.userSinks.clear()
        self.userBuffers.clear()
        self.silenceGenerators.clear()


    def getRecordedUsers(self):
        """Returns a list of user IDs for which audio has been recorded."""
        return list(self.userBuffers.keys())


    def getUserAudio(self, userId: int) -> Optional[bytes]:
        """
        Retrieves the audio data for a specific user.

        Parameters
        ----------
        userId : int
            The ID of the user whose audio data to retrieve.

        Returns
        -------
        Optional[bytes]
            The audio data for the user, or None if not found.
        """

        if userId in self.userBuffers:
            buffer = self.userBuffers[userId]
            buffer.seek(0)
            audioData = buffer.read()
            return audioData

        return


    def getInitialSilenceDuration(self, userId: int) -> float:
        """
        Retrieves the initial silence duration for a specific user.

        Parameters
        ----------
        userId : int
            The ID of the user whose initial silence duration to retrieve.
        """

        if userId in self.firstPacketTime:
            return (self.firstPacketTime[userId] - self.startTime) / 1e9  # nano to sec

        return 0.0


    def mixAudio(self, audioDataDict: Dict[int, bytes]) -> Optional[bytes]:
        """
        Mixes multiple WAV audio data streams into a single WAV audio stream.

        Parameters
        ----------
        audioDataDict : Dict[int, bytes]
            A dictionary mapping user IDs to their respective WAV audio data as bytes.
        
        Returns
        -------
        bytes, optional
            The mixed WAV audio data as bytes, or None if no valid audio data was provided.
        """

        audioArrays = []
        sampleRate = 0
        numChannels = 0
        sampleWidth = 0

        for audioData in audioDataDict.values():
            if len(audioData) <= 44:
                continue

            with wave.open(io.BytesIO(audioData), 'rb') as wavFile:
                params = wavFile.getparams()
                sampleRate = params.framerate
                numChannels = params.nchannels
                sampleWidth = params.sampwidth

                frames = wavFile.readframes(params.nframes)
                audioArray = np.frombuffer(frames, dtype=np.int16)
                audioArrays.append(audioArray)

        if not audioArrays:
            return

        maxLength = max(len(arr) for arr in audioArrays)
        paddedAudioArrays = [np.pad(arr, (0, maxLength - len(arr)), 'constant') for arr in audioArrays]
        mixedAudio = np.mean(paddedAudioArrays, axis=0).astype(np.int16)

        outputBuffer = io.BytesIO()
        with wave.open(outputBuffer, 'wb') as outputWav:
            outputWav.setnchannels(numChannels)
            outputWav.setsampwidth(sampleWidth)
            outputWav.setframerate(sampleRate)
            outputWav.writeframes(mixedAudio.tobytes())

        outputBuffer.seek(0)
        return outputBuffer.read()

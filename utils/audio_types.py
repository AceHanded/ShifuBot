import io
import wave
import discord
from typing import cast
from discord.sinks import Sink
from .duration_handling import format_duration
from .audio_sources import AttachmentSource, YTDLSource

class ByteSink(Sink):
    def __init__(self) -> None:
        super().__init__()

    def write(self, data: bytes, user: int) -> None:
        if user not in self.audio_data: self.audio_data[user] = io.BytesIO()

        self.audio_data[user].write(data)

    def cleanup(self) -> None:
        self.finished = True

        for file in self.audio_data.values():
            file.seek(0)

    def get_audio_as_bytes(self, user: int) -> bytes | None:
        if user not in self.audio_data: return

        self.audio_data[user].seek(0)
        return self.audio_data[user].read()
    
    @staticmethod
    def raw_to_wav_buffer(raw_data: bytes) -> io.BytesIO:
        wav_buffer = io.BytesIO()

        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(raw_data)

        wav_buffer.seek(0)
        return wav_buffer

class PlayerEntry:
    def __init__(self, track: dict):
        self.url: str = track["url"]
        self.start_at: int = track["start_at"]
        self.start_time: float = track["start_time"]
        self.requested_by: str = track["requested_by"]
        self.player: AttachmentSource | YTDLSource | None = None
        self.title: str | None = track.get("title")
        self.duration: int | None = track.get("duration")
        self.formatted_duration: str | None = format_duration(track.get("duration"))
        self.uploader: str | None = track.get("uploader")
        self.uploader_avatar: str | None = track.get("uploader_avatar")
        self.related: list[dict] = track.get("related", [])
        self.source: str | None = track.get("source")

class Queue:
    def __init__(self):
        self.songs: list[PlayerEntry] = []
        self.previous_songs: list[PlayerEntry] = []
        self.text_channel: int = 0
        self.volume: int = 100
        self.autoplay: bool = False
        self.ctx: discord.ApplicationContext = cast(discord.ApplicationContext, None)
        self.loop: str = "Disabled"
        self.filter: dict = {
            "name": "Disabled",
            "value": "anull",
            "intensity": 35
        }
        self.messages: dict = {
            "play": None,
            "pause": None,
            "volume": None,
            "loop": None,
            "remove": None,
            "remove_content": ""
        }

    def __bool__(self) -> bool:
        return True

    def __len__(self) -> int:
        return len(self.songs)

    def empty(self) -> bool:
        return len(self.songs) < 2
    
    def clear(self) -> None:
        self.songs.clear()
        self.previous_songs.clear()

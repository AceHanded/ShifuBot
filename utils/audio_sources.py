import json
import asyncio
import discord
import subprocess
from pytubefix import YouTube

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source: discord.FFmpegPCMAudio, data: dict, volume: float = 1.0):
        super().__init__(source, volume)
        self.data: dict = data

    @classmethod
    async def from_url(cls, url: str, pytube: bool = True, live: bool = False, filter_: str = "anull", start_at: int = 0):
        ffmpeg_options = {
            "before_options": f"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5{f' -ss {start_at}' if not live and start_at else ''}",
            "options": f"-af {filter_}" if filter_ != "anull" else ""
        }

        def _get_audio_url():
            if pytube:
                yt = YouTube(url, use_oauth=False, allow_oauth_cache=False)
                audio_stream = yt.streams.filter(only_audio=True, progressive=False)[-1]
                return { "url": audio_stream.url }
            else:
                command = [
                    "yt-dlp",
                    "-f", "bestaudio[protocol^=http]/best",
                    "-J",
                    "--skip-download",
                    "--flat-playlist",
                    "--extractor-args",
                    f"youtube:player_client=default,-tv,-tv_embedded;player_skip=configs,initial_data;skip={'hls,' if not live else ''}dash,translated_subs",
                    "--no-check-certificates",
                    "--quiet",
                    "--no-warnings",
                    "--cookies", "./data/cookies.txt",
                    url
                ]
                res = json.loads(subprocess.run(command, capture_output=True, text=True).stdout)
                return res

        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, _get_audio_url)

        if not data: return None
        elif data.get("entries"): return data
        return cls(discord.FFmpegPCMAudio(data["url"], before_options=ffmpeg_options["before_options"], options=ffmpeg_options["options"] or None), data=data)

class AttachmentSource(discord.PCMVolumeTransformer):
    def __init__(self, source: discord.FFmpegPCMAudio, volume: float = 1.0):
        super().__init__(source, volume)

    @classmethod
    async def from_url(cls, url: str, filter_: str = "anull", start_at: int = 0):
        ffmpeg_options = {
            "before_options": f"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ss {start_at}",
            "options": f"-af {filter_}"
        }
        return cls(discord.FFmpegPCMAudio(url, before_options=ffmpeg_options["before_options"], options=ffmpeg_options["options"]))

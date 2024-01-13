import discord
import datetime
import yt_dlp
import googleapiclient.discovery
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import lyricsgenius
import sclib
from dotenv import load_dotenv
import os


load_dotenv()


class Color:
    MAGENTA = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    END = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


class Constants:
    SOUNDCLOUD = sclib.SoundcloudAPI()
    GENIUS = lyricsgenius.Genius(os.getenv("GENIUS_API_KEY"), timeout=10, verbose=False, skip_non_songs=True)
    YOUTUBE = googleapiclient.discovery.build("youtube", "v3",
                                              developerKey=os.getenv("YOUTUBE_API_KEY"))
    SPOTIFY = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=os.getenv("SPOTIFY_CLIENT_ID"),
                                                        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
                                                        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URL"),
                                                        scope=os.getenv("SPOTIFY_SCOPE"),
                                                        username=os.getenv("SPOTIFY_USERNAME")))
    YTDL_FORMAT_OPTIONS = {
        "format": "bestaudio",
        "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
        "restrictfilenames": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": False,
        "logtostderr": False,
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch1",
        "source_address": "0.0.0.0",
        "force-ipv4": True,
        "no-cache-dir": True,
        "cookies": "cookies.txt",
        "use-extractors": "Youtube",
        "external-downloader": "aria2c",
        "external-downloader-args": "--min-split-size=1M --max-connection-per-server=16 --max-concurrent-downloads=16"
                                    " --split=16"
    }
    YTDL = yt_dlp.YoutubeDL(YTDL_FORMAT_OPTIONS)
    CARD_VALUE = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "Jack", "Queen", "King", "Ace"]
    CARD_SUIT = {"Clubs": "♧", "Diamonds": "♢", "Hearts": "♡", "Spades": "♤"}


async def parse_timestamp(ctx, timestamp: str, no_seek: bool = False):
    colon_count = timestamp.count(":")

    if colon_count == 2:
        hours, minutes, seconds = timestamp.split(":")
    elif colon_count == 1:
        hours = "00"
        minutes, seconds = timestamp.split(":")
    elif colon_count == 0:
        hours, minutes, seconds = "00", "00", timestamp
    else:
        embed = discord.Embed(
            description=f"**Note:** Invalid timestamp format (hours:minutes:seconds)."
                        f"{' Defaulting to 00:00.' if not no_seek else ''}",
            color=discord.Color.red(),
        )
        await ctx.respond(embed=embed)

        if no_seek:
            return
        hours, minutes, seconds = "00", "00", "00"

    if not (hours.isdigit() and minutes.isdigit() and seconds.isdigit()):
        embed = discord.Embed(
            description=f"**Note:** Invalid timestamp format (hours:minutes:seconds)."
                        f"{' Defaulting to 00:00.' if not no_seek else ''}",
            color=discord.Color.red(),
        )
        await ctx.respond(embed=embed)

        if no_seek:
            return
        hours, minutes, seconds = "00", "00", "00"

    return (int(hours) * 3600) + (int(minutes) * 60) + int(seconds)


def format_duration(seconds: int, compare_to: int = None, use_milliseconds: bool = False):
    if seconds is None:
        return "Live"

    if not compare_to:
        compare_to = seconds

    if not use_milliseconds:
        compare_value = 3600
    else:
        compare_value = 3600000
        seconds //= 1000

    if compare_to >= compare_value:
        return f"{datetime.timedelta(seconds=seconds)}"

    return f"{seconds // 60:02d}:{seconds % 60:02d}"


async def connect_handling(ctx, play_command=False):
    try:
        channel = ctx.author.voice.channel
    except AttributeError:
        embed = discord.Embed(
            description="**Note:** Please connect to a voice channel first.",
            color=discord.Color.blue(),
        )
        await ctx.followup.send(embed=embed)
        return

    if ctx.voice_client is None:
        embed = discord.Embed(
            description=f"**Connecting to voice channel:** <#{channel.id}>",
            color=discord.Color.dark_green()
        )
        await ctx.followup.send(embed=embed)

        await channel.connect()
        await ctx.guild.change_voice_state(channel=channel, self_mute=False, self_deaf=True)
    elif channel != ctx.voice_client.channel:
        embed = discord.Embed(
            description=f"**Moving to voice channel:** <#{channel.id}>",
            color=discord.Color.dark_green()
        )
        await ctx.followup.send(embed=embed)

        await ctx.voice_client.move_to(channel)
        await ctx.guild.change_voice_state(channel=channel, self_mute=False, self_deaf=True)
    elif ctx.voice_client and channel == ctx.voice_client.channel and not play_command:
        embed = discord.Embed(
            description=f"**Error:** Already connected to voice channel: `{channel}`",
            color=discord.Color.red()
        )
        await ctx.followup.send(embed=embed)

    return channel

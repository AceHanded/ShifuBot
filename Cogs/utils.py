import yt_dlp
import googleapiclient.discovery
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import lyricsgenius
import sclib
from dotenv import load_dotenv
import os
import re
from openai import OpenAI
from enum import IntEnum


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


class Sources(IntEnum):
    YOUTUBE = 0
    SPOTIFY = 1
    SOUNDCLOUD = 2


class Constants:
    OPENAI = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
                  "Version/17.5 Safari/605.1.1")
    SOUNDCLOUD = sclib.SoundcloudAPI()
    GENIUS = lyricsgenius.Genius(os.getenv("GENIUS_API_KEY"), timeout=10, verbose=False, remove_section_headers=True,
                                 skip_non_songs=True, retries=5)
    YOUTUBE = googleapiclient.discovery.build("youtube", "v3",
                                              developerKey=os.getenv("YOUTUBE_API_KEY"))
    SPOTIFY = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=os.getenv("SPOTIFY_CLIENT_ID"),
                                                        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
                                                        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URL"),
                                                        scope=os.getenv("SPOTIFY_SCOPE"),
                                                        username=os.getenv("SPOTIFY_USERNAME")))
    YTDL_FORMAT_OPTIONS = {
        "format": "bestaudio",
        "no-playlist": True,
        "no-check-certificates": True,
        "quiet": True,
        "no-warnings": True,
        "default-search": "ytsearch1",
        "force-ipv4": True,
        "no-cache-dir": True,
        "cookies-from-browser": "firefox",
        "downloader": "aria2c",
        "use-extractors": "Youtube",
        "extractor-args": "youtube:formats=dashy;player_client=web;player_skip=configs",
        "concurrent-fragments": 16
    }
    YTDL = yt_dlp.YoutubeDL(YTDL_FORMAT_OPTIONS)
    CARD_VALUE = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "Jack", "Queen", "King", "Ace"]
    CARD_SUIT = {"Clubs": "♧", "Diamonds": "♢", "Hearts": "♡", "Spades": "♤"}
    URL_REGEX = re.compile(r"^(?:https?://)?(?:www\.)?\w+\.([a-z]{2,})/?(.*)$", re.IGNORECASE)
    LIVE_REGEX = re.compile(r"^[(|\[]live[)|\]]$")
    # TIMESTAMP_REGEX = re.compile(r"^(\d{1,2}):(\d{2}):(\d{2})$|^(\d{1,2}):(\d{2})$")
    YOUTUBE_URL = "https://www.youtube.com/watch?v={}"
    YOUTUBE_PLAYLIST_URL = "https://www.youtube.com/playlist?list={}"
    FILTERS = {
        "Disabled": None,
        "Nightcore": '-af "rubberband=pitch={}:tempo=1, aresample=44100"',
        "BassBoost": '-af "bass=g={}, aresample=44100"',
        "EarRape": '-af "acrusher=level_in={}:level_out={}:bits=8:mode=log:aa=1, aresample=44100"'
    }
    EMOJI_DICT = {
        Sources.YOUTUBE: "<:youtube:1267269233772073153>",
        Sources.SPOTIFY: "<:spotify:1267269271390519376>",
        Sources.SOUNDCLOUD: "<:soundcloud:1267269257423618060>"
    }
    ATTACKS = ["a baseball bat", "a crowbar", "their bare fists", "a knife", "a car", "an explosive christmas ornament",
               "a rock", "their mom", "a T-34", "a concealed shiv", "God's hand"]
    SCENES = ["Backyard brawl", "Backstreet brawl", "Saloon brawl", "Pizzeria brawl", "Playground brawl", "Grill brawl"]
    SPOTS = ["back", "knee", "phallus", "head", "face", "neck", "arm", "chest", "ear", "nose", "toe", "buttock"]


def validate_url(url: str):
    regex = re.compile(r"^(?:https?://)?(?:[a-z]{0,4}\.)?([a-zA-Z0-9]{1,10})\.(com|be)/.+$", re.IGNORECASE)
    match = re.match(regex, url)

    return match is not None and match.group(1).lower() in ["youtu", "youtube", "spotify", "soundcloud"]


def validate_timestamp(timestamp: str):
    split_timestamp = timestamp.split(":")

    if len(split_timestamp) > 3 or any(not part.isdigit() for part in split_timestamp):
        return False

    return True


def seconds_to_timestamp(seconds: int):
    hours, minute_remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(minute_remainder, 60)

    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"


def timestamp_to_seconds(timestamp: str):
    if not timestamp:
        return None

    split_timestamp = timestamp.split(":")

    if len(split_timestamp) == 3:
        h, m, s = map(int, split_timestamp)
        seconds = h * 3600 + m * 60 + s
    elif len(split_timestamp) == 2:
        m, s = map(int, split_timestamp)
        seconds = m * 60 + s
    else:
        seconds = int(split_timestamp[0])

    return seconds


def format_timestamp(timestamp: str, comparison: int = None):
    if timestamp == "0:00":
        return "Live"

    split_timestamp = timestamp.split(":")

    if len(split_timestamp) == 3:
        h, m, s = map(int, split_timestamp)
    elif len(split_timestamp) == 2:
        h = 0
        m, s = map(int, split_timestamp)
    else:
        h, m = 0, 0
        s = int(split_timestamp[0])

    seconds = h * 3600 + m * 60 + s

    if comparison and seconds > comparison:
        seconds = comparison

    return seconds_to_timestamp(seconds)

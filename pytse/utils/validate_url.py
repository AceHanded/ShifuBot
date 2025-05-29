import re
from enum import StrEnum

class Patterns(StrEnum):
    DEFAULT = r"^(?:https?:\/\/)?(?:[\w-]+\.)+[a-zA-Z]{2,}(?:\/[^\s]*)?$"
    SOUNDCLOUD = r"^(?:https?:\/\/)?soundcloud\.com\/[\w-]+\/(?:sets\/)?[\w-]+$"
    SPOTIFY = r"^(?:https?:\/\/)?open\.spotify\.com\/(?:track|album|playlist)\/.+$"
    YOUTUBE_MUSIC = r"^(?:https?:\/\/)?music\.youtube\.com\/(?:watch\?v=[\w-]{11}|playlist\?list=.+)$"
    YOUTUBE = r"^(?:https?:\/\/)?(?:(?:www|m)\.)?youtu(?:\.be|be\.com)\/(?:watch\?v=[\w-]{11}(?:&list=.+)?|playlist\?list=.+).*$"

def validate_url(url: str) -> bool | str:
    if re.match(Patterns.SOUNDCLOUD, url): return "soundcloud"
    elif re.match(Patterns.SPOTIFY, url): return "spotify"
    elif re.match(Patterns.YOUTUBE_MUSIC, url): return "youtube_music"
    elif re.match(Patterns.YOUTUBE, url): return "youtube"
    elif re.match(Patterns.DEFAULT, url): return True
    return False

def validate_playlist_url(url: str) -> bool:
    return isinstance(validate_url(url), str) and any(plid in url for plid in ["/sets/", "/album/", "/playlist/", "&list=", "/playlist?list="])

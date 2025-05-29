import re
import json
import asyncio
import urllib.parse
from pytse.utils import request, validate_playlist_url, validate_url
from .youtube_music import search_youtube_music

async def _resolve_track_url(query: str):
    html = await request(f"https://soundcloud.com/search/sounds?q={urllib.parse.quote(query)}", source="soundcloud")
    match = re.search(r'<ul>.+?<li><h2><a href="([^"]+)"', html, re.DOTALL | re.IGNORECASE)

    if match:
        return f"https://soundcloud.com{match.group(1)}"
    
    return ""

async def _resolve_json_data(query: str):
    html = await request(query, source="soundcloud")
    json_str = html.split("sc_hydration = ")[1].split(";</script>")[0]
    if not json_str: raise Exception("Failed to parse initial data")

    return json.loads(json_str)

async def _resolve_playlist_track(track_id: dict[str, None]):
    html = await request(f"https://w.soundcloud.com/player/?url=https%3A//api.soundcloud.com/tracks/{track_id}", source="soundcloud")
    match = re.search(r'<link rel="canonical" href="([^"]+)">', html)

    if match:
        url = match.group(1)
        return await search_soundcloud(url)

async def search_soundcloud(query: str):
    if not validate_url(query): query = await _resolve_track_url(query)
    if not query: raise Exception("Failed to parse search results")
    if validate_playlist_url(query): return await search_soundcloud_playlist(query)

    data = await _resolve_json_data(query)
    sound_data = next((item for item in data if item["hydratable"] == "sound"), {})["data"]
    title = sound_data["title"]
    if sound_data["policy"] == "SNIP": return await search_youtube_music(f"{sound_data['publisher_metadata']['artist']} - {title}")

    duration = int(sound_data["duration"] / 1000)
    uploader = sound_data["user"]["username"]
    uploader_avatar = sound_data["user"]["avatar_url"]

    return { "url": query, "title": title, "duration": duration, "uploader": uploader, "uploader_avatar": uploader_avatar, "source": "soundcloud" }

async def search_soundcloud_playlist(query: str):
    data = await _resolve_json_data(query)
    playlist_data = next((item for item in data if item["hydratable"] == "playlist"), {})["data"]
    playlist_tracks = playlist_data["tracks"]
    if all(track["policy"] == "SNIP" for track in playlist_tracks): return await search_youtube_music(f"{playlist_data['user']['username']} - {playlist_data['title']}", album=True)

    tasks = [_resolve_playlist_track(track["id"]) for track in playlist_tracks]
    tracks = [track for track in await asyncio.gather(*tasks) if track is not None]
    duration = sum(track["duration"] for track in tracks)

    return { "url": query, "title": playlist_data["title"], "duration": duration, "source": "soundcloud", "tracks": tracks }

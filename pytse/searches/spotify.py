import json
import asyncio
import urllib.parse
from pytse.utils import request, validate_playlist_url, validate_url
from .youtube_music import search_youtube_music

async def search_spotify(query: str):
    url_source = validate_url(query)

    if url_source:
        if validate_playlist_url(query): return await search_spotify_playlist(query)
        
        track_id = query.split("/")[-1].split("?")[0]
        track_url = f"https://api.spotify.com/v1/tracks/{track_id}"
    else:
        track_url = f"https://api.spotify.com/v1/search?q={urllib.parse.quote(query)}&type=track&limit=1"

    html = await request(track_url, source="spotify")
    data = json.loads(html)
    if not url_source: data = data["tracks"]["items"][0]

    return await search_youtube_music(f"{', '.join(artist['name'] for artist in data['artists'])} - {data['name']}")

async def search_spotify_playlist(query: str):
    playlist_id = query.split("/")[-1].split("?")[0]
    album = "/album/" in query
    playlist_url = f"https://api.spotify.com/v1/{'albums' if album else 'playlists'}/{playlist_id}"

    if album:
        html = await request(playlist_url, source="spotify")
        data = json.loads(html)

        return await search_youtube_music(f"{', '.join(artist['name'] for artist in data['artists'])} - {data['name']}", album=True)

    playlist_tracks, title = [], ""

    while playlist_url:
        html = await request(playlist_url, source="spotify")
        data = json.loads(html)
        if not title: title = data["name"]

        playlist_tracks.extend([item if album else item["track"] for item in data["tracks"]["items"]])
        playlist_url = data.get("next")

    tasks = [search_youtube_music(f"{', '.join(artist['name'] for artist in track['artists'])} - {track['name']}") for track in playlist_tracks]
    tracks = await asyncio.gather(*tasks)
    duration = sum(track["duration"] for track in tracks)

    return { "url": query, "title": title, "duration": duration, "source": "youtube_music", "tracks": tracks }

import re
import json
import urllib.parse
from pytse.utils import request, parse_duration, validate_playlist_url, validate_url

def _parse_iso_duration(duration: str):
    match = re.match(r"P(\d+)H(\d+)M(\d+)S", duration)
    if match: return parse_duration(f"{match.group(1)}:{match.group(2)}:{match.group(3)}")

    return 0

async def _resolve_track_url(query: str):
    html = await request(f"https://bandcamp.com/search?q={urllib.parse.quote(query)}&item_type=t", source="bandcamp")
    match = re.search(r">(https://[\w-]+\.bandcamp\.com\/track\/[\w-]+)<", html)
    if match: return match.group(1)

    return ""

async def _resolve_json_data(query: str):
    html = await request(query, source="bandcamp")
    json_str = html.split('<script type="application/ld+json">')[1].split("</script>")[0]
    if not json_str: raise Exception("Failed to parse initial data")

    return json.loads(json_str)

async def search_bandcamp(query: str):
    if not validate_url(query): query = await _resolve_track_url(query)
    if not query: raise Exception("Failed to parse search results")
    if validate_playlist_url(query): return await search_bandcamp_playlist(query)

    data = await _resolve_json_data(query)
    duration = _parse_iso_duration(data["duration"])
    uploader = data["byArtist"]["name"]

    return { "url": query, "title": data["name"], "duration": duration, "uploader": uploader, "uploader_avatar": None, "source": "bandcamp" }

async def search_bandcamp_playlist(query: str):
    data = await _resolve_json_data(query)
    uploader = data["byArtist"]["name"]
    
    track_list = data["track"]["itemListElement"]
    tracks = [{
        "url": track["item"]["@id"],
        "title": track["item"]["name"],
        "duration": _parse_iso_duration(track["item"]["duration"]),
        "uploader": uploader,
        "source": "bandcamp"
    } for track in track_list]

    duration = sum(track["duration"] for track in tracks)

    return { "url": query, "title": data["name"], "duration": duration, "source": "bandcamp", "tracks": tracks }

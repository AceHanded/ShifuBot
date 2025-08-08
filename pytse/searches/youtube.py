import re
import json
import urllib.parse
from pytse.utils import parse_duration, request, validate_playlist_url, validate_url

async def _resolve_video_url(query: str):
    html = await request(f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}&sp=EgIQAQ%3D%3D", source="youtube")
    json_str = html.split("var ytInitialData = ")[1].split(";</script>")[0]
    if not json_str: raise Exception("Failed to parse ytInitialData")

    data = json.loads(json_str)
    item_section_renderers = [item for item in data["contents"]["twoColumnSearchResultsRenderer"]["primaryContents"]["sectionListRenderer"]["contents"] if item.get("itemSectionRenderer", {}).get("contents", [{}])[0].get("videoRenderer")]
    if not item_section_renderers: raise Exception("Failed to resolve URL")

    first_video = item_section_renderers[0]["itemSectionRenderer"]["contents"][0]["videoRenderer"]
    video_id = first_video["videoId"]
    
    return f"https://www.youtube.com/watch?v={video_id}"

async def resolve_avatar_and_related(url: str):
    html = await request(url, source="youtube")
    json_str = html.split("var ytInitialData = ")[1].split(";</script>")[0]
    if not json_str: raise Exception("Failed to parse ytInitialData")

    initial_data = json.loads(json_str)
    two_column_results = initial_data["contents"]["twoColumnWatchNextResults"]

    related, lockup_view_models = [], []
    secondary_info_renderers = [item for item in two_column_results["results"]["results"]["contents"] if "videoSecondaryInfoRenderer" in item]
    owner_renderer = secondary_info_renderers[0]["videoSecondaryInfoRenderer"]["owner"]["videoOwnerRenderer"]
    uploader_avatar = owner_renderer["thumbnail"]["thumbnails"][-1]["url"]
    secondary_results = two_column_results["secondaryResults"]["secondaryResults"]["results"]

    try:
        related_video_renderer = secondary_results[1]["itemSectionRenderer"]["contents"] if secondary_results[1].get("itemSectionRenderer") else secondary_results
        lockup_view_models = [item["lockupViewModel"] for item in related_video_renderer if "lockupViewModel" in item]
    except KeyError as e:
        print(e)

    for v in lockup_view_models:
        video_id = v["contentId"]

        if re.match(r"^[\w-]{11}$", video_id):
            related.append({
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "title": v["metadata"]["lockupMetadataViewModel"]["title"]["content"]
            })
    
    return uploader_avatar, related

async def search_youtube(query: str, from_ytm: bool = False, include_avatar_and_related: bool = False):
    if not validate_url(query): query = await _resolve_video_url(query)
    
    modified_query = query.replace("music", "www", 1)
    if validate_playlist_url(query): return await search_youtube_playlist(modified_query, from_ytm)

    source = "youtube_music" if from_ytm else "youtube"
    html = await request(modified_query, source="youtube")
    json_str = html.split("var ytInitialPlayerResponse = ")[1].split(";</script>")[0].split(';var meta')[0]
    if not json_str: raise Exception("Failed to parse ytInitialPlayerResponse")

    player_data = json.loads(json_str)
    title = player_data["videoDetails"]["title"]
    duration = int(player_data["videoDetails"]["lengthSeconds"])
    uploader = player_data["videoDetails"]["author"]
    uploader_avatar, related = None, []

    if include_avatar_and_related:
        uploader_avatar, related = await resolve_avatar_and_related(modified_query)

    return { "url": query, "title": title, "duration": duration, "uploader": uploader, "uploader_avatar": uploader_avatar, "source": source, "related": related }

async def search_youtube_playlist(query: str, from_ytm: bool = False):
    modified_query = f"https://www.youtube.com/playlist?list={match.group(1)}" if (match := re.search(r"[?&]list=([^&]+)", query)) else None
    if not modified_query: raise Exception("Failed to parse playlist URL")

    source = "youtube_music" if from_ytm else "youtube"
    html = await request(modified_query, source="youtube")
    json_str = html.split("var ytInitialData = ")[1].split(";</script>")[0]
    if not json_str: raise Exception("Failed to parse ytInitialData")

    data = json.loads(json_str)
    playlist_contents = data.get("contents")
    if not playlist_contents: return await search_youtube(query.split("&")[0])

    playlist_video_renderers = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"][0]["tabRenderer"]["content"]["sectionListRenderer"]["contents"][0]["itemSectionRenderer"]["contents"][0]["playlistVideoListRenderer"]["contents"]
    tracks = [{
        "url": f"https://{'music' if from_ytm else 'www'}.youtube.com/watch?v={r['playlistVideoRenderer']['videoId']}",
        "title": r["playlistVideoRenderer"]["title"]["runs"][0]["text"],
        "duration": parse_duration(r["playlistVideoRenderer"]["lengthText"]["simpleText"].replace(".", ":")),
        "uploader": r["playlistVideoRenderer"]["shortBylineText"]["runs"][0]["text"],
        "source": source
    } for r in playlist_video_renderers]

    duration = sum(track["duration"] for track in tracks)

    if data["header"].get("playlistHeaderRenderer"):
        title = data["header"]["playlistHeaderRenderer"]["title"]["simpleText"]
    else:
        title = data["header"]["pageHeaderRenderer"]["pageTitle"]

    return { "url": query, "title": title, "duration": duration, "source": source, "tracks": tracks }

import json
import urllib.parse
from pytse.utils import request, validate_url
from .youtube import search_youtube, search_youtube_playlist

async def _resolve_json_data(query: str):
    html = await request(query if validate_url(query) else f"https://music.youtube.com/search?q={urllib.parse.quote(query)}", source="youtube_music")
    initial_data_chunks = [part.split("});")[0].strip() for part in html.split("data: ")[1:]]
    json_str = initial_data_chunks[1] if len(initial_data_chunks) > 1 else initial_data_chunks[0]
    if not json_str: raise Exception("Failed to parse initialData")

    cleaned_json_str = json_str \
        .replace("'", "") \
        .replace("\\x7b", "{") \
        .replace("\\x7d", "}") \
        .replace("\\x22", '"') \
        .replace("\\x5b", "[") \
        .replace("\\x5d", "]") \
        .replace("\\x3d", "=") \
        .replace("\\x27", "'") \
        .replace("\\/", "/") \
        .replace("\\\\\"", "'")
    
    return json.loads(cleaned_json_str)

async def search_youtube_music(query: str, album: bool = False):
    if validate_url(query): return await search_youtube(query, from_ytm=True)

    data = await _resolve_json_data(query)
    section_list_contents = data["contents"]["tabbedSearchResultsRenderer"]["tabs"][0]["tabRenderer"]["content"]["sectionListRenderer"]["contents"]
    music_card_renderers = [item for item in section_list_contents if "musicCardShelfRenderer" in item]
    music_shelf_renderers = [item for item in section_list_contents if "musicShelfRenderer" in item]
    most_popular_renderer = music_card_renderers[0]["musicCardShelfRenderer"]
    navigation_endpoint = most_popular_renderer["title"]["runs"][0]["navigationEndpoint"]
    most_popular_id = None

    if navigation_endpoint.get("watchEndpoint"):
        most_popular_id = navigation_endpoint["watchEndpoint"]["videoId"]
    elif most_popular_renderer.get("contents"):
        most_popular_id = most_popular_renderer["contents"][0]["musicResponsiveListItemRenderer"]["flexColumns"][0]["musicResponsiveListItemFlexColumnRenderer"]["text"]["runs"][0]["navigationEndpoint"]["watchEndpoint"]["videoId"]

    if album:
        if most_popular_id:
            video_id = music_shelf_renderers[2]["musicShelfRenderer"]["contents"][0]["musicResponsiveListItemRenderer"]["overlay"]["musicItemThumbnailOverlayRenderer"]["content"]["musicPlayButtonRenderer"]["playNavigationEndpoint"]["watchPlaylistEndpoint"]["playlistId"]
        else:
            video_id = music_card_renderers[0]["musicCardShelfRenderer"]["buttons"][0]["buttonRenderer"]["command"]["watchPlaylistEndpoint"]["playlistId"]

        url = f"https://music.youtube.com/playlist?list={video_id}"

        return await search_youtube_playlist(url, from_ytm=True)
    
    if most_popular_id:
        video_id = most_popular_id
    else:
        video_id = music_shelf_renderers[0]["musicShelfRenderer"]["contents"][0]["musicResponsiveListItemRenderer"]["flexColumns"][0]["musicResponsiveListItemFlexColumnRenderer"]["text"]["runs"][0]["navigationEndpoint"]["watchEndpoint"]["videoId"]

    url = f"https://music.youtube.com/watch?v={video_id}"

    return await search_youtube(url, from_ytm=True)

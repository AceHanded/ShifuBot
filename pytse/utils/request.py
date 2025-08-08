import json
import time
import base64
import aiohttp
import requests
from pathlib import Path
from dotenv import dotenv_values

with open("./data/cookies.json", "r") as f:
    cookies = json.load(f)

config = dotenv_values(".env")
cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies if c["name"] in ["SID", "HSID", "SSID", "APISID", "SAPISID", "PAPISID", "YSC"])
access_token = {"token": None, "expiry": 0}
session = None

def _get_headers(source: str) -> dict[str, str]:
    if source == "bandcamp":
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
            "Accept-Language": "fi-FI,fi;q=0.8,en-US;q=0.5,en;q=0.3",
            "Referer": "https://bandcamp.com/"
        }
    elif source == "soundcloud":
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
            "Accept-Language": "fi-FI,fi;q=0.8,en-US;q=0.5,en;q=0.3",
            "Referer": "https://soundcloud.com/",
            "Origin": "https://www.soundcloud.com"
        }
    elif source == "spotify":
        return {
            "Authorization": f"Bearer {access_token['token']}"
        }
    elif source == "youtube_music":
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
            "Accept-Language": "fi-FI,fi;q=0.8,en-US;q=0.5,en;q=0.3",
            "Referer": "https://music.youtube.com/",
            "Origin": "https://music.youtube.com",
            "Cookie": cookie_header
        }
    elif source == "youtube":
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
            "Accept-Language": "fi-FI,fi;q=0.8,en-US;q=0.5,en;q=0.3",
            "Referer": "https://www.youtube.com/",
            "Origin": "https://www.youtube.com",
            "Cookie": cookie_header
        }
    else:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
            "Accept-Language": "fi-FI,fi;q=0.8,en-US;q=0.5,en;q=0.3"
        }

def _fetch_access_token() -> dict[str, str | int]:
    credentials = f"{config['SPOTIFY_CID']}:{config['SPOTIFY_SECRET']}"
    encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")

    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "client_credentials"
    }
    response = requests.post("https://accounts.spotify.com/api/token", headers=headers, data=data)
    if not response.ok: raise Exception(f"Failed to fetch access token: {response.status_code} - {response.text}")
    
    data = response.json()
    return {
        "token": data["access_token"],
        "expiry": int(time.time()) + data["expires_in"]
    }

async def close_aiohttp_session() -> None:
    if session: await session.close()

async def request(url: str, source: str) -> str:
    global access_token, session

    if source in [f.stem for f in Path("./pytse/searches").glob("*.py") if f.is_file() and f.name != "__init__.py"]:
        if source == "spotify" and (not access_token["token"] or int(time.time()) >= access_token["expiry"]):
            access_token = _fetch_access_token()

    if not session: session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=25))

    async with session.get(url, headers=_get_headers(source)) as response:
        if not response.ok: raise Exception(f"Failed to fetch: {response.status} - {response.text}")
        return await response.text()

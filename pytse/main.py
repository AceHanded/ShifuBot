import re
import random
import asyncio
import importlib
from pathlib import Path
from pytse.utils import validate_url

async def search(query: str, keyword_source: str = "youtube"):
    url_source = validate_url(query)

    if url_source:
        if not re.match(r"^https?://", query): query = f"https://{query}"
        if not (url_source == "youtube" and "&list=" in query): query = query.split("&")[0]

    await asyncio.sleep(random.randint(100, 300) / 1000)
   
    try:
        if url_source and url_source in [f.stem for f in Path("./pytse/searches").glob("*.py") if f.is_file() and f.name != "__init__.py"]:
            return await getattr(importlib.import_module(f"pytse.searches.{url_source}"), f"search_{url_source}")(query)
        elif url_source:
            return { "url": query, "title": None, "duration": None, "uploader_avatar": None, "source": None }
        
        return await getattr(importlib.import_module(f"pytse.searches.{keyword_source}"), f"search_{keyword_source}")(query)
    except Exception as e:
        print(f"Error occured inside a subsearch module: {e}")
        return { "url": query, "title": None, "duration": None, "uploader_avatar": None, "source": None, "_error": True }

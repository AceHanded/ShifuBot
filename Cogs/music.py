from youtubesearchpython.__future__ import Video
from youtubesearchpython import VideosSearch
import discord
from discord.ext import commands
from discord.ui import Button, Select, View
from pytubefix import YouTube, Playlist
from pytubefix.exceptions import AgeRestrictedError
import asyncio
import re
import random
import time
from sclib import Track as SCTrack, Playlist as SCPlaylist
from spotipy.exceptions import SpotifyException
import requests
from requests_html import HTMLSession
import googleapiclient.errors
from Cogs.utils import (Constants, Sources, seconds_to_timestamp, timestamp_to_seconds,
                        format_timestamp, validate_timestamp, validate_url)


QUEUE_LIST = []


class PytubeSource(discord.PCMVolumeTransformer):
    def __init__(self, source: any, *, data: any, volume: float = 0.50):
        super().__init__(source, volume)
        self.data = data

    @classmethod
    async def from_url(cls, url: str, *, loop: any = None, filter_: str = None, start_at: int = None):
        ffmpeg_options = {"before_options": f"{f'-ss {start_at}' if start_at else ''} "
                                            f"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                          "options": f"{f'-vn {filter_}' if filter_ else ''}"}

        def get_youtube_audio_url(url_: str):
            yt = YouTube(url_, use_oauth=False, allow_oauth_cache=False)
            audio_stream = yt.streams.filter(only_audio=True).first()
            return audio_stream.url

        loop = loop or asyncio.get_event_loop()
        audio_url = await loop.run_in_executor(None, lambda: get_youtube_audio_url(url))

        return cls(discord.FFmpegPCMAudio(audio_url, **ffmpeg_options), data={"url": url})


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source: any, *, data: any, volume: float = 0.50):
        super().__init__(source, volume)

        self.data = data

    @classmethod
    async def from_url(cls, url: str, *, loop: any = None, stream: bool = False, filter_: str = None,
                       start_at: int = None):
        ffmpeg_options = {"before_options": f"{f'-ss {start_at}' if start_at else ''} "
                                            f"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                          "options": f"{f'-vn {filter_}' if filter_ else ''}"}
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: Constants.YTDL.extract_info(url, download=not stream))

        if "entries" in data:
            data = data["entries"][0]

        filename = data["url"] if stream else Constants.YTDL.prepare_filename(data)

        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class PlayerEntry:
    def __init__(self, title: str, url: str, duration: str, uploader: str, uploader_id: str, start: int = 0,
                 filter_: dict[str, any] = None, source: any = None):
        self.title = title
        self.url = url
        self.duration = duration
        self.uploader = uploader
        self.uploader_id = uploader_id
        self.start = start
        self.filter_ = filter_
        self.source = source

    def __str__(self):
        return self.title

    def set_filter(self, filter_: dict[str, any]):
        self.filter_ = filter_

    def set_start(self, start: int):
        self.start = start

    def set_source(self, source: any):
        self.source = source

    def set_volume(self, volume: float):
        if self.source:
            self.source.volume = volume


class Music(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

        self.queue = {}
        self.previous = {}
        self.booleans = {}
        self.filters = {}
        self.volume = {}
        self.elapsed_time = {}
        self.text_channel = {}
        self.loop = {}
        self.messages = {}
        self.removed = {}
        self.button_invoker = {}
        self.gui = {}
        self.views = {}
        self.autoplay = {}

    def store_queue_count(self):
        global QUEUE_LIST
        QUEUE_LIST = [guild_id for guild_id in self.queue]

    def count_elapsed_time(self, ctx: discord.ApplicationContext):
        if not self.elapsed_time[ctx.guild.id]["start"]:
            return 0

        self.elapsed_time[ctx.guild.id]["current"] = time.time()

        if self.elapsed_time[ctx.guild.id]["pause_start"]:
            return int((self.elapsed_time[ctx.guild.id]["current"] - self.elapsed_time[ctx.guild.id]["start"]) -
                       (self.elapsed_time[ctx.guild.id]["current"] - self.elapsed_time[ctx.guild.id]["pause_start"]))
        else:
            return int(self.elapsed_time[ctx.guild.id]["current"] - self.elapsed_time[ctx.guild.id]["start"] -
                       self.elapsed_time[ctx.guild.id]["pause"] + self.elapsed_time[ctx.guild.id]["seek"])

    def resolve_view(self, ctx: discord.ApplicationContext):
        if not (len(self.queue[ctx.guild.id]) - 1) and not self.previous[ctx.guild.id]:
            return self.views[ctx.guild.id]["no_remove_and_back"]
        elif (len(self.queue[ctx.guild.id]) - 1) and not self.previous[ctx.guild.id]:
            return self.views[ctx.guild.id]["no_back"]
        elif not (len(self.queue[ctx.guild.id]) - 1) and self.previous[ctx.guild.id]:
            return self.views[ctx.guild.id]["no_remove"]
        else:
            return self.views[ctx.guild.id]["all"]

    @staticmethod
    async def connect_handling(ctx: discord.ApplicationContext, play: bool = False):
        if not ctx.author.voice:
            embed = discord.Embed(
                description=f"**Note:** Please connect to a voice channel first.",
                color=discord.Color.blue()
            )
            await ctx.respond(embed=embed)
            return

        channel = ctx.author.voice.channel

        if not ctx.voice_client:
            embed = discord.Embed(
                description=f"**Connecting to voice channel:** <#{channel.id}>",
                color=discord.Color.dark_green()
            )
            await ctx.respond(embed=embed)

            await channel.connect()
            await ctx.guild.change_voice_state(channel=channel, self_mute=False, self_deaf=True)
        elif channel != ctx.voice_client.channel:
            embed = discord.Embed(
                description=f"**Moving to voice channel:** <#{channel.id}>",
                color=discord.Color.dark_green()
            )
            await ctx.respond(embed=embed)

            await ctx.voice_client.move_to(channel)
            await ctx.guild.change_voice_state(channel=channel, self_mute=False, self_deaf=True)
        elif ctx.voice_client and channel == ctx.voice_client.channel and not play:
            embed = discord.Embed(
                description=f"**Error:** Already connected to voice channel `{channel}`.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)

        return channel

    @staticmethod
    async def get_video_info(query: str, is_url: bool = False, ignore_live: bool = False):
        if is_url:
            return await Video.getInfo(query)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None,
                                              lambda: VideosSearch(query, limit=1 if not ignore_live else 10).result())

    @staticmethod
    async def get_spotify_tracks(info_dict: dict[str, any], is_playlist: bool = False):
        track_list = []

        tracks = info_dict["items"]

        while info_dict["next"]:
            info_dict = Constants.SPOTIFY.next(info_dict)
            tracks.extend(info_dict["items"])

        for track in tracks:
            if is_playlist:
                track_info = track["track"]
            else:
                track_info = track

            try:
                artist = track_info["album"]["artists"][0]["name"] if is_playlist else track_info["artists"][0]["name"]

                if artist != "Various Artists":
                    track_list.append(f"{artist} - {track_info['name']}")
                else:
                    track_list.append(track_info["name"])
            except IndexError:
                track_list.append(track_info["name"])
            except TypeError:
                continue

        return track_list

    async def cleanup(self, ctx: any):
        try:
            await self.messages[ctx.guild.id]["main"].edit(view=None)
        except (discord.NotFound, discord.HTTPException, AttributeError):
            pass

        for dictionary in [self.queue, self.previous, self.booleans, self.filters, self.volume, self.elapsed_time,
                           self.text_channel, self.loop, self.messages, self.button_invoker, self.gui, self.views,
                           self.removed, self.autoplay]:
            if ctx.guild.id in dictionary:
                del dictionary[ctx.guild.id]
        self.store_queue_count()

    async def resolve_source(self, ctx: discord.ApplicationContext, filter_: str, start: int):
        if ctx.guild.id not in self.queue:
            return

        try:
            source = await PytubeSource.from_url(self.queue[ctx.guild.id][0].url, loop=self.bot.loop, filter_=filter_,
                                                 start_at=start)
        except (AgeRestrictedError, AttributeError):
            source = await YTDLSource.from_url(self.queue[ctx.guild.id][0].url, loop=self.bot.loop, stream=True,
                                               filter_=filter_, start_at=start)

        self.queue[ctx.guild.id][0].set_source(source)
        self.queue[ctx.guild.id][0].filter_ = self.filters[ctx.guild.id]
        self.queue[ctx.guild.id][0].source.volume = self.volume[ctx.guild.id]

        return source

    async def song_addition_handling(self, ctx: discord.ApplicationContext, query: str, is_url: bool = False,
                                     insert: int = None, ignore_live: bool = False, start_at: str = None,
                                     type_: Sources = Sources.YOUTUBE):
        if is_url:
            try:
                result: dict = await self.get_video_info(query, is_url=True)
            except ValueError:
                result: dict = await self.get_video_info(Constants.YOUTUBE_URL.format(query.split("/")[-1]),
                                                         is_url=True)
        else:
            search: dict = await self.get_video_info(query, ignore_live=ignore_live)

            if not search["result"]:
                embed = discord.Embed(
                    description=f"**Error:** No videos found for query `{query}`.",
                    color=discord.Color.red()
                )
                await ctx.respond(embed=embed)
                return

            result = search["result"][0] if not ignore_live else \
                next((item for item in search["result"] if not re.match(Constants.LIVE_REGEX, item["title"].lower())),
                     search["result"][0])

        player_entry = PlayerEntry(
            result["title"], result["link"],
            seconds_to_timestamp(int(result["duration"]["secondsText"])) if is_url else result["duration"],
            result["channel"]["name"], result["channel"]["id"], timestamp_to_seconds(start_at)
        )
        self.queue[ctx.guild.id].append(player_entry)
        dur = player_entry.duration

        if ctx.voice_client.is_playing() and not insert:
            embed = discord.Embed(
                description=f"**{Constants.EMOJI_DICT[type_]} Added to queue:** "
                            f"[{player_entry.title}]({player_entry.url}) "
                            f"[**{f'{format_timestamp(start_at, timestamp_to_seconds(dur))} -> ' if start_at else ''}"
                            f"{format_timestamp(dur)}**] [**{len(self.queue[ctx.guild.id]) - 1}**]",
                color=discord.Color.dark_green()
            )
            await ctx.respond(embed=embed)
        elif ctx.voice_client.is_playing() and insert:
            embed = discord.Embed(
                description=f"**{Constants.EMOJI_DICT[type_]} Inserted to queue:** "
                            f"[{player_entry.title}]({player_entry.url}) "
                            f"[**{f'{format_timestamp(start_at, timestamp_to_seconds(dur))} -> ' if start_at else ''}"
                            f"{format_timestamp(dur)}**] [**{insert}**]",
                color=discord.Color.dark_green()
            )
            await ctx.respond(embed=embed)

    async def playlist_addition_handling(self, ctx: discord.ApplicationContext, queries: list[str], title: str,
                                         url: str, has_urls: bool = False, ignore_live: bool = False,
                                         pre_shuffle: bool = False, type_: any = Sources.YOUTUBE):
        embed = discord.Embed(
            description=f"Adding **{len(queries)}** song(s) to queue from the playlist: {title}\n"
                        f"This will take **a moment...**",
            color=discord.Color.dark_green()
        )
        msg = await ctx.respond(embed=embed)

        results = list(await asyncio.gather(*(self.get_video_info(res, is_url=has_urls, ignore_live=ignore_live) for
                                              res in queries)))

        if pre_shuffle:
            random.shuffle(results)

        if type_ == Sources.YOUTUBE:
            durations = [int(res["duration"]["secondsText"]) if has_urls else res["duration"] for res in results]

            for result in results:
                player_entry = PlayerEntry(
                    result["title"], result["link"],
                    seconds_to_timestamp(int(result["duration"]["secondsText"])),
                    result["channel"]["name"], result["channel"]["id"]
                )
                self.queue[ctx.guild.id].append(player_entry)
        else:
            durations = [timestamp_to_seconds(res["result"][0]["duration"]) for res in results]

            for result in results:
                player_entry = PlayerEntry(
                    result["result"][0]["title"], result["result"][0]["link"], result["result"][0]["duration"],
                    result["result"][0]["channel"]["name"], result["result"][0]["channel"]["id"]
                )
                self.queue[ctx.guild.id].append(player_entry)

        embed = discord.Embed(
            description=f"{Constants.EMOJI_DICT[type_]} Successfully added **{len(results)}** song(s) to queue"
                        f"{' **pre-shuffled**' if pre_shuffle else ''} from the playlist: [{title}]({url}) "
                        f"[**{seconds_to_timestamp(sum(durations))}**]",
            color=discord.Color.dark_green()
        )
        await msg.edit(embed=embed)

    async def populate_select_menu(self, ctx: discord.ApplicationContext):
        rel = await self.get_related_videos(ctx, self.queue[ctx.guild.id][0].url)

        select_options = [discord.SelectOption(label=entry[0], value=entry[1], description=entry[2]) for entry in rel]

        if not select_options:
            self.gui[ctx.guild.id]["select"].options = [discord.SelectOption(
                label=self.queue[ctx.guild.id][0].title, value=self.queue[ctx.guild.id][0].url,
                description=self.queue[ctx.guild.id][0].uploader)]
            return

        self.gui[ctx.guild.id]["select"].options = select_options

    async def get_related_videos(self, ctx: discord.ApplicationContext, url: str, first: bool = False):
        headers = {"User-Agent": Constants.USER_AGENT}
        response = HTMLSession().get(url, headers=headers)
        related = re.findall(r'"/watch\?v=([^"\\]*)"', response.text)
        previous_ids = [entry.url.split("?v=")[1] for entry in self.previous[ctx.guild.id]]

        related_list = []
        for entry in related:
            if entry != url.split("?v=")[1] and entry not in previous_ids:
                try:
                    response = Constants.YOUTUBE.videos().list(part="snippet", id=entry).execute()
                except googleapiclient.errors.HttpError:
                    break
                video = response["items"][0]
                related_list.append((video["snippet"]["title"], Constants.YOUTUBE_URL.format(entry),
                                     video["snippet"]["channelTitle"]))

            if (first and len(related_list) == 1) or len(related_list) == 5:
                break

        return related_list

    async def resolve_gui_callback(self, ctx: discord.ApplicationContext, gui_element: str):
        async def select_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            result: dict = await self.get_video_info(self.gui[ctx.guild.id]["select"].values[0], is_url=True)

            player_entry = PlayerEntry(
                result["title"], result["link"],
                seconds_to_timestamp(int(result["duration"]["secondsText"])),
                result["channel"]["name"], result["channel"]["id"]
            )
            self.queue[ctx.guild.id].append(player_entry)

            embed = discord.Embed(
                description=f"**{Constants.EMOJI_DICT[Sources.YOUTUBE]} Added to queue:** [{player_entry.title}]"
                            f"({player_entry.url}) [**{format_timestamp(player_entry.duration)}**] "
                            f"[**{len(self.queue[ctx.guild.id]) - 1}**]",
                color=discord.Color.dark_green()
            )
            embed.set_footer(text=f"Requested via a suggestion [{interaction.user.name}]")
            await ctx.send(embed=embed)

        async def pause_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            self.button_invoker[ctx.guild.id] = interaction.user.name
            await self.pause(ctx)

            if ctx.voice_client and ctx.voice_client.is_paused():
                self.gui[ctx.guild.id]["pause"].style = discord.ButtonStyle.primary
            else:
                self.gui[ctx.guild.id]["pause"].style = discord.ButtonStyle.secondary

            self.button_invoker[ctx.guild.id] = None
            await interaction.message.edit(view=self.resolve_view(ctx))

        async def skip_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            self.button_invoker[ctx.guild.id] = interaction.user.name
            await self.skip(ctx)
            self.button_invoker[ctx.guild.id] = None

        async def remove_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            self.button_invoker[ctx.guild.id] = interaction.user.name
            await self.remove(ctx, from_="1")
            self.button_invoker[ctx.guild.id] = None
            await interaction.message.edit(view=self.resolve_view(ctx))

        async def back_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            self.button_invoker[ctx.guild.id] = interaction.user.name
            await self.replay(ctx, instant=True)
            self.button_invoker[ctx.guild.id] = None

        async def volume_min_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            self.button_invoker[ctx.guild.id] = interaction.user.name
            await self.volume_(ctx, level=0)
            self.button_invoker[ctx.guild.id] = None

        async def volume_down_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            self.button_invoker[ctx.guild.id] = interaction.user.name
            await self.volume_(ctx, level=(self.queue[ctx.guild.id][0].source.volume * 100) - 10)
            self.button_invoker[ctx.guild.id] = None

        async def volume_mid_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            self.button_invoker[ctx.guild.id] = interaction.user.name
            await self.volume_(ctx, level=50)
            self.button_invoker[ctx.guild.id] = None

        async def volume_up_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            self.button_invoker[ctx.guild.id] = interaction.user.name
            await self.volume_(ctx, level=(self.queue[ctx.guild.id][0].source.volume * 100) + 10)
            self.button_invoker[ctx.guild.id] = None

        async def volume_max_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            self.button_invoker[ctx.guild.id] = interaction.user.name
            await self.volume_(ctx, level=200)
            self.button_invoker[ctx.guild.id] = None

        async def loop_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            self.button_invoker[ctx.guild.id] = interaction.user.name

            if self.loop[ctx.guild.id]["mode"] == "Disabled":
                await self.loop_(ctx, mode="Single")
                self.gui[ctx.guild.id]["loop"].style = discord.ButtonStyle.primary
            elif self.loop[ctx.guild.id]["mode"] == "Single":
                await self.loop_(ctx, mode="Queue")
                self.gui[ctx.guild.id]["loop"].style = discord.ButtonStyle.success
            else:
                await self.loop_(ctx, mode="Disabled")
                self.gui[ctx.guild.id]["loop"].style = discord.ButtonStyle.secondary

            self.button_invoker[ctx.guild.id] = None
            await interaction.message.edit(view=self.resolve_view(ctx))

        callbacks = {
            "select": select_callback,
            "back": back_callback,
            "pause": pause_callback,
            "skip": skip_callback,
            "loop": loop_callback,
            "remove": remove_callback,
            "volume_min": volume_min_callback,
            "volume_down": volume_down_callback,
            "volume_mid": volume_mid_callback,
            "volume_up": volume_up_callback,
            "volume_max": volume_max_callback,
        }
        return callbacks[gui_element]

    async def after_song(self, ctx: discord.ApplicationContext, e: any):
        if ctx.guild.id not in self.queue or not self.queue[ctx.guild.id]:
            return
        elif e:
            print(f"Error occurred after playing: {e}")

        try:
            if self.booleans[ctx.guild.id]["clear_elapsed"]:
                await self.messages[ctx.guild.id]["main"].edit(view=None)
        except (discord.NotFound, discord.HTTPException):
            pass

        last_song = self.queue[ctx.guild.id][0]

        if self.loop[ctx.guild.id]["mode"] != "Single":
            self.loop[ctx.guild.id]["count"] = 0

        if self.booleans[ctx.guild.id]["clear_elapsed"] and self.loop[ctx.guild.id]["mode"] == "Disabled":
            if not self.booleans[ctx.guild.id]["backed"]:
                self.previous[ctx.guild.id].append(self.queue[ctx.guild.id].pop(0))
            else:
                self.queue[ctx.guild.id].pop(0)
        elif ((self.booleans[ctx.guild.id]["clear_elapsed"] and self.loop[ctx.guild.id]["mode"] != "Disabled") or
              not self.booleans[ctx.guild.id]["clear_elapsed"]):
            self.queue[ctx.guild.id].pop(0)

        if self.booleans[ctx.guild.id]["clear_elapsed"] and self.loop[ctx.guild.id]["mode"] != "Disabled":
            copied_last_song = PlayerEntry(
                last_song.title, last_song.url, last_song.duration, last_song.uploader, last_song.uploader_id,
                0, last_song.filter_, last_song.source
            )
            self.queue[ctx.guild.id].append(copied_last_song) if self.loop[ctx.guild.id]["mode"] == "Queue" else \
                self.queue[ctx.guild.id].insert(0, copied_last_song)

        for key in self.elapsed_time[ctx.guild.id].keys():
            if ctx.voice_client and not self.booleans[ctx.guild.id]["clear_elapsed"]:
                continue
            self.elapsed_time[ctx.guild.id][key] = 0

        if self.queue[ctx.guild.id]:
            await self.bot.loop.create_task(self.play_next(ctx))
        elif self.autoplay[ctx.guild.id] == "Enabled":
            related = await self.get_related_videos(ctx, self.previous[ctx.guild.id][-1].url, first=True)
            await self.play(ctx, related[0][1])

    async def play_next(self, ctx: discord.ApplicationContext):
        if ctx.guild.id not in self.queue or not self.queue[ctx.guild.id]:
            return

        filter_val = self.queue[ctx.guild.id][0].filter_["value"] if self.queue[ctx.guild.id][0].filter_ else None
        start_val = self.queue[ctx.guild.id][0].start

        source = await self.resolve_source(ctx, filter_val, start_val)

        if not source:
            return

        ctx.voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(self.after_song(ctx, e),
                                                                                       self.bot.loop))
        self.elapsed_time[ctx.guild.id]["start"] = time.time()

        if start_val:
            self.elapsed_time[ctx.guild.id]["seek"] = start_val
            self.booleans[ctx.guild.id]["clear_elapsed"] = False

        if not self.booleans[ctx.guild.id]["first"] and not self.booleans[ctx.guild.id]["ignore_msg"] and \
                self.loop[ctx.guild.id]["count"] == 0:
            try:
                response = Constants.YOUTUBE.channels().list(part="snippet",
                                                             id=self.queue[ctx.guild.id][0].uploader_id).execute()
                uploader_picture_url = response["items"][0]["snippet"]["thumbnails"]["high"]["url"]
            except (IndexError, googleapiclient.errors.HttpError):
                uploader_picture_url = None

            for key in self.messages[ctx.guild.id].keys():
                self.messages[ctx.guild.id][key] = None if key != "main" else self.messages[ctx.guild.id][key]
            self.removed[ctx.guild.id].clear()

            await self.populate_select_menu(ctx)

            now_playing_msg = (
                f"**♪ Now playing:** " if self.loop[ctx.guild.id]["mode"] == "Disabled" else
                f"**∞ Now looping:** " if self.loop[ctx.guild.id]["mode"] == "Single" else f"**∞ Now in loop:** "
            )
            next_in_queue_msg = (
                f"**Next in {'loop' if self.loop[ctx.guild.id]['mode'] == 'Queue' else 'queue'}:** "
                f"[{self.queue[ctx.guild.id][1].title}]({self.queue[ctx.guild.id][1].url})"
                if len(self.queue[ctx.guild.id]) > 1 else "**Note:** No further songs in queue."
            )
            dur = self.queue[ctx.guild.id][0].duration

            embed = discord.Embed(
                description=f"{now_playing_msg}[{self.queue[ctx.guild.id][0].title}]({self.queue[ctx.guild.id][0].url})"
                            f" [**{f'{seconds_to_timestamp(start_val)} -> ' if start_val else ''}"
                            f"{format_timestamp(dur)}**] [**{len(self.previous[ctx.guild.id]) + 1} | "
                            f"{len(self.queue[ctx.guild.id]) + len(self.previous[ctx.guild.id])}**]\n"
                            f"{next_in_queue_msg}",
                color=discord.Color.dark_green()
            )
            embed.set_footer(text=self.queue[ctx.guild.id][0].uploader, icon_url=uploader_picture_url)
            self.messages[ctx.guild.id]["main"] = await ctx.send(embed=embed, view=self.resolve_view(ctx))
        elif not self.booleans[ctx.guild.id]["first"] and not self.booleans[ctx.guild.id]["ignore_msg"] and \
                self.loop[ctx.guild.id]["count"] > 0:
            channel = self.bot.get_guild(int(ctx.guild.id)).get_channel(self.text_channel[ctx.guild.id])

            try:
                message = await channel.fetch_message(self.messages[ctx.guild.id]["main"].id)
                embed_description = message.embeds[0].description.split("\n\n")[0]

                embed = discord.Embed(
                    description=f"{embed_description}\n\n**Looped: "
                                f"{self.loop[ctx.guild.id]['count']}** time(s)",
                    color=discord.Color.dark_green()
                )
                embed.set_footer(text=message.embeds[0].footer.text, icon_url=message.embeds[0].footer.icon_url)
                await message.edit(embed=embed, view=self.resolve_view(ctx))
            except discord.NotFound:
                pass

        self.booleans[ctx.guild.id]["first"] = False
        self.booleans[ctx.guild.id]["ignore_msg"] = False
        self.booleans[ctx.guild.id]["clear_elapsed"] = True
        self.booleans[ctx.guild.id]["backed"] = False

        self.loop[ctx.guild.id]["count"] += 1 if self.loop[ctx.guild.id]["mode"] == "Single" else \
            -(self.loop[ctx.guild.id]["count"])

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, _):
        if not before.channel:
            return

        if member.guild.voice_client and member.guild.voice_client.channel == before.channel:
            text_channel = self.bot.get_channel(self.text_channel[member.guild.id])

            if len(before.channel.members) < 2 or all([member.bot for member in before.channel.members]):
                await self.cleanup(member)

                try:
                    await member.guild.voice_client.disconnect()

                    embed = discord.Embed(
                        description=f"**Everyone has left the voice channel:** {before.channel}",
                        color=discord.Color.dark_red(),
                    )
                    embed.set_footer(text="Disconnecting, until next time.")
                    await text_channel.send(embed=embed)
                except AttributeError:
                    embed = discord.Embed(
                        description=f"**Disconnecting from current voice channel:** {before.channel}",
                        color=discord.Color.dark_red(),
                    )
                    await text_channel.send(embed=embed)

    @commands.slash_command(description="Invites the bot to the voice channel")
    async def connect(self, ctx: discord.ApplicationContext):
        await ctx.defer()

        channel = await self.connect_handling(ctx)

        if not channel:
            await self.cleanup(ctx)
            return

        self.text_channel[ctx.guild.id] = ctx.channel.id

    @commands.slash_command(description="Removes the bot from the voice channel and clears the queue")
    @discord.option(name="after_song", description="Disconnects once current song has ended", required=False)
    async def disconnect(self, ctx: discord.ApplicationContext, after_song: bool = False):
        await ctx.defer()

        if not ctx.voice_client:
            embed = discord.Embed(
                description="**Error:** Already not connected to a voice channel.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        if after_song and ctx.voice_client.is_playing():
            embed = discord.Embed(
                description=f"**Disconnecting after current song:** {self.queue[ctx.guild.id][0].title} "
                            f"[**{seconds_to_timestamp(self.count_elapsed_time(ctx))} | "
                            f"{self.queue[ctx.guild.id][0].duration}**]",
                color=discord.Color.dark_red()
            )
            await ctx.respond(embed=embed)

            while (ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()) or
                   self.elapsed_time[ctx.guild.id]["seek"]):
                await asyncio.sleep(.1)

        embed = discord.Embed(
            description=f"**Disconnecting from current voice channel:** {ctx.voice_client.channel}",
            color=discord.Color.dark_red()
        )
        await ctx.respond(embed=embed)

        await ctx.voice_client.disconnect()
        await self.cleanup(ctx)

    @commands.slash_command(description="Adds and plays songs in the queue")
    @discord.option(name="query",
                    description="The song that you want to play (SoundCloud/Spotify/YouTube URL, or query)",
                    required=True)
    @discord.option(name="insert", description="Add the song to the given position in queue", required=False)
    @discord.option(name="pre_shuffle", description="Shuffle the songs of the playlist ahead of time", required=False)
    @discord.option(name="start_at", description="Sets the song to start from the given timestamp", required=False)
    @discord.option(name="ignore_live", description="Attempts to ignore songs with '(live)' in their name",
                    required=False)
    async def play(self, ctx: discord.ApplicationContext, query: str, insert: int = None, pre_shuffle: bool = False,
                   start_at: str = None, ignore_live: bool = False):
        try:
            await ctx.defer()
        except (discord.ApplicationCommandInvokeError, discord.InteractionResponded, discord.NotFound):
            pass

        channel = await self.connect_handling(ctx, play=True)

        if not channel:
            if not ctx.voice_client:
                await self.cleanup(ctx)
            return

        self.text_channel[ctx.guild.id] = ctx.channel.id

        insert = max(1, min(insert, len(self.queue[ctx.guild.id]))) if insert else None

        if start_at and not validate_timestamp(start_at):
            embed = discord.Embed(
                description="**Note:** Invalid timestamp format (hh:mm:ss). Defaulting to 0:00.",
                color=discord.Color.blue()
            )
            await ctx.respond(embed=embed)
            start_at = None

        if re.match(Constants.URL_REGEX, query) and not validate_url(query):
            embed = discord.Embed(
                description="**Error:** Invalid URL.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return
        elif re.match(Constants.URL_REGEX, query) and validate_url(query):
            if "youtu" in query and "list=" in query:
                playlist_url = Constants.YOUTUBE_PLAYLIST_URL.format(query.split("list=")[1])
                playlist_entries = Playlist(playlist_url)

                try:
                    await self.playlist_addition_handling(ctx, list(playlist_entries), playlist_entries.title, query,
                                                          has_urls=True, pre_shuffle=pre_shuffle)
                except KeyError:
                    embed = discord.Embed(
                        description=f"**Note:** Unsupported playlist type; adding first song to queue.",
                        color=discord.Color.blue()
                    )
                    await ctx.respond(embed=embed)

                    await self.song_addition_handling(ctx,
                                                      f"www.youtube.com/watch?v={query.split('?v=')[-1].split('&')[0]}",
                                                      is_url=True, insert=insert, start_at=start_at)
            elif "spotify.com/playlist" in query:
                try:
                    spotify_result = Constants.SPOTIFY.playlist_items(playlist_id=query)
                    playlist_name = Constants.SPOTIFY.playlist(playlist_id=query, fields="name")["name"]
                except SpotifyException:
                    embed = discord.Embed(
                        description=f"**Error:** Invalid Spotify URL.",
                        color=discord.Color.red()
                    )
                    await ctx.respond(embed=embed)
                    return

                playlist_entries = await self.get_spotify_tracks(spotify_result, is_playlist=True)
                await self.playlist_addition_handling(ctx, playlist_entries, playlist_name, query,
                                                      pre_shuffle=pre_shuffle, type_=Sources.SPOTIFY)
            elif "spotify.com/album" in query:
                try:
                    spotify_result = Constants.SPOTIFY.album_tracks(album_id=query)
                    playlist_name = Constants.SPOTIFY.album(album_id=query)["name"]
                except SpotifyException:
                    embed = discord.Embed(
                        description=f"**Error:** Invalid Spotify URL.",
                        color=discord.Color.red()
                    )
                    await ctx.respond(embed=embed)
                    return

                playlist_entries = await self.get_spotify_tracks(spotify_result)
                await self.playlist_addition_handling(ctx, playlist_entries, playlist_name, query,
                                                      ignore_live=ignore_live, pre_shuffle=pre_shuffle,
                                                      type_=Sources.SPOTIFY)
            elif "spotify.com/track" in query:
                try:
                    spotify_result = Constants.SPOTIFY.track(track_id=query)
                except SpotifyException:
                    embed = discord.Embed(
                        description=f"**Error:** Invalid Spotify URL.",
                        color=discord.Color.red()
                    )
                    await ctx.respond(embed=embed)
                    return

                try:
                    if spotify_result["album"]["artists"][0]["name"] != "Various Artists":
                        spotify_query = f"{spotify_result['album']['artists'][0]['name']} - {spotify_result['name']}"
                    else:
                        spotify_query = spotify_result["name"]
                except IndexError:
                    spotify_query = spotify_result["name"]

                await self.song_addition_handling(ctx, spotify_query, insert=insert, ignore_live=ignore_live,
                                                  start_at=start_at, type_=Sources.SPOTIFY)
            elif "soundcloud.com/" in query:
                soundcloud_result = Constants.SOUNDCLOUD.resolve(query)

                if isinstance(soundcloud_result, SCTrack):
                    soundcloud_query = f"{soundcloud_result.artist} - {soundcloud_result.title}"
                    await self.song_addition_handling(ctx, soundcloud_query, insert=insert, ignore_live=ignore_live,
                                                      start_at=start_at, type_=Sources.SOUNDCLOUD)
                elif isinstance(soundcloud_result, SCPlaylist):
                    playlist_entries = [f"{track.artist} - {track.title}" for track in soundcloud_result]
                    await self.playlist_addition_handling(ctx, playlist_entries, soundcloud_result.title, query,
                                                          ignore_live=ignore_live, pre_shuffle=pre_shuffle,
                                                          type_=Sources.SOUNDCLOUD)
                else:
                    embed = discord.Embed(
                        description=f"**Error:** Invalid SoundCloud URL.",
                        color=discord.Color.red()
                    )
                    await ctx.respond(embed=embed)
                    return
            else:
                await self.song_addition_handling(ctx, query, is_url=True, insert=insert, start_at=start_at)
        else:
            await self.song_addition_handling(ctx, query, insert=insert, ignore_live=ignore_live, start_at=start_at)

        await self.populate_select_menu(ctx)

        if not ctx.voice_client.is_playing():
            self.booleans[ctx.guild.id]["first"] = True
            dur = self.queue[ctx.guild.id][0].duration

            try:
                response = Constants.YOUTUBE.channels().list(part="snippet",
                                                             id=self.queue[ctx.guild.id][0].uploader_id).execute()
                uploader_picture_url = response["items"][0]["snippet"]["thumbnails"]["high"]["url"]
            except (IndexError, googleapiclient.errors.HttpError):
                uploader_picture_url = None

            now_playing_msg = (
                f"**♪ Now playing:** " if self.loop[ctx.guild.id]["mode"] == "Disabled" else
                f"**∞ Now looping:** " if self.loop[ctx.guild.id]["mode"] == "Single" else f"**∞ Now in loop:** "
            )
            next_in_queue_msg = (
                f"**Next in {'loop' if self.loop[ctx.guild.id]['mode'] == 'Queue' else 'queue'}:** "
                f"[{self.queue[ctx.guild.id][1].title}]({self.queue[ctx.guild.id][1].url})"
                if len(self.queue[ctx.guild.id]) > 1 else "**Note:** No further songs in queue."
            )
            embed = discord.Embed(
                description=f"{now_playing_msg}[{self.queue[ctx.guild.id][0].title}]({self.queue[ctx.guild.id][0].url})"
                            f" [**{f'{format_timestamp(start_at, timestamp_to_seconds(dur))} -> ' if start_at else ''}"
                            f"{format_timestamp(dur)}**] [**{len(self.previous[ctx.guild.id]) + 1} | "
                            f"{len(self.queue[ctx.guild.id]) + len(self.previous[ctx.guild.id])}**]\n"
                            f"{next_in_queue_msg}",
                color=discord.Color.dark_green()
            )
            embed.set_footer(text=self.queue[ctx.guild.id][0].uploader, icon_url=uploader_picture_url)
            self.messages[ctx.guild.id]["main"] = await ctx.respond(embed=embed, view=self.resolve_view(ctx))

            await self.play_next(ctx)

    @commands.slash_command(description="Removes songs from the queue")
    @discord.option(name="from_",
                    description="The start position of the queue removal, or positions separated by semicolons "
                                "(i.e. pos1;pos2;...)", required=True)
    @discord.option(name="to", description="The end position of the queue removal", required=False)
    async def remove(self, ctx: discord.ApplicationContext, from_: str, to: int = None):
        try:
            await ctx.defer()
        except (discord.ApplicationCommandInvokeError, discord.InteractionResponded):
            pass

        if not ctx.voice_client:
            embed = discord.Embed(
                description="**Error:** Queue is empty.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        queue_length = len(self.queue[ctx.guild.id]) - 1

        if not from_.isdigit():
            split_positions = from_.split(";")

            if any([not position.isdigit() for position in split_positions]):
                embed = discord.Embed(
                    description="**Error:** Invalid position format (pos1;pos2;...).",
                    color=discord.Color.red()
                )
                await ctx.respond(embed=embed)
                return

            removed_positions = set([max(1, min(int(pos), queue_length)) for pos in map(int, split_positions)])
            removed_songs = ""

            for i, k in enumerate(removed_positions):
                removed_songs += f"[**{k}**] {self.queue[ctx.guild.id].pop(k - i)}\n"

            next_in_queue_msg = (
                f"**Next in queue:** {self.queue[ctx.guild.id][1].title}" if len(self.queue[ctx.guild.id]) > 1 else
                "**Note:** No further songs in queue."
            )
            embed = discord.Embed(
                description=f"**⊝ Removed the following song(s) from queue:**\n{removed_songs}\n"
                            f"{next_in_queue_msg}",
                color=discord.Color.dark_red()
            )
            await ctx.respond(embed=embed)
            return

        from_ = max(1, min(int(from_), queue_length))
        to = from_ if not to else max(1, min(to, queue_length))
        from_, to = ((from_, to) if from_ < to else (to, from_)) if to != 0 else (from_, to)
        removed_song = self.queue[ctx.guild.id][from_]

        removed_msg = (
            f"**⊝ Removed song:** {removed_song} [**{from_}**]\n" if from_ == to else
            f"Removed **{to + 1 - from_}** songs from the queue. [**{from_}-{to}**]\n"
        )
        del self.queue[ctx.guild.id][from_:to + 1]

        next_in_queue_msg = (
            f"**Next in queue:** {self.queue[ctx.guild.id][1].title}" if len(self.queue[ctx.guild.id]) > 1 else
            "**Note:** No further songs in queue."
        )

        if self.button_invoker[ctx.guild.id]:
            self.removed[ctx.guild.id].append(f"[**{len(self.removed[ctx.guild.id]) + 1}**] {removed_song}")
            joined_removed_songs = "\n".join(self.removed[ctx.guild.id])

            embed = discord.Embed(
                description=f"**⊝ Removed the following song(s) from queue:**\n{joined_removed_songs}\n"
                            f"{next_in_queue_msg}",
                color=discord.Color.dark_red()
            )
            embed.set_footer(text=f"Requested via a button [{self.button_invoker[ctx.guild.id]}]")

            if self.messages[ctx.guild.id]["remove"]:
                await self.messages[ctx.guild.id]["remove"].edit(embed=embed)
            else:
                self.messages[ctx.guild.id]["remove"] = await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description=f"{removed_msg}{next_in_queue_msg}",
                color=discord.Color.dark_red()
            )
            await ctx.respond(embed=embed)

    @commands.slash_command(description="Clears the queue")
    @discord.option(name="from_", description="The start position of the queue clear", required=False)
    async def clear(self, ctx: discord.ApplicationContext, from_: int = 1):
        await self.remove(ctx, str(from_), len(self.queue[ctx.guild.id]))

    @commands.slash_command(description="Skips to the next, or to the specified, song in the queue")
    @discord.option(name="to", description="The position in queue you wish to skip to", required=False)
    async def skip(self, ctx: discord.ApplicationContext, to: int = None):
        try:
            await ctx.defer()
        except (discord.ApplicationCommandInvokeError, discord.InteractionResponded):
            pass

        if not ctx.voice_client:
            embed = discord.Embed(
                description="**Error:** Nothing is currently playing.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        queue_length = len(self.queue[ctx.guild.id]) - 1
        to = 1 if not to or self.loop[ctx.guild.id]["mode"] == "Single" else max(1, min(to, queue_length))

        if ctx.voice_client.is_playing() and to == 1:
            embed = discord.Embed(
                description=f"**↷ Skipping current song:** {self.queue[ctx.guild.id][0]}",
                color=discord.Color.blurple()
            )
            if self.button_invoker[ctx.guild.id]:
                embed.set_footer(text=f"Requested via a button [{self.button_invoker[ctx.guild.id]}]")

                if self.messages[ctx.guild.id]["skip"]:
                    await self.messages[ctx.guild.id]["skip"].edit(embed=embed)
                else:
                    self.messages[ctx.guild.id]["skip"] = await ctx.send(embed=embed)
            else:
                await ctx.respond(embed=embed)

            ctx.voice_client.stop()
        elif ctx.voice_client.is_playing() and to != 1:
            embed = discord.Embed(
                description=f"**↷ Skipping current song:** {self.queue[ctx.guild.id][0]}\n"
                            f"+ **{to - 1}** more...",
                color=discord.Color.blurple()
            )
            await ctx.respond(embed=embed)

            del self.queue[ctx.guild.id][:to - 1]
            ctx.voice_client.stop()
        else:
            embed = discord.Embed(
                description="**Error:** Nothing is currently playing.",
                color=discord.Color.red()
            )
            if self.button_invoker[ctx.guild.id]:
                embed.set_footer(text=f"Requested via a button [{self.button_invoker[ctx.guild.id]}]")

                if self.messages[ctx.guild.id]["skip"]:
                    await self.messages[ctx.guild.id]["skip"].edit(embed=embed)
                else:
                    self.messages[ctx.guild.id]["skip"] = await ctx.send(embed=embed)
            else:
                await ctx.respond(embed=embed)

    @commands.slash_command(description="Displays songs in queue, with the ability to seek them")
    @discord.option(name="to", description="The end position of the queue display", required=False)
    @discord.option(name="from_", description="The start position of the queue display", required=False)
    @discord.option(name="seek", description="Seek songs via given keywords", required=False)
    @discord.option(name="previous", description="Whether to view the previous queue instead", required=False)
    async def view(self, ctx: discord.ApplicationContext, to: int = None, from_: int = 1, seek: str = None,
                   previous: bool = False):
        await ctx.defer()

        if not ctx.voice_client:
            embed = discord.Embed(
                description=f"{'Previous queue' if previous else 'Queue'} is empty.",
                color=discord.Color.dark_gold()
            )
            await ctx.respond(embed=embed)
            return

        queue_length = len(self.queue[ctx.guild.id]) - 1 if not previous else len(self.previous[ctx.guild.id])
        to = (min(10, queue_length) if not to else max(1, min(to, queue_length))) if not seek else queue_length
        from_ = max(1, min(from_, queue_length)) if not seek else 1
        from_, to = ((from_, to) if from_ < to else (to, from_)) if to != 0 else (from_, to)

        queue_songs = ""
        displayed_song_count = to + 1 - from_
        for i, k in enumerate(self.queue[ctx.guild.id][from_:to + 1] if not previous else
                              self.previous[ctx.guild.id][from_ - 1:to]):
            if not seek:
                queue_songs += (f"[**{from_ + i}**] {k} "
                                f"[**{f'{seconds_to_timestamp(k.start)} -> ' if k.start else ''}"
                                f"{format_timestamp(k.duration)}**]\n")
            elif seek and seek.lower() in k.title.lower():
                queue_songs += (f"[**{from_ + i}**] {k} "
                                f"[**{f'{seconds_to_timestamp(k.start)} -> ' if k.start else ''}"
                                f"{format_timestamp(k.duration)}**]\n")

            if len(queue_songs) >= 3952:
                displayed_song_count = i + 1
                break

        queue_durations = [timestamp_to_seconds(k.duration if not k.start else seconds_to_timestamp(
                timestamp_to_seconds(k.duration) - k.start)) for k in self.queue[ctx.guild.id][1:]] if \
            not previous else [timestamp_to_seconds(k.duration if not k.start else seconds_to_timestamp(
                timestamp_to_seconds(k.duration) - k.start)) for k in self.previous[ctx.guild.id]]
        additional_songs_count = queue_length - displayed_song_count
        additional_songs_msg = f"+ **{additional_songs_count}** more...\n\n" if additional_songs_count else "\n"

        if queue_songs and not seek:
            embed = discord.Embed(
                description=f"**\👁 In{' previous' if previous else ''} queue:**\n{queue_songs}{additional_songs_msg}"
                            f"**In total: {queue_length}** song(s) "
                            f"[**{seconds_to_timestamp(sum(queue_durations))}**]",
                color=discord.Color.dark_gold()
            )
        elif queue_songs and seek:
            embed = discord.Embed(
                description=f"**\👁 In{' previous' if previous else ''} queue matching `{seek}`:**\n{queue_songs}\n"
                            f"**In total: {queue_length}** song(s) "
                            f"[**{seconds_to_timestamp(sum(queue_durations))}**]",
                color=discord.Color.dark_gold()
            )
        elif not queue_songs and seek:
            embed = discord.Embed(
                description=f"**\👁 In{' previous' if previous else ''} queue matching `{seek}`:**\nNo songs found.\n\n"
                            f"**In total: {queue_length}** song(s) "
                            f"[**{seconds_to_timestamp(sum(queue_durations))}**]",
                color=discord.Color.dark_gold()
            )
        else:
            embed = discord.Embed(
                description=f"{'Previous queue' if previous else 'Queue'} is empty.",
                color=discord.Color.dark_gold()
            )
        if ctx.voice_client.is_playing():
            filter_mode = self.queue[ctx.guild.id][0].filter_["mode"]
            filter_intensity = self.queue[ctx.guild.id][0].filter_["intensity"]

            embed.set_footer(text=f"> Now playing: {self.queue[ctx.guild.id][0]} "
                                  f"[{seconds_to_timestamp(self.count_elapsed_time(ctx))} | "
                                  f"{format_timestamp(self.queue[ctx.guild.id][0].duration)}]\n"
                                  f"> Volume: {self.queue[ctx.guild.id][0].source.volume * 100}% | Filter: "
                                  f"{filter_mode} {f'[{filter_intensity}%]' if filter_mode != 'Disabled' else ''} | "
                                  f"Loop: {self.loop[ctx.guild.id]['mode']} | Autoplay: {self.autoplay[ctx.guild.id]}")
        await ctx.respond(embed=embed)

    @commands.slash_command(description="Toggles pause for the current song")
    async def pause(self, ctx: discord.ApplicationContext):
        try:
            await ctx.defer()
        except (discord.ApplicationCommandInvokeError, discord.InteractionResponded):
            pass

        if not ctx.voice_client:
            embed = discord.Embed(
                description="**Error:** Nothing is currently playing.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        if not ctx.voice_client.is_paused():
            embed = discord.Embed(
                description=f"**❚❚ Pausing current song:** {self.queue[ctx.guild.id][0]}",
                color=discord.Color.blurple()
            )
            if self.button_invoker[ctx.guild.id]:
                embed.set_footer(text=f"Requested via a button [{self.button_invoker[ctx.guild.id]}]")

                if self.messages[ctx.guild.id]["pause"]:
                    await self.messages[ctx.guild.id]["pause"].edit(embed=embed)
                else:
                    self.messages[ctx.guild.id]["pause"] = await ctx.send(embed=embed)
            else:
                await ctx.respond(embed=embed)

            ctx.voice_client.pause()
            self.elapsed_time[ctx.guild.id]["pause_start"] = time.time()
            return

        embed = discord.Embed(
            description=f"**⯈ Resuming current song:** {self.queue[ctx.guild.id][0]}",
            color=discord.Color.blurple()
        )
        if self.button_invoker[ctx.guild.id]:
            embed.set_footer(text=f"Requested via a button [{self.button_invoker[ctx.guild.id]}]")

            if self.messages[ctx.guild.id]["pause"]:
                await self.messages[ctx.guild.id]["pause"].edit(embed=embed)
            else:
                self.messages[ctx.guild.id]["pause"] = await ctx.send(embed=embed)
        else:
            await ctx.respond(embed=embed)

        ctx.voice_client.resume()
        self.elapsed_time[ctx.guild.id]["pause"] = time.time() - self.elapsed_time[ctx.guild.id]["pause_start"]
        self.elapsed_time[ctx.guild.id]["pause_start"] = None

    @commands.slash_command(description="Shuffles the queue")
    @discord.option(name="from_", description="The start position of the queue shuffle", required=False)
    @discord.option(name="to", description="The end position of the queue shuffle", required=False)
    async def shuffle(self, ctx: discord.ApplicationContext, from_: int = None, to: int = None):
        await ctx.defer()

        if not ctx.voice_client or len(self.queue[ctx.guild.id]) < 2:
            embed = discord.Embed(
                description="**Error:** Queue is empty.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        queue_length = len(self.queue[ctx.guild.id]) - 1
        from_ = 1 if not from_ else max(1, min(from_, queue_length))
        to = queue_length if not to else max(1, min(to, queue_length))
        from_, to = ((from_, to) if from_ < to else (to, from_)) if to != 0 else (from_, to)

        self.queue[ctx.guild.id] = (
                self.queue[ctx.guild.id][:from_] +
                random.sample(self.queue[ctx.guild.id][from_:to + 1], len(self.queue[ctx.guild.id][from_:to + 1])) +
                self.queue[ctx.guild.id][to + 1:]
        )
        embed = discord.Embed(
            description=f"**⤮ Shuffled {to + 1 - from_}** song(s) in queue. [**{from_}-{to}**]\n"
                        f"**Next in queue:** {self.queue[ctx.guild.id][1].title}",
            color=discord.Color.purple()
        )
        await ctx.respond(embed=embed)

    @commands.slash_command(description="Moves the song to the specified position in the queue")
    @discord.option(name="from_", description="The current position of the song in queue", required=True)
    @discord.option(name="to", description="The position in queue you wish to move the song to", required=True)
    @discord.option(name="replace", description="Replaces the song in the target position", required=False)
    async def move(self, ctx: discord.ApplicationContext, from_: int, to: int, replace: bool = False):
        await ctx.defer()

        if not ctx.voice_client or len(self.queue[ctx.guild.id]) < 2:
            embed = discord.Embed(
                description="**Error:** Queue is empty.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        queue_length = len(self.queue[ctx.guild.id]) - 1
        from_ = max(1, min(from_, queue_length))
        to = max(1, min(to, queue_length))

        move_msg = f"**⇄ Moved song:** {self.queue[ctx.guild.id][from_]} [**{from_}**] -> [**{to}**]\n"
        replace_msg = f"**⊝ Replaced song:** {self.queue[ctx.guild.id][to]}\n" if replace else ""

        self.queue[ctx.guild.id].insert(to, self.queue[ctx.guild.id].pop(from_))
        self.queue[ctx.guild.id].pop(to + 1) if replace else None

        embed = discord.Embed(
            description=f"{move_msg}{replace_msg}**Next in queue:** {self.queue[ctx.guild.id][1].title}",
            color=discord.Color.purple()
        )
        await ctx.respond(embed=embed)

    @commands.slash_command(description="Seek a certain part of the song via timestamp")
    @discord.option(name="timestamp", description="The timestamp to seek (i.e. hours:minutes:seconds)", required=True)
    async def seek(self, ctx: discord.ApplicationContext, timestamp: str):
        await ctx.defer()

        if not ctx.voice_client or not self.queue[ctx.guild.id]:
            embed = discord.Embed(
                description="**Error:** Nothing is currently playing.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return
        elif self.queue[ctx.guild.id][0].duration == "0:00":
            embed = discord.Embed(
                description="**Error:** Cannot seek position in live stream.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        self.booleans[ctx.guild.id]["clear_elapsed"] = False
        self.booleans[ctx.guild.id]["ignore_msg"] = True

        if not validate_timestamp(timestamp):
            embed = discord.Embed(
                description="**Error:** Incorrect timestamp format (hh:mm:ss).",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        self.elapsed_time[ctx.guild.id]["seek"] = timestamp_to_seconds(timestamp)

        current_song = self.queue[ctx.guild.id][0]
        current_song.set_start(timestamp_to_seconds(timestamp))
        self.queue[ctx.guild.id].insert(0, current_song)
        dur = self.queue[ctx.guild.id][0].duration

        ctx.voice_client.stop()

        embed = discord.Embed(
            description=f"**⌕ Sought timestamp:** {format_timestamp(timestamp, timestamp_to_seconds(dur))} | "
                        f"{self.queue[ctx.guild.id][0].duration}",
            color=discord.Color.blurple()
        )
        await ctx.respond(embed=embed)

    @commands.slash_command(name="filter", description="Applies an audio filter over the songs")
    @discord.option(name="mode", description="The filter mode you wish to use",
                    choices=["Disabled", "Nightcore", "BassBoost", "EarRape"], required=True)
    @discord.option(name="intensity", description="Set the filter intensity percentage (35 by default)", required=False)
    async def filter_(self, ctx: discord.ApplicationContext, mode: str, intensity: int = None):
        await ctx.defer()

        if not ctx.voice_client:
            embed = discord.Embed(
                description="**Error:** Nothing is currently playing.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        self.booleans[ctx.guild.id]["clear_elapsed"] = False
        self.booleans[ctx.guild.id]["ignore_msg"] = True
        intensity = 35 if not intensity else min(max(intensity, 0), 100)

        if mode == "Disabled":
            self.filters[ctx.guild.id] = {"mode": mode, "value": Constants.FILTERS[mode], "intensity": intensity}
        elif mode == "Nightcore":
            self.filters[ctx.guild.id] = {"mode": mode, "value": Constants.FILTERS[mode].format(1 + intensity / 100),
                                          "intensity": intensity}
        elif mode == "BassBoost":
            self.filters[ctx.guild.id] = {"mode": mode, "value": Constants.FILTERS[mode].format(intensity // 5),
                                          "intensity": intensity}
        else:
            self.filters[ctx.guild.id] = {"mode": mode,
                                          "value": Constants.FILTERS[mode].format(intensity // 5, 1 + ((intensity // 5) * 2)),
                                          "intensity": intensity}

        current_song = self.queue[ctx.guild.id][0]
        current_song.set_filter(self.filters[ctx.guild.id])
        current_song.set_start(self.count_elapsed_time(ctx))
        self.queue[ctx.guild.id].insert(0, current_song)

        self.elapsed_time[ctx.guild.id]["seek"] = self.queue[ctx.guild.id][0].start

        ctx.voice_client.stop()

        embed = discord.Embed(
            description=f"**⎘ Filter mode is now:** {mode} {f'[**{intensity}%**]' if mode != 'Disabled' else ''}",
            color=discord.Color.blurple()
        )
        await ctx.respond(embed=embed)

    @commands.slash_command(filter="volume", description="Changes the music player volume")
    @discord.option(name="level", description="Set the volume level percentage (50 by default)", required=True)
    async def volume_(self, ctx: discord.ApplicationContext, level: float):
        try:
            await ctx.defer()
        except (discord.ApplicationCommandInvokeError, discord.InteractionResponded):
            pass

        if not ctx.voice_client:
            embed = discord.Embed(
                description="**Error:** Nothing is currently playing.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        level = min(max(level, 0), 200) / 100
        self.volume[ctx.guild.id] = round(level, 1)
        self.queue[ctx.guild.id][0].set_volume(self.volume[ctx.guild.id])

        embed = discord.Embed(
            description=f"**🕪 Volume level is now:** {self.queue[ctx.guild.id][0].source.volume * 100:.1f}%",
            color=discord.Color.blurple()
        )
        if self.button_invoker[ctx.guild.id]:
            embed.set_footer(text=f"Requested via a button [{self.button_invoker[ctx.guild.id]}]")

            if self.messages[ctx.guild.id]["volume"]:
                await self.messages[ctx.guild.id]["volume"].edit(embed=embed)
            else:
                self.messages[ctx.guild.id]["volume"] = await ctx.send(embed=embed)
        else:
            await ctx.respond(embed=embed)

    @commands.slash_command(description="Replays the previous song from the queue")
    @discord.option(name="from_", description="Current position of the song in previous queue", required=False)
    @discord.option(name="insert", description="Add the song to the given position in queue", required=False)
    @discord.option(name="instant", description="Whether to replay the song instantly", required=False)
    async def replay(self, ctx: discord.ApplicationContext, from_: int = None, insert: int = None,
                     instant: bool = False):
        try:
            await ctx.defer()
        except (discord.ApplicationCommandInvokeError, discord.InteractionResponded):
            pass

        if not ctx.voice_client or not self.previous[ctx.guild.id]:
            embed = discord.Embed(
                description="**Error:** No previous songs associated with this queue.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        from_ = len(self.previous[ctx.guild.id]) if not from_ else max(1, min(from_, len(self.previous[ctx.guild.id])))
        insert = 1 if instant else len(self.queue[ctx.guild.id]) if not insert else \
            max(1, min(insert, len(self.queue[ctx.guild.id])))

        previous_song = self.previous[ctx.guild.id].pop(from_ - 1)
        next_in_queue_msg = (
            f"**Next in queue:** {self.queue[ctx.guild.id][1]}" if len(self.queue[ctx.guild.id]) > 1 else
            "**Note:** No further songs in queue."
        )
        embed = discord.Embed(
            description=f"**{'⭟ Replaying' if not self.button_invoker[ctx.guild.id] else '↶ Backing to'} song:** "
                        f"{previous_song} [**{insert}**]\n{next_in_queue_msg}",
            color=discord.Color.purple()
        )
        if self.button_invoker[ctx.guild.id]:
            embed.set_footer(text=f"Requested via a button [{self.button_invoker[ctx.guild.id]}]")

            if self.messages[ctx.guild.id]["replay"]:
                await self.messages[ctx.guild.id]["replay"].edit(embed=embed)
            else:
                self.messages[ctx.guild.id]["replay"] = await ctx.send(embed=embed)
        else:
            await ctx.respond(embed=embed)

        if not (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()) and not self.queue[ctx.guild.id]:
            await self.play(ctx, query=previous_song.url)
            return

        self.queue[ctx.guild.id].insert(insert, previous_song)

        if self.button_invoker[ctx.guild.id]:
            self.booleans[ctx.guild.id]["backed"] = True
            self.queue[ctx.guild.id].insert(insert + 1, self.queue[ctx.guild.id][0])
        ctx.voice_client.stop() if instant else None

    @commands.slash_command(description="Get lyrics for the currently playing song")
    @discord.option(name="title", description="Get lyrics from the specified title instead", required=False)
    async def lyrics(self, ctx: discord.ApplicationContext, title: str = None):
        await ctx.defer()

        if not title and (not ctx.voice_client or not ctx.voice_client.is_playing()):
            embed = discord.Embed(
                description=f"**Error:** Nothing is currently playing.",
                color=discord.Color.red(),
            )
            await ctx.respond(embed=embed)
            return

        formatted_title = re.sub(r"\[[^\[\]]*]|\([^()]*\)", "",
                                 title if title else self.queue[ctx.guild.id][0].title)

        try:
            song = Constants.GENIUS.search_song(title=formatted_title, get_full_info=False)
        except (requests.ReadTimeout, requests.Timeout, discord.ApplicationCommandInvokeError):
            embed = discord.Embed(
                description=f"**Error:** Request timed out, please try again.",
                color=discord.Color.red(),
            )
            await ctx.respond(embed=embed)
            return

        if not song:
            embed = discord.Embed(
                description=f"**Error:** No lyrics found for `{title}`.",
                color=discord.Color.dark_gold(),
            )
            await ctx.respond(embed=embed)
            return

        split_lyrics = song.lyrics.split("\n")[1:]
        see_regex = re.compile(r"^(.*)See .+ LiveGet tickets as low as \$\d+(.*)$")
        might_regex = re.compile(r"^(.*)You might also like(.*)$")
        embed_regex = re.compile(r"^(.*)\d*Embed(.*)$")

        if last_line_match := embed_regex.match(split_lyrics[-1]):
            split_lyrics[-1] = last_line_match.group(1)

        for i in range(len(split_lyrics)):
            if see_line := see_regex.match(split_lyrics[i]):
                split_lyrics[i] = re.sub(see_regex, see_line.group(1), split_lyrics[i]).strip()

            if might_line := might_regex.match(split_lyrics[i]):
                split_lyrics[i] = re.sub(might_regex, f"{might_line.group(1)} {might_line.group(2)}",
                                         split_lyrics[i]).strip()

        formatted_lyrics = "\n".join(split_lyrics)

        try:
            embed = discord.Embed(
                description=f"**☲ {song.title} Lyrics**\n\n{formatted_lyrics}",
                color=discord.Color.dark_gold(),
            )
        except discord.HTTPException:
            embed = discord.Embed(
                description=f"**☲ {song.title} Lyrics**\n\nLyrics too long for Discord. [Find them here.]({song.url})",
                color=discord.Color.dark_gold(),
            )
        await ctx.respond(embed=embed)

    @commands.slash_command(name="loop", description="Loops either the song or the entire queue")
    @discord.option(name="mode", description="The loop mode you wish to use", choices=["Disabled", "Single", "Queue"],
                    required=True)
    async def loop_(self, ctx: discord.ApplicationContext, mode: str):
        try:
            await ctx.defer()
        except (discord.ApplicationCommandInvokeError, discord.InteractionResponded):
            pass

        if not ctx.voice_client:
            embed = discord.Embed(
                description="**Error:** Not connected to a voice channel.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        self.loop[ctx.guild.id]["mode"] = mode

        embed = discord.Embed(
            description=f"**⟳ Loop mode is now:** {mode}",
            color=discord.Color.blurple()
        )
        if self.button_invoker[ctx.guild.id]:
            embed.set_footer(text=f"Requested via a button [{self.button_invoker[ctx.guild.id]}]")

            if self.messages[ctx.guild.id]["loop"]:
                await self.messages[ctx.guild.id]["loop"].edit(embed=embed)
            else:
                self.messages[ctx.guild.id]["loop"] = await ctx.send(embed=embed)
        else:
            await ctx.respond(embed=embed)

    @commands.slash_command(name="autoplay", description="Toggles autoplay for the queue")
    async def autoplay_(self, ctx: discord.ApplicationContext):
        await ctx.defer()

        if not ctx.voice_client:
            embed = discord.Embed(
                description="**Error:** Not connected to a voice channel.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        self.autoplay[ctx.guild.id] = "Disabled" if self.autoplay[ctx.guild.id] == "Enabled" else "Enabled"

        embed = discord.Embed(
            description=f"**⮓ Autoplay is now:** {self.autoplay[ctx.guild.id]}",
            color=discord.Color.blurple()
        )
        await ctx.respond(embed=embed)

        if not (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()) and self.previous[ctx.guild.id]:
            related = await self.get_related_videos(ctx, self.previous[ctx.guild.id][-1].url, first=True)
            await self.play(ctx, related[0][1])


    @connect.before_invoke
    @play.before_invoke
    async def ensure_dicts(self, ctx):
        if ctx.guild.id not in self.queue:
            self.queue[ctx.guild.id] = []
            self.previous[ctx.guild.id] = []
            self.removed[ctx.guild.id] = []
            self.volume[ctx.guild.id] = 0.5
            self.booleans[ctx.guild.id] = {"first": False, "ignore_msg": False, "clear_elapsed": True, "backed": False}
            self.filters[ctx.guild.id] = {"mode": "Disabled", "value": None, "intensity": 35}
            self.elapsed_time[ctx.guild.id] = {"start": 0, "pause_start": 0, "pause": 0, "current": 0, "seek": 0}
            self.loop[ctx.guild.id] = {"mode": "Disabled", "count": 0}
            self.messages[ctx.guild.id] = {"main": None, "loop": None, "pause": None, "remove": None, "volume": None,
                                           "skip": None, "replay": None}
            self.button_invoker[ctx.guild.id] = None
            self.autoplay[ctx.guild.id] = "Disabled"
            self.gui[ctx.guild.id] = {
                "select": Select(placeholder="Suggested...", options=[], min_values=1, max_values=1, row=1),
                "back": Button(style=discord.ButtonStyle.secondary, label="Back",
                               emoji="<:goback:1142844613003067402>", row=3),
                "pause": Button(style=discord.ButtonStyle.secondary, label="Pause",
                                emoji="<:playpause:1086408066490183700>", row=3),
                "skip": Button(style=discord.ButtonStyle.secondary, label="Skip",
                               emoji="<:skip:1086405128787067001>", row=3),
                "loop": Button(style=discord.ButtonStyle.secondary, emoji="<loopy:1196862829752500265>", row=3),
                "remove": Button(style=discord.ButtonStyle.danger, emoji="<:remove:1197082264924852325>", row=3),
                "volume_min": Button(style=discord.ButtonStyle.danger, emoji="<:volume_mute:1143513586967257190",
                                     row=2),
                "volume_down": Button(style=discord.ButtonStyle.danger, emoji="<:volume_down:1143513584505192520",
                                      row=2),
                "volume_mid": Button(style=discord.ButtonStyle.secondary, emoji="<:volume_mid:1143514064023212174",
                                     row=2),
                "volume_up": Button(style=discord.ButtonStyle.success, emoji="<:volume_up:1143513588623999087", row=2),
                "volume_max": Button(style=discord.ButtonStyle.success, emoji="<:volume:1142886748200910959", row=2)
            }
            self.views[ctx.guild.id] = {
                "all": View(timeout=None),
                "no_remove": View(timeout=None),
                "no_back": View(timeout=None),
                "no_remove_and_back": View(timeout=None)
            }
            self.store_queue_count()

            for elem in self.gui[ctx.guild.id].keys():
                self.gui[ctx.guild.id][elem].callback = await self.resolve_gui_callback(ctx, elem)

                for view in self.views[ctx.guild.id].keys():
                    if (view in ("no_remove", "no_remove_and_back") and elem == "remove") or \
                            (view in ("no_back", "no_remove_and_back") and elem == "back"):
                        continue
                    self.views[ctx.guild.id][view].add_item(self.gui[ctx.guild.id][elem])


def setup(bot):
    bot.add_cog(Music(bot))

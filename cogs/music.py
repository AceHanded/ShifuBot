import re
import copy
import math
import time
import pytse
import random
import aiohttp
import asyncio
import discord
import subprocess
import lyricsgenius
import speech_recognition
from discord.ext import commands
from dotenv import dotenv_values
from typing import cast, Awaitable, Callable
from pytubefix.exceptions import LiveStreamError, RegexMatchError, VideoUnavailable
from speech_recognition.recognizers import google
from utils import AttachmentSource, ByteSink, EmbedColor, Emoji, format_duration, load_settings, parse_duration, PlayerEntry, Queue, YTDLSource

class PlayMessageMenu(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption], disabled: bool, music: "Music"):
        super().__init__(custom_id="play", placeholder="Suggested...", min_values=1, max_values=1, options=options or [discord.SelectOption(label="Loading...", value="None")], disabled=disabled, row=1)
        self.music = music

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        assert interaction.guild

        command = cast(Callable[..., Awaitable[None]], getattr(self.music, str(self.custom_id), None))
        queue = self.music.queue[interaction.guild.id]
        cctx = copy.copy(queue.ctx)
        setattr(cctx, "_request_type", "suggestion")

        await command(cctx, self.values[0])

class PlayMessageButton(discord.ui.Button):
    def __init__(self, style: discord.ButtonStyle, disabled: bool, custom_id: str, emoji: str, row: int, music: "Music"):
        super().__init__(style=style, disabled=disabled, custom_id=custom_id, emoji=emoji, row=row)
        self.music = music

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        assert interaction.guild

        id_string = str(self.custom_id)
        command = cast(Callable[..., Awaitable[None]], getattr(self.music, id_string.split("_")[0], None))
        queue = self.music.queue[interaction.guild.id]
        cctx = copy.copy(queue.ctx)
        setattr(cctx, "_request_type", "button")

        if callable(command):
            if "volume" in id_string:
                volume_map = {
                    "volume_min": 0,
                    "volume_down": int((queue.volume * 100) - 10),
                    "volume_mid": 100,
                    "volume_up": int((queue.volume * 100) + 10),
                    "volume_max": 200
                }
                await command(cctx, volume_map[id_string])
            elif id_string == "loop":
                loop_modes = ["Disabled", "Single", "Queue"]
                current_mode_index = loop_modes.index(queue.loop)
                next_mode = loop_modes[(current_mode_index + 1) % len(loop_modes)]

                await command(cctx, next_mode)
            elif id_string == "replay":
                await command(cctx, 0, 1, True)
            elif id_string == "remove":
                await command(cctx, "1;")
            else:
                await command(cctx)
    
class PlayMessageView(discord.ui.View):
    def __init__(self, music: "Music", disable_back: bool, disable_remove: bool, pause_style: discord.ButtonStyle, loop_style: discord.ButtonStyle, options: list[discord.SelectOption] = []):
        super().__init__(timeout=None)
        self.add_item(PlayMessageMenu(options[:25], not bool(options), music))
        self.add_item(PlayMessageButton(discord.ButtonStyle.danger, False, "volume_min", Emoji.VOLUME_MIN, 2, music))
        self.add_item(PlayMessageButton(discord.ButtonStyle.danger, False, "volume_down", Emoji.VOLUME_DOWN, 2, music))
        self.add_item(PlayMessageButton(discord.ButtonStyle.secondary, False, "volume_mid", Emoji.VOLUME_MID, 2, music))
        self.add_item(PlayMessageButton(discord.ButtonStyle.success, False, "volume_up", Emoji.VOLUME_UP, 2, music))
        self.add_item(PlayMessageButton(discord.ButtonStyle.success, False, "volume_max", Emoji.VOLUME_MAX, 2, music))
        self.add_item(PlayMessageButton(loop_style, False, "loop", Emoji.LOOP, 3, music))
        self.add_item(PlayMessageButton(discord.ButtonStyle.secondary, disable_back, "replay", Emoji.BACK, 3, music))
        self.add_item(PlayMessageButton(pause_style, False, "pause", Emoji.PAUSE, 3, music))
        self.add_item(PlayMessageButton(discord.ButtonStyle.secondary, False, "skip", Emoji.SKIP, 3, music))
        self.add_item(PlayMessageButton(discord.ButtonStyle.danger, disable_remove, "remove", Emoji.REMOVE, 3, music))

config = dotenv_values(".env")
GENIUS = lyricsgenius.Genius(config["GENIUS_TOKEN"], verbose=False)

class Music(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.queue: dict[int, Queue] = {}

    async def cog_before_invoke(self, ctx: discord.ApplicationContext):
        await self._initialize_queue(ctx)
        self.queue[ctx.guild.id].text_channel = ctx.channel.id
        self.queue[ctx.guild.id].ctx = ctx

    async def _initialize_queue(self, ctx: discord.ApplicationContext):
        self.queue.setdefault(ctx.guild.id, Queue())

    async def _cleanup(self, ctx: discord.ApplicationContext):
        try:
            play_msg = self.queue[ctx.guild.id].messages["play"]
            if play_msg: await play_msg.edit(view=None)
        except discord.NotFound:
            pass

        self.queue[ctx.guild.id].clear()
        del self.queue[ctx.guild.id]

    async def _resolve_view(self, ctx: discord.ApplicationContext):
        queue = self.queue[ctx.guild.id]
        loop_style_map = {
            "Disabled": discord.ButtonStyle.secondary,
            "Single": discord.ButtonStyle.primary,
            "Queue": discord.ButtonStyle.success
        }
        pause_style = discord.ButtonStyle.primary if ctx.voice_client and ctx.voice_client.is_paused() else discord.ButtonStyle.secondary
        loop_style = loop_style_map[queue.loop]
        suggested = [discord.SelectOption(label=song["title"], value=song["url"], description=song["url"]) for song in queue.songs[0].related]

        return PlayMessageView(self, not bool(len(queue.previous_songs)), queue.empty(), pause_style, loop_style, suggested)
    
    async def _update_play_message(self, ctx: discord.ApplicationContext):
        queue = self.queue[ctx.guild.id]
        play_msg = queue.messages["play"]

        try:
            if len(queue) and play_msg:
                song = queue.songs[0]

                loop_count = getattr(song, "_loop_count", None)
                now_playing_msg = f"**{'♪ Now playing' if queue.loop == 'Disabled' else ('∞ Now looping' if queue.loop == 'Single' else '∞ Now in loop')}:** [{song.title}]({song.url}) [**{f'{format_duration(song.start_at, False)} -> ' if song.start_at and not hasattr(song, '_sought') else ''}{song.formatted_duration}**] [**{len(queue.previous_songs) + 1} | {len(queue.previous_songs) + len(queue)}**]{f' [**{loop_count}x**]' if loop_count else ''}\n"
                now_playing_msg += (f"**Next in queue:** [{queue.songs[1].title}]({queue.songs[1].url})" if len((queue)) > 1 else "**Note:** No further songs in queue.")
                
                embed = play_msg.embeds[0].copy()
                embed.description = now_playing_msg
                await play_msg.edit(embed=embed, view=await self._resolve_view(ctx))
            elif play_msg:
                await play_msg.edit(view=await self._resolve_view(ctx))
        except discord.NotFound:
            pass

    async def _detect_speech(self, ctx: discord.ApplicationContext):
        async def finished_callback(sink_: ByteSink, _):
            for user, _ in sink_.audio_data.items():
                audio_bytes = sink_.get_audio_as_bytes(user)

                if audio_bytes:
                    wav_buffer = sink_.raw_to_wav_buffer(audio_bytes)
                    recognizer = speech_recognition.Recognizer()

                    with speech_recognition.AudioFile(wav_buffer) as source:
                        audio = recognizer.record(source)

                    try:
                        recognized_text = str(google.recognize_legacy(recognizer, audio, config["GOOGLE_SPEECH_API_KEY"], "fi-FI"))
                    except speech_recognition.exceptions.UnknownValueError:
                        return

                    split_recognized_text = recognized_text.split()
                    recognized_commands = {
                        "play": self.play,
                        "skip": self.skip,
                        "pause": self.pause,
                        "disconnect": self.disconnect,
                        "toista": self.play,
                        "seuraava": self.skip,
                        "pysäytä": self.pause,
                        "painu vittuun": self.disconnect
                    }

                    if len(split_recognized_text) > 1 and split_recognized_text[0].lower() in ["play", "toista"]:
                        await self._flash_deafen(ctx)
                        await self.play(ctx, " ".join(split_recognized_text[1:]))
                    else:
                        command = " ".join(split_recognized_text).lower()

                        if command in recognized_commands:
                            await self._flash_deafen(ctx)
                            await recognized_commands[command](ctx)

        voice_client = ctx.guild.voice_client

        if voice_client:
            voice_client.start_recording(ByteSink(), finished_callback, voice_client.channel)
            await asyncio.sleep(5)
            voice_client.stop_recording()

    async def _after_song(self, ctx: discord.ApplicationContext, e: Exception | None):
        if e: print(f"{type(e).__name__} occurred in _after_song: {e}")

        queue = self.queue[ctx.guild.id]
        last_song = queue.songs[0]
        ignore_add = hasattr(last_song, "_ignore_add")
        ignore_clear = hasattr(last_song, "_ignore_clear")
        loop_count = hasattr(last_song, "_loop_count")
        sought = hasattr(last_song, "_sought")

        if hasattr(last_song, "_disconnect_after") and not ignore_add:
            await self.disconnect(ctx)
        elif queue.messages["play"] and not ignore_clear and queue.loop != "Single":
            try:
                await queue.messages["play"].edit(view=None)
            except discord.NotFound:
                pass

            queue.messages["play"] = None

        if sought:
            last_song.start_at = 0
            delattr(last_song, "_sought")

        if hasattr(last_song, "_first"): delattr(last_song, "_first")
        if hasattr(last_song, "_replayed"): delattr(last_song, "_replayed")
        if hasattr(last_song, "_ignore_msg"): delattr(last_song, "_ignore_msg")

        if queue.loop == "Single":
            if not loop_count: setattr(last_song, "_loop_count", 0)
            setattr(last_song, "_loop_count", getattr(last_song, "_loop_count") + 1)
        elif queue.loop == "Queue":
            queue.songs.append(queue.songs.pop(0))
        elif ignore_add:
            queue.songs.pop(0)
        else:
            queue.previous_songs.append(queue.songs.pop(0))

        if queue.loop != "Single":
            queue.messages["pause"] = queue.messages["volume"] = queue.messages["loop"] = queue.messages["remove"] = None
            queue.messages["remove_content"] = ""
            if ignore_add: delattr(last_song, "_ignore_add")
            if loop_count: delattr(last_song, "_loop_count")

        if ctx.voice_client and len(queue):
            await self._play_song(ctx, queue.songs[0])
        elif ctx.voice_client and queue.autoplay:
            first_related = last_song.related[0] if last_song.related else None

            if first_related:
                song = PlayerEntry({
                    **first_related,
                    "formatted_duration": format_duration(first_related["duration"]),
                    "uploader": None,
                    "uploader_avatar": None,
                    "start_time": 0,
                    "start_at": 0,
                    "requested_by": ctx.user.name
                })
                queue.songs.append(song)
                await self._play_song(ctx, song)
            else:
                embed = discord.Embed(
                    description=f"**Error:** No related videos found.",
                    color=EmbedColor.RED
                )
                await ctx.send(embed=embed)

    async def _play_song(self, ctx: discord.ApplicationContext, song: PlayerEntry):
        queue = self.queue[ctx.guild.id]

        try:
            assert ctx.voice_client

            if song.source == "file":
                source = await AttachmentSource.from_url(song.url, filter_=queue.filter["value"], start_at=song.start_at)
            else:
                try:
                    source = await YTDLSource.from_url(song.url, pytube=True, filter_=queue.filter["value"], start_at=song.start_at)

                    if not song.related:
                        uploader_avatar, related = await pytse.resolve_avatar_and_related(song.url.replace("music", "www"))
                        song.uploader_avatar, song.related = uploader_avatar, related
                except (LiveStreamError, RegexMatchError, VideoUnavailable) as e:
                    source = await YTDLSource.from_url(song.url, pytube=False, live=isinstance(e, LiveStreamError), filter_=queue.filter["value"], start_at=song.start_at)

                    if not source: raise Exception("Invalid source")
                    elif isinstance(source, dict):
                        embed = discord.Embed(
                            description=f"Added **{len(source['entries'])}** song(s) to queue from the playlist: [{source.get('title') or '[ Unknown title ]'}]({song.url})",
                            color=EmbedColor.GREEN
                        )
                        await ctx.followup.send(embed=embed)

                        added_songs = [PlayerEntry({
                            "url": track["url"],
                            "title": track.get("title") or "[ Unknown title ]",
                            "duration": track.get("duration"),
                            "uploader_avatar": None,
                            "source": None,
                            "start_time": 0,
                            "start_at": 0,
                            "formatted_duration": format_duration(track.get("duration")),
                            "requested_by": ctx.user.name
                        }) for track in source["entries"]]

                        queue.songs[0:1] = added_songs
                        return await self._play_song(ctx, queue.songs[0])

                    if song.title == "[ Unknown title ]": song.title = source.data.get("title") or song.title
                    if not song.uploader: song.uploader = source.data.get("uploader") or "[ Unknown uploader ]"
                    if song.duration is None:
                        duration = source.data.get("duration")
                        song.duration = (parse_duration(duration) if isinstance(duration, str) else int(duration)) if duration is not None else None
                        song.formatted_duration = format_duration(song.duration)
        except Exception as e:
            print(f"{type(e).__name__} occurred in _play_song: {e}")

            embed = discord.Embed(
                description=f"**Error:** Invalid source.",
                color=EmbedColor.RED
            )
            await ctx.followup.send(embed=embed, ephemeral=True)

            if len(queue) == 1: del queue.songs[0]
            elif len(queue):
                del queue.songs[0]
                await self._play_song(ctx, queue.songs[0])
            return
        
        if not isinstance(source, YTDLSource):
            embed = discord.Embed(
                description=f"**Error:** Invalid source.",
                color=EmbedColor.RED
            )
            return await ctx.followup.send(embed=embed, ephemeral=True)

        song.player = source
        song.player.volume = queue.volume
        if not ctx.voice_client: return

        ctx.voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(self._after_song(ctx, e), self.bot.loop))
        song.start_time = time.time()

        ignore_msg = hasattr(song, "_ignore_msg")
        loop_count = getattr(song, "_loop_count", None)
        now_playing_msg = f"**{'♪ Now playing' if queue.loop == 'Disabled' else ('∞ Now looping' if queue.loop == 'Single' else '∞ Now in loop')}:** [{song.title}]({song.url}) [**{f'{format_duration(song.start_at, False)} -> ' if song.start_at and not hasattr(song, '_sought') else ''}{song.formatted_duration}**] [**{len(queue.previous_songs) + 1} | {len(queue.previous_songs) + len(queue)}**]{f' [**{loop_count}x**]' if loop_count else ''}\n"
        now_playing_msg += (f"**Next in queue:** [{queue.songs[1].title}]({queue.songs[1].url})" if len((queue)) > 1 else "**Note:** No further songs in queue.")

        if not (ignore_msg or hasattr(song, "_replayed")) and hasattr(song, "_first"):
            request_type = getattr(ctx, "_request_type", None)

            embed = discord.Embed(
                description=now_playing_msg,
                color=EmbedColor.GREEN
            )
            embed.set_footer(text=f"{song.uploader}\n{f'Requested via a {request_type} [{ctx.user.name}]' if request_type else ''}", icon_url=song.uploader_avatar)
            if request_type:
                queue.messages["play"] = await ctx.send(embed=embed, view=await self._resolve_view(ctx))
            else:
                queue.messages["play"] = await ctx.followup.send(embed=embed, view=await self._resolve_view(ctx))
        elif not ignore_msg:
            embed = discord.Embed(
                description=now_playing_msg,
                color=EmbedColor.GREEN
            )
            embed.set_footer(text=song.uploader, icon_url=song.uploader_avatar)
            
            if queue.loop == "Single" and queue.messages["play"]:
                try:
                    await queue.messages["play"].edit(embed=embed)
                except discord.NotFound:
                    queue.messages["play"] = await ctx.send(embed=embed, view=await self._resolve_view(ctx))
            else:
                queue.messages["play"] = await ctx.send(embed=embed, view=await self._resolve_view(ctx))

    @staticmethod
    async def _flash_deafen(ctx: discord.ApplicationContext):
        if ctx.voice_client:
            await ctx.guild.change_voice_state(channel=ctx.voice_client.channel, self_deaf=False)
            await asyncio.sleep(0.25)
            await ctx.guild.change_voice_state(channel=ctx.voice_client.channel, self_deaf=True)

    @staticmethod
    async def _connect_handling(ctx: discord.ApplicationContext, play: bool = False):
        if not ctx.user.voice:
            embed = discord.Embed(
                description=f"**Note:** Please connect to a voice channel first.",
                color=EmbedColor.BLUE
            )
            await ctx.followup.send(embed=embed, ephemeral=True)
            return False
        
        channel = ctx.user.voice.channel

        if not ctx.voice_client or (ctx.voice_client and not ctx.voice_client.is_connected()):
            await channel.connect()

            embed = discord.Embed(
                description=f"**Connecting to voice channel:** <#{channel.id}>",
                color=EmbedColor.GREEN
            )
            await ctx.followup.send(embed=embed)
        elif channel != ctx.voice_client.channel:
            await ctx.voice_client.move_to(channel)

            embed = discord.Embed(
                description=f"**Moving to voice channel:** <#{channel.id}>",
                color=EmbedColor.GREEN
            )
            await ctx.followup.send(embed=embed)
        elif not play:
            embed = discord.Embed(
                description=f"**Error:** Already connected to the voice channel.",
                color=EmbedColor.RED
            )
            await ctx.followup.send(embed=embed, ephemeral=True)
            return False

        await ctx.guild.change_voice_state(channel=channel, self_deaf=True)
        return True

    @commands.slash_command(description="Attempts to repair the bot's voice connection in case of breakage")
    async def repair(self, ctx: discord.ApplicationContext):
        if not ctx.user.voice:
            embed = discord.Embed(
                description=f"**Note:** Please connect to a voice channel first.",
                color=EmbedColor.BLUE
            )
            return await ctx.respond(embed=embed, ephemeral=True)

        await self._cleanup(ctx)
        await self._initialize_queue(ctx)

        if ctx.user.voice and (channel := ctx.user.voice.channel):
            if not ctx.voice_client or (ctx.voice_client and not ctx.voice_client.is_connected()):
                await channel.connect()
            elif ctx.voice_client and ctx.voice_client.channel != channel:
                await ctx.voice_client.move_to(channel)

        embed = discord.Embed(
            description=f"Bot repaired successfully.",
            color=EmbedColor.GREEN
        )
        await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(description="Invites the bot to the voice channel")
    async def connect(self, ctx: discord.ApplicationContext):
        if not ctx.interaction.response.is_done(): await ctx.defer()

        await self._connect_handling(ctx)

    @commands.slash_command(description="Removes the bot from the voice channel and clears the queue")
    @discord.option(name="after_song", description="Disconnect once the current song has ended", required=False)
    async def disconnect(self, ctx: discord.ApplicationContext, after_song: bool = False):
        if not ctx.voice_client:
            embed = discord.Embed(
                description=f"**Error:** Already not connected to a voice channel.",
                color=EmbedColor.RED
            )
            return await ctx.respond(embed=embed, ephemeral=True)
        elif not ctx.user.voice or ctx.user.voice.channel != ctx.voice_client.channel:
            embed = discord.Embed(
                description=f"**Note:** Please connect to the voice channel first.",
                color=EmbedColor.BLUE
            )
            return await ctx.respond(embed=embed, ephemeral=True)
    
        queue = self.queue[ctx.guild.id]
        current_song = queue.songs[0] if len(queue) else None
        disconnect_after = hasattr(current_song, "_disconnect_after") if current_song else False

        if after_song and current_song:
            setattr(current_song, "_disconnect_after", not disconnect_after)
            elapsed = format_duration(int((getattr(current_song, "_paused_at", None) or time.time()) - current_song.start_time) + current_song.start_at, False)
            embed = discord.Embed(
                description=f"**{'D' if disconnect_after else 'Cancelled d'}isconnecting after current song:** {current_song.title} [**{elapsed} | {current_song.formatted_duration}**]",
                color=EmbedColor.DARK_RED
            )
            return await ctx.respond(embed=embed)
        elif not after_song and current_song and disconnect_after:
            setattr(current_song, "_disconnect_after", False)
        
        channel = ctx.voice_client.channel
        await ctx.voice_client.disconnect()
        await self._cleanup(ctx)

        embed = discord.Embed(
            description=f"**Disconnected from current voice channel:** {channel}",
            color=EmbedColor.DARK_RED
        )
        if ctx.interaction.response.is_done():
            request_type = getattr(ctx, "_request_type", None)
            if request_type: embed.set_footer(text=f"Requested via a {request_type} [{ctx.user.name}]")
            return await ctx.send(embed=embed)
        await ctx.respond(embed=embed)

    @commands.slash_command(description="Adds and plays songs in the queue")
    @discord.option(name="query", description="The song that you wish to play (URL or query)", required=True)
    @discord.option(name="insert", description="Add the song to the given position in queue", min_value=1, required=False)
    @discord.option(name="pre_shuffle", description="Shuffle the songs of the playlist ahead of time", required=False)
    @discord.option(name="start", description="Set the song to start from the given timestamp", required=False)
    async def play(self, ctx: discord.ApplicationContext, query: str, insert: int = 0, pre_shuffle: bool = False, start: str = "0"):
        if not ctx.interaction.response.is_done(): await ctx.defer()

        if not ctx.voice_client:
            success = await self._connect_handling(ctx)
            if not success: return
        elif not ctx.user.voice or ctx.user.voice.channel != ctx.voice_client.channel:
            embed = discord.Embed(
                description=f"**Note:** Please connect to the voice channel first.",
                color=EmbedColor.BLUE
            )
            return await ctx.followup.send(embed=embed, ephemeral=True)
        
        settings = load_settings()
        key = f"{ctx.user.id}-{ctx.guild.id}"
        keyword_source = settings.get(key, {}).get("default_search") or "youtube"

        try:
            result = await pytse.search(query, keyword_source=keyword_source)
            if result.get("_error"): raise Exception("Search failed")

            queue = self.queue[ctx.guild.id]
            insert = min(insert or len(queue), len(queue))
            source = pytse.validate_url(query) or keyword_source
            emoji = getattr(Emoji, str(source).upper(), None) or ":grey_question:"

            if result.get("tracks"):
                added_songs = [PlayerEntry({
                    **track,
                    "start_time": 0,
                    "start_at": 0,
                    "formatted_duration": format_duration(track["duration"]),
                    "requested_by": ctx.user.name
                }) for track in result["tracks"]]

                if (pre_shuffle): random.shuffle(added_songs)

                queue.songs[insert:insert] = added_songs

                embed = discord.Embed(
                    description=f"{emoji} Added **{len(added_songs)}** song(s) to queue{' **pre-shuffled**' if pre_shuffle else ''} from the playlist: [{result['title']}]({query}) [**{format_duration(result['duration'], False)}**]",
                    color=EmbedColor.GREEN
                )
                await ctx.followup.send(embed=embed)
            
                if len(queue) == len(added_songs):
                    return await self._play_song(ctx, queue.songs[0])

                await self._update_play_message(ctx)
            else:
                song = PlayerEntry({
                    **result,
                    "start_time": 0,
                    "start_at": parse_duration(start, result["duration"]),
                    "formatted_duration": format_duration(result["duration"]),
                    "requested_by": ctx.user.name
                })
                if not song.title: song.title = "[ Unknown title ]"
            
                queue.songs.insert(insert, song)

                if len(queue) == 1:
                    setattr(queue.songs[0], "_first", True)
                    await self._play_song(ctx, queue.songs[0])
                else:
                    request_type = getattr(ctx, "_request_type", None)

                    embed = discord.Embed(
                        description=f"**{emoji} Added to queue:** [{song.title}]({song.url}) [**{f'{format_duration(song.start_at, False)} -> ' if song.start_at and not hasattr(song, '_sought') else ''}{song.formatted_duration}**] [**{insert}**]",
                        color=EmbedColor.GREEN
                    )
                    if request_type:
                        embed.set_footer(text=f"Requested via a {request_type} [{ctx.user.name}]")
                        await ctx.send(embed=embed)
                    else:
                        await ctx.followup.send(embed=embed)
                    await self._update_play_message(ctx)
        except Exception as e:
            print(f"{type(e).__name__} occurred in play: {e}")
            embed = discord.Embed(
                description=f"**Error:** Failed to add query.",
                color=EmbedColor.RED
            )
            await ctx.followup.send(embed=embed, ephemeral=True)
    
    @commands.slash_command(description="Plays audio from a given file")
    @discord.option(name="file", description="File to play audio from", required=True)
    @discord.option(name="insert", description="Add the song to the given position in queue", min_value=1, required=False)
    @discord.option(name="start", description="Set the song to start from the given timestamp", required=False)
    async def play_file(self, ctx: discord.ApplicationContext, file: discord.Attachment, insert: int = 0, start: str = "0"):
        if not ctx.interaction.response.is_done(): await ctx.defer()

        if not ctx.voice_client:
            success = await self._connect_handling(ctx)
            if not success: return
        elif file.content_type and not file.content_type.startswith("audio/"):
            embed = discord.Embed(
                description=f"**Error:** Unsupported file format.",
                color=EmbedColor.RED
            )
            return await ctx.followup.send(embed=embed, ephemeral=True)

        queue = self.queue[ctx.guild.id]
        insert = min(insert or len(queue), len(queue))
        channels, sample_rate = 2, 48000

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(file.url) as resp:
                    if resp.status != 200: raise Exception("File download failed")
                    input_bytes = await resp.read()

            result = subprocess.run([
                "ffmpeg",
                "-i", "pipe:0",
                "-f", "s16le",
                "-acodec", "pcm_s16le",
                "-ar", str(sample_rate),
                "-ac", str(channels),
                "pipe:1"
            ], input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)

            pcm_bytes = result.stdout
            total_samples = len(pcm_bytes) / (channels * 2)
            duration = int(total_samples / sample_rate)
        except subprocess.CalledProcessError as e:
            print(f"CalledProcessError occurred in file duration calculation:", e)
            duration = None

        song = PlayerEntry({
            "url": file.url,
            "title": file.filename.replace("_", " "),
            "uploader": ctx.user.name,
            "uploader_avatar": ctx.user.display_avatar,
            "duration": duration,
            "source": "file",
            "start_time": 0,
            "start_at": parse_duration(start, duration),
            "formatted_duration": format_duration(duration),
            "requested_by": ctx.user.name
        })
        queue.songs.insert(insert, song)

        if len(queue) == 1:
            setattr(queue.songs[0], "_first", True)
            await self._play_song(ctx, queue.songs[0])
        else:
            embed = discord.Embed(
                description=f"**{Emoji.FILE} Added to queue:** [{song.title}]({song.url}) [**{f'{format_duration(song.start_at, False)} -> ' if song.start_at and not hasattr(song, '_sought') else ''}{song.formatted_duration}**] [**{insert}**]",
                color=EmbedColor.GREEN
            )
            await ctx.followup.send(embed=embed)

        await self._update_play_message(ctx)

    @commands.slash_command(description="Skips to the next, or to the specified, song in the queue")
    @discord.option(name="to", description="The position in queue you wish to skip to", min_value=1, required=False)
    async def skip(self, ctx: discord.ApplicationContext, to: int = 1):
        if not (ctx.voice_client and ctx.voice_client.is_playing()):
            embed = discord.Embed(
                description=f"**Error:** Nothing is currently playing.",
                color=EmbedColor.RED
            )
            return await ctx.respond(embed=embed, ephemeral=True)
        elif not ctx.user.voice or ctx.user.voice.channel != ctx.voice_client.channel:
            embed = discord.Embed(
                description=f"**Note:** Please connect to the voice channel first.",
                color=EmbedColor.BLUE
            )
            return await ctx.respond(embed=embed, ephemeral=True)
        
        queue = self.queue[ctx.guild.id]
        to = min(to, max(1, len(queue) - 1))
        current_song = queue.songs[0]
        if to != 1: del queue.songs[1:to]

        ctx.voice_client.stop()
        request_type = getattr(ctx, "_request_type", None)

        embed = discord.Embed(
            description=f"**↷ Skipped current song:** {current_song.title}" + (f"\n+ **{to - 1}** more..." if to != 1 else ""),
            color=EmbedColor.BLUE
        )
        if request_type:
            embed.set_footer(text=f"Requested via a {request_type} [{ctx.user.name}]")
            await ctx.send(embed=embed)
        else:
            await ctx.respond(embed=embed)

    @commands.slash_command(description="Removes songs from the queue")
    @discord.option(name="from_", description="The start position of the queue removal, or positions separated by semicolons (i.e. pos1;pos2;...)", required=True)
    @discord.option(name="to", description="The end position of the queue removal", min_value=1, required=False)
    async def remove(self, ctx: discord.ApplicationContext, from_: str, to: int = 0):
        if not ctx.interaction.response.is_done(): await ctx.defer()

        queue = self.queue[ctx.guild.id]

        if not ctx.voice_client or queue.empty():
            embed = discord.Embed(
                description=f"**Error:** Queue is already empty.",
                color=EmbedColor.RED
            )
            return await ctx.followup.send(embed=embed, ephemeral=True)
        elif not ctx.user.voice or ctx.user.voice.channel != ctx.voice_client.channel:
            embed = discord.Embed(
                description=f"**Note:** Please connect to the voice channel first.",
                color=EmbedColor.BLUE
            )
            return await ctx.followup.send(embed=embed, ephemeral=True)
        
        if not from_.isdigit():
            split_indices = from_.split(";")
    
            indices = sorted({max(1, min(int(i), len(queue) - 1)) for i in split_indices if i.strip().isdigit()}, reverse=True)

            if not indices: 
                embed = discord.Embed(
                    description=f"**Error:** Invalid positions provided (pos1;pos2;...).",
                    color=EmbedColor.RED
                )
                return await ctx.followup.send(embed=embed, ephemeral=True)
            
            request_type = getattr(ctx, "_request_type", None)

            if request_type:
                if not queue.messages["remove_content"]: queue.messages["remove_content"] = "**⊝ Removed the following song(s) from queue:**"

                removed_song_count = queue.messages["remove_content"].count("\n")
                queue.messages["remove_content"] += f"\n[**{removed_song_count + 1}**] {queue.songs[1].title}"
                del queue.songs[1]

                await self._update_play_message(ctx)

                embed = discord.Embed(
                    description=queue.messages["remove_content"],
                    color=EmbedColor.DARK_RED
                )
                embed.set_footer(text=f"Requested via a {request_type} [{ctx.user.name}]")
                if queue.messages["remove"]:
                    try:
                        return await queue.messages["remove"].edit(embed=embed)
                    except discord.NotFound:
                        pass
                queue.messages["remove"] = await ctx.send(embed=embed)
                return
            
            removed_songs = "\n".join([f"[**{i}**] {queue.songs[i].title}" for i in indices])

            for i in indices:
                del queue.songs[i]

            await self._update_play_message(ctx)
            
            embed = discord.Embed(
                description=f"**⊝ Removed the following song(s) from queue:**\n{removed_songs}",
                color=EmbedColor.DARK_RED
            )
            return await ctx.followup.send(embed=embed)
        
        new_from_ = max(1, min(int(from_), len(queue) - 1))
        to = min(to or new_from_, len(queue) - 1)
        if new_from_ > to: new_from_, to = to, new_from_

        removed_song = queue.songs[new_from_]
        del queue.songs[new_from_:to + 1]

        await self._update_play_message(ctx)   

        embed = discord.Embed(
            description=f"**⊝ Removed song:** {removed_song.title} [**{from_}**]" + (f"\n+ **{to - new_from_}** more..." if new_from_ != to else ""),
            color=EmbedColor.DARK_RED
        )
        await ctx.followup.send(embed=embed)

    @commands.slash_command(description="Clears the queue")
    @discord.option(name="from_", description="The start position of the queue clear", min_value=1, required=False)
    async def clear(self, ctx: discord.ApplicationContext, from_: int = 1):
        await self.remove(ctx, str(from_), max(1, len(self.queue[ctx.guild.id])))

    @commands.slash_command(description="Shuffles the queue")
    @discord.option(name="from_", description="The start position of the queue shuffle", min_value=1, required=False)
    @discord.option(name="to", description="The end position of the queue shuffle", min_value=1, required=False)
    async def shuffle(self, ctx: discord.ApplicationContext, from_: int = 1, to: int = 0):
        queue = self.queue[ctx.guild.id]

        if not ctx.voice_client or queue.empty():
            embed = discord.Embed(
                description=f"**Error:** Queue is empty.",
                color=EmbedColor.RED
            )
            return await ctx.respond(embed=embed, ephemeral=True)
        elif not ctx.user.voice or ctx.user.voice.channel != ctx.voice_client.channel:
            embed = discord.Embed(
                description=f"**Note:** Please connect to the voice channel first.",
                color=EmbedColor.BLUE
            )
            return await ctx.respond(embed=embed, ephemeral=True)
        
        from_, to = min(from_, len(queue) - 1), min(to or len(queue) - 1, len(queue) - 1)
        if from_ > to: from_, to = to, from_

        queue.songs[from_:to + 1] = random.sample(queue.songs[from_:to + 1], to - from_ + 1)

        embed = discord.Embed(
            description=f"**⤮ Shuffled {to - from_ + 1}** song(s) in queue. [**{from_}-{to}**]",
            color=EmbedColor.PURPLE
        )
        await ctx.respond(embed=embed)

    @commands.slash_command(description="Moves the song to the specified position in the queue")
    @discord.option(name="from_", description="The current position of the song in queue", min_value=1, required=True)
    @discord.option(name="to", description="The position in queue you wish to move the song to", min_value=1, required=True)
    @discord.option(name="replace", description="Replace the song in the target position", required=False)
    async def move(self, ctx: discord.ApplicationContext, from_: int, to: int, replace: bool = False):
        queue = self.queue[ctx.guild.id]

        if not ctx.voice_client or queue.empty():
            embed = discord.Embed(
                description=f"**Error:** Queue is empty.",
                color=EmbedColor.RED
            )
            return await ctx.respond(embed=embed, ephemeral=True)
        elif not ctx.user.voice or ctx.user.voice.channel != ctx.voice_client.channel:
            embed = discord.Embed(
                description=f"**Note:** Please connect to the voice channel first.",
                color=EmbedColor.BLUE
            )
            return await ctx.respond(embed=embed, ephemeral=True)
        
        from_, to = min(from_, len(queue) - 1), min(to, len(queue) - 1)
        replaced_song, moved_song = queue.songs[to], queue.songs.pop(from_)
        
        if replace:
            queue.songs[to] = moved_song

            await self._update_play_message(ctx)   
        else:
            queue.songs.insert(to, moved_song)

        embed = discord.Embed(
            description=f"**⇄ Moved song:**: {moved_song.title} [**{from_}**] -> [**{to}**]" + (f"\n**⊝ Replaced song:** {replaced_song.title}" if replace else ""),
            color=EmbedColor.PURPLE
        )
        await ctx.respond(embed=embed)

    @commands.slash_command(description="Loops either the song or the entire queue")
    @discord.option(name="mode", description="The loop mode you wish to use", choices=["Disabled", "Single", "Queue"], required=True)
    async def loop(self, ctx: discord.ApplicationContext, mode: str):
        if not ctx.interaction.response.is_done(): await ctx.defer()
        
        if not ctx.voice_client:
            embed = discord.Embed(
                description=f"**Error:** Not connected to a voice channel.",
                color=EmbedColor.RED
            )
            return await ctx.followup.send(embed=embed, ephemeral=True)
        elif not ctx.user.voice or ctx.user.voice.channel != ctx.voice_client.channel:
            embed = discord.Embed(
                description=f"**Note:** Please connect to the voice channel first.",
                color=EmbedColor.BLUE
            )
            return await ctx.followup.send(embed=embed, ephemeral=True)
        
        queue = self.queue[ctx.guild.id]
        queue.loop = mode

        await self._update_play_message(ctx)
        request_type = getattr(ctx, "_request_type", None)

        embed = discord.Embed(
            description=f"**⟳ Set loop mode to:** {mode}",
            color=EmbedColor.BLUE
        )
        if request_type:
            embed.set_footer(text=f"Requested via a {request_type} [{ctx.user.name}]")
            if queue.messages["loop"]:
                try:
                    return await queue.messages["loop"].edit(embed=embed)
                except discord.NotFound:
                    pass
            queue.messages["loop"] = await ctx.send(embed=embed)
        else:
            queue.messages["loop"] = await ctx.followup.send(embed=embed)

    @commands.slash_command(description="Toggles autoplay for the queue")
    async def autoplay(self, ctx: discord.ApplicationContext):
        if not ctx.voice_client:
            embed = discord.Embed(
                description=f"**Error:** Not connected to a voice channel.",
                color=EmbedColor.RED
            )
            return await ctx.respond(embed=embed, ephemeral=True)
        elif not ctx.user.voice or ctx.user.voice.channel != ctx.voice_client.channel:
            embed = discord.Embed(
                description=f"**Note:** Please connect to the voice channel first.",
                color=EmbedColor.BLUE
            )
            return await ctx.respond(embed=embed, ephemeral=True)
        
        queue = self.queue[ctx.guild.id]
        queue.autoplay = not queue.autoplay

        embed = discord.Embed(
            description=f"**⮓ Set autoplay to:** {'Enabled' if queue.autoplay else 'Disabled'}",
            color=EmbedColor.PURPLE
        )
        await ctx.respond(embed=embed)

    @commands.slash_command(description="Sets the music player volume")
    @discord.option(name="level", description="Set the volume level percentage (100 by default)", min_value=0, max_value=200, required=True)
    async def volume(self, ctx: discord.ApplicationContext, level: int):
        if not ctx.interaction.response.is_done(): await ctx.defer()

        if not ctx.voice_client:
            embed = discord.Embed(
                description=f"**Error:** Not connected to a voice channel.",
                color=EmbedColor.RED
            )
            return await ctx.followup.send(embed=embed, ephemeral=True)
        elif not ctx.user.voice or ctx.user.voice.channel != ctx.voice_client.channel:
            embed = discord.Embed(
                description=f"**Note:** Please connect to the voice channel first.",
                color=EmbedColor.BLUE
            )
            return await ctx.followup.send(embed=embed, ephemeral=True)
        
        queue = self.queue[ctx.guild.id]
        queue.volume = max(0, min(200, round(level / 100, 2)))
        if ctx.voice_client.is_playing() and queue.songs[0].player: queue.songs[0].player.volume = queue.volume
        request_type = getattr(ctx, "_request_type", None)

        embed = discord.Embed(
            description=f"**🕪 Set volume to:** {level} %",
            color=EmbedColor.BLUE
        )
        if request_type:
            embed.set_footer(text=f"Requested via a {request_type} [{ctx.user.name}]")
            if queue.messages["volume"]:
                try:
                    return await queue.messages["volume"].edit(embed=embed)
                except discord.NotFound:
                    pass
            queue.messages["volume"] = await ctx.send(embed=embed)
        else:
            queue.messages["volume"] = await ctx.followup.send(embed=embed)

    @commands.slash_command(description="Toggles pause for the current song")
    async def pause(self, ctx: discord.ApplicationContext):
        if not ctx.interaction.response.is_done(): await ctx.defer()

        if not (ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused())):
            embed = discord.Embed(
                description=f"**Error:** Nothing is currently playing.",
                color=EmbedColor.RED
            )
            return await ctx.followup.send(embed=embed, ephemeral=True)
        elif not ctx.user.voice or ctx.user.voice.channel != ctx.voice_client.channel:
            embed = discord.Embed(
                description=f"**Note:** Please connect to the voice channel first.",
                color=EmbedColor.BLUE
            )
            return await ctx.followup.send(embed=embed, ephemeral=True)
        
        queue = self.queue[ctx.guild.id]
        song = queue.songs[0]

        if ctx.voice_client.is_playing():
            setattr(song, "_paused_at", time.time())
            ctx.voice_client.pause()
        else:
            if song.start_time and getattr(song, "_paused_at", None):
                song.start_time += time.time() - getattr(song, "_paused_at", time.time())
            else:
                song.start_time = time.time()

            delattr(song, "_paused_at")
            ctx.voice_client.resume()

        await self._update_play_message(ctx)
        request_type = getattr(ctx, "_request_type", None)

        embed = discord.Embed(
            description=f"**{'⯈ Resumed' if ctx.voice_client.is_playing() else '❚❚ Paused'} current song:** {song.title}",
            color=EmbedColor.BLUE
        )
        if request_type:
            embed.set_footer(text=f"Requested via a {request_type} [{ctx.user.name}]")
            if queue.messages["pause"]:
                try:
                    return await queue.messages["pause"].edit(embed=embed)
                except discord.NotFound:
                    pass
            queue.messages["pause"] = await ctx.send(embed=embed)
        else:
            queue.messages["pause"] = await ctx.followup.send(embed=embed)

    @commands.slash_command(description="Seeks a certain part of the song via a timestamp")
    @discord.option(name="timestamp", description="The timestamp to seek (i.e. hours:minutes:seconds)", required=True)
    async def seek(self, ctx: discord.ApplicationContext, timestamp: str):
        if not (ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused())):
            embed = discord.Embed(
                description=f"**Error:** Nothing is currently playing.",
                color=EmbedColor.RED
            )
            return await ctx.respond(embed=embed, ephemeral=True)
        elif not ctx.user.voice or ctx.user.voice.channel != ctx.voice_client.channel:
            embed = discord.Embed(
                description=f"**Note:** Please connect to the voice channel first.",
                color=EmbedColor.BLUE
            )
            return await ctx.respond(embed=embed, ephemeral=True)
        
        queue = self.queue[ctx.guild.id]
        current_song = copy.copy(queue.songs[0])

        if not current_song.duration:
            embed = discord.Embed(
                description=f"**Error:** Songs without a set duration cannot be sought.",
                color=EmbedColor.RED
            )
            return await ctx.respond(embed=embed, ephemeral=True)

        sought = parse_duration(timestamp, current_song.duration)
        current_song.start_at = sought or 0
        setattr(current_song, "_ignore_msg", True)
        setattr(current_song, "_sought", True)

        setattr(queue.songs[0], "_ignore_add", True)
        setattr(queue.songs[0], "_ignore_clear", True)

        queue.songs.insert(1, current_song)
        ctx.voice_client.stop()

        embed = discord.Embed(
            description=f"**⌕ Sought timestamp:** {format_duration(sought, False)} | {current_song.formatted_duration}",
            color=EmbedColor.BLUE
        )
        await ctx.respond(embed=embed)

    @commands.slash_command(description="Applies an audio filter over the songs")
    @discord.option(name="mode", description="The filter mode you wish to use", choices=["Disabled", "Nightcore", "BassBoost", "EarRape", "Doomer", "8D"], required=True)
    @discord.option(name="intensity", description="Set the filter intensity percentage (35 by default)", min_value=0, max_value=100, required=True)
    async def filter(self, ctx: discord.ApplicationContext, mode: str, intensity: int = -1):
        if not ctx.voice_client:
            embed = discord.Embed(
                description=f"**Error:** Not connected to a voice channel.",
                color=EmbedColor.RED
            )
            return await ctx.respond(embed=embed, ephemeral=True)
        elif not ctx.user.voice or ctx.user.voice.channel != ctx.voice_client.channel:
            embed = discord.Embed(
                description=f"**Note:** Please connect to the voice channel first.",
                color=EmbedColor.BLUE
            )
            return await ctx.respond(embed=embed, ephemeral=True)
        
        queue = self.queue[ctx.guild.id]
        intensity = intensity if intensity != -1 else queue.filter["intensity"]

        filter_values = {
            "Disabled": "anull",
            "Nightcore": f"rubberband=pitch={1 + intensity / 100}:tempo=1",
            "BassBoost": f"bass=g={intensity // 5}",
            "EarRape": f"acrusher=level_in={intensity // 5}:level_out={1 + ((intensity // 5) * 2)}:bits=8:mode=log:aa=1",
            "Doomer": f"dynaudnorm=f=200,aecho=1.0:0.5:10:{min(0.99, 0.5 + 0.01 * (intensity - 35))},rubberband=pitch={min(1, 1.15 - intensity / 100)}",
            "8D": f"apulsator=hz={max(0.01, 2.0 * (1 - math.exp(-0.00146 * intensity))):.2f}"
        }
        queue.filter = {"name": mode, "value": filter_values[mode], "intensity": intensity}

        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            current_song = copy.copy(queue.songs[0])
            current_song.start_at = int(time.time() - current_song.start_time) + current_song.start_at
            setattr(current_song, "_ignore_msg", True)
            setattr(current_song, "_sought", True)

            setattr(queue.songs[0], "_ignore_add", True)
            setattr(queue.songs[0], "_ignore_clear", True)

            queue.songs.insert(1, current_song)
            ctx.voice_client.stop()

        embed = discord.Embed(
            description=f"**⎘ Set filter to:** {mode} [**{intensity} %**]",
            color=EmbedColor.BLUE
        )
        await ctx.respond(embed=embed)

    @commands.slash_command(description="Gets lyrics for the currently playing song")
    @discord.option(name="title", description="Get lyrics from the specified title instead", required=False)
    async def lyrics(self, ctx: discord.ApplicationContext, title: str = ""):
        if not title and not (ctx.voice_client and ctx.voice_client.is_playing()):
            embed = discord.Embed(
                description=f"**Error:** Nothing is currently playing.",
                color=EmbedColor.RED
            )
            return await ctx.respond(embed=embed, ephemeral=True)

        title = re.sub(r"\[[^\[\]]*]|\([^()]*\)", "", title if title else str(self.queue[ctx.guild.id].songs[0].title))

        try:
            song = GENIUS.search_song(title=title, get_full_info=False)
        except discord.ApplicationCommandInvokeError:
            embed = discord.Embed(
                description=f"**Error:** Request timed out, please try again.",
                color=EmbedColor.RED
            )
            return await ctx.respond(embed=embed, ephemeral=True)

        if not song:
            embed = discord.Embed(
                description=f"**Error:** No lyrics found for `{title}`",
                color=EmbedColor.YELLOW
            )
            return await ctx.respond(embed=embed, ephemeral=True)

        split_lyrics = song.lyrics.replace("\n\n\n", "\n\n").split("\n")
        if match := re.search(r"\[[^\[\]]+\]$", split_lyrics[0]): split_lyrics[0] = match.group()
        lyrics = "\n".join(split_lyrics)

        try:
            embed = discord.Embed(
                description=f"**☲ [{song.title}]({song.url}) Lyrics**\n\n{lyrics}",
                color=EmbedColor.YELLOW
            )
            await ctx.respond(embed=embed)
        except discord.HTTPException:
            embed = discord.Embed(
                description=f"**☲ [{song.title}]({song.url}) Lyrics**\n\nLyrics too long for Discord. Click on the title to view them.",
                color=EmbedColor.YELLOW
            )
            await ctx.respond(embed=embed)

    @commands.slash_command(description="Replays previous songs from the queue")
    @discord.option(name="from_", description="Current position of the song in previous queue", min_value=1, required=False)
    @discord.option(name="insert", description="Add the song to the given position in queue", min_value=1, required=False)
    @discord.option(name="instant", description="Replay the song instantly", required=False)
    async def replay(self, ctx: discord.ApplicationContext, from_: int = 0, insert: int = 1, instant: bool = False):
        queue = self.queue[ctx.guild.id]

        if not (ctx.voice_client and len(queue.previous_songs)):
            embed = discord.Embed(
                description=f"**Error:** No previous songs associated with this queue.",
                color=EmbedColor.RED
            )
            return await ctx.respond(embed=embed, ephemeral=True)
        elif not ctx.user.voice or ctx.user.voice.channel != ctx.voice_client.channel:
            embed = discord.Embed(
                description=f"**Note:** Please connect to the voice channel first.",
                color=EmbedColor.BLUE
            )
            return await ctx.respond(embed=embed, ephemeral=True)
        
        from_ = min(from_ - 1 or len(queue.previous_songs) - 1, len(queue.previous_songs) - 1)
        replayed_song = queue.previous_songs.pop(from_)
        setattr(replayed_song, "_replayed", True)
        queue.songs.insert(insert, replayed_song)

        await self._update_play_message(ctx)
        request_type = getattr(ctx, "_request_type", None)

        if request_type:
            current_song = copy.copy(queue.songs[0])
            setattr(queue.songs[0], "_ignore_add", True)
            queue.songs.insert(2, current_song)

        embed = discord.Embed(
            description=f"**⭟ Replaying song:** {replayed_song.title} [**{insert}**]",
            color=EmbedColor.PURPLE
        )
        if request_type:
            embed.set_footer(text=f"Requested via a {request_type} [{ctx.user.name}]")
            await ctx.send(embed=embed)
        else:
            await ctx.respond(embed=embed)

        if not (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            await self._play_song(ctx, queue.songs[0])
        elif instant:
            ctx.voice_client.stop()
    
    @commands.slash_command(description="Displays songs in queue, with the ability to seek them")
    @discord.option(name="to", description="The end position of the queue display", min_value=1, required=False)
    @discord.option(name="from_", description="The start position of the queue display", min_value=1, required=False)
    @discord.option(name="seek", description="Seek songs via given keywords", required=False)
    @discord.option(name="previous", description="Display the previous queue", required=False)
    async def view(self, ctx: discord.ApplicationContext, to: int = 0, from_: int = 0, seek: str = "", previous: bool = False):
        queue = self.queue[ctx.guild.id]
        previous_offset = 1 if previous else 0
        queue_songs = (queue.previous_songs if previous else queue.songs) if queue else []
        queue_length = len(queue_songs) - (not previous_offset)

        to = ((max(1, min(queue_length if (not to and (from_ or seek)) else (to or 10), queue_length)))) - previous_offset
        from_ = (max(1, min(from_ or 1, queue_length))) - previous_offset
        if from_ > to: from_, to = to, from_

        displayed_song_count = to + 1 - from_
        joined_queue, char_count, seek_excess = "", 0, 0
        
        for i, song in enumerate(queue_songs[from_:to + 1]):
            if seek and song.title and seek.lower() not in song.title.lower():
                seek_excess += 1
                continue

            queue_entry = f"[**{from_ + i + previous_offset}**] {song.title} [**{f'{format_duration(song.start_at, False)} -> ' if song.start_at and not hasattr(song, '_sought') else ''}{song.formatted_duration}**]"
            
            if char_count + len(queue_entry) > 3940:
                displayed_song_count = i - (not previous_offset)
                break

            joined_queue += f"{queue_entry}\n"
            char_count += len(queue_entry)

        excess = queue_length - displayed_song_count + seek_excess
        current_song = queue.songs[0] if len(queue) else None
        total_duration = sum(song.duration - song.start_at for song in queue_songs[(not previous_offset):] if song.duration)
        filter_intensity_msg = f"[{queue.filter['intensity']} %]" if queue and queue.filter["name"] != "Disabled" else ""

        if current_song:
            elapsed = format_duration(int((getattr(current_song, "_paused_at", None) or time.time()) - current_song.start_time) + current_song.start_at, False)
            footer_msg = f"> Now playing: {current_song.title} [{elapsed} | {current_song.formatted_duration}]\n> Volume: {queue.volume * 100} % | Filter: {queue.filter['name']}{filter_intensity_msg} | Loop: {queue.loop} | Autoplay: {'Enabled' if queue.autoplay else 'Disabled'}"
        else:
            footer_msg = f"> Volume: {queue.volume * 100} % | Filter: {queue.filter['name']}{filter_intensity_msg} | Loop: {queue.loop} | Autoplay: {'Enabled' if queue.autoplay else 'Disabled'}"

        if not joined_queue:
            embed = discord.Embed(
                description=f"**\\👁 In{' previous' if previous else ''} queue** matching `{seek}` [**{from_ + previous_offset}-{to + previous_offset}**]:\nNo matches found." if seek else "Queue is empty.",
                color=EmbedColor.YELLOW
            )
            embed.set_footer(text=footer_msg)
            return await ctx.respond(embed=embed)
        
        excess_msg = f"+ **{excess}** more...\n" if excess else ""
        embed = discord.Embed(
            description=f"**\\👁 In{' previous' if previous else ''} queue**{f' matching `{seek}`' if seek else ''} [**{from_ + previous_offset}-{to + previous_offset}**]:\n{joined_queue}{excess_msg}\n**In total: {queue_length}** song(s) [**{format_duration(total_duration, False)}**]",
            color=EmbedColor.YELLOW
        )
        embed.set_footer(text=footer_msg)
        await ctx.respond(embed=embed)
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        voice_channel = before.channel or after.channel
        if not voice_channel: return

        voice_client = member.guild.voice_client
        if not voice_client or voice_client.channel != voice_channel: return

        assert self.bot.user

        bot_connected = any(member.id == self.bot.user.id for member in voice_channel.members)
        non_bot_members = [member for member in voice_channel.members if not member.bot]
        queue = self.queue[member.guild.id]
        if not queue: return

        if voice_client and before.self_mute and not after.self_mute:
            settings = load_settings()
            key = f"{member.id}-{member.guild.id}"
            cctx = copy.copy(queue.ctx)
            setattr(cctx, "_request_type", "voice command")
            if settings.get(key, {}).get("speech_recognition"): await self._detect_speech(cctx)

        if not bot_connected or len(non_bot_members) == 0:
            text_channel = self.bot.get_channel(queue.text_channel)
            await self._cleanup(queue.ctx)
            await voice_client.disconnect()

            if isinstance(text_channel, (discord.TextChannel, discord.Thread)):
                if not bot_connected:
                    embed = discord.Embed(
                        description=f"**Disconnected from current voice channel:** {voice_channel}",
                        color=EmbedColor.DARK_RED
                    )
                    return await text_channel.send(embed=embed)

                embed = discord.Embed(
                    description=f"**Everyone has left the voice channel:** {voice_channel}",
                    color=EmbedColor.DARK_RED
                )
                embed.set_footer(text="Disconnecting, until next time.")
                await text_channel.send(embed=embed)

def setup(bot):
    bot.add_cog(Music(bot))

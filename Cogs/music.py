import discord
from discord import option
from discord.ui import Button, View
from discord.ext import commands, tasks
from pytube import Playlist
from sclib import Track as SCTrack, Playlist as SCPlaylist
import random
import asyncio
import requests
import yt_dlp.utils
import googleapiclient.errors
from concurrent.futures import ThreadPoolExecutor
from Cogs.utils import format_duration, parse_timestamp, connect_handling, get_language_strings, Constants


QUEUE = {}
PLAYER_INFO = {}
PLAY_TIMER = {}
PLAYER_MOD = {}
INVOKED = {}


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.50):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get("title")
        self.duration = data.get("duration")
        self.uploader = data.get("uploader")
        self.channel_id = data.get("channel_id")
        self.url = data.get("webpage_url")

        self.start_at_seconds = 0
        self.start_at = None
        self.formatted_duration = format_duration(self.duration)

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False, filter_=None, start_at=None):
        ffmpeg_options = {"before_options": f"{f'-ss {start_at}' if start_at else ''} "
                                            f"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                          "options": f"{f'-vn {filter_}' if filter_ else ''}"}

        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(ThreadPoolExecutor(),
                                          lambda: Constants.YTDL.extract_info(url, download=not stream))

        if "entries" in data:
            data = data["entries"][0]

        filename = data["url"] if stream else Constants.YTDL.prepare_filename(data)

        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        channel = after.channel or before.channel
        if not channel:
            return

        if member.guild.voice_client and member.guild.voice_client.channel == before.channel:
            text_channel = self.bot.get_channel(PLAYER_INFO.get(member.guild.id, {}).get("TextChannel"))

            if len(channel.members) < 2 or all([member.bot for member in channel.members]):
                strings = await get_language_strings(member)

                await self.cleanup(member)

                try:
                    await member.guild.voice_client.disconnect()

                    embed = discord.Embed(
                        description=strings["Music.EmptyChannel"].format(before.channel),
                        color=discord.Color.dark_red(),
                    )
                    embed.set_footer(text=strings["Music.Disconnecting"])
                    await text_channel.send(embed=embed)
                except AttributeError:
                    embed = discord.Embed(
                        description=strings["Music.Disconnect"].format(before.channel),
                        color=discord.Color.dark_red(),
                    )
                    await text_channel.send(embed=embed)

    @tasks.loop()
    async def convert(self, ctx):
        try:
            if len(QUEUE[ctx.guild.id]["Current"]) >= 11:
                count = 11
            else:
                count = len(QUEUE[ctx.guild.id]["Current"])

            for song_index in range(1, count):
                if not ctx.voice_client or not ctx.voice_client.is_playing() or song_index == count:
                    break
                elif not isinstance(QUEUE[ctx.guild.id]["Current"][song_index], YTDLSource):
                    try:
                        QUEUE[ctx.guild.id]["Current"][song_index] = await YTDLSource.from_url(
                                                                            QUEUE[ctx.guild.id]["Current"][song_index],
                                                                            loop=self.bot.loop, stream=True)
                    except (TypeError, IndexError):
                        QUEUE[ctx.guild.id]["Current"].pop(song_index)
                        continue
        except (IndexError, KeyError, TypeError):
            self.convert.cancel()
            return

        self.convert.cancel()

    @tasks.loop()
    async def duration_counter(self, ctx, player_counter: int):
        try:
            if PLAY_TIMER[ctx.guild.id]["Old"] >= player_counter:
                PLAY_TIMER[ctx.guild.id]["Old"] = player_counter

            PLAY_TIMER[ctx.guild.id]["Raw"] = PLAY_TIMER[ctx.guild.id]["Old"]

            while PLAY_TIMER[ctx.guild.id]["Raw"] < player_counter:
                try:
                    await asyncio.sleep(1)

                    if INVOKED[ctx.guild.id]:
                        continue

                    if ctx.voice_client and not ctx.voice_client.is_paused() and ctx.voice_client.is_playing() and \
                            PLAY_TIMER[ctx.guild.id]["Act"] != PLAYER_INFO[ctx.guild.id]["Object"].formatted_duration:
                        if PLAYER_MOD[ctx.guild.id]["Filter"]["Name"] == "Nightcore":
                            PLAY_TIMER[ctx.guild.id]["Raw"] += 1 + PLAYER_MOD[ctx.guild.id]["Filter"]["Intensity"] / 100
                        else:
                            PLAY_TIMER[ctx.guild.id]["Raw"] += 1

                        PLAY_TIMER[ctx.guild.id]["Act"] = format_duration(int(PLAY_TIMER[ctx.guild.id]["Raw"]),
                                                                          PLAYER_INFO[ctx.guild.id]["DurationSec"])
                except (AttributeError, KeyError):
                    PLAY_TIMER[ctx.guild.id]["Raw"], PLAY_TIMER[ctx.guild.id]["Act"] = 0, ""
                    break
            else:
                PLAY_TIMER[ctx.guild.id]["Raw"] = player_counter
                PLAY_TIMER[ctx.guild.id]["Act"] = format_duration(int(PLAY_TIMER[ctx.guild.id]["Raw"]),
                                                                  PLAYER_INFO[ctx.guild.id]["DurationSec"])
        except KeyError:
            return

    @staticmethod
    async def button_edit_handling(ctx, interaction, views):
        if len(QUEUE[ctx.guild.id]["Current"]) - 1 < 1 and not QUEUE[ctx.guild.id]["Previous"]:
            await interaction.response.edit_message(view=views[0])
        elif len(QUEUE[ctx.guild.id]["Current"]) - 1 >= 1 and not QUEUE[ctx.guild.id]["Previous"]:
            await interaction.response.edit_message(view=views[1])
        elif len(QUEUE[ctx.guild.id]["Current"]) - 1 < 1 and QUEUE[ctx.guild.id]["Previous"]:
            await interaction.response.edit_message(view=views[2])
        else:
            await interaction.response.edit_message(view=views[3])

    @staticmethod
    async def song_deletion_handling(ctx, player):
        if PLAYER_MOD[ctx.guild.id]["Loop"] == "Queue":
            if len(QUEUE[ctx.guild.id]["Current"]) - 1 < 1:
                PLAYER_INFO[ctx.guild.id]["LoopCount"] += 1
            QUEUE[ctx.guild.id]["Current"].append(player.url)
        elif PLAYER_MOD[ctx.guild.id]["Loop"] == "Single":
            QUEUE[ctx.guild.id]["Current"].insert(1, player.url)
            PLAYER_INFO[ctx.guild.id]["LoopCount"] += 1
        QUEUE[ctx.guild.id]["Current"].pop(0)

        if not PLAYER_INFO[ctx.guild.id]["Backed"] and (PLAYER_MOD[ctx.guild.id]["Loop"] != "Queue" and
                                                        PLAYER_MOD[ctx.guild.id]["Loop"] != "Single"):
            QUEUE[ctx.guild.id]["Previous"].append(PLAYER_INFO[ctx.guild.id]["URL"])
        PLAYER_INFO[ctx.guild.id]["Backed"] = False

    async def resolve_player_start(self, ctx, query: str, timestamp: str):
        strings = await get_language_strings(ctx)

        try:
            if timestamp:
                timer_value = await parse_timestamp(ctx, timestamp=timestamp)
                sought = format_duration(timer_value, PLAYER_INFO[ctx.guild.id]["DurationSec"])

                player = await YTDLSource.from_url(query.split("&list=")[0], loop=self.bot.loop, stream=True,
                                                   start_at=sought)
                player.start_at_seconds = min(timer_value, player.duration)
                player.start_at = str(min(sought, player.formatted_duration))
            else:
                player = await YTDLSource.from_url(query.split("&list=")[0], loop=self.bot.loop, stream=True)
        except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError):
            embed = discord.Embed(
                description=strings["Errors.VideoUnavailable"],
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return
        except IndexError:
            embed = discord.Embed(
                description=strings["Errors.NoResults"],
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        return player

    async def cleanup(self, ctx):
        if self.convert.is_running():
            self.convert.cancel()
        if self.duration_counter.is_running():
            self.duration_counter.cancel()

        try:
            channel = self.bot.get_guild(int(ctx.guild.id)).get_channel(PLAYER_INFO[ctx.guild.id]["TextChannel"])
            message = await channel.fetch_message(PLAYER_INFO[ctx.guild.id]["EmbedID"])
            await message.edit(view=None)
        except (discord.NotFound, discord.HTTPException, AttributeError, KeyError, UnboundLocalError):
            pass

        for dictionary in (QUEUE, PLAYER_INFO, PLAY_TIMER, PLAYER_MOD, INVOKED):
            try:
                if dictionary == QUEUE:
                    dictionary[ctx.guild.id]["Current"].clear(), dictionary[ctx.guild.id]["Previous"].clear()
                elif dictionary == PLAYER_INFO:
                    dictionary[ctx.guild.id]["Removed"].clear()
                del dictionary[ctx.guild.id]
            except KeyError:
                continue

    @commands.slash_command(description="Invites the bot to the voice channel")
    async def connect(self, ctx):
        await ctx.defer()

        channel = await connect_handling(ctx)

        if not channel:
            await self.cleanup(ctx)
            return
        PLAYER_INFO[ctx.guild.id]["TextChannel"] = ctx.channel.id

    @commands.slash_command(description="Adds and plays songs in the queue")
    @option(name="query", description="The song that you want to play (SoundCloud/Spotify/YouTube URL, or query)",
            required=True)
    @option(name="insert", description="Add the song to the given position in queue", required=False)
    @option(name="pre_shuffle", description="Shuffle the songs of the playlist ahead of time", choices=[True, False],
            required=False)
    @option(name="ignore_live", description="Attempts to ignore songs with '(live)' in their name",
            choices=[True, False], required=False)
    @option(name="start_at", description="Sets the song to start from the given timestamp", required=False)
    async def play(self, ctx, *, query: str, insert: int = None, pre_shuffle: bool = False, ignore_live: bool = False,
                   start_at: str = None):
        try:
            await ctx.defer()
        except (discord.ApplicationCommandInvokeError, discord.InteractionResponded, discord.NotFound):
            pass

        strings = await get_language_strings(ctx)
        channel = await connect_handling(ctx, play_command=True)

        if not channel:
            if not ctx.voice_client:
                await self.cleanup(ctx)
            return
        PLAYER_INFO[ctx.guild.id]["TextChannel"] = ctx.channel.id

        volumemin_button = Button(style=discord.ButtonStyle.danger, emoji="<:volume_mute:1143513586967257190", row=1)
        volumedown_button = Button(style=discord.ButtonStyle.danger, emoji="<:volume_down:1143513584505192520", row=1)
        volumemid_button = Button(style=discord.ButtonStyle.secondary, emoji="<:volume_mid:1143514064023212174", row=1)
        volumeup_button = Button(style=discord.ButtonStyle.success, emoji="<:volume_up:1143513588623999087", row=1)
        volumemax_button = Button(style=discord.ButtonStyle.success, emoji="<:volume:1142886748200910959", row=1)
        loop_button = Button(style=discord.ButtonStyle.secondary, emoji="<loopy:1196862829752500265>", row=2)
        back_button = Button(style=discord.ButtonStyle.secondary, label="Back",
                             emoji="<:goback:1142844613003067402>", row=2)
        pause_button = Button(style=discord.ButtonStyle.secondary, label="Pause",
                              emoji="<:playpause:1086408066490183700>", row=2)
        skip_button = Button(style=discord.ButtonStyle.secondary, label="Skip",
                             emoji="<:skip:1086405128787067001>", row=2)
        remove_button = Button(style=discord.ButtonStyle.danger, emoji="<:remove:1197082264924852325>", row=2)

        async def pause_button_callback(interaction: discord.Interaction):
            PLAYER_INFO[ctx.guild.id]["ButtonInvoke"] = interaction.user.name
            await self.pause(ctx)

            if ctx.voice_client and ctx.voice_client.is_paused():
                pause_button.style = discord.ButtonStyle.primary
            else:
                pause_button.style = discord.ButtonStyle.secondary

            PLAYER_INFO[ctx.guild.id]["ButtonInvoke"] = None
            await self.button_edit_handling(ctx, interaction, views=[view, view2, view3, view4])

        async def skip_button_callback(interaction: discord.Interaction):
            PLAYER_INFO[ctx.guild.id]["ButtonInvoke"] = interaction.user.name
            await self.skip(ctx)
            PLAYER_INFO[ctx.guild.id]["ButtonInvoke"] = None
            await interaction.response.defer()

        async def remove_button_callback(interaction: discord.Interaction):
            PLAYER_INFO[ctx.guild.id]["ButtonInvoke"] = interaction.user.name
            await self.remove(ctx, from_="1")
            PLAYER_INFO[ctx.guild.id]["ButtonInvoke"] = None
            await self.button_edit_handling(ctx, interaction, views=[view, view2, view3, view4])

        async def back_button_callback(interaction: discord.Interaction):
            PLAYER_INFO[ctx.guild.id]["ButtonInvoke"] = interaction.user.name
            await self.replay(ctx)
            PLAYER_INFO[ctx.guild.id]["ButtonInvoke"] = None
            await interaction.response.defer()

        async def volumemin_button_callback(interaction: discord.Interaction):
            PLAYER_INFO[ctx.guild.id]["ButtonInvoke"] = interaction.user.name
            await self.volume(ctx, level=0)
            PLAYER_INFO[ctx.guild.id]["ButtonInvoke"] = None
            await interaction.response.defer()

        async def volumedown_button_callback(interaction: discord.Interaction):
            PLAYER_INFO[ctx.guild.id]["ButtonInvoke"] = interaction.user.name
            await self.volume(ctx, level=int(PLAYER_MOD[ctx.guild.id]["Volume"] * 100) - 10)
            PLAYER_INFO[ctx.guild.id]["ButtonInvoke"] = None
            await interaction.response.defer()

        async def volumemid_button_callback(interaction: discord.Interaction):
            PLAYER_INFO[ctx.guild.id]["ButtonInvoke"] = interaction.user.name
            await self.volume(ctx, level=50)
            PLAYER_INFO[ctx.guild.id]["ButtonInvoke"] = None
            await interaction.response.defer()

        async def volumeup_button_callback(interaction: discord.Interaction):
            PLAYER_INFO[ctx.guild.id]["ButtonInvoke"] = interaction.user.name
            await self.volume(ctx, level=int(PLAYER_MOD[ctx.guild.id]["Volume"] * 100) + 10)
            PLAYER_INFO[ctx.guild.id]["ButtonInvoke"] = None
            await interaction.response.defer()

        async def volumemax_button_callback(interaction: discord.Interaction):
            PLAYER_INFO[ctx.guild.id]["ButtonInvoke"] = interaction.user.name
            await self.volume(ctx, level=100)
            PLAYER_INFO[ctx.guild.id]["ButtonInvoke"] = None
            await interaction.response.defer()

        async def loop_button_callback(interaction: discord.Interaction):
            PLAYER_INFO[ctx.guild.id]["ButtonInvoke"] = interaction.user.name

            if PLAYER_MOD[ctx.guild.id]["Loop"] == "Disabled":
                await self.loop(ctx, mode="Single")
                loop_button.style = discord.ButtonStyle.primary
            elif PLAYER_MOD[ctx.guild.id]["Loop"] == "Single":
                await self.loop(ctx, mode="Queue")
                loop_button.style = discord.ButtonStyle.success
            else:
                await self.loop(ctx, mode="Disabled")
                loop_button.style = discord.ButtonStyle.secondary

            PLAYER_INFO[ctx.guild.id]["ButtonInvoke"] = None
            await self.button_edit_handling(ctx, interaction, views=[view, view2, view3, view4])

        button_callbacks = {pause_button: pause_button_callback, skip_button: skip_button_callback,
                            remove_button: remove_button_callback, back_button: back_button_callback,
                            volumedown_button: volumedown_button_callback, volumeup_button: volumeup_button_callback,
                            volumemin_button: volumemin_button_callback, volumemid_button: volumemid_button_callback,
                            volumemax_button: volumemax_button_callback, loop_button: loop_button_callback}

        for button, callback in button_callbacks.items():
            button.callback = callback

        if insert:
            insert = min(max(insert, 1), len(QUEUE[ctx.guild.id]["Current"]))

        if not query.startswith(("http://", "https://")) and ":" in query:
            query = query.replace(":", "")
        elif query.startswith(("http://", "https://", "www.")) and not ("youtu" in query or "open.spotify.com/"
                                                                        in query or "soundcloud.com/" in query):
            embed = discord.Embed(
                description=strings["Errors.InvalidURL"],
                color=discord.Color.red(),
            )
            await ctx.respond(embed=embed)
            return
        elif not query.startswith(("http://", "https://")) and ("open.spotify.com/" in query or
                                                                "soundcloud.com/" in query):
            embed = discord.Embed(
                description=strings["Notes.EntireURL"],
                color=discord.Color.blue(),
            )
            await ctx.respond(embed=embed)
            return

        if query.startswith(("http://", "https://", "www.")) and "youtu" in query and "list=" in query:
            if "&start_radio=" in query:
                player = await self.resolve_player_start(ctx, query, start_at)

                if not player:
                    return

                if insert:
                    QUEUE[ctx.guild.id]["Current"].insert(insert, player)
                else:
                    QUEUE[ctx.guild.id]["Current"].append(player)
                queue_pos = QUEUE[ctx.guild.id]["Current"].index(player)

                embed = discord.Embed(
                    description=strings["Notes.UnsupportedPlaylist"].format(
                        strings["Music.Inserted"] if insert else strings["Music.Added"],
                        QUEUE[ctx.guild.id]["Current"][QUEUE[ctx.guild.id]["Current"].index(player)].title,
                        QUEUE[ctx.guild.id]["Current"][QUEUE[ctx.guild.id]["Current"].index(player)].url,
                        player.start_at + " → " if start_at else "", player.formatted_duration,
                        queue_pos if queue_pos else 1),
                    color=discord.Color.blue(),
                )
                await ctx.respond(embed=embed)
            else:
                PLAYER_INFO[ctx.guild.id]["ListSec"], PLAYER_INFO[ctx.guild.id]["ListDuration"] = 0, ""

                try:
                    playlist_entries = Playlist(f"https://www.youtube.com/playlist?list={query.split('list=')[1]}")

                    embed = discord.Embed(
                        description=strings["Music.AddPlaylist"].format(
                            len(playlist_entries), playlist_entries.title, query),
                        color=discord.Color.dark_green(),
                    )
                    main = await ctx.respond(embed=embed)

                    for link in playlist_entries:
                        try:
                            response = Constants.YOUTUBE.videos().list(part="snippet,contentDetails",
                                                                       id=link.split("?v=")[1]).execute()
                            video = response["items"][0]
                            uploader_and_title = f"{video['snippet']['channelTitle']} - {video['snippet']['title']}"
                            duration_part = video["contentDetails"]["duration"].split("T")[1]

                            if "H" in duration_part:
                                list_hours = int(duration_part.split("H")[0])
                                PLAYER_INFO[ctx.guild.id]["ListSec"] += list_hours * 3600

                            if "M" in duration_part:
                                list_minutes = int(duration_part.split("M")[0].split("H")[-1])
                                PLAYER_INFO[ctx.guild.id]["ListSec"] += list_minutes * 60

                            if "S" in duration_part:
                                list_seconds = int(duration_part.split("S")[0].split("M")[-1])
                                PLAYER_INFO[ctx.guild.id]["ListSec"] += list_seconds

                            QUEUE[ctx.guild.id]["Current"].append(uploader_and_title)
                        except googleapiclient.errors.HttpError:
                            QUEUE[ctx.guild.id]["Current"].append(link)

                    PLAYER_INFO[ctx.guild.id]["ListDuration"] = format_duration(PLAYER_INFO[ctx.guild.id]["ListSec"],
                                                                                PLAYER_INFO[ctx.guild.id]["ListSec"])

                    if pre_shuffle:
                        copy = QUEUE[ctx.guild.id]["Current"][-1 - len(playlist_entries):-1]
                        random.shuffle(copy)
                        QUEUE[ctx.guild.id]["Current"][-1 - len(playlist_entries):-1] = copy

                    embed = discord.Embed(
                        description=strings["Music.SuccessAddPlaylist"].format(
                            len(playlist_entries), strings["Music.PreShuffled"] if pre_shuffle else "",
                            playlist_entries.title, query, PLAYER_INFO[ctx.guild.id]["ListDuration"]),
                        color=discord.Color.dark_green(),
                    )
                    await main.edit(embed=embed)

                    if ctx.voice_client and not ctx.voice_client.is_playing():
                        QUEUE[ctx.guild.id]["Current"][0] = await YTDLSource.from_url(QUEUE[ctx.guild.id]["Current"][0],
                                                                                      loop=self.bot.loop, stream=True)

                        try:
                            QUEUE[ctx.guild.id]["Current"][1] = await YTDLSource.from_url(
                                                                                    QUEUE[ctx.guild.id]["Current"][1],
                                                                                    loop=self.bot.loop, stream=True)
                        except IndexError:
                            pass

                except KeyError:
                    embed = discord.Embed(
                        description=strings["Errors.PlaylistRead"],
                        color=discord.Color.red(),
                    )
                    await ctx.respond(embed=embed)
        elif query.startswith(("http://", "https://")) and "spotify.com/" in query and "/track/" not in query:
            PLAYER_INFO[ctx.guild.id]["ListSec"], PLAYER_INFO[ctx.guild.id]["ListDuration"] = 0, ""

            try:
                if "playlist/" in query:
                    results = Constants.SPOTIFY.playlist_items(playlist_id=query)
                    playlist_info = Constants.SPOTIFY.playlist(playlist_id=query, fields="name")
                    playlist_name = playlist_info["name"]
                    album_name = ""
                else:
                    results = Constants.SPOTIFY.album_tracks(album_id=query)
                    album_info = Constants.SPOTIFY.album(album_id=query)
                    album_name = album_info["name"]
                    playlist_name = ""
            except Exception as exc:
                print(f"Spotify error: {exc} [{type(exc).__name__}]")
                embed = discord.Embed(
                    description=strings["Errors.InvalidURLSpotify"],
                    color=discord.Color.red(),
                )
                await ctx.respond(embed=embed)
                return

            tracks = results["items"]

            while results["next"]:
                results = Constants.SPOTIFY.next(results)
                tracks.extend(results["items"])

            if "playlist/" in query:
                embed = discord.Embed(
                    description=strings["Music.AddPlaylistSpotify"].format(len(tracks), playlist_name, query),
                    color=discord.Color.dark_green(),
                )
                main = await ctx.respond(embed=embed)
            else:
                embed = discord.Embed(
                    description=strings["Music.AddAlbumSpotify"].format(len(tracks), album_name, query),
                    color=discord.Color.dark_green(),
                )
                main = await ctx.respond(embed=embed)

            for track in tracks:
                try:
                    if "playlist/" in query:
                        if track["track"]["album"]["artists"][0]["name"] != "Various Artists":
                            QUEUE[ctx.guild.id]["Current"].append(f"{track['track']['album']['artists'][0]['name']}"
                                                                  f" - {track['track']['name']}")
                        else:
                            QUEUE[ctx.guild.id]["Current"].append(track["track"]["name"])
                        PLAYER_INFO[ctx.guild.id]["ListSec"] += track["track"]["duration_ms"]
                    else:
                        if track["artists"][0]["name"] != "Various Artists":
                            QUEUE[ctx.guild.id]["Current"].append(f"{track['artists'][0]['name']} - "
                                                                  f"{track['name']}")
                        else:
                            QUEUE[ctx.guild.id]["Current"].append(track["name"])
                        PLAYER_INFO[ctx.guild.id]["ListSec"] += track["duration_ms"]
                except IndexError:
                    if "playlist/" in query:
                        QUEUE[ctx.guild.id]["Current"].append(track["track"]["name"])
                        PLAYER_INFO[ctx.guild.id]["ListSec"] += track["track"]["duration_ms"]
                    else:
                        QUEUE[ctx.guild.id]["Current"].append(track["name"])
                        PLAYER_INFO[ctx.guild.id]["ListSec"] += track["duration_ms"]
                except TypeError:
                    continue

            PLAYER_INFO[ctx.guild.id]["ListDuration"] = format_duration(PLAYER_INFO[ctx.guild.id]["ListSec"],
                                                                        PLAYER_INFO[ctx.guild.id]["ListSec"],
                                                                        use_milliseconds=True)

            if pre_shuffle:
                copy = QUEUE[ctx.guild.id]["Current"][-1 - (len(tracks) - 1):-1]
                random.shuffle(copy)
                QUEUE[ctx.guild.id]["Current"][-1 - (len(tracks) - 1):-1] = copy

            embed = discord.Embed(
                description=strings["Music.SuccessAddPlaylistSpotify"].format(
                    len(tracks), strings["Music.PreShuffled"] if pre_shuffle else "",
                    strings["Music.Playlist"] if "playlist/" in query else strings["Music.Album"],
                    playlist_name if "playlist/" in query else album_name, query,
                    PLAYER_INFO[ctx.guild.id]["ListDuration"]),
                color=discord.Color.dark_green(),
            )
            await main.edit(embed=embed)

            if ctx.voice_client and not ctx.voice_client.is_playing():
                QUEUE[ctx.guild.id]["Current"][0] = await YTDLSource.from_url(QUEUE[ctx.guild.id]["Current"][0],
                                                                              loop=self.bot.loop, stream=True)

                try:
                    QUEUE[ctx.guild.id]["Current"][1] = await YTDLSource.from_url(QUEUE[ctx.guild.id]["Current"][1],
                                                                                  loop=self.bot.loop, stream=True)
                except IndexError:
                    pass
        else:
            if query.startswith(("http://", "https://")) and "spotify.com/" in query:
                try:
                    results = Constants.SPOTIFY.track(track_id=query)
                except Exception as exc:
                    print(f"Spotify error: {exc} [{type(exc).__name__}]")
                    embed = discord.Embed(
                        description=strings["Errors.InvalidURLSpotify"],
                        color=discord.Color.red(),
                    )
                    await ctx.respond(embed=embed)
                    return

                try:
                    if results["album"]["artists"][0]["name"] != "Various Artists":
                        modified_query = f"{results['album']['artists'][0]['name']} - {results['name']}"
                    else:
                        modified_query = results["name"]
                except IndexError:
                    modified_query = results["name"]
            elif query.startswith(("http://", "https://")) and "soundcloud.com/" in query:
                soundcloud_query = Constants.SOUNDCLOUD.resolve(query)

                if isinstance(soundcloud_query, SCTrack):
                    modified_query = f"{soundcloud_query.artist} - {soundcloud_query.title}"
                elif isinstance(soundcloud_query, SCPlaylist):
                    PLAYER_INFO[ctx.guild.id]["ListSec"] = soundcloud_query.duration
                    PLAYER_INFO[ctx.guild.id]["ListDuration"] = ""

                    embed = discord.Embed(
                        description=strings["Music.AddPlaylistSoundCloud"].format(
                            soundcloud_query.track_count, soundcloud_query.title, query),
                        color=discord.Color.dark_green(),
                    )
                    main = await ctx.respond(embed=embed)

                    for track in soundcloud_query:
                        QUEUE[ctx.guild.id]["Current"].append(f"{track.artist} - {track.title}")

                    PLAYER_INFO[ctx.guild.id]["ListDuration"] = format_duration(PLAYER_INFO[ctx.guild.id]["ListSec"],
                                                                                PLAYER_INFO[ctx.guild.id]["ListSec"],
                                                                                use_milliseconds=True)

                    if pre_shuffle:
                        copy = QUEUE[ctx.guild.id]["Current"][-1 - (soundcloud_query.track_count - 1):-1]
                        random.shuffle(copy)
                        QUEUE[ctx.guild.id]["Current"][-1 - (soundcloud_query.track_count - 1):-1] = copy

                    embed = discord.Embed(
                        description=strings["Music.SuccessAddPlaylistSoundCloud"].format(
                            soundcloud_query.track_count, strings["Music.PreShuffled"] if pre_shuffle else "",
                            soundcloud_query.title, query, PLAYER_INFO[ctx.guild.id]["ListDuration"]),
                        color=discord.Color.dark_green(),
                    )
                    await main.edit(embed=embed)

                    QUEUE[ctx.guild.id]["Current"][0] = await YTDLSource.from_url(QUEUE[ctx.guild.id]["Current"][0],
                                                                                  loop=self.bot.loop, stream=True)

                    try:
                        QUEUE[ctx.guild.id]["Current"][1] = await YTDLSource.from_url(QUEUE[ctx.guild.id]["Current"][1],
                                                                                      loop=self.bot.loop, stream=True)
                    except (IndexError, AttributeError):
                        pass
                    modified_query = None
                else:
                    embed = discord.Embed(
                        description=strings["Errors.InvalidURLSoundCloud"],
                        color=discord.Color.red()
                    )
                    await ctx.respond(embed=embed)
                    return
            else:
                modified_query = query

            if modified_query:
                try:
                    if ignore_live:
                        response = Constants.YOUTUBE.search().list(q=modified_query, type="video", part="id,snippet",
                                                                   maxResults=2).execute()
                        video_id = response["items"][0]["id"]["videoId"]
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                        video_title = response["items"][0]["snippet"]["title"]

                        if "(live)" in video_title.lower():
                            video_id = response["items"][1]["id"]["videoId"]
                            video_url = f"https://www.youtube.com/watch?v={video_id}"
                    else:
                        response = Constants.YOUTUBE.search().list(q=modified_query, type="video", part="id",
                                                                   maxResults=1).execute()
                        video_id = response["items"][0]["id"]["videoId"]
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                except (IndexError, googleapiclient.errors.HttpError):
                    video_url = modified_query
                except BrokenPipeError:
                    embed = discord.Embed(
                        description=strings["Errors.BrokenPipe"],
                        color=discord.Color.red()
                    )
                    await ctx.respond(embed=embed)
                    return

                player = await self.resolve_player_start(ctx, video_url, start_at)

                if not player:
                    return

                if insert:
                    QUEUE[ctx.guild.id]["Current"].insert(insert, player)
                else:
                    QUEUE[ctx.guild.id]["Current"].append(player)

                if ctx.voice_client and not (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
                    PLAYER_INFO[ctx.guild.id]["First"] = True
                else:
                    embed = discord.Embed(
                        description=strings["Music.AddQuery"].format(
                            strings["Music.Inserted"] if insert else strings["Music.Added"],
                            QUEUE[ctx.guild.id]["Current"][QUEUE[ctx.guild.id]["Current"].index(player)].title,
                            QUEUE[ctx.guild.id]["Current"][QUEUE[ctx.guild.id]["Current"].index(player)].url,
                            player.start_at + " → " if start_at else "", player.formatted_duration,
                            QUEUE[ctx.guild.id]["Current"].index(player)),
                        color=discord.Color.dark_green()
                    )
                    await ctx.respond(embed=embed)

        view = View(timeout=None)
        view2 = View(timeout=None)
        view3 = View(timeout=None)
        view4 = View(timeout=None)

        for view_ in [view, view2, view3, view4]:
            view_.add_item(back_button) if view_ == view3 or view_ == view4 else None
            view_.add_item(pause_button), view_.add_item(skip_button), view_.add_item(volumemin_button)
            view_.add_item(volumedown_button), view_.add_item(volumemid_button), view_.add_item(volumeup_button)
            view_.add_item(volumemax_button), view_.add_item(loop_button)
            view_.add_item(remove_button) if view_ == view2 or view_ == view4 else None

        try:
            while QUEUE[ctx.guild.id]["Current"]:
                await asyncio.sleep(.1)

                try:
                    if (len(QUEUE[ctx.guild.id]["Current"]) >= 11 and not
                            all(isinstance(QUEUE[ctx.guild.id]["Current"][i], YTDLSource) for i
                                in range(1, 11))) and not self.convert.is_running():
                        self.convert.start(ctx)
                    elif (1 < len(QUEUE[ctx.guild.id]["Current"]) < 11 and not
                            all(isinstance(QUEUE[ctx.guild.id]["Current"][i], YTDLSource) for i
                                in range(1, len(QUEUE[ctx.guild.id]["Current"])))) and not self.convert.is_running():
                        self.convert.start(ctx)

                    if ctx.voice_client and not (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()) and \
                            not INVOKED[ctx.guild.id]:
                        self.duration_counter.cancel()
                        self.convert.cancel()

                        PLAY_TIMER[ctx.guild.id]["Raw"], PLAY_TIMER[ctx.guild.id]["Act"] = 0, ""

                        if PLAYER_MOD[ctx.guild.id]["Loop"] == "Disabled":
                            loop_button.style = discord.ButtonStyle.secondary
                        elif PLAYER_MOD[ctx.guild.id]["Loop"] == "Single":
                            loop_button.style = discord.ButtonStyle.primary
                        else:
                            loop_button.style = discord.ButtonStyle.success
                        pause_button.style = discord.ButtonStyle.secondary

                        try:
                            if PLAYER_INFO[ctx.guild.id]["EmbedID"]:
                                channel = self.bot.get_guild(int(ctx.guild.id)).get_channel(
                                    PLAYER_INFO[ctx.guild.id]["TextChannel"])
                                message = await channel.fetch_message(PLAYER_INFO[ctx.guild.id]["EmbedID"])

                                if PLAYER_MOD[ctx.guild.id]["Loop"] != "Single" and not \
                                        (PLAYER_MOD[ctx.guild.id]["Loop"] == "Queue" and
                                         len(QUEUE[ctx.guild.id]["Current"]) - 1 < 1):
                                    await message.edit(view=None)
                                    PLAYER_INFO[ctx.guild.id]["LoopCount"] = 0
                                else:
                                    embed = discord.Embed(
                                        description=strings["Music.LoopCount"].format(
                                            PLAYER_INFO[ctx.guild.id]["Embed"].description,
                                            PLAYER_INFO[ctx.guild.id]["LoopCount"]),
                                        color=discord.Color.dark_green()
                                    )
                                    embed.set_footer(text=PLAYER_INFO[ctx.guild.id]["Embed"].footer.text,
                                                     icon_url=PLAYER_INFO[ctx.guild.id]["Embed"].footer.icon_url)
                                    await message.edit(embed=embed)
                        except (discord.NotFound, discord.HTTPException, AttributeError, KeyError, UnboundLocalError):
                            pass

                        try:
                            if not isinstance(QUEUE[ctx.guild.id]["Current"][0], YTDLSource):
                                player = await YTDLSource.from_url(QUEUE[ctx.guild.id]["Current"][0],
                                                                   loop=self.bot.loop, stream=True,
                                                                   filter_=PLAYER_MOD[ctx.guild.id]["Filter"]["Val"])
                            elif PLAYER_MOD[ctx.guild.id]["Filter"]["Name"] != "Disabled":
                                player = await YTDLSource.from_url(QUEUE[ctx.guild.id]["Current"][0].url,
                                                                   loop=self.bot.loop, stream=True,
                                                                   filter_=PLAYER_MOD[ctx.guild.id]["Filter"]["Val"])
                            else:
                                player = QUEUE[ctx.guild.id]["Current"][0]
                        except IndexError:
                            continue

                        try:
                            response = Constants.YOUTUBE.channels().list(part="snippet", id=player.channel_id).execute()
                            uploader_picture_url = response["items"][0]["snippet"]["thumbnails"]["high"]["url"]
                        except (IndexError, googleapiclient.errors.HttpError):
                            uploader_picture_url = None
                        except BrokenPipeError:
                            embed = discord.Embed(
                                description=strings["Errors.BrokenPipe"],
                                color=discord.Color.red()
                            )
                            await ctx.respond(embed=embed)
                            continue

                        PLAY_TIMER[ctx.guild.id]["Old"] = player.start_at_seconds
                        player.volume = PLAYER_MOD[ctx.guild.id]["Volume"]

                        try:
                            ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(
                                                                            self.song_deletion_handling(ctx, player),
                                                                            self.bot.loop))
                        except discord.ClientException:
                            continue

                        PLAYER_INFO[ctx.guild.id]["Object"] = player
                        PLAYER_INFO[ctx.guild.id]["Title"], PLAYER_INFO[ctx.guild.id]["URL"] = player.title, player.url

                        if not PLAYER_INFO[ctx.guild.id]["Object"].duration:
                            PLAYER_INFO[ctx.guild.id]["Object"].duration = 999999999
                        if not self.duration_counter.is_running():
                            self.duration_counter.start(ctx, PLAYER_INFO[ctx.guild.id]["Object"].duration)

                        PLAYER_INFO[ctx.guild.id]["DurationSec"] = PLAYER_INFO[ctx.guild.id]["Object"].duration

                        QUEUE[ctx.guild.id]["Sum"] = (len(QUEUE[ctx.guild.id]["Previous"]) +
                                                      (len(QUEUE[ctx.guild.id]["Current"]) - 1)) + 1

                        if len(QUEUE[ctx.guild.id]["Current"]) > 1:
                            if not isinstance(QUEUE[ctx.guild.id]["Current"][1], YTDLSource):
                                QUEUE[ctx.guild.id]["Current"][1] = await YTDLSource.from_url(
                                                                                    QUEUE[ctx.guild.id]["Current"][1],
                                                                                    loop=self.bot.loop, stream=True)

                            if PLAYER_MOD[ctx.guild.id]["Loop"] == "Queue" and \
                                    player.title != QUEUE[ctx.guild.id]["Current"][1].title:
                                embed = discord.Embed(
                                    description=strings["Music.Looping"].format(
                                        player.title, player.url, player.start_at + " → " if player.start_at else "",
                                        player.formatted_duration, len(QUEUE[ctx.guild.id]["Previous"]) + 1,
                                        QUEUE[ctx.guild.id]["Sum"], QUEUE[ctx.guild.id]["Current"][1].title,
                                        QUEUE[ctx.guild.id]["Current"][1].url),
                                    color=discord.Color.dark_green()
                                )
                                embed.set_footer(text=player.uploader, icon_url=uploader_picture_url)
                                PLAYER_INFO[ctx.guild.id]["Embed"] = embed

                                if not len(QUEUE[ctx.guild.id]["Previous"]):
                                    if not PLAYER_INFO[ctx.guild.id]["First"]:
                                        embed_message = await ctx.send(embed=embed, view=view2)
                                        PLAYER_INFO[ctx.guild.id]["EmbedID"] = embed_message.id
                                    else:
                                        embed_message = await ctx.respond(embed=embed, view=view2)
                                        PLAYER_INFO[ctx.guild.id]["EmbedID"] = embed_message.id
                                else:
                                    if not PLAYER_INFO[ctx.guild.id]["First"]:
                                        embed_message = await ctx.send(embed=embed, view=view4)
                                        PLAYER_INFO[ctx.guild.id]["EmbedID"] = embed_message.id
                                    else:
                                        embed_message = await ctx.respond(embed=embed, view=view4)
                                        PLAYER_INFO[ctx.guild.id]["EmbedID"] = embed_message.id
                            elif PLAYER_MOD[ctx.guild.id]["Loop"] == "Disabled":
                                embed = discord.Embed(
                                    description=strings["Music.Playing"].format(
                                        player.title, player.url, player.start_at + " → " if player.start_at else "",
                                        player.formatted_duration, len(QUEUE[ctx.guild.id]["Previous"]) + 1,
                                        QUEUE[ctx.guild.id]["Sum"], QUEUE[ctx.guild.id]["Current"][1].title,
                                        QUEUE[ctx.guild.id]["Current"][1].url),
                                    color=discord.Color.dark_green(),
                                )
                                embed.set_footer(text=player.uploader, icon_url=uploader_picture_url)
                                PLAYER_INFO[ctx.guild.id]["Embed"] = embed

                                if not len(QUEUE[ctx.guild.id]["Previous"]):
                                    if not PLAYER_INFO[ctx.guild.id]["First"]:
                                        embed_message = await ctx.send(embed=embed, view=view2)
                                        PLAYER_INFO[ctx.guild.id]["EmbedID"] = embed_message.id
                                    else:
                                        embed_message = await ctx.respond(embed=embed, view=view2)
                                        PLAYER_INFO[ctx.guild.id]["EmbedID"] = embed_message.id
                                else:
                                    if not PLAYER_INFO[ctx.guild.id]["First"]:
                                        embed_message = await ctx.send(embed=embed, view=view4)
                                        PLAYER_INFO[ctx.guild.id]["EmbedID"] = embed_message.id
                                    else:
                                        embed_message = await ctx.respond(embed=embed, view=view4)
                                        PLAYER_INFO[ctx.guild.id]["EmbedID"] = embed_message.id
                        else:
                            if PLAYER_INFO[ctx.guild.id]["First"] and PLAYER_MOD[ctx.guild.id]["Loop"] != "Disabled":
                                embed = discord.Embed(
                                    description=strings["Music.LoopingLast"].format(
                                        player.title, player.url, player.start_at + " → " if player.start_at else "",
                                        player.formatted_duration, len(QUEUE[ctx.guild.id]["Previous"]) + 1,
                                        QUEUE[ctx.guild.id]["Sum"]),
                                    color=discord.Color.dark_green(),
                                )
                                embed.set_footer(text=player.uploader, icon_url=uploader_picture_url)
                                PLAYER_INFO[ctx.guild.id]["Embed"] = embed

                                if not len(QUEUE[ctx.guild.id]["Previous"]):
                                    embed_message = await ctx.respond(embed=embed, view=view)
                                    PLAYER_INFO[ctx.guild.id]["EmbedID"] = embed_message.id
                                else:
                                    embed_message = await ctx.respond(embed=embed, view=view3)
                                    PLAYER_INFO[ctx.guild.id]["EmbedID"] = embed_message.id
                            elif PLAYER_MOD[ctx.guild.id]["Loop"] == "Disabled":
                                embed = discord.Embed(
                                    description=strings["Music.PlayingLast"].format(
                                        player.title, player.url, player.start_at + " → " if player.start_at else "",
                                        player.formatted_duration, len(QUEUE[ctx.guild.id]["Previous"]) + 1,
                                        QUEUE[ctx.guild.id]["Sum"]),
                                    color=discord.Color.dark_green(),
                                )
                                embed.set_footer(text=player.uploader, icon_url=uploader_picture_url)
                                PLAYER_INFO[ctx.guild.id]["Embed"] = embed

                                if not len(QUEUE[ctx.guild.id]["Previous"]):
                                    if not PLAYER_INFO[ctx.guild.id]["First"]:
                                        embed_message = await ctx.send(embed=embed, view=view)
                                        PLAYER_INFO[ctx.guild.id]["EmbedID"] = embed_message.id
                                    else:
                                        embed_message = await ctx.respond(embed=embed, view=view)
                                        PLAYER_INFO[ctx.guild.id]["EmbedID"] = embed_message.id
                                else:
                                    if not PLAYER_INFO[ctx.guild.id]["First"]:
                                        embed_message = await ctx.send(embed=embed, view=view3)
                                        PLAYER_INFO[ctx.guild.id]["EmbedID"] = embed_message.id
                                    else:
                                        embed_message = await ctx.respond(embed=embed, view=view3)
                                        PLAYER_INFO[ctx.guild.id]["EmbedID"] = embed_message.id

                        PLAYER_INFO[ctx.guild.id]["TextChannel"] = ctx.channel.id

                        if PLAYER_MOD[ctx.guild.id]["Loop"] != "Single" and not \
                                (PLAYER_MOD[ctx.guild.id]["Loop"] == "Queue" and
                                 len(QUEUE[ctx.guild.id]["Current"]) - 1 < 1):
                            PLAYER_INFO[ctx.guild.id]["PauseMsg"] = None
                            PLAYER_INFO[ctx.guild.id]["VolMsg"] = None
                            PLAYER_INFO[ctx.guild.id]["RmvMsg"] = None
                            PLAYER_INFO[ctx.guild.id]["LoopMsg"] = None
                            PLAYER_INFO[ctx.guild.id]["Removed"].clear()
                            PLAYER_INFO[ctx.guild.id]["First"] = False
                    continue

                except Exception as exc:
                    if isinstance(exc, KeyError):
                        continue
                    if isinstance(exc, (AttributeError, ConnectionResetError)):
                        await self.cleanup(ctx)
                    elif isinstance(exc, yt_dlp.DownloadError):
                        embed = discord.Embed(
                            description=strings["Errors.StreamFailure"].format(QUEUE[ctx.guild.id]["Current"].pop(0)),
                            color=discord.Color.red()
                        )
                        await ctx.send(embed=embed)

                    print(f"In upper exception: {exc} [{type(exc).__name__}]")
        except KeyError:
            pass

    @commands.slash_command(description="Removes songs from the queue")
    @option(name="from_", description="The start position of the queue removal, or positions separated by semicolons "
                                      "(i.e. pos1;pos2;...)", required=True)
    @option(name="to", description="The end position of the queue removal", required=False)
    async def remove(self, ctx, from_: str, to: int = None):
        try:
            await ctx.defer()
        except (discord.ApplicationCommandInvokeError, discord.InteractionResponded):
            pass

        strings = await get_language_strings(ctx)

        if len(QUEUE[ctx.guild.id]["Current"]) - 1 < 1:
            embed = discord.Embed(
                description=strings["Errors.QueueEmpty"],
                color=discord.Color.red()
            )
            if PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]:
                embed.set_footer(text=strings["Music.ButtonRequest"].format(PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]))
                await ctx.send(embed=embed)
            else:
                await ctx.respond(embed=embed)

            if not ctx.voice_client:
                await self.cleanup(ctx)
            return

        if ";" in from_:
            amount = 0
            valid_removed_positions = [int(pos) for pos in from_.split(";") if pos.isnumeric()]
            valid_songs = []

            for position in sorted(valid_removed_positions):
                try:
                    if not isinstance(QUEUE[ctx.guild.id]["Current"][int(position) - amount], YTDLSource):
                        removed_player = await YTDLSource.from_url(
                                                            QUEUE[ctx.guild.id]["Current"][int(position) - amount],
                                                            loop=self.bot.loop, stream=True)
                        valid_songs.append(f"[**{position}**] {removed_player.title}")
                    else:
                        valid_songs.append(f"[**{position}**] "
                                           f"{QUEUE[ctx.guild.id]['Current'][int(position) - amount].title}")
                    QUEUE[ctx.guild.id]["Current"].pop(int(position) - amount)
                    amount += 1
                except IndexError:
                    continue

            if len(valid_songs) == 0:
                embed = discord.Embed(
                    description=strings["Errors.InvalidPositions"],
                    color=discord.Color.red()
                )
                await ctx.respond(embed=embed)
                return

            formatted_valid_songs = "\n".join(valid_songs)

            if len(QUEUE[ctx.guild.id]["Current"]) - 1 < 1:
                embed = discord.Embed(
                    description=strings["Music.RemovedFollowingLast"].format(formatted_valid_songs),
                    color=discord.Color.dark_red()
                )
                await ctx.respond(embed=embed)
            else:
                if not isinstance(QUEUE[ctx.guild.id]["Current"][1], YTDLSource):
                    QUEUE[ctx.guild.id]["Current"][1] = await YTDLSource.from_url(QUEUE[ctx.guild.id]["Current"][1],
                                                                                  loop=self.bot.loop, stream=True)

                embed = discord.Embed(
                    description=strings["Music.RemovedFollowing"].format(
                        formatted_valid_songs, QUEUE[ctx.guild.id]["Current"][1].title),
                    color=discord.Color.dark_red()
                )
                await ctx.respond(embed=embed)
            return
        elif ";" not in from_ and not from_.isnumeric():
            embed = discord.Embed(
                description=strings["Errors.FromParameter"],
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        if not to:
            to = int(from_)
        elif to < int(from_):
            from_, to = to, from_

        from_ = min(max(int(from_), 1), len(QUEUE[ctx.guild.id]["Current"]) - 1)
        to = min(max(int(to), 1), len(QUEUE[ctx.guild.id]["Current"]) - 1)

        if to == int(from_):
            if not isinstance(QUEUE[ctx.guild.id]["Current"][int(from_)], YTDLSource):
                removed_player = await YTDLSource.from_url(QUEUE[ctx.guild.id]["Current"][int(from_)],
                                                           loop=self.bot.loop, stream=True)
            else:
                removed_player = QUEUE[ctx.guild.id]["Current"][int(from_)]

            QUEUE[ctx.guild.id]["Current"].pop(int(from_))

            if len(QUEUE[ctx.guild.id]["Current"]) - 1 < 1:
                if not PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]:
                    embed = discord.Embed(
                        description=strings["Music.RemovedLast"].format(removed_player.title, from_),
                        color=discord.Color.dark_red()
                    )
                    await ctx.respond(embed=embed)
                else:
                    PLAYER_INFO[ctx.guild.id]["Removed"].append(f"[**{len(PLAYER_INFO[ctx.guild.id]['Removed']) + 1}**]"
                                                                f" {removed_player.title}")
                    joined_removed_songs = "\n".join(PLAYER_INFO[ctx.guild.id]["Removed"])

                    embed = discord.Embed(
                        description=strings["Music.RemovedFollowingLast"].format(joined_removed_songs),
                        color=discord.Color.dark_red()
                    )
                    embed.set_footer(text=strings["Music.ButtonRequest"].format(
                        PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]))

                    if PLAYER_INFO[ctx.guild.id]["RmvMsg"]:
                        await PLAYER_INFO[ctx.guild.id]["RmvMsg"].edit(embed=embed)
                    else:
                        PLAYER_INFO[ctx.guild.id]["RmvMsg"] = await ctx.send(embed=embed)
            else:
                if not isinstance(QUEUE[ctx.guild.id]["Current"][1], YTDLSource):
                    QUEUE[ctx.guild.id]["Current"][1] = await YTDLSource.from_url(QUEUE[ctx.guild.id]["Current"][1],
                                                                                  loop=self.bot.loop, stream=True)

                if not PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]:
                    embed = discord.Embed(
                        description=strings["Music.Removed"].format(
                            removed_player.title, from_, QUEUE[ctx.guild.id]["Current"][1].title),
                        color=discord.Color.dark_red()
                    )
                    await ctx.respond(embed=embed)
                else:
                    PLAYER_INFO[ctx.guild.id]["Removed"].append(
                        f"[**{len(PLAYER_INFO[ctx.guild.id]['Removed']) + 1}**] "
                        f"{removed_player.title}")
                    joined_removed_songs = "\n".join(PLAYER_INFO[ctx.guild.id]["Removed"])

                    embed = discord.Embed(
                        description=strings["Music.RemovedFollowing"].format(
                            joined_removed_songs, QUEUE[ctx.guild.id]["Current"][1].title),
                        color=discord.Color.dark_red()
                    )
                    embed.set_footer(text=strings["Music.ButtonRequest"].format(
                        PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]))

                    if PLAYER_INFO[ctx.guild.id]["RmvMsg"]:
                        await PLAYER_INFO[ctx.guild.id]["RmvMsg"].edit(embed=embed)
                    else:
                        PLAYER_INFO[ctx.guild.id]["RmvMsg"] = await ctx.send(embed=embed)
        else:
            del QUEUE[ctx.guild.id]["Current"][int(from_):to + 1]

            if len(QUEUE[ctx.guild.id]["Current"]) - 1 < 1:
                embed = discord.Embed(
                    description=strings["Music.RemovedRangeLast"].format(abs(int(from_) - to) + 1, from_, to),
                    color=discord.Color.dark_red()
                )
                await ctx.respond(embed=embed)
            else:
                if not isinstance(QUEUE[ctx.guild.id]["Current"][1], YTDLSource):
                    QUEUE[ctx.guild.id]["Current"][1] = await YTDLSource.from_url(QUEUE[ctx.guild.id]["Current"][1],
                                                                                  loop=self.bot.loop, stream=True)

                embed = discord.Embed(
                    description=strings["Music.RemovedRange"].format(
                        abs(int(from_) - to) + 1, from_, to, QUEUE[ctx.guild.id]["Current"][1].title),
                    color=discord.Color.dark_red()
                )
                await ctx.respond(embed=embed)

    @commands.slash_command(description="Clears the queue")
    @option(name="from_", description="The start position of the queue clear", required=False)
    async def clear(self, ctx, from_: int = 1):
        await ctx.defer()

        from_ = min(max(from_, 1), len(QUEUE[ctx.guild.id]["Current"]) - 1)
        await self.remove(ctx, from_=str(from_), to=len(QUEUE[ctx.guild.id]["Current"]) - 1)

    @commands.slash_command(description="Displays songs in queue, with the ability to seek them")
    @option(name="to", description="The end position of the queue display", required=False)
    @option(name="from_", description="The start position of the queue display", required=False)
    @option(name="seek", description="Seek songs via given keywords", required=False)
    async def view(self, ctx, to: int = None, from_: int = 1, seek: str = None):
        await ctx.defer()

        strings = await get_language_strings(ctx)

        if not to:
            if len(QUEUE[ctx.guild.id]["Current"]) - 1 >= 10 and from_ == 1 and not seek:
                to = 10
            else:
                to = len(QUEUE[ctx.guild.id]["Current"])

        queue_sum = len(QUEUE[ctx.guild.id]["Previous"]) + (len(QUEUE[ctx.guild.id]["Current"]) - 1) + 1

        if len(QUEUE[ctx.guild.id]["Current"]) - 1 < 1:
            embed = discord.Embed(
                description=strings["Music.QueueEmpty"],
                color=discord.Color.dark_gold()
            )

            if ctx.voice_client and PLAY_TIMER[ctx.guild.id]["Act"] != "":
                embed.set_footer(text=strings["Music.NowPlaying"].format(
                    PLAYER_INFO[ctx.guild.id]["Title"], PLAY_TIMER[ctx.guild.id]["Act"],
                    PLAYER_INFO[ctx.guild.id]["Object"].formatted_duration, len(QUEUE[ctx.guild.id]["Previous"]) + 1,
                    queue_sum, int(PLAYER_MOD[ctx.guild.id]["Volume"] * 100),
                    PLAYER_MOD[ctx.guild.id]["Filter"]["Name"], PLAYER_MOD[ctx.guild.id]["Filter"]["Intensity"],
                    PLAYER_MOD[ctx.guild.id]["Loop"]))
            await ctx.respond(embed=embed)

            if not ctx.voice_client:
                await self.cleanup(ctx)
            return

        positional_queue = {"List": [], "Formatted": ""}

        from_ = min(max(from_, 1), len(QUEUE[ctx.guild.id]["Current"]) - 1)
        to = min(max(to, 1), len(QUEUE[ctx.guild.id]["Current"]) - 1)

        if to < from_:
            from_, to = to, from_

        if not seek:
            embed = discord.Embed(
                description=strings["Music.FetchingSongs"].format(abs(from_ - to) + 1, from_, to),
                color=discord.Color.dark_gold()
            )
            await ctx.respond(embed=embed)
        else:
            embed = discord.Embed(
                description=strings["Music.SeekingSongs"].format(seek, from_, to),
                color=discord.Color.dark_gold()
            )
            await ctx.respond(embed=embed)

        for song_index, song_name in enumerate(QUEUE[ctx.guild.id]["Current"][from_:to + 1]):
            if not seek:
                player = QUEUE[ctx.guild.id]["Current"][song_index + from_]

                if isinstance(song_name, YTDLSource):
                    positional_queue["List"].append(f"[**{from_ + song_index}**] {player.title} "
                                                    f"[**{player.start_at + ' → ' if player.start_at else ''}"
                                                    f"{player.formatted_duration}**]")
                else:
                    positional_queue["List"].append(f"[**{from_ + song_index}**] {player}")
                positional_queue["Formatted"] = "\n".join(positional_queue["List"])
            else:
                player = QUEUE[ctx.guild.id]["Current"][song_index + from_]

                if isinstance(song_name, YTDLSource):
                    if seek.lower() in player.title.strip().lower():
                        positional_queue["List"].append(f"[**{from_ + song_index}**] {player.title} "
                                                        f"[**{player.start_at + ' → ' if player.start_at else ''}"
                                                        f"{player.formatted_duration}**]")
                else:
                    if seek.lower() in player.strip().lower():
                        positional_queue["List"].append(f"[**{from_ + song_index}**] {player}")
                positional_queue["Formatted"] = "\n".join(positional_queue["List"])

            if len(positional_queue["Formatted"]) >= 3952:
                break

        if seek and len(positional_queue["Formatted"]) == 0:
            embed = discord.Embed(
                description=strings["Music.SeekingSongsNotFound"].format(seek, from_, to),
                color=discord.Color.dark_gold()
            )
            await ctx.edit(embed=embed)
            return
        elif seek and len(positional_queue["Formatted"]) > 0:
            embed = discord.Embed(
                description=strings["Music.SeekingSongsSuccess"].format(
                    len(positional_queue["List"]), from_, to),
                color=discord.Color.dark_gold()
            )
            await ctx.edit(embed=embed)

            embed = discord.Embed(
                description=strings["Music.SeekingSongsInQueue"].format(seek, positional_queue["Formatted"]),
                color=discord.Color.dark_gold()
            )
            if ctx.voice_client and PLAY_TIMER[ctx.guild.id]["Act"] != "":
                embed.set_footer(text=strings["Music.NowPlaying"].format(
                    PLAYER_INFO[ctx.guild.id]["Title"], PLAY_TIMER[ctx.guild.id]["Act"],
                    PLAYER_INFO[ctx.guild.id]["Object"].formatted_duration, len(QUEUE[ctx.guild.id]["Previous"]) + 1,
                    queue_sum, int(PLAYER_MOD[ctx.guild.id]["Volume"] * 100),
                    PLAYER_MOD[ctx.guild.id]["Filter"]["Name"], PLAYER_MOD[ctx.guild.id]["Filter"]["Intensity"],
                    PLAYER_MOD[ctx.guild.id]["Loop"]))
            await ctx.send(embed=embed)
            return

        if len(positional_queue["Formatted"]) >= 3952:
            embed = discord.Embed(
                description=strings["Music.FetchingSongsSuccess"].format(
                    len(positional_queue["List"]), abs(from_ - to) + 1, from_, to),
                color=discord.Color.dark_gold()
            )
            await ctx.edit(embed=embed)

            embed = discord.Embed(
                description=strings["Music.FetchingSongsInQueue"].format(positional_queue["Formatted"]),
                color=discord.Color.dark_gold()
            )
            if ctx.voice_client and PLAY_TIMER[ctx.guild.id]["Act"] != "":
                embed.set_footer(text=strings["Music.NowPlaying"].format(
                    PLAYER_INFO[ctx.guild.id]["Title"], PLAY_TIMER[ctx.guild.id]["Act"],
                    PLAYER_INFO[ctx.guild.id]["Object"].formatted_duration, len(QUEUE[ctx.guild.id]["Previous"]) + 1,
                    queue_sum, int(PLAYER_MOD[ctx.guild.id]["Volume"] * 100),
                    PLAYER_MOD[ctx.guild.id]["Filter"]["Name"], PLAYER_MOD[ctx.guild.id]["Filter"]["Intensity"],
                    PLAYER_MOD[ctx.guild.id]["Loop"]))
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description=strings["Music.FetchingSongsSuccess"].format(
                    len(positional_queue["List"]), abs(from_ - to) + 1, from_, to),
                color=discord.Color.dark_gold()
            )
            await ctx.edit(embed=embed)

            additional_songs = len(QUEUE[ctx.guild.id]["Current"]) - (len(positional_queue["List"]) + 1)
            total_duration = None

            if all(isinstance(song, YTDLSource) for song in QUEUE[ctx.guild.id]["Current"][1:]):
                total_duration = format_duration(sum(song.duration if song.duration else 0
                                                     for song in QUEUE[ctx.guild.id]["Current"][1:]))

            embed = discord.Embed(
                description=strings["Music.TotalInQueue"].format(
                    positional_queue["Formatted"],
                    strings["Music.Additional"].format(additional_songs) if additional_songs else "",
                    len(QUEUE[ctx.guild.id]["Current"]) - 1, f" [**{total_duration}**]" if total_duration else ""),
                color=discord.Color.dark_gold()
            )
            if ctx.voice_client and PLAY_TIMER[ctx.guild.id]["Act"] != "":
                embed.set_footer(text=strings["Music.NowPlaying"].format(
                    PLAYER_INFO[ctx.guild.id]["Title"], PLAY_TIMER[ctx.guild.id]["Act"],
                    PLAYER_INFO[ctx.guild.id]["Object"].formatted_duration, len(QUEUE[ctx.guild.id]["Previous"]) + 1,
                    queue_sum, int(PLAYER_MOD[ctx.guild.id]["Volume"] * 100),
                    PLAYER_MOD[ctx.guild.id]["Filter"]["Name"], PLAYER_MOD[ctx.guild.id]["Filter"]["Intensity"],
                    PLAYER_MOD[ctx.guild.id]["Loop"]))
            await ctx.send(embed=embed)

    @commands.slash_command(description="Shuffles the queue")
    @option(name="from_", description="The start position of the queue shuffle", required=False)
    @option(name="to", description="The end position of the queue shuffle", required=False)
    async def shuffle(self, ctx, from_: int = 1, to: int = None):
        await ctx.defer()

        strings = await get_language_strings(ctx)

        if len(QUEUE[ctx.guild.id]["Current"]) - 1 < 1:
            embed = discord.Embed(
                description=strings["Errors.QueueEmpty"],
                color=discord.Color.red(),
            )
            await ctx.respond(embed=embed)

            if not ctx.voice_client:
                await self.cleanup(ctx)
            return

        if not to:
            to = len(QUEUE[ctx.guild.id]["Current"])
        elif to < from_:
            from_, to = to, from_

        from_ = min(max(from_, 1), len(QUEUE[ctx.guild.id]["Current"]) - 1)
        to = min(max(to, 1), len(QUEUE[ctx.guild.id]["Current"]))

        copy = QUEUE[ctx.guild.id]["Current"][from_:to]
        random.shuffle(copy)
        QUEUE[ctx.guild.id]["Current"][from_:to] = copy

        if not isinstance(QUEUE[ctx.guild.id]["Current"][1], YTDLSource):
            QUEUE[ctx.guild.id]["Current"][1] = await YTDLSource.from_url(QUEUE[ctx.guild.id]["Current"][1],
                                                                          loop=self.bot.loop, stream=True)

        embed = discord.Embed(
            description=strings["Music.Shuffle"].format(
                abs(from_ - to), from_, to - 1, QUEUE[ctx.guild.id]["Current"][1].title),
            color=discord.Color.purple(),
        )
        await ctx.respond(embed=embed)

    @commands.slash_command(description="Moves the song to the specified position in the queue")
    @option(name="from_", description="The current position of the song in queue", required=True)
    @option(name="to", description="The position in queue you wish to move the song to", required=True)
    @option(name="replace", description="Replaces the song in the target position", required=False)
    async def move(self, ctx, from_: int, to: int, replace: bool = False):
        await ctx.defer()

        strings = await get_language_strings(ctx)

        if len(QUEUE[ctx.guild.id]["Current"]) - 1 < 1:
            embed = discord.Embed(
                description=strings["Errors.QueueEmpty"],
                color=discord.Color.red(),
            )
            await ctx.respond(embed=embed)

            if not ctx.voice_client:
                await self.cleanup(ctx)
            return

        from_ = min(max(from_, 1), len(QUEUE[ctx.guild.id]["Current"]) - 1)
        to = min(max(to, 1), len(QUEUE[ctx.guild.id]["Current"]) - 1)

        if not isinstance(QUEUE[ctx.guild.id]["Current"][from_], YTDLSource):
            from_player = await YTDLSource.from_url(QUEUE[ctx.guild.id]["Current"][from_], loop=self.bot.loop,
                                                    stream=True)
        else:
            from_player = QUEUE[ctx.guild.id]["Current"][from_]

        if replace:
            if not isinstance(QUEUE[ctx.guild.id]["Current"][to], YTDLSource):
                to_player = await YTDLSource.from_url(QUEUE[ctx.guild.id]["Current"][to], loop=self.bot.loop,
                                                      stream=True)
            else:
                to_player = QUEUE[ctx.guild.id]["Current"][to]

            QUEUE[ctx.guild.id]["Current"][to] = from_player
            QUEUE[ctx.guild.id]["Current"].pop(from_)

            if not isinstance(QUEUE[ctx.guild.id]["Current"][1], YTDLSource):
                QUEUE[ctx.guild.id]["Current"][1] = await YTDLSource.from_url(QUEUE[ctx.guild.id]["Current"][1],
                                                                              loop=self.bot.loop, stream=True)

            embed = discord.Embed(
                description=strings["Music.MoveReplace"].format(
                    from_player.title, from_, to, to_player.title, QUEUE[ctx.guild.id]["Current"][1].title),
                color=discord.Color.purple(),
            )
            await ctx.respond(embed=embed)
            return

        QUEUE[ctx.guild.id]["Current"].pop(from_)
        QUEUE[ctx.guild.id]["Current"].insert(to, from_player)

        if not isinstance(QUEUE[ctx.guild.id]["Current"][1], YTDLSource):
            QUEUE[ctx.guild.id]["Current"][1] = await YTDLSource.from_url(QUEUE[ctx.guild.id]["Current"][1],
                                                                          loop=self.bot.loop, stream=True)

        embed = discord.Embed(
            description=strings["Music.Move"].format(
                from_player.title, from_, to, QUEUE[ctx.guild.id]["Current"][1].title),
            color=discord.Color.purple(),
        )
        await ctx.respond(embed=embed)

    @commands.slash_command(description="Skips to the next, or to the specified, song in the queue")
    @option(name="to", description="The position in queue you wish to skip to", required=False)
    async def skip(self, ctx, to: int = 1):
        try:
            await ctx.defer()
        except (discord.ApplicationCommandInvokeError, discord.InteractionResponded):
            pass

        strings = await get_language_strings(ctx)

        if not ctx.voice_client or (not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused()):
            embed = discord.Embed(
                description=strings["Errors.NothingPlaying"],
                color=discord.Color.red(),
            )
            if PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]:
                embed.set_footer(text=strings["Music.ButtonRequest"].format(PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]))
                await ctx.send(embed=embed)
            else:
                await ctx.respond(embed=embed)

            if not ctx.voice_client:
                await self.cleanup(ctx)
            return

        if PLAYER_MOD[ctx.guild.id]["Loop"] == "Single" or (PLAYER_MOD[ctx.guild.id]["Loop"] == "Queue" and
                                                            len(QUEUE[ctx.guild.id]["Current"]) - 1 < 1):
            PLAYER_MOD[ctx.guild.id]["Loop"] = "Disabled"
        PLAYER_INFO[ctx.guild.id]["PauseMsg"] = None
        PLAYER_INFO[ctx.guild.id]["VolMsg"] = None
        PLAYER_INFO[ctx.guild.id]["RmvMsg"] = None
        PLAYER_INFO[ctx.guild.id]["LoopMsg"] = None
        PLAYER_INFO[ctx.guild.id]["Removed"].clear()
        PLAYER_INFO[ctx.guild.id]["First"] = False

        to = min(max(to, 1), len(QUEUE[ctx.guild.id]["Current"]) - 1)

        if to <= 1 or len(QUEUE[ctx.guild.id]["Current"]) - 1 < 1:
            ctx.voice_client.stop()

            embed = discord.Embed(
                description=strings["Music.Skip"].format(PLAYER_INFO[ctx.guild.id]["Title"]),
                color=discord.Color.blurple()
            )
            if PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]:
                embed.set_footer(text=strings["Music.ButtonRequest"].format(PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]))
                await ctx.send(embed=embed)
            else:
                await ctx.respond(embed=embed)
        else:
            if not isinstance(QUEUE[ctx.guild.id]["Current"][to], YTDLSource):
                next_player = await YTDLSource.from_url(QUEUE[ctx.guild.id]["Current"][to], loop=self.bot.loop,
                                                        stream=True)
            else:
                next_player = QUEUE[ctx.guild.id]["Current"][to]

            del QUEUE[ctx.guild.id]["Current"][:to - 1]

            if len(QUEUE[ctx.guild.id]["Current"]) - 1 >= 1 and \
                    isinstance(QUEUE[ctx.guild.id]["Current"][1], YTDLSource):
                next_player_ = QUEUE[ctx.guild.id]["Current"][1]

                if next_player_.start_at:
                    PLAY_TIMER[ctx.guild.id]["Old"] = next_player_.start_at_seconds
            else:
                PLAY_TIMER[ctx.guild.id]["Old"] = 0

            ctx.voice_client.stop()

            embed = discord.Embed(
                description=strings["Music.SkipRange"].format(to - 1, to - 1, next_player.title),
                color=discord.Color.blurple()
            )
            await ctx.respond(embed=embed)

        PLAY_TIMER[ctx.guild.id]["Raw"], PLAY_TIMER[ctx.guild.id]["Act"] = 0, ""

    @commands.slash_command(description="Removes the bot from the voice channel and clears the queue")
    @option(name="after_song", description="Disconnects once current song has ended", choices=[True, False],
            required=False)
    async def disconnect(self, ctx, after_song: bool = False):
        await ctx.defer()

        strings = await get_language_strings(ctx)

        if not ctx.voice_client or not ctx.voice_client.is_connected():
            embed = discord.Embed(
                description=strings["Errors.NotConnected"],
                color=discord.Color.red(),
            )
            await ctx.respond(embed=embed)
            return

        channel = ctx.voice_client.channel

        if after_song and ctx.voice_client.is_playing():
            embed = discord.Embed(
                description=strings["Music.DisconnectAfterSong"].format(
                    PLAYER_INFO[ctx.guild.id]["Title"], PLAY_TIMER[ctx.guild.id]["Act"],
                    PLAYER_INFO[ctx.guild.id]["Object"].formatted_duration),
                color=discord.Color.dark_red()
            )
            await ctx.respond(embed=embed)

            while ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
                await asyncio.sleep(1)

        if ctx.guild.id in QUEUE:
            QUEUE[ctx.guild.id]["Current"].clear()

        await self.cleanup(ctx)

        try:
            await ctx.voice_client.disconnect()
        except AttributeError:
            return

        embed = discord.Embed(
            description=strings["Music.Disconnect"].format(channel),
            color=discord.Color.dark_red()
        )
        await ctx.respond(embed=embed)

    @commands.slash_command(description="Loops either the song or the entire queue")
    @option(name="mode", description="The loop mode you wish to use", choices=["Single", "Queue", "Disabled"],
            required=False)
    async def loop(self, ctx, mode: str = None):
        try:
            await ctx.defer()
        except (discord.ApplicationCommandInvokeError, discord.InteractionResponded):
            pass

        strings = await get_language_strings(ctx)

        if not ctx.voice_client or not ctx.voice_client.is_connected():
            embed = discord.Embed(
                description=strings["Errors.NotConnected"],
                color=discord.Color.red(),
            )
            await ctx.respond(embed=embed)

            if not ctx.voice_client:
                await self.cleanup(ctx)
            return
        elif not mode:
            embed = discord.Embed(
                description=strings["Music.Loop"].format(PLAYER_MOD[ctx.guild.id]["Loop"]),
                color=discord.Color.dark_gold(),
            )
            await ctx.respond(embed=embed)
            return

        PLAYER_MOD[ctx.guild.id]["Loop"] = mode

        embed = discord.Embed(
            description=strings["Music.LoopNew"].format(PLAYER_MOD[ctx.guild.id]["Loop"]),
            color=discord.Color.blurple(),
        )
        if PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]:
            embed.set_footer(text=strings["Music.ButtonRequest"].format(PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]))
            if PLAYER_INFO[ctx.guild.id]["LoopMsg"]:
                await PLAYER_INFO[ctx.guild.id]["LoopMsg"].edit(embed=embed)
            else:
                PLAYER_INFO[ctx.guild.id]["LoopMsg"] = await ctx.send(embed=embed)
        else:
            await ctx.respond(embed=embed)

    @commands.slash_command(description="Toggles pause for the current song")
    async def pause(self, ctx):
        try:
            await ctx.defer()
        except (discord.ApplicationCommandInvokeError, discord.InteractionResponded):
            pass

        strings = await get_language_strings(ctx)

        if not ctx.voice_client or (not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused()):
            embed = discord.Embed(
                description=strings["Errors.NothingPlaying"],
                color=discord.Color.red(),
            )
            if PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]:
                embed.set_footer(text=strings["Music.ButtonRequest"].format(PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]))
                await ctx.send(embed=embed)
            else:
                await ctx.respond(embed=embed)

            if not ctx.voice_client:
                await self.cleanup(ctx)
            return
        elif ctx.voice_client.is_playing():
            embed = discord.Embed(
                description=strings["Music.Pause"].format(PLAYER_INFO[ctx.guild.id]["Title"]),
                color=discord.Color.blurple(),
            )
            if PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]:
                embed.set_footer(text=strings["Music.ButtonRequest"].format(PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]))
                if PLAYER_INFO[ctx.guild.id]["PauseMsg"]:
                    await PLAYER_INFO[ctx.guild.id]["PauseMsg"].edit(embed=embed)
                else:
                    PLAYER_INFO[ctx.guild.id]["PauseMsg"] = await ctx.send(embed=embed)
            else:
                await ctx.respond(embed=embed)

            ctx.voice_client.pause()
        else:
            embed = discord.Embed(
                description=strings["Music.Resume"].format(PLAYER_INFO[ctx.guild.id]["Title"]),
                color=discord.Color.blurple(),
            )
            if PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]:
                embed.set_footer(text=strings["Music.ButtonRequest"].format(PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]))
                if PLAYER_INFO[ctx.guild.id]["PauseMsg"]:
                    await PLAYER_INFO[ctx.guild.id]["PauseMsg"].edit(embed=embed)
                else:
                    PLAYER_INFO[ctx.guild.id]["PauseMsg"] = await ctx.send(embed=embed)
            else:
                await ctx.respond(embed=embed)

            ctx.voice_client.resume()

    @commands.slash_command(name="filter", description="Applies an audio filter over the songs")
    @option(name="mode", description="The filter mode you wish to use",
            choices=["Nightcore", "BassBoost", "EarRape", "Disabled"], required=False)
    @option(name="intensity", description="Set the filter intensity percentage (35 by default)", required=False)
    async def filter_(self, ctx, mode: str, intensity: int = None):
        await ctx.defer()

        strings = await get_language_strings(ctx)

        if not ctx.voice_client or not ctx.voice_client.is_connected():
            embed = discord.Embed(
                description=strings["Errors.NotConnected"],
                color=discord.Color.red(),
            )
            await ctx.respond(embed=embed)

            if not ctx.voice_client:
                await self.cleanup(ctx)
            return

        if intensity:
            intensity = min(max(intensity, 0), 100)

        if not mode and not intensity:
            embed = discord.Embed(
                description=strings["Music.Filter"].format(
                    PLAYER_MOD[ctx.guild.id]["Filter"]["Name"], PLAYER_MOD[ctx.guild.id]["Filter"]["Intensity"]),
                color=discord.Color.dark_gold(),
            )
            await ctx.respond(embed=embed)
            return
        elif not mode and intensity:
            INVOKED[ctx.guild.id] = True

            if PLAYER_MOD[ctx.guild.id]["Filter"]["Name"] == "Nightcore":
                PLAYER_MOD[ctx.guild.id]["Filter"] = {"Name": "Nightcore",
                                                      "Val": f'-af "asetrate=44100*{1 + intensity / 100}, '
                                                             f'aresample=44100"',
                                                      "Intensity": intensity}
            elif PLAYER_MOD[ctx.guild.id]["Filter"]["Name"] == "BassBoost":
                PLAYER_MOD[ctx.guild.id]["Filter"] = {"Name": "BassBoost",
                                                      "Val": f'-af "bass=g={intensity // 5}, aresample=44100"',
                                                      "Intensity": intensity}
            elif PLAYER_MOD[ctx.guild.id]["Filter"]["Name"] == "EarRape":
                PLAYER_MOD[ctx.guild.id]["Filter"] = {"Name": "EarRape",
                                                      "Val": f'-af "acrusher=level_in={intensity // 5}:level_out='
                                                             f'{1 + ((intensity // 5) * 2)}:bits=8:mode=log:aa=1, '
                                                             f'aresample=44100"',
                                                      "Intensity": intensity}
            else:
                PLAYER_MOD[ctx.guild.id]["Filter"] = {"Name": "Disabled", "Val": "", "Intensity": intensity}
        else:
            INVOKED[ctx.guild.id] = True

            if not intensity:
                intensity = 35

            if mode == "Nightcore":
                PLAYER_MOD[ctx.guild.id]["Filter"] = {"Name": "Nightcore",
                                                      "Val": f'-af "asetrate=44100*{1 + intensity / 100}, '
                                                             f'aresample=44100"',
                                                      "Intensity": intensity}
            elif mode == "BassBoost":
                PLAYER_MOD[ctx.guild.id]["Filter"] = {"Name": "BassBoost",
                                                      "Val": f'-af "bass=g={intensity // 5}, aresample=44100"',
                                                      "Intensity": intensity}
            elif mode == "EarRape":
                PLAYER_MOD[ctx.guild.id]["Filter"] = {"Name": "EarRape",
                                                      "Val": f'-af "acrusher=level_in={intensity // 5}:level_out='
                                                             f'{1 + ((intensity // 5) * 2)}:bits=8:mode=log:aa=1, '
                                                             f'aresample=44100"',
                                                      "Intensity": intensity}
            else:
                PLAYER_MOD[ctx.guild.id]["Filter"] = {"Name": "Disabled", "Val": "", "Intensity": intensity}

        embed = discord.Embed(
            description=strings["Music.FilterApplying"].format(
                PLAYER_MOD[ctx.guild.id]["Filter"]["Name"], PLAYER_MOD[ctx.guild.id]["Filter"]["Intensity"]),
            color=discord.Color.blurple(),
        )
        main = await ctx.respond(embed=embed)

        if ctx.voice_client and ctx.voice_client.is_playing():
            old_timer_value = int(PLAY_TIMER[ctx.guild.id]["Raw"])
            previous_song = QUEUE[ctx.guild.id]["Current"][0]

            ctx.voice_client.stop()

            PLAY_TIMER[ctx.guild.id]["Old"], PLAY_TIMER[ctx.guild.id]["Raw"] = old_timer_value, old_timer_value
            timer = format_duration(old_timer_value)

            player = await YTDLSource.from_url(PLAYER_INFO[ctx.guild.id]["URL"], loop=self.bot.loop,
                                               stream=True, filter_=PLAYER_MOD[ctx.guild.id]["Filter"]["Val"],
                                               start_at=timer)

            while ctx.voice_client:
                try:
                    ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(
                                                                        self.song_deletion_handling(ctx, player),
                                                                        self.bot.loop))
                    QUEUE[ctx.guild.id]["Current"].insert(0, previous_song)
                    break
                except discord.ClientException:
                    await asyncio.sleep(1)
                    continue

        embed = discord.Embed(
            description=strings["Music.FilterNew"].format(
                PLAYER_MOD[ctx.guild.id]["Filter"]["Name"], PLAYER_MOD[ctx.guild.id]["Filter"]["Intensity"]),
            color=discord.Color.blurple(),
        )
        await main.edit(embed=embed)

        INVOKED[ctx.guild.id] = False

    @commands.slash_command(description="Changes the music player volume")
    @option(name="level", description="Set the volume level percentage (50 by default)", required=False)
    async def volume(self, ctx, level: int = None):
        try:
            await ctx.defer()
        except (discord.ApplicationCommandInvokeError, discord.InteractionResponded):
            pass

        strings = await get_language_strings(ctx)

        if not ctx.voice_client or not ctx.voice_client.is_connected():
            embed = discord.Embed(
                description=strings["Errors.NotConnected"],
                color=discord.Color.red(),
            )
            await ctx.respond(embed=embed)

            if not ctx.voice_client:
                await self.cleanup(ctx)
            return
        elif level is None:
            embed = discord.Embed(
                description=strings["Music.Volume"].format(int(PLAYER_MOD[ctx.guild.id]["Volume"] * 100)),
                color=discord.Color.dark_gold(),
            )
            await ctx.respond(embed=embed)
            return

        PLAYER_MOD[ctx.guild.id]["Volume"] = min(max(level, 0), 100) / 100

        if ctx.voice_client:
            PLAYER_INFO[ctx.guild.id]["Object"].volume = PLAYER_MOD[ctx.guild.id]["Volume"]

        embed = discord.Embed(
            description=strings["Music.VolumeNew"].format(int(PLAYER_MOD[ctx.guild.id]["Volume"] * 100)),
            color=discord.Color.blurple(),
        )
        if PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]:
            embed.set_footer(text=strings["Music.ButtonRequest"].format(PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]))
            if PLAYER_INFO[ctx.guild.id]["VolMsg"]:
                await PLAYER_INFO[ctx.guild.id]["VolMsg"].edit(embed=embed)
            else:
                PLAYER_INFO[ctx.guild.id]["VolMsg"] = await ctx.send(embed=embed)
        else:
            await ctx.respond(embed=embed)

    @commands.slash_command(description="Replays the previous song from the queue")
    @option(name="insert", description="Add the song to the given position in queue", required=False)
    async def replay(self, ctx, insert: int = 1):
        try:
            await ctx.defer()
        except (discord.ApplicationCommandInvokeError, discord.InteractionResponded):
            pass

        strings = await get_language_strings(ctx)

        if not len(QUEUE[ctx.guild.id]["Previous"]):
            embed = discord.Embed(
                description=strings["Errors.NoRecent"],
                color=discord.Color.red(),
            )
            if PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]:
                embed.set_footer(text=strings["Music.ButtonRequest"].format(PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]))
                await ctx.send(embed=embed)
            else:
                await ctx.respond(embed=embed)

            if not ctx.voice_client:
                await self.cleanup(ctx)
            return

        insert = min(max(insert, 1), len(QUEUE[ctx.guild.id]["Current"]))

        previous_song = QUEUE[ctx.guild.id]["Previous"][-1]
        replayed_player = await YTDLSource.from_url(previous_song, loop=self.bot.loop, stream=True)

        QUEUE[ctx.guild.id]["Previous"].pop(-1)

        if PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]:
            QUEUE[ctx.guild.id]["Current"].insert(1, replayed_player)
            QUEUE[ctx.guild.id]["Current"].insert(2, PLAYER_INFO[ctx.guild.id]["URL"])

            PLAYER_INFO[ctx.guild.id]["Backed"] = True

            ctx.voice_client.stop()

            embed = discord.Embed(
                description=strings["Music.Back"].format(replayed_player.title),
                color=discord.Color.blurple()
            )
            embed.set_footer(text=strings["Music.ButtonRequest"].format(PLAYER_INFO[ctx.guild.id]["ButtonInvoke"]))
            await ctx.send(embed=embed)

            PLAY_TIMER[ctx.guild.id]["Raw"], PLAY_TIMER[ctx.guild.id]["Act"] = 0, ""

            if PLAYER_INFO[ctx.guild.id]["Object"].start_at:
                PLAY_TIMER[ctx.guild.id]["Old"] = PLAYER_INFO[ctx.guild.id]["Object"].start_at_seconds
            else:
                PLAY_TIMER[ctx.guild.id]["Old"] = 0
            return

        if (ctx.voice_client and not ctx.voice_client.is_playing()) and not QUEUE[ctx.guild.id]["Current"]:
            embed = discord.Embed(
                description=strings["Music.ReplayLast"].format(replayed_player.title),
                color=discord.Color.purple(),
            )
            await ctx.respond(embed=embed)

            await self.play(ctx, query=previous_song)
        else:
            QUEUE[ctx.guild.id]["Current"].insert(insert, replayed_player)

            if not isinstance(QUEUE[ctx.guild.id]["Current"][1], YTDLSource):
                QUEUE[ctx.guild.id]["Current"][1] = await YTDLSource.from_url(QUEUE[ctx.guild.id]["Current"][1],
                                                                              loop=self.bot.loop, stream=True)

            embed = discord.Embed(
                description=strings["Music.Replay"].format(
                    replayed_player.title, insert, QUEUE[ctx.guild.id]["Current"][1].title),
                color=discord.Color.purple(),
            )
            await ctx.respond(embed=embed)

    @commands.slash_command(description="Seek a certain part of the song via timestamp")
    @option(name="timestamp", description="The timestamp to seek (i.e. hours:minutes:seconds)", required=True)
    async def seek(self, ctx, timestamp: str):
        await ctx.defer()

        strings = await get_language_strings(ctx)

        if not ctx.voice_client or (not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused()):
            embed = discord.Embed(
                description=strings["Errors.NothingPlaying"],
                color=discord.Color.red(),
            )
            await ctx.respond(embed=embed)

            if not ctx.voice_client:
                await self.cleanup(ctx)
            return
        elif PLAYER_INFO[ctx.guild.id]["Object"].formatted_duration == "Live":
            embed = discord.Embed(
                description=strings["Errors.SeekLive"],
                color=discord.Color.red(),
            )
            await ctx.respond(embed=embed)
            return

        new_timer_value = await parse_timestamp(ctx, timestamp=timestamp, no_seek=True)

        if new_timer_value is None:
            return
        elif new_timer_value >= PLAYER_INFO[ctx.guild.id]["Object"].duration:
            new_timer_value = PLAYER_INFO[ctx.guild.id]["Object"].duration

        INVOKED[ctx.guild.id] = True
        previous_song = QUEUE[ctx.guild.id]["Current"][0]

        ctx.voice_client.stop()

        PLAY_TIMER[ctx.guild.id]["Old"], PLAY_TIMER[ctx.guild.id]["Raw"] = new_timer_value, new_timer_value
        sought = format_duration(new_timer_value, PLAYER_INFO[ctx.guild.id]["DurationSec"])

        embed = discord.Embed(
            description=strings["Music.Seek"].format(sought, PLAYER_INFO[ctx.guild.id]["Object"].formatted_duration),
            color=discord.Color.blurple(),
        )
        main = await ctx.respond(embed=embed)

        player = await YTDLSource.from_url(PLAYER_INFO[ctx.guild.id]["URL"], loop=self.bot.loop, stream=True,
                                           filter_=PLAYER_MOD[ctx.guild.id]["Filter"]["Val"], start_at=sought)
        while ctx.voice_client:
            try:
                ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(
                                                                            self.song_deletion_handling(ctx, player),
                                                                            self.bot.loop))
                QUEUE[ctx.guild.id]["Current"].insert(0, previous_song)
                break
            except discord.ClientException:
                await asyncio.sleep(1)
                continue

        embed = discord.Embed(
            description=strings["Music.SeekSuccess"].format(
                sought, PLAYER_INFO[ctx.guild.id]["Object"].formatted_duration),
            color=discord.Color.blurple(),
        )
        await main.edit(embed=embed)

        INVOKED[ctx.guild.id] = False

    @commands.slash_command(description="Get lyrics for the currently playing song")
    @option(name="title", description="Get lyrics from the specified title instead", required=False)
    async def lyrics(self, ctx, title: str = None):
        await ctx.defer()

        strings = await get_language_strings(ctx)

        if not title and (not ctx.voice_client or (ctx.voice_client and not ctx.voice_client.is_playing())):
            embed = discord.Embed(
                description=strings["Errors.NothingPlaying"],
                color=discord.Color.red(),
            )
            await ctx.respond(embed=embed)
            return
        elif not title:
            title = PLAYER_INFO[ctx.guild.id]["Title"]

        embed = discord.Embed(
            description=strings["Music.FetchingLyrics"].format(title),
            color=discord.Color.dark_gold(),
        )
        main = await ctx.respond(embed=embed)

        title_list = list(title)
        stack = []

        for index, char in enumerate(title):
            if char in ("(", "["):
                stack.append((index, char))
            elif char in (")", "]") and stack:
                opening_index, opening_char = stack.pop()
                if (opening_char == "(" and char == ")") or (opening_char == "[" and char == "]"):
                    title_list[opening_index:index + 1] = [""] * (index - opening_index + 1)

        proper_title = "".join(title_list)

        try:
            song = Constants.GENIUS.search_song(title=proper_title, get_full_info=False)
        except (requests.ReadTimeout, requests.Timeout, discord.ApplicationCommandInvokeError):
            embed = discord.Embed(
                description=strings["Errors.TimedOut"],
                color=discord.Color.red(),
            )
            await main.edit(embed=embed)
            return

        if not song:
            embed = discord.Embed(
                description=strings["Music.FetchingLyricsNotFound"].format(title),
                color=discord.Color.dark_gold(),
            )
            await main.edit(embed=embed)
            return

        split_lyrics = song.lyrics.split("\n")
        split_lyrics[0] = split_lyrics[0].split("Lyrics")[1]
        split_lyrics[-1] = split_lyrics[-1].split("Embed")[0]

        for index in range(len(split_lyrics)):
            if "You might also like" in split_lyrics[index]:
                if split_lyrics[index].split("You might also like")[1].startswith("["):
                    split_lyrics[index] = split_lyrics[index].replace("You might also like", "\n")
                else:
                    split_lyrics[index] = split_lyrics[index].replace("You might also like", "")

            if split_lyrics[index].startswith("[") and split_lyrics[index - 1].strip() != "":
                split_lyrics[index] = f"\n{split_lyrics[index]}"

            if index == len(split_lyrics) - 1:
                reducer = 0

                while split_lyrics[index][-1].isnumeric():
                    split_lyrics[index] = split_lyrics[index][:len(split_lyrics[index]) - reducer]
                    reducer += 1

        proper_lyrics = "\n".join(split_lyrics)

        embed = discord.Embed(
            description=strings["Music.FetchingLyricsSuccess"].format(title),
            color=discord.Color.dark_gold(),
        )
        await main.edit(embed=embed)

        try:
            embed = discord.Embed(
                description=strings["Music.Lyrics"].format(song.title, proper_lyrics),
                color=discord.Color.dark_gold()
            )
            await ctx.send(embed=embed)
        except discord.HTTPException:
            embed = discord.Embed(
                description=strings["Music.LyricsTooLong"].format(song.title, song.url),
                color=discord.Color.dark_gold()
            )
            await ctx.send(embed=embed)

    @connect.before_invoke
    @play.before_invoke
    @remove.before_invoke
    @clear.before_invoke
    @view.before_invoke
    @shuffle.before_invoke
    @move.before_invoke
    @skip.before_invoke
    @loop.before_invoke
    @pause.before_invoke
    @filter_.before_invoke
    @volume.before_invoke
    @replay.before_invoke
    @seek.before_invoke
    async def ensure_dicts(self, ctx):
        if ctx.guild.id not in QUEUE:
            QUEUE[ctx.guild.id] = {"Current": [], "Previous": [], "Sum": 0}
        if ctx.guild.id not in PLAYER_MOD:
            PLAYER_MOD[ctx.guild.id] = {"Loop": "Disabled", "Filter": {"Name": "Disabled", "Val": "", "Intensity": 35},
                                        "Volume": 0.50}
        if ctx.guild.id not in PLAYER_INFO:
            PLAYER_INFO[ctx.guild.id] = {"Title": "", "URL": "", "Duration": "", "DurationSec": 0, "Object": None,
                                         "EmbedID": 0, "ListSec": 0, "ListDuration": "", "Backed": False,
                                         "PauseMsg": None, "VolMsg": None, "RmvMsg": None, "LoopMsg": None,
                                         "Removed": [], "TextChannel": 0, "First": False, "ButtonInvoke": None,
                                         "LoopCount": 0, "Embed": None}
        if ctx.guild.id not in PLAY_TIMER:
            PLAY_TIMER[ctx.guild.id] = {"Raw": 0, "Act": "", "Old": 0}
        if ctx.guild.id not in INVOKED:
            INVOKED[ctx.guild.id] = False


def setup(bot):
    bot.add_cog(Music(bot))

import json
import asyncio
import discord
import discord.utils
from discord.ext import commands
from utils import EmbedColor, get_performance_metrics, load_roles, load_settings

class RoleMenu(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(custom_id="role_assign", placeholder="Select roles...", min_values=0, max_values=len(options), options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        member = interaction.user
        added, removed = [], []

        assert interaction.guild and isinstance(member, discord.Member)

        if not interaction.guild.me.guild_permissions.manage_roles:
            embed = discord.Embed(
                description="**Error:** Missing permissions: `Manage Roles`",
                color=EmbedColor.RED
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            for role_id in [int(opt.value) for opt in self.options]:
                role = discord.utils.get(interaction.guild.roles, id=role_id)
                if not role: continue

                if str(role_id) in self.values:
                    if role_id not in [role.id for role in member.roles]:
                        await member.add_roles(role)
                        added.append(role.name)
                else:
                    if role_id in [role.id for role in member.roles]:
                        await member.remove_roles(role)
                        removed.append(role.name)
        except discord.Forbidden:
            embed = discord.Embed(
                description="**Error:** Missing permissions.",
                color=EmbedColor.RED
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if not (added or removed):
            role_msg = "No changes to roles."
        else:
            added_msg = f"**Added roles:** {', '.join(added)}\n" if added else ""
            removed_msg = f"**Removed roles:** {', '.join(removed)}" if removed else ""
            role_msg = added_msg + removed_msg

        embed = discord.Embed(
            description=role_msg,
            color=EmbedColor.GREEN
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
class RoleView(discord.ui.View):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(timeout=None)
        self.add_item(RoleMenu(options))

class Basic(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @commands.slash_command(description="Simple help command")
    @discord.option(name="subsection", description="The subsection of the help command", choices=["Basic", "Music", "Voice"], required=False)
    async def help(self, ctx: discord.ApplicationContext, subsection: str = ""):
        help_string = """
        [] = Required field
        {} = Optional field\n
        **/help Basic** - Basic commands
        **/help Music** - Music commands
        **/help Voice** - Voice commands
        """
        basic = """
        **/help {subsection}** - Simple help command
        \\* **subsection** - The subsection of the help command\n
        **/settings {speech_recognition} {default_search}** - Modifies user-specific settings
        \\* **speech_recognition** - Toggle the ability to recognize speech for the user
        \\* **default_search** - Set the default source to use when searching for songs\n
        **/perfstat** - Displays performance statistics\n
        **/repair** - Attempts to repair the bot's voice connection in case of breakage\n
        **/msgdel [amount] | ADMIN** - Deletes the specified amount of messages in a channel
        \\* **amount** - The amount of messages to delete\n
        **/joinrole {role} | ADMIN** - Specifies the role that new members get upon joining
        \\* **role** - The role to give new members\n
        **/role_assign [roles] {message} | ADMIN** - Creates a menu for self-assigning roles
        \\* **roles** - The menu roles separated by semicolons (i.e. role1;role2;...)
        \\* **message** - The menu message
        \\* **message_id** - The ID of the message to update
        """
        music = """
        **/connect** - Invites the bot to the voice channel\n
        **/disconnect {after_song}** - Removes the bot from the voice channel and clears the queue
        \\* **after_song** - Disconnect once the current song has ended\n
        **/play [query] {insert} {pre-shuffle} {start}** - Adds and plays songs in the queue
        \\* **query** - The song that you wish to play (URL or query)
        \\* **insert** - Add the song to the given position in queue
        \\* **pre_shuffle** - Shuffle the songs of the playlist ahead of time
        \\* **start** - Set the song to start from the given timestamp\n
        **/play_file [file] {insert} {start}** - Plays audio from a given file
        \\* **file** - File to play audio from
        \\* **insert** - Add the song to the given position in queue
        \\* **start** - Set the song to start from the given timestamp\n
        **/view {to} {from_} {seek} {previous}** - Displays songs in queue, with the ability to seek them
        \\* **to** - The end position of the queue display
        \\* **from_** - The start position of the queue display
        \\* **seek** - Seek songs via given keywords
        \\* **previous** - Display the previous queue\n
        **/remove [from_] {to}** - Removes songs from the queue
        \\* **from_** - The start position of the queue removal, or positions separated by semicolons (i.e. pos1;pos2;...)
        \\* **to** - The end position of the queue removal\n
        **/shuffle {from_} {to}** - Shuffles the queue
        \\* **from_** - The start position of the queue shuffle
        \\* **to** - The end position of the queue shuffle\n
        **/move [from_] [to] {replace}** - Moves the song to the specified position in the queue
        \\* **from_** - The current position of the song in queue
        \\* **to** - The position in queue you wish to move the song to
        \\* **replace** - Replace the song in the target position\n
        **/clear {from_}** - Clears the queue
        \\* **from_** - The start position of the queue clear\n
        **/skip {to}** - Skips to the next, or to the specified, song in the queue
        \\* **to** - The position in queue you wish to skip to\n
        **/loop [mode]** - Loops either the song or the entire queue
        \\* **mode** - The loop mode you wish to use\n
        **/pause** - Toggles pause for the current song\n
        **/filter [mode] {intensity}** - Applies an audio filter over the songs
        \\* **mode** - The filter mode you wish to use
        \\* **intensity** - Set the filter intensity percentage (35 by default)\n
        **/volume [level]** - Sets the music player volume
        \\* **level** - Set the volume level percentage (100 by default)\n
        **/replay {from_} {insert} {instant}** - Replays previous songs from the queue
        \\* **from_** - Current position of the song in previous queue
        \\* **insert** - Add the song to the given position in queue
        \\* **instant** - Replay the song instantly\n
        **/seek [timestamp]** - Seeks a certain part of the song via a timestamp
        \\* **timestamp** - The timestamp to seek (i.e. hours:minutes:seconds)\n
        **/lyrics {title}** - Gets lyrics for the currently playing song
        \\* **title** - Get lyrics from the specified title instead\n
        **/autoplay** - Toggles autoplay for the queue
        """
        voice = """
        **Note:** Speech recognition can be toggled per user via the </settings:1372991283387170932> command.
        Speech recognition is activated by muting and unmuting the microphone, after which speech is listened to for 5 seconds.\n
        **play | toista [query]** - Adds and plays songs in the queue
        \\* **query** - The song that you wish to play\n
        **skip | seuraava** - Skips to the next song in the queue\n
        **pause | pysäytä** - Toggles pause for the current song\n
        **disconnect | painu vittuun** -  Removes the bot from the voice channel and clears the queue
        """

        if not subsection:
            embed = discord.Embed(
                description=help_string,
                color=EmbedColor.YELLOW
            )
            embed.set_author(name=f"{ctx.guild.name} - Helpdesk", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
            return await ctx.respond(embed=embed, ephemeral=True)

        embed = discord.Embed(
            title=f"**{subsection} Commands**",
            description=locals()[subsection.lower()],
            color=EmbedColor.YELLOW
        )
        embed.set_author(name=f"{ctx.guild.name} - Helpdesk", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(description="Modifies user-specific settings")
    @discord.option(name="speech_recognition", description="Toggle the ability to recognize speech for the user", required=False)
    @discord.option(name="default_search", description="Set the default source to use when searching for songs", choices=["SoundCloud", "Spotify", "YouTube Music", "YouTube"], required=False)
    async def settings(self, ctx: discord.ApplicationContext, speech_recognition: bool = None, default_search: str = ""):
        key = f"{ctx.author.id}-{ctx.guild.id}"
        data = load_settings()
        search_names = {
            "soundcloud": "SoundCloud",
            "spotify": "Spotify",
            "youtube_music": "YouTube Music",
            "youtube": "YouTube"
        }
        data.setdefault(key, {"speech_recognition": True, "default_search": "youtube"})

        if speech_recognition is not None: data[key]["speech_recognition"] = speech_recognition
        if default_search: data[key]["default_search"] = default_search.replace(" ", "_").lower()

        with open("./data/settings.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        embed = discord.Embed(
            title=f"**Settings ({ctx.author.name})**",
            description=f"**Speech recognition:** {'Enabled' if data[key]['speech_recognition'] else 'Disabled'}\n**Default search:** {search_names[data[key]['default_search']]}",
            color=EmbedColor.YELLOW
        )
        await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(description="Displays performance statistics")
    async def perfstat(self, ctx: discord.ApplicationContext):
        ram_total, ram_usage, ram_percent, cpu, guilds = get_performance_metrics(self.bot)

        embed = discord.Embed(
            description=f"Currently connected to **{len(guilds)}** of **{len(self.bot.guilds)}** guild(s).\n**RAM:** {ram_usage} ({ram_percent}) / {ram_total} GiB (100.0 %)\n**CPU:** {cpu} / 100.0 %",
            color=EmbedColor.YELLOW
        )
        await ctx.respond(embed=embed, ephemeral=True)

    @commands.has_permissions(administrator=True)
    @commands.slash_command(description="Deletes the specified amount of messages in a channel")
    @discord.option(name="amount", description="The amount of messages to delete", min_value=1, max_value=100, required=True)
    async def msgdel(self, ctx: discord.ApplicationContext, amount: int):
        if not ctx.guild.me.guild_permissions.manage_messages:
            embed = discord.Embed(
                description="**Error:** Missing permissions: `Manage Messages`",
                color=EmbedColor.RED
            )
            return await ctx.respond(embed=embed, ephemeral=True)
        
        await ctx.defer()

        embed = discord.Embed(
            description=f"Deleting **{amount}** message(s), please wait a few seconds...",
            color=EmbedColor.DARK_RED
        )
        embed.set_footer(text="Note: If you wish to cancel, delete this message.")
        failsafe = await ctx.send_followup(embed=embed)
        await asyncio.sleep(7.5)
        await failsafe.delete()
        await ctx.channel.purge(limit=amount)

    @commands.has_permissions(administrator=True)
    @commands.slash_command(description="Specifies the role that new members get upon joining")
    @discord.option(name="role", description="The role to give new members", required=False)
    async def joinrole(self, ctx: discord.ApplicationContext, role: discord.Role = None):
        if not ctx.guild.me.guild_permissions.manage_roles:
            embed = discord.Embed(
                description="**Error:** Missing permissions: `Manage Roles`",
                color=EmbedColor.RED
            )
            return await ctx.respond(embed=embed, ephemeral=True)
        elif role and role.is_default():
            embed = discord.Embed(
                description="**Error:** The default role cannot be assigned as the join role.",
                color=EmbedColor.RED
            )
            return await ctx.respond(embed=embed, ephemeral=True)
        elif role and role.position >= ctx.guild.me.top_role.position:
            embed = discord.Embed(
                description="**Error:** Role must be lower in the hierarchy than that of the bot.",
                color=EmbedColor.RED
            )
            return await ctx.respond(embed=embed, ephemeral=True)

        data = load_roles()
        data.setdefault(str(ctx.guild.id), {"join": None, "assign": {}})
        if role: data[str(ctx.guild.id)]["join"] = role.id

        with open("./data/roles.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        embed = discord.Embed(
            description=f"**Current join role:** {discord.utils.get(ctx.guild.roles, id=data[str(ctx.guild.id)]['join'])}",
            color=EmbedColor.YELLOW
        )
        await ctx.respond(embed=embed, ephemeral=True)

    @commands.has_permissions(administrator=True)
    @commands.slash_command(description="Creates a menu for self-assigning roles")
    @discord.option(name="roles", description="The menu roles separated by semicolons (i.e. role1;role2;...)", required=True)
    @discord.option(name="message", description="The menu message", required=False)
    @discord.option(name="message_id", description="The ID of the message to update", required=False)
    async def role_assign(self, ctx: discord.ApplicationContext, roles: str, message: str = "", message_id: str = ""):
        role_names = {name.strip() for name in roles.split(";") if name.strip()}
        role_list = [discord.utils.get(ctx.guild.roles, name=role_name) for role_name in role_names]
        valid_roles = [role for role in role_list if role and role.position < ctx.guild.me.top_role.position]
        invalid_role_names = [f"`{role}`" for role in role_names - {role.name for role in valid_roles}]

        if invalid_role_names:
            embed = discord.Embed(
                description=f"**Error:** The following roles were not found or were too high in the hierarchy:\n{', '.join(invalid_role_names)}",
                color=EmbedColor.RED
            )
            await ctx.respond(embed=embed, ephemeral=True)

        if not valid_roles:
            embed = discord.Embed(
                description="**Error:** Given roles not found.",
                color=EmbedColor.RED
            )
            return await ctx.respond(embed=embed, ephemeral=True)
        elif not ctx.guild.me.guild_permissions.manage_roles:
            embed = discord.Embed(
                description="**Error:** Missing permissions: `Manage Roles`",
                color=EmbedColor.RED
            )
            return await ctx.respond(embed=embed, ephemeral=True)

        options = [discord.SelectOption(label=role.name[:100], value=str(role.id)) for role in valid_roles]
        role_ids = [role.id for role in valid_roles]
        
        data = load_roles()
        data.setdefault(str(ctx.guild.id), {"join": None, "assign": {}})

        if message_id:
            try:
                msg = await ctx.channel.fetch_message(int(message_id))
                embed = msg.embeds[0].copy()
                if message: embed.description = message

                await msg.edit(embed=embed, view=RoleView(options))

                data[str(ctx.guild.id)]["assign"] = {"channel_id": ctx.channel.id, "message_id": int(message_id), "options": role_ids}

                with open("./data/roles.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
            
                embed = discord.Embed(
                    description="Role assignment menu updated.",
                    color=EmbedColor.GREEN
                )
                return await ctx.respond(embed=embed, ephemeral=True)
            except (discord.HTTPException, discord.NotFound):
                embed = discord.Embed(
                    description="**Error:** Could not find message with given ID.",
                    color=EmbedColor.RED
                )
                return await ctx.respond(embed=embed, ephemeral=True)
            
        embed = discord.Embed(
            description=message or "Role assignment time.",
            color=EmbedColor.GREEN
        )
        if ctx.interaction.response.is_done():
            saved_msg = await ctx.followup.send(embed=embed, view=RoleView(options))
        else:
            await ctx.respond(embed=embed, view=RoleView(options))
            saved_msg = await ctx.interaction.original_response()

        if saved_msg:
            data[str(ctx.guild.id)]["assign"] = {"channel_id": ctx.channel.id, "message_id": saved_msg.id, "options": role_ids}

            with open("./data/roles.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

    @commands.Cog.listener()
    async def on_application_command_error(self, ctx: discord.ApplicationContext, error: discord.DiscordException):
        if isinstance(error, commands.CheckFailure):
            embed = discord.Embed(
                description="**Error:** Only admins are allowed to execute this command.",
                color=EmbedColor.RED
            )
            await ctx.respond(embed=embed, ephemeral=True)
        else:
            print(error)

def setup(bot):
    bot.add_cog(Basic(bot))

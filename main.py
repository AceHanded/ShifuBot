import discord
from discord import option
from discord.ext import commands, tasks
from discord.ui import Select, View
import psutil
from datetime import datetime
import json
from dotenv import load_dotenv
import os
from Cogs.utils import Color, get_language_strings


load_dotenv()

SELECT = {}

bot = commands.Bot(command_prefix="€", case_insensitive=True, help_command=None)

cogs = ["music", "basic", "admin", "game", "economy"]
for cog in cogs:
    bot.load_extension(f"Cogs.{cog}")


@bot.slash_command(description="Loads the specified cog", guild_ids=[os.getenv("PERSONAL_GUILD")])
@option(name="extension", description="The extension to handle", required=True, choices=cogs)
@commands.is_owner()
async def load(ctx, extension: str):
    strings = await get_language_strings(ctx)

    bot.load_extension(f"Cogs.{extension}")

    embed = discord.Embed(
        description=strings["Main.LoadCog"].format(extension),
        color=discord.Color.dark_green()
    )
    await ctx.response.send_message(embed=embed)


@bot.slash_command(description="Unloads the specified cog", guild_ids=[os.getenv("PERSONAL_GUILD")])
@option(name="extension", description="The extension to handle", required=True, choices=cogs)
@commands.is_owner()
async def unload(ctx, extension: str):
    strings = await get_language_strings(ctx)

    bot.unload_extension(f"Cogs.{extension}")

    embed = discord.Embed(
        description=strings["Main.UnloadCog"].format(extension),
        color=discord.Color.dark_green()
    )
    await ctx.response.send_message(embed=embed)


@bot.slash_command(description="Reloads the specified cog", guild_ids=[os.getenv("PERSONAL_GUILD")])
@option(name="extension", description="The extension to handle", required=True, choices=cogs)
@commands.is_owner()
async def reload(ctx, extension: str):
    strings = await get_language_strings(ctx)

    bot.reload_extension(f"Cogs.{extension}")

    embed = discord.Embed(
        description=strings["Main.ReloadCog"].format(extension),
        color=discord.Color.dark_green()
    )
    await ctx.response.send_message(embed=embed)


@bot.event
async def on_message(msg):
    if msg.content == bot.user.mention:
        strings = await get_language_strings(msg)

        embed = discord.Embed(
            description=strings["Main.Mention"],
            color=discord.Color.dark_gold(),
        )
        await msg.channel.send(embed=embed)


@bot.event
async def on_member_join(member):
    with open("Data/joinroles.json", "r") as role_file:
        roles = json.load(role_file)

    if member.guild.id in roles:
        try:
            await member.add_roles(discord.utils.get(member.guild.roles, name=roles[member.guild.id]))
            print(f"[{Color.CYAN}{datetime.now().strftime('%H:%M:%S')}{Color.END}] A new member has joined "
                  f"{Color.GREEN}{bot.get_guild(member.guild.id)}{Color.END} and was assigned the role: "
                  f"{Color.MAGENTA}{roles[member.guild.id].name}{Color.END}")
        except (AttributeError, discord.Forbidden) as e:
            print(e)


@bot.event
async def on_ready():
    print(f"{bot.user} ({bot.user.id}) initialized!\n-----")
    print("Initializing role menus...")

    with open("Data/messages.json", "r") as message_file:
        messages = json.load(message_file)

    with open("Data/settings.json", "r") as settings_file:
        settings = json.load(settings_file)

    valid_message_guilds, invalid_message_guilds = [], []
    for guild_id in messages:
        try:
            with open(f"Locales/{settings.get(str(guild_id), 'english')}.json") as lang_file:
                strings = json.load(lang_file)

            select = Select(placeholder=strings["RoleSelection.Placeholder"], options=[], min_values=0)

            running_number = 1
            for role in messages[guild_id]["Opts"]:
                async def role_callback(interaction: discord.Interaction):
                    member = bot.get_guild(interaction.guild_id).get_member(interaction.user.id)

                    unselected_options = [option_.label for option_ in SELECT[str(interaction.guild.id)].options if
                                          option_.value not in SELECT[str(interaction.guild.id)].values]

                    assigned_roles, removed_roles, unassigned_roles = [], [], []
                    for option_ in SELECT[str(interaction.guild.id)].values:
                        role_ = discord.utils.get(interaction.guild.roles, name=option_)

                        if role_ not in member.roles:
                            try:
                                await member.add_roles(role_)
                                assigned_roles.append(f"`{option_}`")
                            except discord.Forbidden:
                                unassigned_roles.append(f"`{option_}`")

                    for option_ in unselected_options:
                        role_ = discord.utils.get(interaction.guild.roles, name=option_)

                        if role_ in member.roles:
                            try:
                                await member.remove_roles(role_)
                                removed_roles.append(f"`{option_}`")
                            except discord.Forbidden:
                                unassigned_roles.append(f"`{option_}`")

                    joined_assigned = "\n".join(assigned_roles) + "\n"
                    joined_removed = "\n".join(removed_roles)
                    joined_unassigned = "\n".join(unassigned_roles)

                    if assigned_roles or removed_roles or unassigned_roles:
                        roles_assigned_message = strings["RoleSelection.Assigned"]
                        roles_removed_message = strings["RoleSelection.Removed"]
                        roles_unassigned_message = strings["RoleSelection.Unassigned"]

                        embed_ = discord.Embed(
                            description=f"{roles_assigned_message + joined_assigned if assigned_roles else ''}"
                                        f"{roles_removed_message + joined_removed if removed_roles else ''}"
                                        f"{roles_unassigned_message + joined_unassigned if unassigned_roles else ''}",
                            color=discord.Color.dark_green() if not unassigned_roles else discord.Color.red()
                        )
                    else:
                        embed_ = discord.Embed(
                            description=strings["RoleSelection.NoChanges"],
                            color=discord.Color.dark_green()
                        )
                    await interaction.response.send_message(embed=embed_, ephemeral=True)

                select.callback = role_callback
                select.add_option(label=role, value=role, description=f"{running_number} - {role}")
                running_number += 1

            if len(messages[guild_id]["Opts"]) > 0:
                select.max_values = len(messages[guild_id]["Opts"])
            else:
                select.max_values = 1

            view = View(timeout=None)
            view.add_item(select)

            channel = bot.get_guild(int(guild_id)).get_channel(messages[guild_id]["ChannelID"])
            message = await channel.fetch_message(messages[guild_id]["MessageID"])
            await message.edit(view=view)

            SELECT[guild_id] = select
            valid_message_guilds.append(guild_id)
        except discord.NotFound:
            invalid_message_guilds.append(guild_id)
            continue

    for guild in invalid_message_guilds:
        del messages[guild]

    with open("Data/messages.json", "w") as message_file:
        json.dump(messages, message_file, indent=4)

    print(f"Role menus initialized!"
          f"{f' ({Color.GREEN}{len(valid_message_guilds)} updates{Color.END})' if valid_message_guilds else ''}"
          f"{f' ({Color.RED}{len(invalid_message_guilds)} removals{Color.END})' if invalid_message_guilds else ''}")

    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="tracks | /help"))
    resource_display.start()


@bot.slash_command(description="Displays performance statistics")
async def perfstat(ctx):
    from Cogs.music import QUEUE

    strings = await get_language_strings(ctx)

    ram = psutil.virtual_memory()[3] / 1000000000
    ramt = psutil.virtual_memory().total / 1000000000
    ramp = round(ram / ramt, 3) * 100
    cpu = psutil.cpu_percent(1)
    current_time = datetime.now().strftime('%H:%M:%S')

    embed = discord.Embed(
        description=strings["Main.Perfstat"].format(len(bot.guilds), len(QUEUE), ram, ramp, ramt, cpu),
        color=discord.Color.dark_gold()
    )
    embed.set_footer(text=strings["Main.RequestTimestamp"].format(current_time))
    await ctx.response.send_message(embed=embed, ephemeral=True)


@tasks.loop(minutes=5)
async def resource_display():
    from Cogs.music import QUEUE

    queues = [str(bot.get_guild(queue)) for queue in QUEUE]
    queues_amount = len(queues)
    queues_joined = ", ".join(queues)
    ram = psutil.virtual_memory()[3] / 1000000000
    ramt = psutil.virtual_memory().total / 1000000000
    ramp = round(ram / ramt, 3) * 100
    cpu = psutil.cpu_percent(1)
    current_time = datetime.now().strftime('%H:%M:%S')

    print(f"[{Color.CYAN}{current_time}{Color.END}] ShifuBot currently connected to {Color.GREEN}{queues_amount}"
          f"{Color.END} guild(s): {Color.GREEN}{queues_joined}{Color.END}\n- RAM usage: "
          f"{Color.GREEN if ramp < 33.3 else Color.YELLOW if 33.3 < ramp < 67.7 else Color.RED}{ram:.4f} ({ramp:.1f})"
          f"{Color.END} / {ramt:.4f} GB (100.0 %)\n- CPU usage: "
          f"{Color.GREEN if cpu < 33.3 else Color.YELLOW if 33.3 < cpu < 67.7 else Color.RED}{cpu}{Color.END} "
          f"/ 100.0 %")


bot.run(os.getenv("BOT_TOKEN"))

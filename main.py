import discord
from discord.ext import commands, tasks
from discord.ui import Select, View
import psutil
from datetime import datetime
from Cogs.utils import Color
import json
import os
from dotenv import load_dotenv


load_dotenv()


SELECT = {}

bot = commands.Bot(command_prefix="€", case_insensitive=True, help_command=None, intents=discord.Intents.default())
cogs = ["music", "basic", "admin", "economy", "game"]

for cog in cogs:
    bot.load_extension(f"Cogs.{cog}")


async def role_callback(interaction: discord.Interaction):
    member = bot.get_guild(interaction.guild_id).get_member(interaction.user.id)

    assigned_roles, removed_roles, unassigned_roles = [], [], []
    unselected_options = [option_.label for option_ in SELECT[str(interaction.guild.id)].options if
                          option_.value not in SELECT[str(interaction.guild.id)].values]
    options = set(SELECT[str(interaction.guild.id)].values) | set(unselected_options)

    for option in options:
        role = discord.utils.get(interaction.guild.roles, name=option)

        try:
            if option in SELECT[str(interaction.guild.id)].values and role not in member.roles:
                await member.add_roles(role)
                assigned_roles.append(f"`{option}`")
            elif option in unselected_options and role in member.roles:
                await member.remove_roles(role)
                removed_roles.append(f"`{option}`")
        except discord.Forbidden:
            unassigned_roles.append(f"`{option}`")

    if assigned_roles or removed_roles or unassigned_roles:
        joined_assigned = "\n".join(assigned_roles)
        joined_removed = "\n".join(removed_roles)
        joined_unassigned = "\n".join(unassigned_roles)

        roles_assigned_message = f"You have **assigned** the following roles to yourself:\n{joined_assigned}\n"
        roles_removed_message = f"You have **removed** the following roles from yourself:\n{joined_removed}\n"
        roles_unassigned_message = (f"The following roles could not be accessed due to permission issues:\n"
                                    f"{joined_unassigned}\n\nPlease ensure that the bot has the `Manage Roles` "
                                    f"permission.")

        embed = discord.Embed(
            description=f"{roles_assigned_message if assigned_roles else ''}"
                        f"{roles_removed_message if removed_roles else ''}"
                        f"{roles_unassigned_message if unassigned_roles else ''}",
            color=discord.Color.dark_green() if not unassigned_roles else discord.Color.red()
        )
    else:
        embed = discord.Embed(
            description="No changes made to roles.",
            color=discord.Color.dark_green()
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def update_select_menus():
    with open("Data/messages.json", "r") as message_file:
        messages = json.load(message_file)

    valid_message_guilds, invalid_message_guilds = [], []
    for guild_id in messages:
        try:
            select = Select(placeholder="Roles...", options=[], min_values=0)

            for i, role in enumerate(messages[guild_id]["opts"]):
                select.callback = role_callback
                select.add_option(label=role, value=role, description=f"{i + 1} - {role}")

            select.max_values = len(messages[guild_id]["opts"]) if len(messages[guild_id]["opts"]) > 0 else 1

            view = View(timeout=None)
            view.add_item(select)

            channel = bot.get_guild(int(guild_id)).get_channel(messages[guild_id]["channel_id"])
            message = await channel.fetch_message(messages[guild_id]["message_id"])
            await message.edit(view=view)

            SELECT[guild_id] = select
            valid_message_guilds.append(guild_id)
        except discord.NotFound:
            invalid_message_guilds.append(guild_id)
            continue

    for guild_id in invalid_message_guilds:
        del messages[guild_id]

    with open("Data/messages.json", "w") as message_file:
        json.dump(messages, message_file, indent=4)

    return len(valid_message_guilds), len(invalid_message_guilds)


@bot.slash_command(description="Loads the specified cog")
@discord.option(name="extension", description="The extension to handle", required=True, choices=cogs)
@commands.is_owner()
async def load(ctx: discord.ApplicationContext, extension: str):
    bot.load_extension(f"Cogs.{extension}")

    embed = discord.Embed(
        description=f"Cog `{extension}` loaded successfully.",
        color=discord.Color.dark_green()
    )
    await ctx.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(description="Unloads the specified cog")
@discord.option(name="extension", description="The extension to handle", required=True, choices=cogs)
@commands.is_owner()
async def unload(ctx: discord.ApplicationContext, extension: str):
    bot.unload_extension(f"Cogs.{extension}")

    embed = discord.Embed(
        description=f"Cog `{extension}` unloaded successfully.",
        color=discord.Color.dark_green()
    )
    await ctx.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(description="Reloads the specified cog")
@discord.option(name="extension", description="The extension to handle", required=True, choices=cogs)
@commands.is_owner()
async def reload(ctx: discord.ApplicationContext, extension: str):
    bot.reload_extension(f"Cogs.{extension}")

    embed = discord.Embed(
        description=f"Cog `{extension}` reloaded successfully.",
        color=discord.Color.dark_green()
    )
    await ctx.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(description="Displays performance statistics")
async def perfstat(ctx: discord.ApplicationContext):
    from Cogs.music import QUEUE_LIST

    ram = psutil.virtual_memory()[3] / 1000000000
    ramt = psutil.virtual_memory().total / 1000000000
    ramp = round(ram / ramt, 3) * 100
    cpu = psutil.cpu_percent(1)
    current_time = datetime.now().strftime("%H:%M:%S")

    embed = discord.Embed(
        description=f"**Total guilds:** {len(bot.guilds)}\n**Currently connected to:** {len(QUEUE_LIST)}\n"
                    f"**RAM:** {ram:.4f} ({ramp:.1f}) / {ramt:.4f} GB (100.0 %)\n**CPU:** {cpu} / 100.0 %",
        color=discord.Color.dark_gold()
    )
    embed.set_footer(text=f"Requested at: {current_time}")
    await ctx.response.send_message(embed=embed, ephemeral=True)


@tasks.loop(minutes=5)
async def resource_display():
    from Cogs.music import QUEUE_LIST

    queues = [bot.get_guild(guild_id).name for guild_id in QUEUE_LIST]
    queues_amount = len(queues)
    queues_joined = ", ".join(queues)
    ram = psutil.virtual_memory()[3] / 1000000000
    ramt = psutil.virtual_memory().total / 1000000000
    ramp = round(ram / ramt, 3) * 100
    cpu = psutil.cpu_percent(1)
    current_time = datetime.now().strftime("%H:%M:%S")

    print(f"[{Color.CYAN}{current_time}{Color.END}] ShifuBot currently connected to {Color.GREEN}{queues_amount}"
          f"{Color.END} guild(s): {Color.GREEN}{queues_joined}{Color.END}\n- RAM usage: "
          f"{Color.GREEN if ramp < 33.3 else Color.YELLOW if 33.3 < ramp < 67.7 else Color.RED}{ram:.4f} ({ramp:.1f})"
          f"{Color.END} / {ramt:.4f} GB (100.0 %)\n- CPU usage: "
          f"{Color.GREEN if cpu < 33.3 else Color.YELLOW if 33.3 < cpu < 67.7 else Color.RED}{cpu}{Color.END} "
          f"/ 100.0 %")


@bot.event
async def on_message(msg: discord.Message):
    if msg.content == bot.user.mention:
        embed = discord.Embed(
            description="Use the command `/help` to get started.",
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

    valid, invalid = await update_select_menus()

    print(f"Role menus initialized! ({Color.GREEN}{valid} updates{Color.END}) "
          f"({Color.RED}{invalid} removals{Color.END})")

    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="tracks | /help"))

    if not resource_display.is_running():
        resource_display.start()


bot.run(os.getenv("BOT_TOKEN"))

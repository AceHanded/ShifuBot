import json
import discord
import discord.utils
from datetime import datetime
from cogs.basic import RoleView
from dotenv import dotenv_values
from discord.ext import commands, tasks
from pytse.utils import close_aiohttp_session
from utils import get_performance_metrics, EmbedColor, load_roles, TerminalColor as C

class ShifuBot(commands.Bot):
    async def close(self) -> None:
        music_cog = self.get_cog("Music")

        if music_cog is not None:
            queue = getattr(music_cog, "queue", {})

            for queue_id in queue:
                play_msg = queue[queue_id].messages["play"]
                if play_msg: await play_msg.edit(view=None)

        await close_aiohttp_session()
        await super().close()

config = dotenv_values(".env")
intents = discord.Intents.default() + discord.Intents.members + discord.Intents.message_content
bot = ShifuBot(command_prefix="€", case_insensitive=True, help_command=None, intents=intents)
cogs = ["basic", "music"]
active_guilds = []

for cog in cogs:
    bot.load_extension(f"cogs.{cog}")

async def _update_select_menus() -> tuple[list[str], list[str]]:
    roles = load_roles()
    valid, invalid = [], []

    for guild_id in roles:
        if not roles[guild_id]["assign"]: continue

        try:
            assign = roles[guild_id]["assign"]
            guild = bot.get_guild(int(guild_id))

            assert guild

            channel = guild.get_channel(assign["channel_id"])

            if isinstance(channel, discord.TextChannel):
                message = await channel.fetch_message(assign["message_id"])
                
                proper_roles = [discord.utils.get(guild.roles, id=role_id) for role_id in assign["options"]]
                options = [discord.SelectOption(label=role.name[:100], value=str(role.id)) for role in proper_roles if role]
                await message.edit(view=RoleView(options))

                valid.append(guild_id)
        except (discord.HTTPException, discord.NotFound):
            invalid.append(guild_id)
            continue

    for guild_id in invalid:
        roles[guild_id]["assign"] = {}

    with open("./data/roles.json", "w", encoding="utf-8") as f:
        json.dump(roles, f, indent=4)

    return valid, invalid

@bot.slash_command(description="Loads the specified cog")
@discord.option(name="cog", description="The cog to load", required=True, choices=cogs)
@commands.is_owner()
async def load(ctx: discord.ApplicationContext, cog: str):
    bot.load_extension(f"cogs.{cog}")

    embed = discord.Embed(
        description=f"Cog `{cog}` loaded successfully.",
        color=EmbedColor.GREEN
    )
    await ctx.response.send_message(embed=embed, ephemeral=True)

@bot.slash_command(description="Unloads the specified cog")
@discord.option(name="cog", description="The cog to unload", required=True, choices=cogs)
@commands.is_owner()
async def unload(ctx: discord.ApplicationContext, cog: str):
    bot.unload_extension(f"cogs.{cog}")

    embed = discord.Embed(
        description=f"Cog `{cog}` unloaded successfully.",
        color=EmbedColor.GREEN
    )
    await ctx.response.send_message(embed=embed, ephemeral=True)

@bot.slash_command(description="Reloads the specified cog")
@discord.option(name="cog", description="The cog to reload", required=True, choices=cogs)
@commands.is_owner()
async def reload(ctx: discord.ApplicationContext, cog: str):
    bot.reload_extension(f"cogs.{cog}")

    embed = discord.Embed(
        description=f"Cog `{cog}` reloaded successfully.",
        color=EmbedColor.GREEN
    )
    await ctx.response.send_message(embed=embed, ephemeral=True)

@tasks.loop(minutes=5)
async def resource_display():
    global active_guilds

    ram_total, ram_usage, ram_percent, cpu, guilds = get_performance_metrics(bot)
    ram_color = C.GREEN if ram_percent < 33.3 else C.YELLOW if ram_percent < 66.7 else C.RED
    cpu_color = C.GREEN if cpu < 33.3 else C.YELLOW if cpu < 66.7 else C.RED
    print(f"[{C.CYAN}{datetime.now().strftime('%X')}{C.END}] ShifuBot connected to {C.GREEN}{len(guilds)}{C.END} guild(s): {C.GREEN}{', '.join(guilds)}{C.END}\nRAM: {ram_color}{ram_usage} ({ram_percent}){C.END} / {ram_total} GiB (100.0 %)\nCPU: {cpu_color}{cpu}{C.END} / 100.0 %")

@bot.event
async def on_member_join(member: discord.Member):
    data = load_roles()

    if data.get(str(member.guild.id)):
        try:
            role = discord.utils.get(member.guild.roles, id=data[str(member.guild.id)])
            if role: await member.add_roles(role)
        except (AttributeError, discord.Forbidden) as e:
            print("Error occurred while applying join role:", e)

@bot.event
async def on_message(msg: discord.Message):
    assert bot.user

    if msg.content == bot.user.mention:
        embed = discord.Embed(
            description="Get started by using the </help:1372991283169202253> command.",
            color=EmbedColor.YELLOW
        )
        await msg.channel.send(embed=embed)

@bot.event
async def on_ready():
    assert bot.user

    print("Initializing role menus...")
    valid, invalid = await _update_select_menus()
    print(f"{C.GREEN}{len(valid)}{C.END} updates, {C.RED}{len(invalid)}{C.END} removals")

    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="tracks | /help"))
    resource_display.start()
    print(f"{bot.user} ({bot.user.id}) initialized!\n-----")

if __name__ == "__main__":
    bot.run(config["TOKEN"])
